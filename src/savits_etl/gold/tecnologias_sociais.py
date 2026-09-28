from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path

ODS_NAMES = {
    "1": "Erradicação da Pobreza",
    "2": "Fome Zero e Agricultura Sustentável",
    "3": "Saúde e Bem Estar",
    "4": "Educação de Qualidade",
    "5": "Igualdade de Gênero",
    "6": "Água Potável e Saneamento",
    "7": "Energia Acessível e Limpa",
    "8": "Trabalho Decente e Crescimento Econômico",
    "9": "Indústria, Inovação e Infraestrutura",
    "10": "Redução das Desigualdades",
    "11": "Cidades e Comunidades Sustentáveis",
    "12": "Consumo e Produção Responsáveis",
    "13": "Ação Contra a Mudança Global do Clima",
    "14": "Vida na Água",
    "15": "Vida Terrestre",
    "16": "Paz, Justiça e Instituições Eficazes",
    "17": "Parcerias e Meios de Implementação",
}

ODS_CODES = {
    name: code
    for code, name in ODS_NAMES.items()
}


GOLD_FIELDS = (
    "id_registro",
    "fonte_registro",
    "id_fonte",
    "titulo",
    "organizacao",
    "referencia_fonte",
    "tipo_referencia",
    "ano_inicio",
    "ano_premio",
    "tipo_status",
    "status_registro",
    "qtd_ods",
    "ods_codigos",
    "ods_nomes",
    "qtd_publicos",
    "publicos",
    "temas",
    "modalidades",
    "descricao",
    "texto_analitico",
    "source_url",
    "completude_cadastro",
)


TRANSFORMA_TEXT_FIELDS = (
    ("Resumo", "resumo"),
    ("Objetivo", "objetivo"),
    (
        "Problema solucionado",
        "problema_solucionado",
    ),
    ("Descrição", "descricao"),
    (
        "Resultados alcançados",
        "resultados_alcancados",
    ),
)


FEAC_FALLBACK_FIELDS = (
    (
        "Categoria",
        "categoria_tecnologia",
    ),
    (
        "Modalidades",
        "modalidade_todas",
    ),
    (
        "Público",
        "publico_final",
    ),
    (
        "Palavras-chave",
        "palavras_chave_tec",
    ),
)


MISSING_VALUES = {
    "",
    "não informado",
    "não identificada",
    "não identificado",
}


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


def separar_valores(
    value: str,
) -> list[str]:
    """Separa valores delimitados por ponto e vírgula."""

    result: list[str] = []
    seen: set[str] = set()

    for item in value.split(";"):
        item = item.strip()

        if not item:
            continue

        if item in seen:
            continue

        seen.add(item)
        result.append(item)

    return result


def normalizar_ods_feac(
    value: str,
) -> tuple[list[str], list[str]]:
    """Converte códigos ODS da FEAC em códigos e nomes."""

    codes = separar_valores(
        value
    )

    names = [
        ODS_NAMES[code]
        for code in codes
        if code in ODS_NAMES
    ]

    return codes, names


def normalizar_ods_transforma(
    value: str,
) -> tuple[list[str], list[str]]:
    """Converte nomes ODS do Transforma! em códigos e nomes."""

    names = separar_valores(
        value
    )

    codes = [
        ODS_CODES[name]
        for name in names
        if name in ODS_CODES
    ]

    return codes, names


def _valor_informativo(
    value: str,
) -> bool:
    """Indica se o valor contém informação útil."""

    return (
        value.strip().casefold()
        not in MISSING_VALUES
    )


def construir_texto_feac(
    row: dict[str, str],
) -> str:
    """
    Monta texto analítico da FEAC.

    Quando existe descrição original, ela é preservada.
    Caso contrário, usa apenas campos estruturados reais
    disponíveis na fonte.
    """

    description = row.get(
        "desc_tecnologia",
        "",
    ).strip()

    if description:
        return description

    parts: list[str] = []

    for label, field in FEAC_FALLBACK_FIELDS:
        value = row.get(
            field,
            "",
        ).strip()

        if not _valor_informativo(
            value
        ):
            continue

        parts.append(
            f"{label}: {value}"
        )

    return " ".join(
        parts
    )


