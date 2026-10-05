from __future__ import annotations

import csv
import json
from collections.abc import Iterator
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path


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


def _json_value(
    value,
) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _references_by_type(
    references,
    document_id_type: str,
) -> list[dict[str, object]]:
    return [
        reference
        for reference in references
        if isinstance(
            reference,
            dict,
        )
        and reference.get(
            "document_id_type"
        )
        == document_id_type
    ]


def _canonical_application_date(
    bibliography: dict[str, object],
    canonical_epodoc: str,
) -> str:
    references = bibliography.get(
        "application_references",
        [],
    )

    dates = _unique_strings(
        reference.get(
            "date",
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
        and (
            not canonical_epodoc
            or reference.get(
                "doc_number"
            )
            == canonical_epodoc
        )
    )

    if len(dates) == 1:
        return dates[0]

    return ""


def _party_names(
    parties,
    data_format: str,
) -> list[str]:
    return _unique_strings(
        party.get(
            "name",
            "",
        )
        for party in parties
        if isinstance(
            party,
            dict,
        )
        and party.get(
            "data_format"
        )
        == data_format
    )


def _party_count(
    parties,
) -> int:
    sequences = _unique_strings(
        party.get(
            "sequence",
            "",
        )
        for party in parties
        if isinstance(
            party,
            dict,
        )
    )

    if sequences:
        return len(
            sequences
        )

    names = _unique_strings(
        party.get(
            "name",
            "",
        )
        for party in parties
        if isinstance(
            party,
            dict,
        )
    )

    return len(
        names
    )


def _classification_values(
    classifications,
    source: str,
) -> list[str]:
    values = []

    for classification in classifications:
        if not isinstance(
            classification,
            dict,
        ):
            continue

        if classification.get(
            "source"
        ) != source:
            continue

        symbol = str(
            classification.get(
                "symbol",
                "",
            )
        ).strip()

        if symbol:
            values.append(
                symbol
            )
            continue

        section = str(
            classification.get(
                "section",
                "",
            )
        ).strip()

        class_number = str(
            classification.get(
                "class",
                "",
            )
        ).strip()

        subclass = str(
            classification.get(
                "subclass",
                "",
            )
        ).strip()

        main_group = str(
            classification.get(
                "main_group",
                "",
            )
        ).strip()

        subgroup = str(
            classification.get(
                "subgroup",
                "",
            )
        ).strip()

        value = (
            f"{section}"
            f"{class_number}"
            f"{subclass}"
        )

        if main_group:
            value += main_group

        if subgroup:
            value += (
                f"/{subgroup}"
            )

        if value:
            values.append(
                value
            )

    return _unique_strings(
        values
    )


def build_epo_gold_record(
    silver: dict[str, object],
) -> dict[str, object]:
    bibliography = silver.get(
        "bibliography",
        {},
    )

    if not isinstance(
        bibliography,
        dict,
    ):
        bibliography = {}

    canonical_epodoc = str(
        silver.get(
            "epodoc_aplicacao_canonico",
            "",
        )
    )

    publications = bibliography.get(
        "publication_references",
        [],
    )

    docdb_publications = (
        _references_by_type(
            publications,
            "docdb",
        )
    )

    publication_dates = sorted(
        _unique_strings(
            publication.get(
                "date",
                "",
            )
            for publication
            in docdb_publications
            if isinstance(
                publication,
                dict,
            )
        )
    )

    publication_kinds = (
        _unique_strings(
            publication.get(
                "kind",
                "",
            )
            for publication
            in docdb_publications
            if isinstance(
                publication,
                dict,
            )
        )
    )

    titles = bibliography.get(
        "titles",
        [],
    )

    title_texts = _unique_strings(
        title.get(
            "text",
            "",
        )
        for title in titles
        if isinstance(
            title,
            dict,
        )
    )

    abstracts = bibliography.get(
        "abstracts",
        [],
    )

    abstract_texts = _unique_strings(
        abstract.get(
            "text",
            "",
        )
        for abstract in abstracts
        if isinstance(
            abstract,
            dict,
        )
    )

    applicants = bibliography.get(
        "applicants",
        [],
    )

    inventors = bibliography.get(
        "inventors",
        [],
    )

    priorities = bibliography.get(
        "priorities",
        [],
    )

    classifications = bibliography.get(
        "classifications",
        [],
    )

    family_ids = _unique_strings(
        bibliography.get(
            "family_ids",
            [],
        )
    )

    return {
        "numero_pedido": str(
            silver.get(
                "numero_pedido_inpi",
                "",
            )
        ),
        "epo_status": str(
            silver.get(
                "status",
                "",
            )
        ),
        "epo_original_ops": str(
            silver.get(
                "original_ops",
                "",
            )
        ),
        "epo_epodoc_consulta": str(
            silver.get(
                "epodoc_consulta",
                "",
            )
        ),
        "epo_epodoc_aplicacao": (
            canonical_epodoc
        ),
        "epo_epodoc_diverge": bool(
            silver.get(
                "epodoc_consulta_diverge_canonico",
                False,
            )
        ),
        "epo_data_aplicacao": (
            _canonical_application_date(
                bibliography,
                canonical_epodoc,
            )
        ),
        "epo_family_ids": (
            _json_value(
                family_ids
            )
        ),
        "epo_quantidade_familias": len(
            family_ids
        ),
        "epo_quantidade_exchange_documents": (
            int(
                bibliography.get(
                    "exchange_document_count",
                    0,
                )
                or 0
            )
        ),
        "epo_quantidade_publicacoes": len(
            docdb_publications
        ),
        "epo_primeira_publicacao": (
            publication_dates[0]
            if publication_dates
            else ""
        ),
        "epo_ultima_publicacao": (
            publication_dates[-1]
            if publication_dates
            else ""
        ),
        "epo_kinds_publicacao": (
            _json_value(
                publication_kinds
            )
        ),
        "epo_publicacoes": (
            _json_value(
                docdb_publications
            )
        ),
        "epo_quantidade_titulos": len(
            title_texts
        ),
        "epo_titulos": _json_value(
            titles
        ),
        "epo_possui_resumo": bool(
            abstract_texts
        ),
        "epo_resumos": _json_value(
            abstracts
        ),
        "epo_quantidade_depositantes": (
            _party_count(
                applicants
            )
        ),
        "epo_depositantes_epodoc": (
            _json_value(
                _party_names(
                    applicants,
                    "epodoc",
                )
            )
        ),
        "epo_depositantes_original": (
            _json_value(
                _party_names(
                    applicants,
                    "original",
                )
            )
        ),
        "epo_quantidade_inventores": (
            _party_count(
                inventors
            )
        ),
        "epo_inventores_epodoc": (
            _json_value(
                _party_names(
                    inventors,
                    "epodoc",
                )
            )
        ),
        "epo_inventores_original": (
            _json_value(
                _party_names(
                    inventors,
                    "original",
                )
            )
        ),
        "epo_quantidade_prioridades": len(
            priorities
        ),
        "epo_prioridades": (
            _json_value(
                priorities
            )
        ),
        "epo_classificacoes_ipcr": (
            _json_value(
                _classification_values(
                    classifications,
                    "classification-ipcr",
                )
            )
        ),
        "epo_classificacoes_ipc": (
            _json_value(
                _classification_values(
                    classifications,
                    "classification-ipc",
                )
            )
        ),
        "epo_classificacoes_patent": (
            _json_value(
                _classification_values(
                    classifications,
                    "patent-classification",
                )
            )
        ),
        "epo_quantidade_classificacoes": len(
            classifications
        ),
        "epo_xml_sha256": str(
            silver.get(
                "xml_sha256",
                "",
            )
        ),
    }


def build_epo_gold_snapshot(
    *,
    silver_snapshot: Path | str,
    gold_root: Path | str = "data/gold",
) -> tuple[Path, Path]:
    silver_path = Path(
        silver_snapshot
    )

    input_path = (
        silver_path
        / "pedidos.jsonl"
    )

    if not input_path.exists():
        raise FileNotFoundError(
            "Silver EPO não encontrada: "
            f"{input_path}"
        )

    reference = (
        silver_path.name
    )

    output_dir = (
        Path(gold_root)
        / "epo"
        / "inpi"
        / reference
    )

    output_path = (
        output_dir
        / "patentes_epo_analitico.csv"
    )

    metadata_path = (
        output_dir
        / "metadata.json"
    )

    records = [
        build_epo_gold_record(
            silver
        )
        for silver in _read_jsonl(
            input_path
        )
    ]

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    if records:
        fieldnames = list(
            records[0].keys()
        )

        with output_path.open(
            "w",
            encoding="utf-8",
            newline="",
        ) as file:
            writer = csv.DictWriter(
                file,
                fieldnames=fieldnames,
            )

            writer.writeheader()
            writer.writerows(
                records
            )

    else:
        output_path.write_text(
            "",
            encoding="utf-8",
        )

    matched = [
        record
        for record in records
        if record["epo_status"]
        == "matched"
    ]

    metadata = {
        "source": (
            "European Patent Office OPS "
            "enriquecimento INPI"
        ),
        "layer": "gold",
        "dataset": (
            "patentes_epo_analitico"
        ),
        "snapshot_reference": (
            reference
        ),
        "generated_at": datetime.now(
            UTC
        ).isoformat(),
        "records": len(
            records
        ),
        "matched_records": len(
            matched
        ),
        "with_abstract": sum(
            bool(
                record[
                    "epo_possui_resumo"
                ]
            )
            for record in matched
        ),
        "canonical_epodoc_divergences": (
            sum(
                bool(
                    record[
                        "epo_epodoc_diverge"
                    ]
                )
                for record in matched
            )
        ),
        "input": {
            "file": str(
                input_path
            ),
            "sha256": (
                _sha256_file(
                    input_path
                )
            ),
        },
        "output": {
            "file": str(
                output_path
            ),
            "sha256": (
                _sha256_file(
                    output_path
                )
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

    return (
        output_path,
        metadata_path,
    )