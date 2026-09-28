from __future__ import annotations

import json
import shutil
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from savits_etl.sources.base import BaseSource


class _CollectionBlockedError(RuntimeError):
    """Indica bloqueio ou limitação explícita do servidor."""


class _CatalogParser(HTMLParser):
    """Extrai URLs de tecnologias sociais das páginas de listagem."""

    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.links: list[str] = []
        self._seen: set[str] = set()

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag != "a":
            return

        href = dict(attrs).get("href")

        if not href:
            return

        url = urljoin(self.base_url, href)
        path = urlparse(url).path.rstrip("/")

        prefix = "/tecnologia-social/"

        if not path.startswith(prefix):
            return

        slug = path[len(prefix):]

        if not slug:
            return

        if slug == "pesquisa":
            return

        if "/" in slug:
            return

        if url in self._seen:
            return

        self._seen.add(url)
        self.links.append(url)


class TransformaSource(BaseSource):
    """Acesso à plataforma Transforma! da Fundação Banco do Brasil."""

    name = "Fundação Banco do Brasil - Transforma!"
    dataset = "tecnologias_sociais"

    base_url = "https://transforma.fbb.org.br"
    search_url = (
        "https://transforma.fbb.org.br/"
        "tecnologia-social/pesquisa"
    )

    encoding = "utf-8"

    def __init__(
        self,
        bronze_root: Path | str = "data/bronze",
        request_interval: float = 0.4,
        timeout: float = 30.0,
        max_pages: int = 10_000,
    ) -> None:
        self.bronze_root = Path(bronze_root)
        self.request_interval = request_interval
        self.timeout = timeout
        self.max_pages = max_pages
        self.user_agent = "savits-etl/0.1"

    def download(
        self,
        reference: int,
        overwrite: bool = False,
        start_sequence: int = 1,
        collect_missing: bool = True,
    ) -> Path:
        """
        Obtém ou consolida um snapshot da fonte.

        A referência deve identificar o snapshot, preferencialmente
        no formato YYYYMMDD.

        start_sequence define a posição do catálogo a partir da qual
        páginas ausentes podem ser requisitadas.

        Quando collect_missing=False, nenhuma requisição de detalhe
        ou catálogo é realizada. O snapshot é consolidado apenas com
        os arquivos já existentes na camada Bronze.
        """

        if start_sequence < 1:
            raise ValueError(
                "start_sequence deve ser maior ou igual a 1."
            )

        if overwrite and not collect_missing:
            raise ValueError(
                "overwrite=True não pode ser usado com "
                "collect_missing=False."
            )

        directory = self._directory(reference)

        catalog_path = (
            directory
            / "catalogo.jsonl"
        )

        manifest_path = (
            directory
            / "manifesto.jsonl"
        )

        failures_path = (
            directory
            / "falhas.jsonl"
        )

        listings_directory = (
            directory
            / "listagens"
        )

        details_directory = (
            directory
            / "detalhes"
        )

        if overwrite and directory.exists():
            shutil.rmtree(directory)

        directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        listings_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        details_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        if catalog_path.exists():
            records = list(
                self._read_jsonl(
                    catalog_path
                )
            )
        else:
            if not collect_missing:
                raise FileNotFoundError(
                    "Catálogo Bronze não encontrado: "
                    f"{catalog_path}"
                )

            records = self._download_catalog(
                listings_directory
            )

            self._write_jsonl(
                catalog_path,
                records,
            )

        total = len(records)

        if total == 0:
            raise ValueError(
                "Catálogo do Transforma! está vazio."
            )

        if (
            collect_missing
            and start_sequence > total
        ):
            raise ValueError(
                "start_sequence maior que o total "
                f"de registros do catálogo: {total}"
            )

        previous_failures = (
            self._previous_failures(
                failures_path
            )
        )

        manifest: list[dict[str, object]] = []
        failures: list[dict[str, object]] = []

        for index, record in enumerate(
            records,
            start=1,
        ):
            source_url = str(
                record["source_url"]
            )

            slug = str(
                record["slug"]
            )

            listing_page = int(
                record["listing_page"]
            )

            destination = (
                details_directory
                / self._detail_filename(
                    source_url
                )
            )

            if destination.exists():
                manifest.append(
                    self._manifest_record(
                        sequence=index,
                        listing_page=listing_page,
                        slug=slug,
                        source_url=source_url,
                        path=destination,
                    )
                )

                continue

            if not collect_missing:
                failures.append(
                    self._failure_record(
                        sequence=index,
                        listing_page=listing_page,
                        slug=slug,
                        source_url=source_url,
                        error=previous_failures.get(
                            source_url,
                            (
                                "Arquivo de detalhe ausente "
                                "na camada Bronze."
                            ),
                        ),
                    )
                )

                continue

            if index < start_sequence:
                failures.append(
                    self._failure_record(
                        sequence=index,
                        listing_page=listing_page,
                        slug=slug,
                        source_url=source_url,
                        error=previous_failures.get(
                            source_url,
                            (
                                "Arquivo ausente antes de "
                                "start_sequence; não "
                                "requisitado nesta retomada."
                            ),
                        ),
                    )
                )

                continue

            try:
                content = self._fetch(
                    source_url,
                    individual_detail=True,
                )

            except _CollectionBlockedError:
                raise

            except RuntimeError as exc:
                failures.append(
                    self._failure_record(
                        sequence=index,
                        listing_page=listing_page,
                        slug=slug,
                        source_url=source_url,
                        error=str(exc),
                    )
                )

                print(
                    f"[falha] "
                    f"{index}/{total} "
                    f"{slug}",
                    flush=True,
                )

                self._pause()
                continue

            if not content:
                failures.append(
                    self._failure_record(
                        sequence=index,
                        listing_page=listing_page,
                        slug=slug,
                        source_url=source_url,
                        error=(
                            "Página retornada vazia."
                        ),
                    )
                )

                print(
                    f"[vazia] "
                    f"{index}/{total} "
                    f"{slug}",
                    flush=True,
                )

                self._pause()
                continue

            destination.write_bytes(
                content
            )

            manifest.append(
                self._manifest_record(
                    sequence=index,
                    listing_page=listing_page,
                    slug=slug,
                    source_url=source_url,
                    path=destination,
                )
            )

            print(
                f"[ok] "
                f"{index}/{total} "
                f"{slug}",
                flush=True,
            )

            self._pause()

        self._write_jsonl(
            manifest_path,
            manifest,
        )

        if failures:
            self._write_jsonl(
                failures_path,
                failures,
            )
        elif failures_path.exists():
            failures_path.unlink()

        self._write_metadata(
            reference=reference,
            catalog_path=catalog_path,
            manifest_path=manifest_path,
            failures_path=failures_path,
            records=records,
            manifest=manifest,
            failures=failures,
            collect_missing=collect_missing,
        )

        return catalog_path

    def read(
        self,
        reference: int,
        **kwargs: str,
    ) -> Iterator[dict[str, str]]:
        """
        Lê apenas registros efetivamente disponíveis na Bronze.

        O manifesto representa os detalhes coletados com sucesso.
        Registros presentes no catálogo mas ausentes na Bronze não
        interrompem a leitura.
        """

        directory = self._directory(
            reference
        )

        manifest_path = (
            directory
            / "manifesto.jsonl"
        )

        details_directory = (
            directory
            / "detalhes"
        )

        if not manifest_path.exists():
            raise FileNotFoundError(
                "Manifesto Bronze não encontrado: "
                f"{manifest_path}"
            )

        for record in self._read_jsonl(
            manifest_path
        ):
            detail_path = (
                details_directory
                / str(record["file"])
            )

            if not detail_path.exists():
                raise FileNotFoundError(
                    "Arquivo listado no manifesto "
                    "não encontrado: "
                    f"{detail_path}"
                )

            yield {
                "slug": str(
                    record["slug"]
                ),
                "source_url": str(
                    record["source_url"]
                ),
                "listing_page": str(
                    record["listing_page"]
                ),
                "html": detail_path.read_text(
                    encoding=self.encoding,
                    errors="replace",
                ),
            }

    def _download_catalog(
        self,
        listings_directory: Path,
    ) -> list[dict[str, object]]:
        records: list[dict[str, object]] = []
        seen: set[str] = set()

        for page in range(
            1,
            self.max_pages + 1,
        ):
            url = (
                f"{self.search_url}"
                f"?page={page}"
            )

            content = self._fetch(url)

            listing_path = (
                listings_directory
                / f"{page:04d}.html"
            )

            listing_path.write_bytes(
                content
            )

            html = content.decode(
                self.encoding,
                errors="replace",
            )

            links = self.extract_detail_links(
                html
            )

            if not links:
                break

            new_links = 0

            for link in links:
                if link in seen:
                    continue

                seen.add(link)

                records.append(
                    {
                        "listing_page": page,
                        "slug": (
                            urlparse(link)
                            .path
                            .rstrip("/")
                            .split("/")[-1]
                        ),
                        "source_url": link,
                    }
                )

                new_links += 1

            if new_links == 0:
                raise RuntimeError(
                    "Paginação do Transforma! "
                    "não avançou."
                )

            self._pause()

        else:
            raise RuntimeError(
                "Limite máximo de páginas atingido "
                "antes do fim do catálogo."
            )

        if not records:
            raise ValueError(
                "Nenhuma tecnologia social "
                "foi encontrada."
            )

        return records

    @classmethod
    def extract_detail_links(
        cls,
        html: str,
    ) -> list[str]:
        """Extrai links de detalhes de uma página de resultados."""

        parser = _CatalogParser(
            cls.base_url
        )

        parser.feed(html)

        return parser.links

    def _fetch(
        self,
        url: str,
        individual_detail: bool = False,
    ) -> bytes:
        attempts = 3

        for attempt in range(
            1,
            attempts + 1,
        ):
            request = Request(
                url,
                headers={
                    "User-Agent": (
                        self.user_agent
                    ),
                },
            )

            try:
                with urlopen(
                    request,
                    timeout=self.timeout,
                ) as response:
                    return response.read()

            except HTTPError as exc:
                if exc.code == 429:
                    raise _CollectionBlockedError(
                        "Coleta interrompida pelo "
                        "servidor HTTP 429: "
                        f"{url}"
                    ) from exc

                if exc.code == 403:
                    if individual_detail:
                        raise RuntimeError(
                            "Página individual retornou "
                            f"HTTP 403: {url}"
                        ) from exc

                    raise _CollectionBlockedError(
                        "Coleta interrompida pelo "
                        "servidor HTTP 403: "
                        f"{url}"
                    ) from exc

                raise RuntimeError(
                    "Erro HTTP ao acessar "
                    f"{url}: {exc.code}"
                ) from exc

            except (
                TimeoutError,
                URLError,
            ) as exc:
                if attempt == attempts:
                    reason = getattr(
                        exc,
                        "reason",
                        str(exc),
                    )

                    raise RuntimeError(
                        "Falha de rede após "
                        f"{attempts} tentativas "
                        "ao acessar "
                        f"{url}: {reason}"
                    ) from exc

                time.sleep(
                    2.0 * attempt
                )

        raise RuntimeError(
            f"Falha inesperada ao acessar {url}"
        )

    def _pause(self) -> None:
        if self.request_interval > 0:
            time.sleep(
                self.request_interval
            )

    def _directory(
        self,
        reference: int,
    ) -> Path:
        return (
            self.bronze_root
            / "fbb"
            / "transforma"
            / str(reference)
        )

    @staticmethod
    def _detail_filename(
        source_url: str,
    ) -> str:
        digest = sha256(
            source_url.encode("utf-8")
        ).hexdigest()[:24]

        return f"{digest}.html"

    @staticmethod
    def _manifest_record(
        sequence: int,
        listing_page: int,
        slug: str,
        source_url: str,
        path: Path,
    ) -> dict[str, object]:
        return {
            "sequence": sequence,
            "listing_page": listing_page,
            "slug": slug,
            "source_url": source_url,
            "file": path.name,
            "size_bytes": path.stat().st_size,
            "sha256": (
                TransformaSource._sha256(
                    path
                )
            ),
        }

    @staticmethod
    def _failure_record(
        sequence: int,
        listing_page: int,
        slug: str,
        source_url: str,
        error: str,
    ) -> dict[str, object]:
        return {
            "sequence": sequence,
            "listing_page": listing_page,
            "slug": slug,
            "source_url": source_url,
            "error": error,
        }

    @staticmethod
    def _previous_failures(
        path: Path,
    ) -> dict[str, str]:
        if not path.exists():
            return {}

        failures: dict[str, str] = {}

        for record in TransformaSource._read_jsonl(
            path
        ):
            source_url = str(
                record.get(
                    "source_url",
                    "",
                )
            )

            error = str(
                record.get(
                    "error",
                    "",
                )
            )

            if source_url:
                failures[source_url] = error

        return failures

    @staticmethod
    def _read_jsonl(
        path: Path,
    ) -> Iterator[dict[str, object]]:
        with path.open(
            encoding="utf-8",
        ) as file:
            for line in file:
                if not line.strip():
                    continue

                yield json.loads(line)

    @staticmethod
    def _write_jsonl(
        path: Path,
        records: list[dict[str, object]],
    ) -> None:
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

            temporary.replace(path)

        finally:
            if temporary.exists():
                temporary.unlink()

    @staticmethod
    def _sha256(
        path: Path,
    ) -> str:
        digest = sha256()

        with path.open("rb") as file:
            while chunk := file.read(
                1024 * 1024
            ):
                digest.update(chunk)

        return digest.hexdigest()

    def _write_metadata(
        self,
        reference: int,
        catalog_path: Path,
        manifest_path: Path,
        failures_path: Path,
        records: list[dict[str, object]],
        manifest: list[dict[str, object]],
        failures: list[dict[str, object]],
        collect_missing: bool,
    ) -> None:
        pages = {
            int(record["listing_page"])
            for record in records
        }

        catalog_records = len(records)
        detail_files = len(manifest)
        failed_records = len(failures)

        coverage = (
            detail_files / catalog_records
            if catalog_records
            else 0.0
        )

        status = (
            "complete"
            if failed_records == 0
            else "partial"
        )

        metadata = {
            "source": self.name,
            "dataset": self.dataset,
            "snapshot_reference": reference,
            "source_url": self.search_url,
            "retrieved_at": (
                datetime.now(UTC).isoformat()
            ),
            "catalog_records": (
                catalog_records
            ),
            "detail_files": detail_files,
            "failed_records": (
                failed_records
            ),
            "coverage": round(
                coverage,
                6,
            ),
            "listing_pages_with_records": (
                len(pages)
            ),
            "last_listing_page": (
                max(pages)
            ),
            "catalog_file": (
                catalog_path.name
            ),
            "catalog_sha256": (
                self._sha256(
                    catalog_path
                )
            ),
            "manifest_file": (
                manifest_path.name
            ),
            "manifest_sha256": (
                self._sha256(
                    manifest_path
                )
            ),
            "failures_file": (
                failures_path.name
                if failures
                else None
            ),
            "failures_sha256": (
                self._sha256(
                    failures_path
                )
                if failures
                else None
            ),
            "request_interval_seconds": (
                self.request_interval
            ),
            "user_agent": self.user_agent,
            "collection_mode": (
                "network"
                if collect_missing
                else "local_only"
            ),
            "status": status,
        }

        metadata_path = (
            catalog_path.parent
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