from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path

from savits_etl.sources.feac import FEACSource


def normalizar_nome_coluna(name: str) -> str:
    """Padroniza nomes das colunas da FEAC."""

    name = name.strip()

    if name == "ID":
        return "id_tecnologia"

    return name.lower()


def normalizar_linha(
    row: dict[str, str],
) -> dict[str, str]:
    """Padroniza nomes de campos e espaços."""

    return {
        normalizar_nome_coluna(key): value.strip()
        for key, value in row.items()
    }


def separar_valores(value: str) -> list[str]:
    """Separa campos multivalorados delimitados por ponto e vírgula."""

    return [
        item.strip()
        for item in value.split(";")
        if item.strip()
    ]


def salvar_csv(
    rows: list[dict[str, str]],
    path: Path,
    fieldnames: list[str],
) -> None:
    """Salva registros em CSV UTF-8."""

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(rows)


def gerar_silver_feac(
    reference: int = 2024,
    source: FEACSource | None = None,
    silver_root: Path | str = "data/silver",
) -> tuple[Path, Path, Path, Path, Path]:
    """Gera os datasets Silver da FEAC."""

    if source is None:
        source = FEACSource()

    rows = [
        normalizar_linha(row)
        for row in source.read(reference)
    ]

    if not rows:
        raise ValueError(
            "A fonte FEAC não possui registros."
        )

    ids = [
        row["id_tecnologia"]
        for row in rows
    ]

    if any(not identifier for identifier in ids):
        raise ValueError(
            "Foram encontrados registros sem ID."
        )

    if len(ids) != len(set(ids)):
        raise ValueError(
            "Foram encontrados IDs duplicados."
        )

    output_dir = (
        Path(silver_root)
        / "feac"
        / "tecnologias_sociais"
        / str(reference)
    )

    tecnologias_path = (
        output_dir
        / "tecnologias.csv"
    )

    ods_path = (
        output_dir
        / "tecnologias_ods.csv"
    )

    dimensoes_path = (
        output_dir
        / "tecnologias_ods_dimensoes.csv"
    )

    modalidades_path = (
        output_dir
        / "tecnologias_modalidades.csv"
    )

    metadata_path = (
        output_dir
        / "metadata.json"
    )

    salvar_csv(
        rows,
        tecnologias_path,
        list(rows[0]),
    )

    ods_rows = []
    dimensoes_rows = []
    modalidades_rows = []

    for row in rows:
        identifier = row["id_tecnologia"]

        for ods in separar_valores(
            row.get("ods_lista", "")
        ):
            ods_rows.append(
                {
                    "id_tecnologia": identifier,
                    "ods": ods,
                }
            )

        for dimension in separar_valores(
            row.get("ods_dimensoes", "")
        ):
            dimensoes_rows.append(
                {
                    "id_tecnologia": identifier,
                    "dimensao_ods": dimension,
                }
            )

        for modalidade in separar_valores(
            row.get("modalidade_todas", "")
        ):
            modalidades_rows.append(
                {
                    "id_tecnologia": identifier,
                    "modalidade": modalidade,
                }
            )

    salvar_csv(
        ods_rows,
        ods_path,
        [
            "id_tecnologia",
            "ods",
        ],
    )

    salvar_csv(
        dimensoes_rows,
        dimensoes_path,
        [
            "id_tecnologia",
            "dimensao_ods",
        ],
    )

    salvar_csv(
        modalidades_rows,
        modalidades_path,
        [
            "id_tecnologia",
            "modalidade",
        ],
    )

    metadata = {
        "source": "FEAC / Casa Hacker",
        "dataset": "tecnologias_sociais",
        "layer": "silver",
        "reference_year": reference,
        "generated_at": datetime.now(UTC).isoformat(),
        "format": "csv",
        "encoding": "utf-8",
        "datasets": {
            "tecnologias": {
                "file": tecnologias_path.name,
                "records": len(rows),
                "unique_ids": len(set(ids)),
                "missing_nome_tecnologia": sum(
                    not row.get(
                        "nome_tecnologia_social",
                        "",
                    )
                    for row in rows
                ),
            },
            "ods": {
                "file": ods_path.name,
                "records": len(ods_rows),
            },
            "ods_dimensoes": {
                "file": dimensoes_path.name,
                "records": len(dimensoes_rows),
            },
            "modalidades": {
                "file": modalidades_path.name,
                "records": len(modalidades_rows),
            },
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
        tecnologias_path,
        ods_path,
        dimensoes_path,
        modalidades_path,
        metadata_path,
    )