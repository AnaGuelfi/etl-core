from __future__ import annotations

import csv
import json
import time
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Iterator
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from savits_etl.sources.epo import EPOSource

DEFAULT_INPI_GOLD = Path(
    "data/gold/inpi/pedidos_patentes/"
    "consolidado/patentes_analitico.csv"
)


def _read_jsonl(
    path: Path,
) -> Iterator[dict[str, object]]:
    with path.open(
        encoding="utf-8",
    ) as file:
        for line in file:
            if line.strip():
                yield json.loads(
                    line
                )


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


def _sha256_file(
    path: Path,
) -> str:
    digest = sha256()

    with path.open(
        "rb",
    ) as file:
        while chunk := file.read(
            1024 * 1024
        ):
            digest.update(
                chunk
            )

    return digest.hexdigest()


def _local_name(
    tag: str,
) -> str:
    return tag.rsplit(
        "}",
        1,
    )[-1]


def _application_aliases(
    numero_pedido: str,
    data_deposito: str,
    epodoc_consulta: str,
) -> set[str]:
    aliases = {
        epodoc_consulta.strip().upper()
    }

    compact = "".join(
        character
        for character
        in numero_pedido.strip().upper()
        if not character.isspace()
    )

    # MU legado é consultável como BRMUxxxxxxx,
    # mas a bibliografia devolve o EPODOC canônico
    # no formato BRyyyyMUxxxxxU.
    if (
        len(compact) == 9
        and compact.startswith("MU")
        and compact[2:].isdigit()
    ):
        value = data_deposito.strip()

        if (
            len(value) >= 4
            and value[:4].isdigit()
        ):
            aliases.add(
                f"BR{value[:4]}MU"
                f"{compact[-5:]}U"
            )

    return aliases


