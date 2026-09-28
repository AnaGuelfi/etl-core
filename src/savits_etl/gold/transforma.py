from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path

GOLD_FIELDS = (
    "id_tecnologia",
    "fonte_registro",
    "snapshot_reference",
    "slug",
    "titulo",
    "instituicao",
    "instituicao_url",
    "status_premio",
    "ano_premio",
    "qtd_temas",
    "temas",
    "qtd_ods",
    "ods",
    "qtd_publicos",
    "publicos",
    "resumo",
    "objetivo",
    "objetivos_especificos",
    "problema_solucionado",
    "descricao",
    "recursos_necessarios",
    "resultados_alcancados",
    "source_url",
    "completude_cadastro",
)


COMPLETENESS_FIELDS = (
    "titulo",
    "instituicao",
    "status_premio",
    "ano_premio",
    "resumo",
    "problema_solucionado",
    "descricao",
    "recursos_necessarios",
    "resultados_alcancados",
)


def carregar_csv(
    path: Path,
) -> list[dict[str, str]]:
    """Carrega um CSV UTF-8."""

    with path.open(
        encoding="utf-8",
        newline="",
    ) as file:
        return list(
            csv.DictReader(file)
        )


def agrupar_relacoes(
    rows: list[dict[str, str]],
    value_field: str,
) -> dict[str, list[str]]:
    """Agrupa relações multivaloradas por slug."""

    grouped: dict[str, list[str]] = {}
    seen: dict[str, set[str]] = {}

    for row in rows:
        slug = row.get(
            "slug",
            "",
        ).strip()

        value = row.get(
            value_field,
            "",
        ).strip()

        if not slug or not value:
            continue

        if slug not in grouped:
            grouped[slug] = []
            seen[slug] = set()

        if value in seen[slug]:
            continue

        seen[slug].add(
            value
        )

        grouped[slug].append(
            value
        )

    return grouped


def calcular_completude(
    row: dict[str, str],
) -> str:
    """Calcula completude dos campos principais."""

    filled = sum(
        bool(
            row.get(
                field,
                "",
            ).strip()
        )
        for field in COMPLETENESS_FIELDS
    )

    completeness = (
        filled
        / len(COMPLETENESS_FIELDS)
        * 100
    )

    return f"{completeness:.2f}"


def construir_gold(
    rows: list[dict[str, str]],
    themes: list[dict[str, str]],
    ods: list[dict[str, str]],
    publics: list[dict[str, str]],
    reference: int,
) -> list[dict[str, str]]:
    """Constrói a visão analítica do Transforma!."""

    themes_by_slug = agrupar_relacoes(
        themes,
        "tema",
    )

    ods_by_slug = agrupar_relacoes(
        ods,
        "ods",
    )

    publics_by_slug = agrupar_relacoes(
        publics,
        "publico",
    )

    gold: list[
        dict[str, str]
    ] = []

    for row in rows:
        slug = row.get(
            "slug",
            "",
        ).strip()

        row_themes = themes_by_slug.get(
            slug,
            [],
        )

        row_ods = ods_by_slug.get(
            slug,
            [],
        )

        row_publics = publics_by_slug.get(
            slug,
            [],
        )

        record = {
            "id_tecnologia": (
                f"fbb_transforma:{slug}"
            ),
            "fonte_registro": (
                "fbb_transforma"
            ),
            "snapshot_reference": str(
                reference
            ),
            "slug": slug,
            "titulo": row.get(
                "titulo",
                "",
            ),
            "instituicao": row.get(
                "instituicao",
                "",
            ),
            "instituicao_url": row.get(
                "instituicao_url",
                "",
            ),
            "status_premio": row.get(
                "status_premio",
                "",
            ),
            "ano_premio": row.get(
                "ano_premio",
                "",
            ),
            "qtd_temas": str(
                len(row_themes)
            ),
            "temas": "; ".join(
                row_themes
            ),
            "qtd_ods": str(
                len(row_ods)
            ),
            "ods": "; ".join(
                row_ods
            ),
            "qtd_publicos": str(
                len(row_publics)
            ),
            "publicos": "; ".join(
                row_publics
            ),
            "resumo": row.get(
                "resumo",
                "",
            ),
            "objetivo": row.get(
                "objetivo",
                "",
            ),
            "objetivos_especificos": (
                row.get(
                    "objetivos_especificos",
                    "",
                )
            ),
            "problema_solucionado": (
                row.get(
                    "problema_solucionado",
                    "",
                )
            ),
            "descricao": row.get(
                "descricao",
                "",
            ),
            "recursos_necessarios": (
                row.get(
                    "recursos_necessarios",
                    "",
                )
            ),
            "resultados_alcancados": (
                row.get(
                    "resultados_alcancados",
                    "",
                )
            ),
            "source_url": row.get(
                "source_url",
                "",
            ),
        }

        record[
            "completude_cadastro"
        ] = calcular_completude(
            record
        )

        gold.append(
            record
        )

    gold.sort(
        key=lambda row: row[
            "id_tecnologia"
        ]
    )

    return gold


