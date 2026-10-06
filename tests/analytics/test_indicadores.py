import csv
import json
from pathlib import Path

from savits_etl.analytics.indicadores import (
    build_dashboard,
    build_inpi_indicators,
    build_social_technology_indicators,
)


def _write_csv(
    path: Path,
    fields: list[str],
    rows: list[dict[str, str]],
) -> None:
    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fields,
        )
        writer.writeheader()
        writer.writerows(rows)


def test_build_inpi_indicators(
    tmp_path: Path,
) -> None:
    path = tmp_path / "inpi.csv"

    fields = [
        "numero_pedido",
        "ano_fonte",
        "ano_deposito",
        "titulo",
        "quantidade_depositantes",
        "quantidade_inventores",
        "quantidade_despachos",
        "quantidade_classificacoes",
        "quantidade_prioridades",
        "possui_pct",
        "primeira_publicacao_rpi",
        "classificacao_ipc",
        "campo_tecnologico",
    ]

    rows = [
        {
            "numero_pedido": "1",
            "ano_fonte": "2024",
            "ano_deposito": "2020",
            "titulo": "Patente A",
            "quantidade_depositantes": "2",
            "quantidade_inventores": "3",
            "quantidade_despachos": "4",
            "quantidade_classificacoes": "2",
            "quantidade_prioridades": "1",
            "possui_pct": "1",
            "primeira_publicacao_rpi": "2021",
            "classificacao_ipc": "A61K 31/00",
            "campo_tecnologico": "14",
        },
        {
            "numero_pedido": "2",
            "ano_fonte": "2024",
            "ano_deposito": "2021",
            "titulo": "Patente B",
            "quantidade_depositantes": "1",
            "quantidade_inventores": "1",
            "quantidade_despachos": "2",
            "quantidade_classificacoes": "1",
            "quantidade_prioridades": "0",
            "possui_pct": "0",
            "primeira_publicacao_rpi": "2022",
            "classificacao_ipc": "H04L 12/00",
            "campo_tecnologico": "4",
        },
        {
            "numero_pedido": "3",
            "ano_fonte": "2024",
            "ano_deposito": "2099",
            "titulo": "Patente C",
            "quantidade_depositantes": "1",
            "quantidade_inventores": "2",
            "quantidade_despachos": "3",
            "quantidade_classificacoes": "1",
            "quantidade_prioridades": "0",
            "possui_pct": "sim",
            "primeira_publicacao_rpi": "2023",
            "classificacao_ipc": "C07D 1/00",
            "campo_tecnologico": "16",
        },
    ]

    _write_csv(
        path,
        fields,
        rows,
    )

    result = build_inpi_indicators(
        path
    )

    assert result["total_pedidos"] == 3
    assert result["com_pct"] == 2

    assert (
        result["ano_limite_fonte"]
        == 2024
    )

    assert (
        result[
            "anos_deposito_fora_cobertura"
        ]
        == 1
    )

    assert result[
        "percentual_multiplos_inventores"
    ] == 66.67

    assert result[
        "percentual_multiplos_depositantes"
    ] == 33.33

    assert result[
        "media_despachos"
    ] == 3.0

    assert result[
        "media_classificacoes"
    ] == 1.33

    assert result[
        "serie_ano_deposito"
    ] == [
        {
            "ano": 2020,
            "quantidade": 1,
        },
        {
            "ano": 2021,
            "quantidade": 1,
        },
    ]

    assert result[
        "top_campos_tecnologicos"
    ][0]["label"] in {
        "14 — Química orgânica fina",
        "16 — Farmacêutica",
        "4 — Comunicação digital",
    }

    labels_ipc = {
        item["label"]
        for item in result[
            "ipc_secoes"
        ]
    }

    assert (
        "A — Necessidades humanas"
        in labels_ipc
    )

    assert (
        "C — Química e metalurgia"
        in labels_ipc
    )

    assert (
        "H — Eletricidade"
        in labels_ipc
    )


