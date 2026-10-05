from __future__ import annotations

import csv
import json
import time
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
            if not line.strip():
                continue

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

def _compact_failures(
    failures_path: Path,
    links_path: Path,
) -> int:
    """
    Mantém em falhas.jsonl apenas falhas técnicas
    ainda não resolvidas.

    Se um numero_pedido já possui resultado semântico
    em vinculos.jsonl, sua falha anterior é considerada
    resolvida.

    Para falhas repetidas do mesmo pedido, preserva
    somente a ocorrência mais recente.
    """

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

    latest_by_identifier: dict[
        str,
        dict[str, object],
    ] = {}

    for failure in _read_jsonl(
        failures_path
    ):
        numero_pedido = str(
            failure.get(
                "numero_pedido",
                "",
            )
        )

        if not numero_pedido:
            continue

        if numero_pedido in processed:
            continue

        latest_by_identifier[
            numero_pedido
        ] = failure

    unresolved = list(
        latest_by_identifier.values()
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

def _sha256_file(
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

def _sha256_bytes(
    content: bytes,
) -> str:
    return sha256(
        content
    ).hexdigest()


def _safe_filename(
    sequence: int,
    numero_pedido: str,
) -> str:
    digest = sha256(
        numero_pedido.encode()
    ).hexdigest()[:16]

    return (
        f"{sequence:06d}_"
        f"{digest}.xml"
    )


def _is_blocking_error(
    exc: RuntimeError,
) -> bool:
    message = str(
        exc
    )

    return (
        "HTTP 403" in message
        or "HTTP 429" in message
    )


def _write_metadata(
    *,
    metadata_path: Path,
    reference: int,
    links_path: Path,
    failures_path: Path,
    xml_dir: Path,
    status: str,
    new_records: int,
    input_path: Path,
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
        "dataset": "inpi_epo_links",
        "snapshot_reference": reference,
        "generated_at": datetime.now(
            UTC
        ).isoformat(),
        "service": "EPO OPS 3.2",
        "input": {
            "file": str(
                input_path
            ),
            "sha256": _sha256_file(
                input_path
            ),
        },
        "records": len(
            links
        ),
        "new_records_this_run": (
            new_records
        ),
        "status_counts": dict(
            sorted(
                counts.items()
            )
        ),
        "technical_failures": len(
            failures
        ),
        "xml_files": len(
            list(
                xml_dir.glob(
                    "*.xml"
                )
            )
        ),
        "links_file": (
            links_path.name
        ),
        "failures_file": (
            failures_path.name
            if failures_path.exists()
            else None
        ),
        "status": status,
        "semantic_statuses": {
            "matched": (
                "Identificador EPODOC "
                "normalizado e bibliografia "
                "encontrada na OPS."
            ),
            "no_bibliography": (
                "Identificador EPODOC válido, "
                "mas sem bibliografia publicada "
                "recuperável na OPS."
            ),
            "epodoc_unusable": (
                "O Number Service não produziu "
                "EPODOC utilizável."
            ),
            "unsupported_inpi_format": (
                "Formato INPI ainda não "
                "suportado pelo adaptador."
            ),
        },
    }

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


def coletar_bronze_inpi_epo(
    reference: int,
    *,
    inpi_path: Path | str = DEFAULT_INPI_GOLD,
    bronze_root: Path | str = "data/bronze",
    limit: int | None = None,
    request_interval: float = 1.0,
    timeout: float = 30.0,
    source: EPOSource | None = None,
) -> tuple[Path, Path]:
    """
    Coleta a Bronze de ligação entre a Gold INPI e a EPO.

    Estados semânticos são gravados em vinculos.jsonl.
    Falhas técnicas ficam em falhas.jsonl e podem ser
    tentadas novamente em execução posterior.

    limit limita apenas novos registros processados.
    """

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
        / "inpi"
        / str(reference)
    )

    xml_dir = (
        root
        / "xml"
    )

    links_path = (
        root
        / "vinculos.jsonl"
    )

    failures_path = (
        root
        / "falhas.jsonl"
    )

    metadata_path = (
        root
        / "metadata.json"
    )

    root.mkdir(
        parents=True,
        exist_ok=True,
    )

    xml_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    epo = (
        source
        if source is not None
        else EPOSource(
            request_interval=(
                request_interval
            ),
            timeout=timeout,
        )
    )

    existing_links = (
        list(
            _read_jsonl(
                links_path
            )
        )
        if links_path.exists()
        else []
    )

    processed = {
        str(
            row.get(
                "numero_pedido",
                "",
            )
        )
        for row in existing_links
    }

    sequence = len(
        existing_links
    )

    new_records = 0
    reached_limit = False
    interrupted = False

    try:
        with input_path.open(
            encoding="utf-8",
            newline="",
        ) as file:
            reader = csv.DictReader(
                file
            )

            for row in reader:
                numero_pedido = (
                    row.get(
                        "numero_pedido",
                        "",
                    )
                    .strip()
                )

                if (
                    numero_pedido
                    in processed
                ):
                    continue

                if (
                    limit is not None
                    and new_records
                    >= limit
                ):
                    reached_limit = True
                    break

                data_deposito = (
                    row.get(
                        "data_deposito",
                        "",
                    )
                    .strip()
                )

                original_ops = (
                    EPOSource
                    .construir_numero_original_inpi_ops(
                        numero_pedido=(
                            numero_pedido
                        ),
                        data_deposito=(
                            data_deposito
                        ),
                    )
                )

                record: dict[
                    str,
                    object,
                ] = {
                    "numero_pedido": (
                        numero_pedido
                    ),
                    "ano_fonte": row.get(
                        "ano_fonte",
                        "",
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
                    "possui_pct": row.get(
                        "possui_pct",
                        "",
                    ),
                    "original_ops": (
                        original_ops or ""
                    ),
                    "epodoc_consulta": "",
                    "status": "",
                    "xml_file": "",
                    "xml_sha256": "",
                }

                if original_ops is None:
                    record["status"] = (
                        "unsupported_inpi_format"
                    )

                    sequence += 1
                    new_records += 1

                    _append_jsonl(
                        links_path,
                        record,
                    )

                    processed.add(
                        numero_pedido
                    )

                    print(
                        f"[{sequence}] "
                        f"{numero_pedido} "
                        "-> unsupported_inpi_format",
                        flush=True,
                    )

                    continue

                try:
                    epodoc = (
                        epo
                        .standardize_application_original(
                            original_ops
                        )
                    )

                    if request_interval > 0:
                        time.sleep(
                            request_interval
                        )

                    if epodoc is None:
                        record["status"] = (
                            "epodoc_unusable"
                        )

                    else:
                        record[
                            "epodoc_consulta"
                        ] = epodoc

                        content = (
                            epo
                            .fetch_application_biblio(
                                epodoc
                            )
                        )

                        if request_interval > 0:
                            time.sleep(
                                request_interval
                            )

                        if content is None:
                            record[
                                "status"
                            ] = (
                                "no_bibliography"
                            )

                        else:
                            record[
                                "status"
                            ] = "matched"

                            filename = (
                                _safe_filename(
                                    sequence + 1,
                                    numero_pedido,
                                )
                            )

                            xml_path = (
                                xml_dir
                                / filename
                            )

                            xml_path.write_bytes(
                                content
                            )

                            record[
                                "xml_file"
                            ] = filename

                            record[
                                "xml_sha256"
                            ] = (
                                _sha256_bytes(
                                    content
                                )
                            )

                except RuntimeError as exc:
                    if _is_blocking_error(
                        exc
                    ):
                        interrupted = True
                        raise

                    failure = {
                        "numero_pedido": (
                            numero_pedido
                        ),
                        "original_ops": (
                            original_ops
                        ),
                        "error": str(
                            exc
                        ),
                        "generated_at": (
                            datetime.now(
                                UTC
                            ).isoformat()
                        ),
                    }

                    _append_jsonl(
                        failures_path,
                        failure,
                    )

                    print(
                        f"[falha técnica] "
                        f"{numero_pedido}: "
                        f"{exc}",
                        flush=True,
                    )

                    continue

                sequence += 1
                new_records += 1

                _append_jsonl(
                    links_path,
                    record,
                )

                processed.add(
                    numero_pedido
                )

                print(
                    f"[{sequence}] "
                    f"{numero_pedido} "
                    f"-> {record['status']}",
                    flush=True,
                )

    finally:
        unresolved_failures = (
            _compact_failures(
                failures_path=failures_path,
                links_path=links_path,
            )
        )

        if interrupted:
            status = "interrupted"

        elif reached_limit:
            status = "partial_limit"

        elif unresolved_failures:
            status = "partial_failures"

        else:
            status = "complete"

        _write_metadata(
            metadata_path=(
                metadata_path
            ),
            reference=reference,
            links_path=links_path,
            failures_path=(
                failures_path
            ),
            xml_dir=xml_dir,
            status=status,
            new_records=(
                new_records
            ),
            input_path=input_path,
        )

    return (
        links_path,
        metadata_path,
    )