def construir_texto_transforma(
    row: dict[str, str],
) -> str:
    """Monta um texto analítico com campos textuais do Transforma!."""

    parts: list[str] = []

    for label, field in TRANSFORMA_TEXT_FIELDS:
        value = row.get(
            field,
            "",
        ).strip()

        if not value:
            continue

        parts.append(
            f"{label}: {value}"
        )

    return " ".join(
        parts
    )


def construir_registro_feac(
    row: dict[str, str],
) -> dict[str, str]:
    """Converte uma tecnologia FEAC para o contrato comum."""

    id_fonte = row.get(
        "id_tecnologia",
        "",
    ).strip()

    codes, names = normalizar_ods_feac(
        row.get(
            "ods_lista",
            "",
        )
    )

    public_value = row.get(
        "publico_final",
        "",
    ).strip()

    if not _valor_informativo(
        public_value
    ):
        publics: list[str] = []
    else:
        publics = [
            public_value
        ]

    description = row.get(
        "desc_tecnologia",
        "",
    ).strip()

    return {
        "id_registro": (
            f"feac_casa_hacker:{id_fonte}"
        ),
        "fonte_registro": (
            "feac_casa_hacker"
        ),
        "id_fonte": id_fonte,
        "titulo": row.get(
            "nome_tecnologia_social",
            "",
        ).strip(),
        "organizacao": row.get(
            "organizacao",
            "",
        ).strip(),
        "referencia_fonte": row.get(
            "ano_referencia",
            "",
        ).strip(),
        "tipo_referencia": "ano",
        "ano_inicio": row.get(
            "ano_inicio",
            "",
        ).strip(),
        "ano_premio": "",
        "tipo_status": "atividade",
        "status_registro": row.get(
            "status_ativa",
            "",
        ).strip(),
        "qtd_ods": str(
            len(codes)
        ),
        "ods_codigos": "; ".join(
            codes
        ),
        "ods_nomes": "; ".join(
            names
        ),
        "qtd_publicos": str(
            len(publics)
        ),
        "publicos": "; ".join(
            publics
        ),
        "temas": "",
        "modalidades": row.get(
            "modalidade_todas",
            "",
        ).strip(),
        "descricao": description,
        "texto_analitico": (
            construir_texto_feac(
                row
            )
        ),
        "source_url": "",
        "completude_cadastro": row.get(
            "completude_cadastro",
            "",
        ).strip(),
    }


def construir_registro_transforma(
    row: dict[str, str],
) -> dict[str, str]:
    """Converte uma tecnologia Transforma! para o contrato comum."""

    slug = row.get(
        "slug",
        "",
    ).strip()

    codes, names = normalizar_ods_transforma(
        row.get(
            "ods",
            "",
        )
    )

    publics = separar_valores(
        row.get(
            "publicos",
            "",
        )
    )

    return {
        "id_registro": (
            f"fbb_transforma:{slug}"
        ),
        "fonte_registro": (
            "fbb_transforma"
        ),
        "id_fonte": slug,
        "titulo": row.get(
            "titulo",
            "",
        ).strip(),
        "organizacao": row.get(
            "instituicao",
            "",
        ).strip(),
        "referencia_fonte": row.get(
            "snapshot_reference",
            "",
        ).strip(),
        "tipo_referencia": (
            "data_snapshot"
        ),
        "ano_inicio": "",
        "ano_premio": row.get(
            "ano_premio",
            "",
        ).strip(),
        "tipo_status": "premiacao",
        "status_registro": row.get(
            "status_premio",
            "",
        ).strip(),
        "qtd_ods": str(
            len(names)
        ),
        "ods_codigos": "; ".join(
            codes
        ),
        "ods_nomes": "; ".join(
            names
        ),
        "qtd_publicos": str(
            len(publics)
        ),
        "publicos": "; ".join(
            publics
        ),
        "temas": row.get(
            "temas",
            "",
        ).strip(),
        "modalidades": "",
        "descricao": row.get(
            "descricao",
            "",
        ).strip(),
        "texto_analitico": (
            construir_texto_transforma(
                row
            )
        ),
        "source_url": row.get(
            "source_url",
            "",
        ).strip(),
        "completude_cadastro": row.get(
            "completude_cadastro",
            "",
        ).strip(),
    }


