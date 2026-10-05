from __future__ import annotations

import base64
import json
import os
import shutil
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from hashlib import sha256
from http.client import RemoteDisconnected
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from savits_etl.sources.base import BaseSource


class _OPSBlockedError(RuntimeError):
    """Indica bloqueio ou limitação de uso da OPS."""


class _OPSRequestError(RuntimeError):
    """Representa erro HTTP recuperável de uma requisição OPS."""

    def __init__(
        self,
        code: int,
        url: str,
        message: str,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.url = url


class EPOSource(BaseSource):
    """Cliente da EPO Open Patent Services (OPS)."""

    name = "European Patent Office - OPS"
    dataset = "patentes"

    auth_url = (
        "https://ops.epo.org/3.2/"
        "auth/accesstoken"
    )

    rest_url = (
        "https://ops.epo.org/3.2/"
        "rest-services"
    )

    biblio_url = (
        f"{rest_url}/published-data/"
        "publication/epodoc/biblio"
    )

    encoding = "utf-8"

    def __init__(
        self,
        bronze_root: Path | str = "data/bronze",
        consumer_key: str | None = None,
        consumer_secret: str | None = None,
        batch_size: int = 25,
        request_interval: float = 0.5,
        timeout: float = 30.0,
    ) -> None:
        if batch_size < 1:
            raise ValueError(
                "batch_size deve ser maior ou igual a 1."
            )

        if batch_size > 100:
            raise ValueError(
                "O cliente SAVITS limita batch_size a 100."
            )

        self.bronze_root = Path(
            bronze_root
        )

        self.consumer_key = (
            consumer_key
            or os.getenv(
                "EPO_OPS_CONSUMER_KEY"
            )
        )

        self.consumer_secret = (
            consumer_secret
            or os.getenv(
                "EPO_OPS_CONSUMER_SECRET"
            )
        )

        self.batch_size = batch_size
        self.request_interval = (
            request_interval
        )
        self.timeout = timeout

        self._access_token: str | None = None
        self._token_expires_at = 0.0

    def download(
        self,
        reference: int,
        overwrite: bool = False,
        identifiers: list[str] | None = None,
    ) -> Path:
        """
        Obtém dados bibliográficos da EPO OPS.

        reference identifica o snapshot, preferencialmente
        no formato YYYYMMDD.

        identifiers deve conter números de publicação no
        formato EPODOC, por exemplo EP1000000.A1.

        Quando identifiers não é informado, o método reutiliza
        o arquivo de identificadores já salvo na Bronze.
        """

        directory = self._directory(
            reference
        )

        identifiers_path = (
            directory
            / "identificadores.jsonl"
        )

        batches_directory = (
            directory
            / "batches"
        )

        manifest_path = (
            directory
            / "manifesto.jsonl"
        )

        failures_path = (
            directory
            / "falhas.jsonl"
        )

        metadata_path = (
            directory
            / "metadata.json"
        )

        if overwrite and directory.exists():
            shutil.rmtree(
                directory
            )

        directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        batches_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        if identifiers is not None:
            requested = (
                self.normalize_identifiers(
                    identifiers
                )
            )

            if not requested:
                raise ValueError(
                    "Nenhum identificador EPO "
                    "foi informado."
                )

            if (
                identifiers_path.exists()
                and not overwrite
            ):
                existing = (
                    self._read_identifiers(
                        identifiers_path
                    )
                )

                if existing != requested:
                    raise ValueError(
                        "O snapshot já possui uma "
                        "lista diferente de "
                        "identificadores. Use outra "
                        "referência ou overwrite=True."
                    )
            else:
                self._write_identifiers(
                    identifiers_path,
                    requested,
                )

        else:
            if not identifiers_path.exists():
                raise ValueError(
                    "Informe identifiers na primeira "
                    "execução do snapshot."
                )

            requested = (
                self._read_identifiers(
                    identifiers_path
                )
            )

        previous_manifest = (
            list(
                self._read_jsonl(
                    manifest_path
                )
            )
            if manifest_path.exists()
            else []
        )

        completed = {
            str(identifier)
            for record
            in previous_manifest
            for identifier
            in record.get(
                "identifiers",
                [],
            )
        }

        pending = [
            identifier
            for identifier in requested
            if identifier not in completed
        ]

        failures: list[
            dict[str, object]
        ] = []

        manifest_count = len(
            previous_manifest
        )

        try:
            for start in range(
                0,
                len(pending),
                self.batch_size,
            ):
                group = pending[
                    start:
                    start + self.batch_size
                ]

                manifest_count = (
                    self._collect_group(
                        identifiers=group,
                        batches_directory=(
                            batches_directory
                        ),
                        manifest_path=(
                            manifest_path
                        ),
                        failures=failures,
                        manifest_count=(
                            manifest_count
                        ),
                    )
                )

        except _OPSBlockedError:
            self._write_failures(
                failures_path,
                failures,
            )

            self._write_metadata(
                reference=reference,
                identifiers_path=(
                    identifiers_path
                ),
                manifest_path=(
                    manifest_path
                ),
                failures_path=(
                    failures_path
                ),
                requested=requested,
                failures=failures,
                status="interrupted",
            )

            raise

        self._write_failures(
            failures_path,
            failures,
        )

        final_manifest = list(
            self._read_jsonl(
                manifest_path
            )
        )

        final_completed = {
            str(identifier)
            for record
            in final_manifest
            for identifier
            in record.get(
                "identifiers",
                [],
            )
        }

        status = (
            "complete"
            if len(final_completed)
            == len(requested)
            else "partial"
        )

        self._write_metadata(
            reference=reference,
            identifiers_path=(
                identifiers_path
            ),
            manifest_path=manifest_path,
            failures_path=failures_path,
            requested=requested,
            failures=failures,
            status=status,
        )

        if (
            status == "complete"
            and metadata_path.exists()
        ):
            return manifest_path

        return manifest_path

    def read(
        self,
        reference: int,
        **kwargs: str,
    ) -> Iterator[dict[str, str]]:
        """Lê os XMLs bibliográficos armazenados na Bronze."""

        directory = self._directory(
            reference
        )

        manifest_path = (
            directory
            / "manifesto.jsonl"
        )

        batches_directory = (
            directory
            / "batches"
        )

        if not manifest_path.exists():
            raise FileNotFoundError(
                "Manifesto Bronze EPO "
                f"não encontrado: {manifest_path}"
            )

        for record in self._read_jsonl(
            manifest_path
        ):
            filename = str(
                record["file"]
            )

            path = (
                batches_directory
                / filename
            )

            if not path.exists():
                raise FileNotFoundError(
                    "Arquivo XML listado no "
                    "manifesto não encontrado: "
                    f"{path}"
                )

            yield {
                "batch_sequence": str(
                    record[
                        "batch_sequence"
                    ]
                ),
                "file": filename,
                "identifiers": json.dumps(
                    record.get(
                        "identifiers",
                        [],
                    ),
                    ensure_ascii=False,
                ),
                "xml": path.read_text(
                    encoding=self.encoding,
                    errors="replace",
                ),
            }

    @staticmethod
    def normalize_identifiers(
        identifiers: list[str],
    ) -> list[str]:
        """Normaliza e remove identificadores duplicados."""

        result: list[str] = []
        seen: set[str] = set()

        for identifier in identifiers:
            value = (
                identifier
                .strip()
                .upper()
            )

            if not value:
                continue

            if value in seen:
                continue

            seen.add(
                value
            )

            result.append(
                value
            )

        return result

    @staticmethod
    def calcular_dv_inpi(
        numero_pedido: str,
    ) -> str:
        """
        Calcula o dígito verificador de pedido INPI
        no padrão novo de 12 dígitos.
        """

        digits = "".join(
            character
            for character in numero_pedido
            if character.isdigit()
        )

        if len(digits) != 12:
            raise ValueError(
                "O número de pedido INPI deve possuir "
                "12 dígitos para o padrão novo."
            )

        weights = (
            5,
            4,
            3,
            2,
            9,
            8,
            7,
            6,
            5,
            4,
            3,
            2,
        )

        total = sum(
            int(digit) * weight
            for digit, weight
            in zip(
                digits,
                weights,
                strict=True,
            )
        )

        check_digit = (
            11 - (total % 11)
        )

        if check_digit in {
            10,
            11,
        }:
            check_digit = 0

        return str(
            check_digit
        )

    @classmethod
    def construir_numero_original_inpi(
        cls,
        numero_pedido: str,
        data_deposito: str = "",
    ) -> str:
        """
        Constrói o identificador original aceito pelo
        EPO Number Service para pedidos INPI modernos.

        A data de depósito e o dígito verificador não
        participam da normalização OPS.

        Naturezas 10/11/12/13 usam kind A.
        Naturezas 20/21/22 usam kind U.
        """

        del data_deposito

        digits = "".join(
            character
            for character in numero_pedido
            if character.isdigit()
        )

        if len(digits) != 12:
            raise ValueError(
                "Pedido INPI moderno deve possuir "
                "12 dígitos."
            )

        natureza = digits[:2]

        if natureza in {
            "10",
            "11",
            "12",
            "13",
        }:
            kind = "A"

        elif natureza in {
            "20",
            "21",
            "22",
        }:
            kind = "U"

        else:
            raise ValueError(
                "Natureza de pedido INPI moderno "
                f"ainda não suportada: {natureza}."
            )

        ano = digits[2:6]
        sequencial = digits[6:]

        return (
            f"BR.{natureza} "
            f"{ano} "
            f"{sequencial}."
            f"{kind}"
        )

    @staticmethod
    def pedido_inpi_compativel(
        numero_pedido: str,
        data_deposito: str = "",
    ) -> bool:
        """
        Indica se o registro usa um formato moderno INPI
        já validado contra o EPO Number Service.

        data_deposito é mantido apenas por compatibilidade
        com chamadas existentes e não participa da regra.
        """

        del data_deposito

        digits = "".join(
            character
            for character in numero_pedido
            if character.isdigit()
        )

        if len(digits) != 12:
            return False

        natureza = digits[:2]

        return natureza in {
            "10",
            "11",
            "12",
            "13",
            "20",
            "21",
            "22",
        }

    @staticmethod
    def epodoc_application_valido(
        value: str,
    ) -> bool:
        """
        Verifica se um identificador retornado pela OPS
        tem formato compatível com application EPODOC.

        Não tenta corrigir conversões ambíguas.
        """

        identifier = value.strip().upper()

        if len(identifier) < 3:
            return False

        if not identifier[:2].isalpha():
            return False

        return identifier.isalnum()

    @staticmethod
    def pedido_inpi_legado_compativel(
        numero_pedido: str,
    ) -> bool:
        """
        Indica se o pedido usa um formato legado PI/MU
        já validado contra o EPO Number Service.
        """

        compact = "".join(
            character
            for character in numero_pedido.strip().upper()
            if not character.isspace()
        )

        if len(compact) != 9:
            return False

        prefix = compact[:2]
        digits = compact[2:]

        return (
            prefix in {"PI", "MU"}
            and digits.isdigit()
            and len(digits) == 7
        )

    @classmethod
    def construir_numero_original_inpi_legado(
        cls,
        numero_pedido: str,
    ) -> str:
        """
        Constrói o número original OPS para pedidos
        legados PI/MU.

        A data e o dígito verificador não são incluídos,
        porque o Number Service foi validado sem eles.

        Exemplos:
        PI9714779 -> BR.PI9714779.A
        MU8403134 -> BR.MU8403134.A
        """

        if not cls.pedido_inpi_legado_compativel(
            numero_pedido
        ):
            raise ValueError(
                "Pedido INPI legado deve possuir "
                "prefixo PI ou MU seguido de "
                "7 dígitos."
            )

        compact = "".join(
            character
            for character in numero_pedido.strip().upper()
            if not character.isspace()
        )

        return f"BR.{compact}.A"

    @classmethod
    def construir_numero_original_inpi_ops(
        cls,
        numero_pedido: str,
        data_deposito: str = "",
    ) -> str | None:
        """
        Seleciona o adaptador INPI adequado para a OPS.

        Pedidos modernos usam apenas a numeração oficial.
        Pedidos legados PI/MU usam sua regra própria.
        """

        if cls.pedido_inpi_compativel(
            numero_pedido=numero_pedido,
            data_deposito=data_deposito,
        ):
            return cls.construir_numero_original_inpi(
                numero_pedido=numero_pedido,
                data_deposito=data_deposito,
            )

        if cls.pedido_inpi_legado_compativel(
            numero_pedido
        ):
            return (
                cls.construir_numero_original_inpi_legado(
                    numero_pedido
                )
            )

        return None

    @classmethod
    def construir_epodoc_inpi_direto(
        cls,
        numero_pedido: str,
        data_deposito: str = "",
    ) -> str | None:
        """
        Deriva diretamente o identificador de aplicação
        consultável no Published Data da OPS.

        A regra é restrita aos formatos já validados
        empiricamente contra a EPO.

        Retorna None quando a derivação não é segura.
        """

        compact = "".join(
            character
            for character
            in numero_pedido.strip().upper()
            if not character.isspace()
        )

        # Pedidos modernos:
        # 10/11/12/13 -> aplicação A
        # 20/21/22    -> aplicação U
        if (
            len(compact) == 12
            and compact.isdigit()
        ):
            natureza = compact[:2]

            if natureza not in {
                "10",
                "11",
                "12",
                "13",
                "20",
                "21",
                "22",
            }:
                return None

            ano = compact[2:6]
            sequencial = compact[6:]

            # Regra validada no conjunto INPI atual.
            if not sequencial.startswith("0"):
                return None

            epodoc = (
                "BR"
                + ano
                + natureza
                + sequencial[1:]
            )

            if natureza in {
                "20",
                "21",
                "22",
            }:
                epodoc += "U"

            return epodoc

        # PI legado.
        if (
            len(compact) == 9
            and compact.startswith("PI")
            and compact[2:].isdigit()
        ):
            date_value = (
                data_deposito.strip()
            )

            if (
                len(date_value) < 4
                or not date_value[:4].isdigit()
            ):
                return None

            ano = date_value[:4]

            return (
                f"BR{ano}PI"
                f"{compact[-5:]}"
            )

        # MU legado.
        #
        # A forma BRMUxxxxxxx funciona como
        # identificador de consulta no Published Data.
        if (
            len(compact) == 9
            and compact.startswith("MU")
            and compact[2:].isdigit()
        ):
            return (
                f"BR{compact}"
            )

        return None

    def standardize_application_original(
        self,
        original: str,
    ) -> str | None:
        """
        Converte um número de pedido original para EPODOC.

        Retorna None quando a OPS não encontra o número
        ou quando a conversão retornada não é um EPODOC
        utilizável pelo Published Data.
        """

        value = original.strip()

        if not value:
            raise ValueError(
                "Número original de pedido vazio."
            )

        url = (
            f"{self.rest_url}/"
            "number-service/application/"
            "original/epodoc"
        )

        content = self._post_ops(
            url=url,
            body=value.encode(),
            accept="application/ops+xml",
            not_found_is_none=True,
        )

        if content is None:
            return None

        epodoc = (
            self._parse_standardized_epodoc(
                content
            )
        )

        if not self.epodoc_application_valido(
            epodoc
        ):
            return None

        return epodoc.upper()

    def fetch_application_biblio(
        self,
        epodoc: str,
    ) -> bytes | None:
        """
        Obtém bibliografia pelo número de pedido EPODOC.

        Um HTTP 404 é tratado como ausência legítima de
        publicação bibliográfica e retorna None.
        """

        identifier = epodoc.strip().upper()

        if not identifier:
            raise ValueError(
                "Número EPODOC de pedido vazio."
            )

        url = (
            f"{self.rest_url}/"
            "published-data/application/"
            f"epodoc/{identifier}/biblio"
        )

        return self._get_ops(
            url=url,
            accept="application/exchange+xml",
            not_found_is_none=True,
        )

    def fetch_application_biblio_batch(
        self,
        identifiers: list[str],
    ) -> bytes:
        """
        Obtém bibliografia de múltiplas aplicações EPODOC.

        O retorno bruto é preservado para que o coletor
        possa separar os resultados por aplicação.
        """

        normalized = (
            self.normalize_identifiers(
                identifiers
            )
        )

        if not normalized:
            raise ValueError(
                "Lote de aplicações EPO vazio."
            )

        if len(normalized) > 100:
            raise ValueError(
                "O lote de aplicações EPO "
                "não pode exceder 100 IDs."
            )

        url = (
            f"{self.rest_url}/"
            "published-data/application/"
            "epodoc/biblio"
        )

        content = self._post_ops(
            url=url,
            body=",".join(
                normalized
            ).encode(
                "ascii"
            ),
            accept="application/exchange+xml",
        )

        if content is None:
            raise RuntimeError(
                "A OPS não retornou conteúdo "
                "para o lote de aplicações."
            )

        return content

    @staticmethod
    def parse_application_batch_status(
        content: bytes,
    ) -> dict[str, str]:
        """
        Classifica cada aplicação presente numa resposta
        em lote da OPS.

        matched:
            há pelo menos um exchange-document com
            doc-number de publicação.

        no_bibliography:
            a aplicação foi devolvida apenas como
            placeholder, sem publicação bibliográfica.
        """

        import xml.etree.ElementTree as ET

        root = ET.fromstring(
            content
        )

        def local_name(
            tag: str,
        ) -> str:
            return tag.rsplit(
                "}",
                1,
            )[-1]

        statuses: dict[
            str,
            str,
        ] = {}

        for document in root.iter():
            if (
                local_name(document.tag)
                != "exchange-document"
            ):
                continue

            application_epodocs = []

            for reference in document.iter():
                if (
                    local_name(reference.tag)
                    != "application-reference"
                ):
                    continue

                for document_id in reference:
                    if (
                        local_name(
                            document_id.tag
                        )
                        != "document-id"
                    ):
                        continue

                    if (
                        document_id.attrib.get(
                            "document-id-type"
                        )
                        != "epodoc"
                    ):
                        continue

                    for child in document_id:
                        if (
                            local_name(
                                child.tag
                            )
                            == "doc-number"
                            and child.text
                        ):
                            application_epodocs.append(
                                child.text.strip().upper()
                            )

            if not application_epodocs:
                continue

            publication_number = (
                document.attrib.get(
                    "doc-number",
                    ""
                ).strip()
            )

            status = (
                "matched"
                if publication_number
                else "no_bibliography"
            )

            for epodoc in application_epodocs:
                previous = statuses.get(
                    epodoc
                )

                # Se qualquer variante possuir publicação,
                # matched prevalece sobre placeholder.
                if (
                    previous == "matched"
                    or status == "matched"
                ):
                    statuses[
                        epodoc
                    ] = "matched"
                else:
                    statuses[
                        epodoc
                    ] = (
                        "no_bibliography"
                    )

        return statuses

    def _post_ops(
        self,
        url: str,
        body: bytes,
        accept: str,
        not_found_is_none: bool = False,
    ) -> bytes | None:
        """Executa POST autenticado na OPS."""

        attempts = 3
        refreshed_token = False

        for attempt in range(
            1,
            attempts + 1,
        ):
            token = self._get_token(
                force=refreshed_token
            )

            request = Request(
                url,
                data=body,
                headers={
                    "Authorization": (
                        f"Bearer {token}"
                    ),
                    "Accept": accept,
                    "Content-Type": "text/plain",
                },
                method="POST",
            )

            try:
                with urlopen(
                    request,
                    timeout=self.timeout,
                ) as response:
                    content = response.read()

                    if not content:
                        raise RuntimeError(
                            "A OPS retornou uma "
                            "resposta vazia."
                        )

                    return content

            except HTTPError as exc:
                if (
                    exc.code == 401
                    and not refreshed_token
                ):
                    refreshed_token = True
                    self._access_token = None
                    self._token_expires_at = 0.0
                    continue

                if (
                    exc.code == 404
                    and not_found_is_none
                ):
                    return None

                if exc.code in {
                    403,
                    429,
                }:
                    usage = self._usage_headers(
                        exc.headers
                    )

                    rejection = usage.get(
                        "x-rejection-reason",
                        "não informado",
                    )

                    hourly = usage.get(
                        "x-individualquotaperhour-used",
                        "não informado",
                    )

                    weekly = usage.get(
                        "x-registeredquotaperweek-used",
                        "não informado",
                    )

                    throttling = usage.get(
                        "x-throttling-control",
                        "não informado",
                    )

                    retry_after = usage.get(
                        "retry-after",
                        "não informado",
                    )

                    raise _OPSBlockedError(
                        "Requisição OPS interrompida "
                        f"por HTTP {exc.code}. "
                        f"rejection_reason={rejection}; "
                        f"hourly_used={hourly}; "
                        f"weekly_used={weekly}; "
                        f"throttling={throttling}; "
                        f"retry_after={retry_after}; "
                        f"url={url}"
                    ) from exc

                if (
                    exc.code >= 500
                    and attempt < attempts
                ):
                    time.sleep(
                        2.0 * attempt
                    )
                    continue

                raise _OPSRequestError(
                    code=exc.code,
                    url=url,
                    message=(
                        "Erro HTTP OPS "
                        f"{exc.code}: {url}"
                    ),
                ) from exc

            except (
                RemoteDisconnected,
                TimeoutError,
                URLError,
            ) as exc:
                if attempt < attempts:
                    time.sleep(
                        2.0 * attempt
                    )
                    continue

                raise RuntimeError(
                    "Falha de rede após "
                    f"{attempts} tentativas."
                ) from exc

        raise RuntimeError(
            "Falha inesperada na OPS."
        )

    def _get_ops(
        self,
        url: str,
        accept: str,
        not_found_is_none: bool = False,
    ) -> bytes | None:
        """Executa GET autenticado na OPS."""

        attempts = 3
        refreshed_token = False

        for attempt in range(
            1,
            attempts + 1,
        ):
            token = self._get_token(
                force=refreshed_token
            )

            request = Request(
                url,
                headers={
                    "Authorization": (
                        f"Bearer {token}"
                    ),
                    "Accept": accept,
                },
            )

            try:
                with urlopen(
                    request,
                    timeout=self.timeout,
                ) as response:
                    content = response.read()

                    if not content:
                        raise RuntimeError(
                            "A OPS retornou uma "
                            "resposta vazia."
                        )

                    return content

            except HTTPError as exc:
                if (
                    exc.code == 401
                    and not refreshed_token
                ):
                    refreshed_token = True
                    self._access_token = None
                    self._token_expires_at = 0.0
                    continue

                if (
                    exc.code == 404
                    and not_found_is_none
                ):
                    return None

                if exc.code in {
                    403,
                    429,
                }:
                    raise _OPSBlockedError(
                        "Requisição OPS interrompida "
                        f"por HTTP {exc.code}: "
                        f"{url}"
                    ) from exc

                if (
                    exc.code >= 500
                    and attempt < attempts
                ):
                    time.sleep(
                        2.0 * attempt
                    )
                    continue

                raise _OPSRequestError(
                    code=exc.code,
                    url=url,
                    message=(
                        "Erro HTTP OPS "
                        f"{exc.code}: {url}"
                    ),
                ) from exc

            except (
                RemoteDisconnected,
                TimeoutError,
                URLError,
            ) as exc:
                if attempt < attempts:
                    time.sleep(
                        2.0 * attempt
                    )
                    continue

                raise RuntimeError(
                    "Falha de rede após "
                    f"{attempts} tentativas."
                ) from exc

        raise RuntimeError(
            "Falha inesperada na OPS."
        )

    @staticmethod
    def _parse_standardized_epodoc(
        content: bytes,
    ) -> str:
        """Extrai o número EPODOC do Number Service."""

        import xml.etree.ElementTree as ET

        root = ET.fromstring(
            content
        )

        namespaces = {
            "ex": (
                "http://www.epo.org/exchange"
            ),
            "ops": (
                "http://ops.epo.org"
            ),
        }

        value = root.findtext(
            ".//ops:output/"
            "ops:application-reference/"
            "ex:document-id"
            "[@document-id-type='epodoc']/"
            "ex:doc-number",
            namespaces=namespaces,
        )

        if not value:
            raise RuntimeError(
                "Number Service respondeu "
                "sem número EPODOC."
            )

        return value.strip()

    def _collect_group(
        self,
        identifiers: list[str],
        batches_directory: Path,
        manifest_path: Path,
        failures: list[dict[str, object]],
        manifest_count: int,
    ) -> int:
        """
        Coleta um grupo.

        Se um lote retornar 400/404, divide o grupo até
        isolar o identificador problemático.
        """

        try:
            content, response_headers = (
                self._fetch_batch(
                    identifiers
                )
            )

        except _OPSBlockedError:
            raise

        except _OPSRequestError as exc:
            if (
                exc.code in {400, 404}
                and len(identifiers) > 1
            ):
                middle = (
                    len(identifiers)
                    // 2
                )

                first = identifiers[
                    :middle
                ]

                second = identifiers[
                    middle:
                ]

                manifest_count = (
                    self._collect_group(
                        identifiers=first,
                        batches_directory=(
                            batches_directory
                        ),
                        manifest_path=(
                            manifest_path
                        ),
                        failures=failures,
                        manifest_count=(
                            manifest_count
                        ),
                    )
                )

                return self._collect_group(
                    identifiers=second,
                    batches_directory=(
                        batches_directory
                    ),
                    manifest_path=(
                        manifest_path
                    ),
                    failures=failures,
                    manifest_count=(
                        manifest_count
                    ),
                )

            for identifier in identifiers:
                failures.append(
                    {
                        "identifier": (
                            identifier
                        ),
                        "http_status": (
                            exc.code
                        ),
                        "error": str(
                            exc
                        ),
                    }
                )

                print(
                    "[falha] "
                    f"{identifier} "
                    f"HTTP {exc.code}",
                    flush=True,
                )

            self._pause()

            return manifest_count

        except RuntimeError as exc:
            for identifier in identifiers:
                failures.append(
                    {
                        "identifier": (
                            identifier
                        ),
                        "http_status": None,
                        "error": str(
                            exc
                        ),
                    }
                )

                print(
                    "[falha] "
                    f"{identifier}",
                    flush=True,
                )

            self._pause()

            return manifest_count

        manifest_count += 1

        digest = sha256(
            ",".join(
                identifiers
            ).encode(
                "utf-8"
            )
        ).hexdigest()[:16]

        filename = (
            f"{manifest_count:06d}_"
            f"{digest}.xml"
        )

        destination = (
            batches_directory
            / filename
        )

        destination.write_bytes(
            content
        )

        record = {
            "batch_sequence": (
                manifest_count
            ),
            "identifiers": (
                identifiers
            ),
            "identifier_count": (
                len(identifiers)
            ),
            "file": filename,
            "size_bytes": (
                destination.stat().st_size
            ),
            "sha256": self._sha256(
                destination
            ),
            "response_headers": (
                response_headers
            ),
        }

        self._append_jsonl(
            manifest_path,
            record,
        )

        print(
            "[ok] "
            f"batch {manifest_count} "
            f"({len(identifiers)} IDs)",
            flush=True,
        )

        self._pause()

        return manifest_count

    def _fetch_batch(
        self,
        identifiers: list[str],
    ) -> tuple[
        bytes,
        dict[str, str],
    ]:
        """Obtém bibliografia OPS para um lote EPODOC."""

        if not identifiers:
            raise ValueError(
                "Lote EPO vazio."
            )

        body = ",".join(
            identifiers
        ).encode(
            "ascii"
        )

        attempts = 3
        refreshed_token = False

        for attempt in range(
            1,
            attempts + 1,
        ):
            token = self._get_token(
                force=refreshed_token
            )

            request = Request(
                self.biblio_url,
                data=body,
                headers={
                    "Authorization": (
                        f"Bearer {token}"
                    ),
                    "Accept": (
                        "application/"
                        "exchange+xml"
                    ),
                    "Content-Type": (
                        "text/plain; "
                        "charset=utf-8"
                    ),
                },
                method="POST",
            )

            try:
                with urlopen(
                    request,
                    timeout=self.timeout,
                ) as response:
                    content = (
                        response.read()
                    )

                    headers = (
                        self._usage_headers(
                            response.headers
                        )
                    )

                    if not content:
                        raise RuntimeError(
                            "A OPS retornou uma "
                            "resposta vazia."
                        )

                    return (
                        content,
                        headers,
                    )

            except HTTPError as exc:
                if (
                    exc.code == 401
                    and not refreshed_token
                ):
                    refreshed_token = True
                    self._access_token = None
                    self._token_expires_at = 0.0
                    continue

                if exc.code in {
                    403,
                    429,
                }:
                    raise _OPSBlockedError(
                        "Coleta OPS interrompida "
                        f"por HTTP {exc.code}: "
                        f"{self.biblio_url}"
                    ) from exc

                if (
                    exc.code >= 500
                    and attempt < attempts
                ):
                    time.sleep(
                        2.0 * attempt
                    )
                    continue

                raise _OPSRequestError(
                    code=exc.code,
                    url=self.biblio_url,
                    message=(
                        "Erro HTTP OPS "
                        f"{exc.code} para "
                        f"{', '.join(identifiers)}"
                    ),
                ) from exc

            except (
                RemoteDisconnected,
                TimeoutError,
                URLError,
            ) as exc:
                if attempt < attempts:
                    time.sleep(
                        2.0 * attempt
                    )
                    continue

                reason = getattr(
                    exc,
                    "reason",
                    str(exc),
                )

                raise RuntimeError(
                    "Falha de rede após "
                    f"{attempts} tentativas: "
                    f"{reason}"
                ) from exc

        raise RuntimeError(
            "Falha inesperada na OPS."
        )

    def _get_token(
        self,
        force: bool = False,
    ) -> str:
        """Obtém e armazena temporariamente um token OAuth."""

        if (
            not force
            and self._access_token
            and time.monotonic()
            < self._token_expires_at
        ):
            return self._access_token

        self._ensure_credentials()

        credentials = base64.b64encode(
            (
                f"{self.consumer_key}:"
                f"{self.consumer_secret}"
            ).encode()
        ).decode(
            "ascii"
        )

        request = Request(
            self.auth_url,
            data=urlencode(
                {
                    "grant_type": (
                        "client_credentials"
                    ),
                }
            ).encode(
                "ascii"
            ),
            headers={
                "Authorization": (
                    f"Basic {credentials}"
                ),
                "Content-Type": (
                    "application/"
                    "x-www-form-urlencoded"
                ),
            },
            method="POST",
        )

        try:
            with urlopen(
                request,
                timeout=self.timeout,
            ) as response:
                payload = json.loads(
                    response.read().decode(
                        "utf-8"
                    )
                )

        except HTTPError as exc:
            raise RuntimeError(
                "Falha na autenticação OPS: "
                f"HTTP {exc.code}."
            ) from exc

        except (
            TimeoutError,
            URLError,
        ) as exc:
            raise RuntimeError(
                "Falha de rede durante "
                "autenticação OPS."
            ) from exc

        token = str(
            payload.get(
                "access_token",
                "",
            )
        )

        if not token:
            raise RuntimeError(
                "Resposta OAuth OPS sem "
                "access_token."
            )

        expires_in = int(
            payload.get(
                "expires_in",
                1200,
            )
        )

        self._access_token = token

        self._token_expires_at = (
            time.monotonic()
            + max(
                expires_in - 60,
                1,
            )
        )

        return token

    def _ensure_credentials(
        self,
    ) -> None:
        if (
            not self.consumer_key
            or not self.consumer_secret
        ):
            raise RuntimeError(
                "Credenciais EPO OPS não "
                "configuradas. Defina "
                "EPO_OPS_CONSUMER_KEY e "
                "EPO_OPS_CONSUMER_SECRET."
            )

    def _directory(
        self,
        reference: int,
    ) -> Path:
        return (
            self.bronze_root
            / "epo"
            / "ops"
            / str(reference)
        )

    def _pause(
        self,
    ) -> None:
        if self.request_interval > 0:
            time.sleep(
                self.request_interval
            )

    @staticmethod
    def _usage_headers(
        headers: object,
    ) -> dict[str, str]:
        """Preserva apenas headers úteis de quota e throttling."""

        allowed = {
            "x-throttling-control",
            "x-individualquotaperhour-used",
            "x-registeredquotaperweek-used",
            "x-registeredpayingquotaperweek-used",
            "x-rejection-reason",
            "retry-after",
        }

        result: dict[str, str] = {}

        items = getattr(
            headers,
            "items",
            None,
        )

        if items is None:
            return result

        for key, value in items():
            name = str(
                key
            ).lower()

            if name not in allowed:
                continue

            result[name] = str(
                value
            )

        return result

    @staticmethod
    def _write_identifiers(
        path: Path,
        identifiers: list[str],
    ) -> None:
        records = [
            {
                "sequence": index,
                "identifier": identifier,
            }
            for index, identifier
            in enumerate(
                identifiers,
                start=1,
            )
        ]

        EPOSource._write_jsonl(
            path,
            records,
        )

    @staticmethod
    def _read_identifiers(
        path: Path,
    ) -> list[str]:
        return [
            str(
                record["identifier"]
            )
            for record
            in EPOSource._read_jsonl(
                path
            )
        ]

    @staticmethod
    def _read_jsonl(
        path: Path,
    ) -> Iterator[
        dict[str, object]
    ]:
        with path.open(
            encoding="utf-8",
        ) as file:
            for line in file:
                if not line.strip():
                    continue

                yield json.loads(
                    line
                )

    @staticmethod
    def _write_jsonl(
        path: Path,
        records: list[
            dict[str, object]
        ],
    ) -> None:
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary = path.with_suffix(
            path.suffix + ".part"
        )

        try:
            with temporary.open(
                "w",
                encoding="utf-8",
            ) as file:
                for record in records:
                    file.write(
                        json.dumps(
                            record,
                            ensure_ascii=False,
                        )
                    )
                    file.write("\n")

            temporary.replace(
                path
            )

        finally:
            if temporary.exists():
                temporary.unlink()

    @staticmethod
    def _append_jsonl(
        path: Path,
        record: dict[str, object],
    ) -> None:
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with path.open(
            "a",
            encoding="utf-8",
        ) as file:
            file.write(
                json.dumps(
                    record,
                    ensure_ascii=False,
                )
            )
            file.write("\n")
            file.flush()
            os.fsync(
                file.fileno()
            )

    @staticmethod
    def _write_failures(
        path: Path,
        failures: list[
            dict[str, object]
        ],
    ) -> None:
        if failures:
            EPOSource._write_jsonl(
                path,
                failures,
            )

        elif path.exists():
            path.unlink()

    @staticmethod
    def _sha256(
        path: Path,
    ) -> str:
        digest = sha256()

        with path.open(
            "rb"
        ) as file:
            while chunk := file.read(
                1024 * 1024
            ):
                digest.update(
                    chunk
                )

        return digest.hexdigest()

    def _write_metadata(
        self,
        reference: int,
        identifiers_path: Path,
        manifest_path: Path,
        failures_path: Path,
        requested: list[str],
        failures: list[
            dict[str, object]
        ],
        status: str,
    ) -> None:
        manifest = (
            list(
                self._read_jsonl(
                    manifest_path
                )
            )
            if manifest_path.exists()
            else []
        )

        completed = {
            str(identifier)
            for record in manifest
            for identifier
            in record.get(
                "identifiers",
                [],
            )
        }

        metadata = {
            "source": self.name,
            "dataset": self.dataset,
            "layer": "bronze",
            "snapshot_reference": (
                reference
            ),
            "generated_at": (
                datetime.now(
                    UTC
                ).isoformat()
            ),
            "service": "EPO OPS 3.2",
            "operation": (
                "published-data/"
                "publication/epodoc/"
                "biblio"
            ),
            "requested_identifiers": (
                len(requested)
            ),
            "completed_identifiers": (
                len(completed)
            ),
            "failed_identifiers": (
                len(
                    {
                        str(
                            record[
                                "identifier"
                            ]
                        )
                        for record
                        in failures
                    }
                )
            ),
            "response_batches": (
                len(manifest)
            ),
            "batch_size": (
                self.batch_size
            ),
            "request_interval_seconds": (
                self.request_interval
            ),
            "identifiers_file": (
                identifiers_path.name
            ),
            "identifiers_sha256": (
                self._sha256(
                    identifiers_path
                )
            ),
            "manifest_file": (
                manifest_path.name
            ),
            "manifest_sha256": (
                self._sha256(
                    manifest_path
                )
                if manifest_path.exists()
                else None
            ),
            "failures_file": (
                failures_path.name
                if failures_path.exists()
                else None
            ),
            "failures_sha256": (
                self._sha256(
                    failures_path
                )
                if failures_path.exists()
                else None
            ),
            "credentials_stored": False,
            "status": status,
        }

        metadata_path = (
            identifiers_path.parent
            / "metadata.json"
        )

        with metadata_path.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                metadata,
                file,
                ensure_ascii=False,
                indent=2,
            )