def _document_application_epodocs(
    document: ET.Element,
) -> set[str]:
    result = set()

    for reference in document.iter():
        if (
            _local_name(reference.tag)
            != "application-reference"
        ):
            continue

        for document_id in reference:
            if (
                _local_name(
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
                    _local_name(
                        child.tag
                    )
                    == "doc-number"
                    and child.text
                ):
                    result.add(
                        child.text.strip().upper()
                    )

    return result


def _parse_batch_documents(
    content: bytes,
) -> list[
    tuple[
        set[str],
        bool,
    ]
]:
    root = ET.fromstring(
        content
    )

    result = []

    for document in root.iter():
        if (
            _local_name(document.tag)
            != "exchange-document"
        ):
            continue

        application_epodocs = (
            _document_application_epodocs(
                document
            )
        )

        if not application_epodocs:
            continue

        has_publication = bool(
            document.attrib.get(
                "doc-number",
                "",
            ).strip()
        )

        result.append(
            (
                application_epodocs,
                has_publication,
            )
        )

    return result


def _compact_failures(
    failures_path: Path,
    links_path: Path,
) -> int:
    if not failures_path.exists():
        return 0

    processed = set()

    if links_path.exists():
        processed = {
            str(
                row.get(
                    "numero_pedido",
                    "",
                )
            )
            for row in _read_jsonl(
                links_path
            )
        }

    latest: dict[
        str,
        dict[str, object],
    ] = {}

    for failure in _read_jsonl(
        failures_path
    ):
        numero = str(
            failure.get(
                "numero_pedido",
                "",
            )
        )

        if not numero:
            continue

        if numero in processed:
            continue

        latest[numero] = failure

    unresolved = list(
        latest.values()
    )

    if not unresolved:
        failures_path.unlink()
        return 0

    temporary = failures_path.with_suffix(
        failures_path.suffix + ".part"
    )

    try:
        with temporary.open(
            "w",
            encoding="utf-8",
        ) as file:
            for record in unresolved:
                file.write(
                    json.dumps(
                        record,
                        ensure_ascii=False,
                    )
                )
                file.write("\n")

        temporary.replace(
            failures_path
        )

    finally:
        if temporary.exists():
            temporary.unlink()

    return len(
        unresolved
    )


def _write_metadata(
    *,
    root: Path,
    reference: int,
    input_path: Path,
    links_path: Path,
    failures_path: Path,
    manifest_path: Path,
    status: str,
    attempted_this_run: int,
    new_records_this_run: int,
    batch_size: int,
) -> None:
    links = (
        list(
            _read_jsonl(
                links_path
            )
        )
        if links_path.exists()
        else []
    )

    failures = (
        list(
            _read_jsonl(
                failures_path
            )
        )
        if failures_path.exists()
        else []
    )

    manifest = (
        list(
            _read_jsonl(
                manifest_path
            )
        )
        if manifest_path.exists()
        else []
    )

    counts = Counter(
        str(
            row.get(
                "status",
                "",
            )
        )
        for row in links
    )

    metadata = {
        "source": (
            "INPI enriquecido com "
            "European Patent Office OPS"
        ),
        "layer": "bronze",
        "dataset": (
            "inpi_epo_producao"
        ),
        "snapshot_reference": (
            reference
        ),
        "generated_at": datetime.now(
            UTC
        ).isoformat(),
        "service": "EPO OPS 3.2",
        "strategy": (
            "direct_epodoc_application_batch"
        ),
        "records": len(
            links
        ),
        "attempted_this_run": (
            attempted_this_run
        ),
        "new_records_this_run": (
            new_records_this_run
        ),
        "status_counts": dict(
            sorted(
                counts.items()
            )
        ),
        "technical_failures": len(
            failures
        ),
        "response_batches": len(
            manifest
        ),
        "batch_size": batch_size,
        "status": status,
        "input": {
            "file": str(
                input_path
            ),
            "sha256": _sha256_file(
                input_path
            ),
        },
        "files": {
            "links": (
                links_path.name
            ),
            "manifest": (
                manifest_path.name
                if manifest_path.exists()
                else None
            ),
            "failures": (
                failures_path.name
                if failures_path.exists()
                else None
            ),
            "batches_directory": (
                "batches"
            ),
        },
        "semantic_statuses": {
            "matched": (
                "Bibliografia encontrada "
                "na OPS."
            ),
            "no_bibliography": (
                "A OPS reconheceu a aplicação, "
                "mas não devolveu publicação "
                "bibliográfica."
            ),
            "unsupported_inpi_format": (
                "Formato INPI não contemplado "
                "pela derivação direta."
            ),
            "unresolved_batch_http_404": (
                "Lote reduzido retornou HTTP 404 "
                "e foi ignorado para manter "
                "a coleta em andamento."
            ),
            "unresolved_batch_http_400": (
                "Lote reduzido retornou HTTP 400 "
                "e foi ignorado para manter "
                "a coleta em andamento."
            ),
        },
    }

    metadata_path = (
        root / "metadata.json"
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


def coletar_bronze_inpi_epo_batch(
    reference: int,
    *,
    inpi_path: Path | str = DEFAULT_INPI_GOLD,
    bronze_root: Path | str = "data/bronze",
    batch_size: int = 25,
    limit: int | None = None,
    request_interval: float = 1.0,
    timeout: float = 30.0,
    source: EPOSource | None = None,
) -> tuple[Path, Path]:
    """
    Coleta a Bronze EPO de produção.

    A aplicação EPODOC é derivada localmente.
    A bibliografia é consultada em lotes.

    O snapshot é retomável: pedidos já presentes
    em vinculos.jsonl não são consultados novamente.
    """

    if not 1 <= batch_size <= 100:
        raise ValueError(
            "batch_size deve estar "
            "entre 1 e 100."
        )

    if (
        limit is not None
        and limit < 1
    ):
        raise ValueError(
            "limit deve ser maior "
            "ou igual a 1."
        )

    input_path = Path(
        inpi_path
    )

    if not input_path.exists():
        raise FileNotFoundError(
            "Gold INPI não encontrada: "
            f"{input_path}"
        )

    root = (
        Path(bronze_root)
        / "epo"
        / "inpi_producao"
        / str(reference)
    )

    batches_dir = (
        root / "batches"
    )

    links_path = (
        root / "vinculos.jsonl"
    )

    failures_path = (
        root / "falhas.jsonl"
    )

    manifest_path = (
        root / "manifesto.jsonl"
    )

    root.mkdir(
        parents=True,
        exist_ok=True,
    )

    batches_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    epo = (
        source
        if source is not None
        else EPOSource(
            request_interval=0,
            timeout=timeout,
        )
    )

    processed = (
        {
            str(
                row.get(
                    "numero_pedido",
                    "",
                )
            )
            for row in _read_jsonl(
                links_path
            )
        }
        if links_path.exists()
        else set()
    )

    if failures_path.exists():
        processed.update(
            str(
                row.get(
                    "numero_pedido",
                    "",
                )
            )
            for row in _read_jsonl(
                failures_path
            )
        )

    batch_sequence = (
        sum(
            1
            for _ in _read_jsonl(
                manifest_path
            )
        )
        if manifest_path.exists()
        else 0
    )

    attempted = 0
    new_records = 0
    reached_limit = False
    interrupted = False

    pending: list[
        dict[str, object]
    ] = []

    def append_link(
        entry: dict[str, object],
        *,
        status: str,
        batch_file: str = "",
        epodoc_response: str = "",
    ) -> None:
        nonlocal new_records

        record = {
            "numero_pedido": (
                entry["numero_pedido"]
            ),
            "ano_fonte": (
                entry["ano_fonte"]
            ),
            "ano_deposito_inpi": (
                entry["ano_deposito_inpi"]
            ),
            "data_deposito_inpi": (
                entry["data_deposito_inpi"]
            ),
            "possui_pct": (
                entry["possui_pct"]
            ),
            "original_ops": (
                entry["original_ops"]
            ),
            "epodoc_consulta": (
                entry["epodoc_consulta"]
            ),
            "epodoc_aplicacao_resposta": (
                epodoc_response
            ),
            "status": status,
            "batch_file": batch_file,
            "xml_file": "",
            "xml_sha256": "",
        }

        _append_jsonl(
            links_path,
            record,
        )

        processed.add(
            str(
                entry["numero_pedido"]
            )
        )

        new_records += 1

    def append_failure(
        entry: dict[str, object],
        error: str,
    ) -> None:
        _append_jsonl(
            failures_path,
            {
                "numero_pedido": (
                    entry[
                        "numero_pedido"
                    ]
                ),
                "epodoc_consulta": (
                    entry[
                        "epodoc_consulta"
                    ]
                ),
                "error": error,
                "generated_at": (
                    datetime.now(
                        UTC
                    ).isoformat()
                ),
            },
        )

    def process_group(
        entries: list[
            dict[str, object]
        ],
        *,
        allow_fallback: bool = True,
    ) -> None:
        nonlocal batch_sequence

        if not entries:
            return

        identifiers = [
            str(
                entry[
                    "epodoc_consulta"
                ]
            )
            for entry in entries
        ]

        if request_interval > 0:
            time.sleep(
                request_interval
            )

        try:
            content = (
                epo
                .fetch_application_biblio_batch(
                    identifiers
                )
            )

        except RuntimeError as exc:
            code = getattr(
                exc,
                "code",
                None,
            )

            message = str(
                exc
            )

            if (
                "HTTP 403" in message
                or "HTTP 429" in message
            ):
                raise

            if code in {
                400,
                404,
            }:
                if (
                    allow_fallback
                    and len(entries) > 25
                ):
                    print(
                        "[fallback] "
                        f"HTTP {code} em "
                        f"{len(entries)} pedidos; "
                        "tentando sublotes de 25.",
                        flush=True,
                    )

                    for start in range(
                        0,
                        len(entries),
                        25,
                    ):
                        process_group(
                            entries[
                                start:
                                start + 25
                            ],
                            allow_fallback=False,
                        )

                    return

                status = (
                    "unresolved_batch_"
                    f"http_{code}"
                )

                for entry in entries:
                    append_link(
                        entry,
                        status=status,
                    )

                print(
                    "[skip] "
                    f"HTTP {code}: "
                    f"{len(entries)} pedidos "
                    "marcados como não resolvidos.",
                    flush=True,
                )

                return

            if (
                code == 404
                and len(entries) == 1
            ):
                append_link(
                    entries[0],
                    status=(
                        "no_bibliography"
                    ),
                )
                return

            for entry in entries:
                append_failure(
                    entry,
                    str(exc),
                )

            return

        batch_sequence += 1

        digest = sha256(
            ",".join(
                identifiers
            ).encode(
                "utf-8"
            )
        ).hexdigest()[:16]

        filename = (
            f"{batch_sequence:06d}_"
            f"{digest}.xml"
        )

        batch_path = (
            batches_dir
            / filename
        )

        batch_path.write_bytes(
            content
        )

        _append_jsonl(
            manifest_path,
            {
                "batch_sequence": (
                    batch_sequence
                ),
                "identifiers": (
                    identifiers
                ),
                "pedidos": [
                    str(
                        entry[
                            "numero_pedido"
                        ]
                    )
                    for entry in entries
                ],
                "identifier_count": (
                    len(entries)
                ),
                "file": filename,
                "size_bytes": (
                    len(content)
                ),
                "sha256": (
                    _sha256_file(
                        batch_path
                    )
                ),
            },
        )

        documents = (
            _parse_batch_documents(
                content
            )
        )

        for entry in entries:
            aliases = set(
                entry[
                    "aliases"
                ]
            )

            matching = [
                (
                    document_ids,
                    has_publication,
                )
                for (
                    document_ids,
                    has_publication,
                )
                in documents
                if aliases
                & document_ids
            ]

            matched = [
                document_ids
                for (
                    document_ids,
                    has_publication,
                )
                in matching
                if has_publication
            ]

            if matched:
                response_ids = sorted(
                    {
                        identifier
                        for document_ids
                        in matched
                        for identifier
                        in document_ids
                    }
                )

                canonical = (
                    response_ids[0]
                    if response_ids
                    else ""
                )

                append_link(
                    entry,
                    status="matched",
                    batch_file=filename,
                    epodoc_response=(
                        canonical
                    ),
                )

            elif matching:
                response_ids = sorted(
                    {
                        identifier
                        for (
                            document_ids,
                            _
                        )
                        in matching
                        for identifier
                        in document_ids
                    }
                )

                append_link(
                    entry,
                    status=(
                        "no_bibliography"
                    ),
                    batch_file=filename,
                    epodoc_response=(
                        response_ids[0]
                        if response_ids
                        else ""
                    ),
                )

            else:
                append_failure(
                    entry,
                    (
                        "Aplicação não retornada "
                        "na resposta do lote."
                    ),
                )

        print(
            "[ok] "
            f"batch {batch_sequence} "
            f"({len(entries)} pedidos)",
            flush=True,
        )

    try:
        with input_path.open(
            encoding="utf-8",
            newline="",
        ) as file:
            reader = csv.DictReader(
                file
            )

            for row in reader:
                numero = (
                    row.get(
                        "numero_pedido",
                        "",
                    )
                    .strip()
                )

                if numero in processed:
                    continue

                if (
                    limit is not None
                    and attempted >= limit
                ):
                    reached_limit = True
                    break

                attempted += 1

                data_deposito = (
                    row.get(
                        "data_deposito",
                        "",
                    )
                    .strip()
                )

                epodoc = (
                    EPOSource
                    .construir_epodoc_inpi_direto(
                        numero_pedido=numero,
                        data_deposito=(
                            data_deposito
                        ),
                    )
                )

                original_ops = (
                    EPOSource
                    .construir_numero_original_inpi_ops(
                        numero_pedido=numero,
                        data_deposito=(
                            data_deposito
                        ),
                    )
                )

                entry: dict[
                    str,
                    object,
                ] = {
                    "numero_pedido": (
                        numero
                    ),
                    "ano_fonte": (
                        row.get(
                            "ano_fonte",
                            "",
                        )
                    ),
                    "ano_deposito_inpi": (
                        row.get(
                            "ano_deposito",
                            "",
                        )
                    ),
                    "data_deposito_inpi": (
                        data_deposito
                    ),
                    "possui_pct": (
                        row.get(
                            "possui_pct",
                            "",
                        )
                    ),
                    "original_ops": (
                        original_ops or ""
                    ),
                    "epodoc_consulta": (
                        epodoc or ""
                    ),
                    "aliases": [],
                }

                if epodoc is None:
                    append_link(
                        entry,
                        status=(
                            "unsupported_inpi_format"
                        ),
                    )
                    continue

                entry[
                    "aliases"
                ] = sorted(
                    _application_aliases(
                        numero_pedido=numero,
                        data_deposito=(
                            data_deposito
                        ),
                        epodoc_consulta=(
                            epodoc
                        ),
                    )
                )

                pending.append(
                    entry
                )

                if (
                    len(pending)
                    >= batch_size
                ):
                    process_group(
                        pending
                    )
                    pending = []

            if pending:
                process_group(
                    pending
                )

    except RuntimeError as exc:
        message = str(
            exc
        )

        if (
            "HTTP 403" in message
            or "HTTP 429" in message
        ):
            interrupted = True

        raise

    except KeyboardInterrupt:
        interrupted = True
        raise

    finally:
        unresolved = (
            _compact_failures(
                failures_path,
                links_path,
            )
        )

        if interrupted:
            status = "interrupted"

        elif reached_limit:
            status = "partial_limit"

        elif unresolved:
            status = (
                "partial_failures"
            )

        else:
            status = "complete"

        _write_metadata(
            root=root,
            reference=reference,
            input_path=input_path,
            links_path=links_path,
            failures_path=(
                failures_path
            ),
            manifest_path=(
                manifest_path
            ),
            status=status,
            attempted_this_run=(
                attempted
            ),
            new_records_this_run=(
                new_records
            ),
            batch_size=batch_size,
        )

    return (
        links_path,
        root / "metadata.json",
    )