def _validar_relacoes(
    slugs: set[str],
    rows: list[dict[str, str]],
    dataset: str,
) -> None:
    """Valida se relações apontam para tecnologias existentes."""

    relation_slugs = {
        row.get(
            "slug",
            "",
        ).strip()
        for row in rows
        if row.get(
            "slug",
            "",
        ).strip()
    }

    missing = (
        relation_slugs
        - slugs
    )

    if missing:
        raise ValueError(
            "Foram encontradas relações "
            f"órfãs em {dataset}: "
            f"{len(missing)} slugs."
        )


def gerar_gold_transforma(
    reference: int = 20260927,
    silver_root: Path | str = "data/silver",
    gold_root: Path | str = "data/gold",
) -> tuple[Path, Path]:
    """Gera o dataset analítico do Transforma!."""

    silver_dir = (
        Path(silver_root)
        / "fbb"
        / "transforma"
        / str(reference)
    )

    technologies_path = (
        silver_dir
        / "tecnologias.csv"
    )

    themes_path = (
        silver_dir
        / "tecnologias_temas.csv"
    )

    ods_path = (
        silver_dir
        / "tecnologias_ods.csv"
    )

    publics_path = (
        silver_dir
        / "tecnologias_publicos.csv"
    )

    silver_paths = (
        technologies_path,
        themes_path,
        ods_path,
        publics_path,
    )

    for path in silver_paths:
        if not path.exists():
            raise FileNotFoundError(
                "Dataset Silver não "
                f"encontrado: {path}"
            )

    rows = carregar_csv(
        technologies_path
    )

    themes = carregar_csv(
        themes_path
    )

    ods = carregar_csv(
        ods_path
    )

    publics = carregar_csv(
        publics_path
    )

    if not rows:
        raise ValueError(
            "A Silver do Transforma! "
            "não possui registros."
        )

    slugs = [
        row.get(
            "slug",
            "",
        ).strip()
        for row in rows
    ]

    if any(
        not slug
        for slug in slugs
    ):
        raise ValueError(
            "Foram encontrados registros "
            "sem slug na Silver."
        )

    if len(slugs) != len(set(slugs)):
        raise ValueError(
            "Foram encontrados slugs "
            "duplicados na Silver."
        )

    slug_set = set(
        slugs
    )

    _validar_relacoes(
        slug_set,
        themes,
        "temas",
    )

    _validar_relacoes(
        slug_set,
        ods,
        "ODS",
    )

    _validar_relacoes(
        slug_set,
        publics,
        "públicos",
    )

    gold = construir_gold(
        rows=rows,
        themes=themes,
        ods=ods,
        publics=publics,
        reference=reference,
    )

    ids = [
        row["id_tecnologia"]
        for row in gold
    ]

    if len(ids) != len(set(ids)):
        raise ValueError(
            "Foram encontrados IDs "
            "duplicados na Gold."
        )

    output_dir = (
        Path(gold_root)
        / "fbb"
        / "transforma"
        / "consolidado"
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    dataset_path = (
        output_dir
        / "tecnologias_sociais_analitico.csv"
    )

    with dataset_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=GOLD_FIELDS,
        )

        writer.writeheader()
        writer.writerows(
            gold
        )

    completeness_values = [
        float(
            row[
                "completude_cadastro"
            ]
        )
        for row in gold
    ]

    metadata = {
        "source": (
            "Fundação Banco do Brasil "
            "- Transforma!"
        ),
        "dataset": (
            "tecnologias_sociais"
        ),
        "layer": "gold",
        "snapshot_reference": (
            reference
        ),
        "generated_at": (
            datetime.now(UTC).isoformat()
        ),
        "file": dataset_path.name,
        "format": "csv",
        "encoding": "utf-8",
        "records": len(gold),
        "unique_ids": len(
            set(ids)
        ),
        "unique_slugs": len(
            slug_set
        ),
        "with_themes": sum(
            int(
                row["qtd_temas"]
            )
            > 0
            for row in gold
        ),
        "with_ods": sum(
            int(
                row["qtd_ods"]
            )
            > 0
            for row in gold
        ),
        "with_publics": sum(
            int(
                row["qtd_publicos"]
            )
            > 0
            for row in gold
        ),
        "missing_title": sum(
            not row["titulo"]
            for row in gold
        ),
        "missing_institution": sum(
            not row["instituicao"]
            for row in gold
        ),
        "average_completeness": round(
            sum(
                completeness_values
            )
            / len(
                completeness_values
            ),
            2,
        ),
        "completeness_fields": list(
            COMPLETENESS_FIELDS
        ),
        "source_silver_files": [
            path.name
            for path in silver_paths
        ],
    }

    metadata_path = (
        output_dir
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

    return (
        dataset_path,
        metadata_path,
    )