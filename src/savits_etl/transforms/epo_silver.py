from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from savits_etl.transforms.epo import (
    parse_epo_biblio,
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


def _write_jsonl(
    path: Path,
    records: list[dict[str, object]],
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


def _unique_strings(
    values,
) -> list[str]:
    result = []
    seen = set()

    for value in values:
        text = str(
            value
        ).strip()

        if not text:
            continue

        if text in seen:
            continue

        seen.add(
            text
        )

        result.append(
            text
        )

    return result


def _canonical_application_epodoc(
    parsed: dict[str, object],
) -> tuple[str, list[str]]:
    references = parsed.get(
        "application_references",
        [],
    )

    identifiers = _unique_strings(
        reference.get(
            "doc_number",
            "",
        )
        for reference in references
        if isinstance(
            reference,
            dict,
        )
        and reference.get(
            "document_id_type"
        )
        == "epodoc"
    )

    if len(identifiers) == 1:
        return (
            identifiers[0],
            identifiers,
        )

    return (
        "",
        identifiers,
    )


def _empty_bibliography() -> dict[str, object]:
    return {
        "exchange_document_count": 0,
        "family_ids": [],
        "exchange_documents": [],
        "publication_references": [],
        "application_references": [],
        "titles": [],
        "applicants": [],
        "inventors": [],
        "priorities": [],
        "classifications": [],
        "abstracts": [],
    }


def build_epo_silver_record(
    link: dict[str, object],
    *,
    xml: bytes | None = None,
) -> dict[str, object]:
    numero_pedido = str(
        link.get(
            "numero_pedido",
            "",
        )
    )

    status = str(
        link.get(
            "status",
            "",
        )
    )

    epodoc_consulta = str(
        link.get(
            "epodoc_consulta",
            "",
        )
    )

    xml_file = str(
        link.get(
            "xml_file",
            "",
        )
    )

    if status == "matched":
        if xml is None:
            raise ValueError(
                "Registro matched exige XML: "
                f"{numero_pedido}"
            )

        parsed = parse_epo_biblio(
            xml,
            numero_pedido_inpi=(
                numero_pedido
            ),
            epodoc_consulta=(
                epodoc_consulta
            ),
            xml_file=xml_file,
        )

        (
            epodoc_canonico,
            epodoc_aplicacoes,
        ) = _canonical_application_epodoc(
            parsed
        )

        bibliography = {
            key: value
            for key, value in parsed.items()
            if key
            not in {
                "numero_pedido_inpi",
                "epodoc_consulta",
                "xml_file",
            }
        }

    else:
        epodoc_canonico = ""
        epodoc_aplicacoes = []
        bibliography = (
            _empty_bibliography()
        )

    return {
        "numero_pedido_inpi": (
            numero_pedido
        ),
        "status": status,
        "original_ops": str(
            link.get(
                "original_ops",
                "",
            )
        ),
        "epodoc_consulta": (
            epodoc_consulta
        ),
        "epodoc_aplicacao_canonico": (
            epodoc_canonico
        ),
        "epodoc_aplicacoes": (
            epodoc_aplicacoes
        ),
        "epodoc_consulta_diverge_canonico": (
            bool(
                epodoc_canonico
                and epodoc_consulta
                and epodoc_canonico
                != epodoc_consulta
            )
        ),
        "ano_fonte_inpi": str(
            link.get(
                "ano_fonte",
                "",
            )
        ),
        "ano_deposito_inpi": str(
            link.get(
                "ano_deposito_inpi",
                "",
            )
        ),
        "data_deposito_inpi": str(
            link.get(
                "data_deposito_inpi",
                "",
            )
        ),
        "possui_pct_inpi": str(
            link.get(
                "possui_pct",
                "",
            )
        ),
        "xml_file": xml_file,
        "xml_sha256": str(
            link.get(
                "xml_sha256",
                "",
            )
        ),
        "bibliography": bibliography,
    }


def transform_epo_bronze_snapshot(
    *,
    bronze_snapshot: Path | str,
    silver_root: Path | str = "data/silver",
) -> tuple[Path, Path]:
    bronze_path = Path(
        bronze_snapshot
    )

    links_path = (
        bronze_path
        / "vinculos.jsonl"
    )

    xml_dir = (
        bronze_path
        / "xml"
    )

    bronze_metadata_path = (
        bronze_path
        / "metadata.json"
    )

    if not links_path.exists():
        raise FileNotFoundError(
            "vinculos.jsonl não encontrado: "
            f"{links_path}"
        )

    reference = (
        bronze_path.name
    )

    output_dir = (
        Path(silver_root)
        / "epo"
        / "inpi"
        / reference
    )

    output_path = (
        output_dir
        / "pedidos.jsonl"
    )

    metadata_path = (
        output_dir
        / "metadata.json"
    )

    records = []

    for link in _read_jsonl(
        links_path
    ):
        status = str(
            link.get(
                "status",
                "",
            )
        )

        xml = None

        if status == "matched":
            xml_file = str(
                link.get(
                    "xml_file",
                    "",
                )
            )

            if not xml_file:
                raise ValueError(
                    "Registro matched sem "
                    "xml_file: "
                    f"{link.get('numero_pedido', '')}"
                )

            xml_path = (
                xml_dir
                / xml_file
            )

            if not xml_path.exists():
                raise FileNotFoundError(
                    "XML Bronze não encontrado: "
                    f"{xml_path}"
                )

            xml = xml_path.read_bytes()

        records.append(
            build_epo_silver_record(
                link,
                xml=xml,
            )
        )

    _write_jsonl(
        output_path,
        records,
    )

    status_counts: dict[
        str,
        int,
    ] = {}

    for record in records:
        status = str(
            record["status"]
        )

        status_counts[
            status
        ] = (
            status_counts.get(
                status,
                0,
            )
            + 1
        )

    matched = [
        record
        for record in records
        if record["status"]
        == "matched"
    ]

    divergences = sum(
        bool(
            record[
                "epodoc_consulta_diverge_canonico"
            ]
        )
        for record in matched
    )

    ambiguous_canonical = sum(
        (
            len(
                record[
                    "epodoc_aplicacoes"
                ]
            )
            != 1
        )
        for record in matched
    )

    with_abstract = sum(
        bool(
            record[
                "bibliography"
            ][
                "abstracts"
            ]
        )
        for record in matched
    )

    metadata = {
        "source": (
            "European Patent Office OPS "
            "enriquecimento INPI"
        ),
        "layer": "silver",
        "dataset": "inpi_epo",
        "snapshot_reference": (
            reference
        ),
        "generated_at": datetime.now(
            UTC
        ).isoformat(),
        "records": len(
            records
        ),
        "status_counts": dict(
            sorted(
                status_counts.items()
            )
        ),
        "matched_records": len(
            matched
        ),
        "canonical_epodoc_divergences": (
            divergences
        ),
        "canonical_epodoc_ambiguous": (
            ambiguous_canonical
        ),
        "matched_with_abstract": (
            with_abstract
        ),
        "input": {
            "links_file": str(
                links_path
            ),
            "links_sha256": (
                _sha256_file(
                    links_path
                )
            ),
            "bronze_metadata_file": (
                str(
                    bronze_metadata_path
                )
                if bronze_metadata_path.exists()
                else None
            ),
            "bronze_metadata_sha256": (
                _sha256_file(
                    bronze_metadata_path
                )
                if bronze_metadata_path.exists()
                else None
            ),
        },
        "output": {
            "file": str(
                output_path
            ),
            "sha256": _sha256_file(
                output_path
            ),
        },
        "notes": {
            "epodoc_consulta": (
                "Identificador usado na "
                "consulta à OPS."
            ),
            "epodoc_aplicacao_canonico": (
                "Identificador EPODOC de "
                "aplicação devolvido pela "
                "bibliografia EPO quando há "
                "exatamente um valor único."
            ),
            "language_codes": (
                "Códigos de idioma da OPS são "
                "preservados sem interpretação."
            ),
            "party_names": (
                "Representações original e "
                "epodoc são preservadas."
            ),
        },
    }

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
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

    return (
        output_path,
        metadata_path,
    )