def construir_gold(
    feac_rows: list[dict[str, str]],
    transforma_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Constrói a Gold consolidada de tecnologias sociais."""

    gold = [
        construir_registro_feac(
            row
        )
        for row in feac_rows
    ]

    gold.extend(
        construir_registro_transforma(
            row
        )
        for row in transforma_rows
    )

    ids = [
        row["id_registro"]
        for row in gold
    ]

    if any(
        not identifier
        for identifier in ids
    ):
        raise ValueError(
            "Foram encontrados registros "
            "sem identificador."
        )

    if len(ids) != len(set(ids)):
        raise ValueError(
            "Foram encontrados IDs "
            "duplicados na Gold consolidada."
        )

    gold.sort(
        key=lambda row: (
            row["fonte_registro"],
            row["id_fonte"],
        )
    )

    return gold


def gerar_gold_tecnologias_sociais(
    feac_root: Path | str = "data/gold",
    transforma_root: Path | str = "data/gold",
    gold_root: Path | str = "data/gold",
) -> tuple[Path, Path]:
    """Gera a Gold consolidada de tecnologias sociais."""

    feac_path = (
        Path(feac_root)
        / "feac"
        / "tecnologias_sociais"
        / "consolidado"
        / "tecnologias_sociais_analitico.csv"
    )

    transforma_path = (
        Path(transforma_root)
        / "fbb"
        / "transforma"
        / "consolidado"
        / "tecnologias_sociais_analitico.csv"
    )

    source_paths = (
        feac_path,
        transforma_path,
    )

    for path in source_paths:
        if not path.exists():
            raise FileNotFoundError(
                "Dataset Gold de origem "
                f"não encontrado: {path}"
            )

    feac_rows = carregar_csv(
        feac_path
    )

    transforma_rows = carregar_csv(
        transforma_path
    )

    if not feac_rows:
        raise ValueError(
            "A Gold FEAC não possui registros."
        )

    if not transforma_rows:
        raise ValueError(
            "A Gold Transforma! não possui registros."
        )

    gold = construir_gold(
        feac_rows=feac_rows,
        transforma_rows=transforma_rows,
    )

    output_dir = (
        Path(gold_root)
        / "tecnologias_sociais"
        / "consolidado"
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    dataset_path = (
        output_dir
        / "tecnologias_sociais.csv"
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

    ids = {
        row["id_registro"]
        for row in gold
    }

    metadata = {
        "dataset": "tecnologias_sociais",
        "layer": "gold",
        "scope": "multi_source",
        "generated_at": (
            datetime.now(UTC).isoformat()
        ),
        "file": dataset_path.name,
        "format": "csv",
        "encoding": "utf-8",
        "records": len(gold),
        "unique_ids": len(ids),
        "sources": {
            "feac_casa_hacker": {
                "file": str(
                    feac_path
                ),
                "records": len(
                    feac_rows
                ),
            },
            "fbb_transforma": {
                "file": str(
                    transforma_path
                ),
                "records": len(
                    transforma_rows
                ),
            },
        },
        "quality": {
            "missing_title": sum(
                not row["titulo"]
                for row in gold
            ),
            "missing_organization": sum(
                not row["organizacao"]
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
            "with_description": sum(
                bool(
                    row["descricao"]
                )
                for row in gold
            ),
            "with_analytical_text": sum(
                bool(
                    row["texto_analitico"]
                )
                for row in gold
            ),
        },
        "semantic_notes": {
            "status_registro": (
                "Preserva o significado da fonte. "
                "Na FEAC representa atividade; "
                "no Transforma! representa situação "
                "na premiação."
            ),
            "referencia_fonte": (
                "Na FEAC representa ano de referência; "
                "no Transforma! representa a data "
                "do snapshot YYYYMMDD."
            ),
            "temas_modalidades": (
                "Temas do Transforma! e modalidades "
                "da FEAC permanecem em campos separados."
            ),
            "texto_analitico": (
                "Na FEAC, quando desc_tecnologia está "
                "ausente, usa fallback apenas com campos "
                "estruturados disponíveis na fonte."
            ),
            "completude_cadastro": (
                "Indicador preservado da Gold de origem. "
                "As metodologias das fontes são diferentes "
                "e os valores não devem ser comparados "
                "diretamente."
            ),
        },
        "ods_mapping": ODS_NAMES,
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