def test_build_social_technology_indicators(
    tmp_path: Path,
) -> None:
    path = (
        tmp_path
        / "tecnologias.csv"
    )

    fields = [
        "id_registro",
        "fonte_registro",
        "titulo",
        "organizacao",
        "status_registro",
        "ods_codigos",
        "ods_nomes",
        "publicos",
        "temas",
        "modalidades",
        "descricao",
        "texto_analitico",
        "completude_cadastro",
    ]

    rows = [
        {
            "id_registro": "a",
            "fonte_registro": "feac_casa_hacker",
            "titulo": "Tecnologia A",
            "organizacao": "Organização A",
            "status_registro": "ativa",
            "ods_codigos": "4;10",
            "ods_nomes": (
                "Educação de Qualidade;"
                "Redução das Desigualdades"
            ),
            "publicos": "Jovens|Mulheres",
            "temas": "Educação",
            "modalidades": "Presencial",
            "descricao": "Descrição A",
            "texto_analitico": "Texto A",
            "completude_cadastro": "0.80",
        },
        {
            "id_registro": "b",
            "fonte_registro": "fbb_transforma",
            "titulo": "Tecnologia B",
            "organizacao": "Organização B",
            "status_registro": "premiada",
            "ods_codigos": "4",
            "ods_nomes": (
                "Educação de Qualidade"
            ),
            "publicos": "Jovens",
            "temas": "Saúde",
            "modalidades": "Híbrida",
            "descricao": "Descrição B",
            "texto_analitico": "Texto B",
            "completude_cadastro": "100",
        },
    ]

    _write_csv(
        path,
        fields,
        rows,
    )

    result = (
        build_social_technology_indicators(
            path
        )
    )

    assert (
        result[
            "total_tecnologias_sociais"
        ]
        == 2
    )

    assert result["com_ods"] == 2
    assert result["com_publicos"] == 2

    assert (
        result[
            "percentual_com_organizacao"
        ]
        == 100.0
    )

    assert (
        result[
            "percentual_com_texto_analitico"
        ]
        == 100.0
    )

    assert (
        result[
            "media_completude_cadastro"
        ]
        == 90.0
    )

    assert result[
        "top_ods"
    ][0] == {
        "label": (
            "Educação de Qualidade"
        ),
        "quantidade": 2,
    }


def test_build_dashboard(
    tmp_path: Path,
) -> None:
    inpi = tmp_path / "inpi.csv"

    technologies = (
        tmp_path
        / "tecnologias.csv"
    )

    _write_csv(
        inpi,
        [
            "numero_pedido",
            "ano_fonte",
            "ano_deposito",
            "titulo",
            "quantidade_depositantes",
            "quantidade_inventores",
            "quantidade_despachos",
            "quantidade_classificacoes",
            "quantidade_prioridades",
            "possui_pct",
            "primeira_publicacao_rpi",
            "classificacao_ipc",
            "campo_tecnologico",
        ],
        [
            {
                "numero_pedido": "1",
                "ano_fonte": "2024",
                "ano_deposito": "2020",
                "titulo": "Patente",
                "quantidade_depositantes": "1",
                "quantidade_inventores": "2",
                "quantidade_despachos": "3",
                "quantidade_classificacoes": "1",
                "quantidade_prioridades": "0",
                "possui_pct": "1",
                "primeira_publicacao_rpi": "2021",
                "classificacao_ipc": "A61K",
                "campo_tecnologico": "13",
            }
        ],
    )

    _write_csv(
        technologies,
        [
            "id_registro",
            "fonte_registro",
            "titulo",
            "organizacao",
            "status_registro",
            "ods_codigos",
            "ods_nomes",
            "publicos",
            "temas",
            "modalidades",
            "descricao",
            "texto_analitico",
            "completude_cadastro",
        ],
        [
            {
                "id_registro": "a",
                "fonte_registro": "feac_casa_hacker",
                "titulo": "TS",
                "organizacao": "Org",
                "status_registro": "ativa",
                "ods_codigos": "4",
                "ods_nomes": (
                    "Educação de Qualidade"
                ),
                "publicos": "Jovens",
                "temas": "Educação",
                "modalidades": "Presencial",
                "descricao": "Descrição",
                "texto_analitico": "Texto",
                "completude_cadastro": "100",
            }
        ],
    )

    json_path, html_path = (
        build_dashboard(
            inpi_path=inpi,
            social_technologies_path=(
                technologies
            ),
            output_directory=(
                tmp_path / "reports"
            ),
        )
    )

    assert json_path.exists()
    assert html_path.exists()

    with json_path.open(
        encoding="utf-8",
    ) as file:
        indicators = json.load(
            file
        )

    assert (
        indicators[
            "patentes"
        ]["total_pedidos"]
        == 1
    )

    assert (
        indicators[
            "tecnologias_sociais"
        ][
            "total_tecnologias_sociais"
        ]
        == 1
    )

    dashboard = (
        html_path.read_text(
            encoding="utf-8"
        )
    )

    dashboard_normalized = (
        dashboard.casefold()
    )

    assert (
        "patentes e tecnologias sociais"
        in dashboard_normalized
    )

    assert (
        "pedidos por ano de depósito"
        in dashboard_normalized
    )

    assert (
        "principais campos tecnológicos"
        in dashboard_normalized
    )

    assert (
        "principais grupos ipc"
        in dashboard_normalized
    )

    assert (
        "registros por fonte"
        in dashboard_normalized
    )

    assert (
        "ods mais frequentes"
        in dashboard_normalized
    )

    assert (
        "assets/logo.jpg"
        in dashboard
    )

    assert (
        "Nota metodológica"
        not in dashboard
    )

    assert (
        "Gerado em"
        not in dashboard
    )