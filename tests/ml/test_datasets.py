import csv
import json
from pathlib import Path

from savits_etl.ml.datasets import (
    build_ml_datasets,
    build_patent_ml_dataset,
    build_social_technology_ml_dataset,
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


def test_build_patent_ml_dataset(
    tmp_path: Path,
) -> None:
    source = tmp_path / "inpi.csv"
    output = tmp_path / "patentes_ml.csv"

    fields = [
        "numero_pedido",
        "ano_fonte",
        "ano_deposito",
        "quantidade_depositantes",
        "quantidade_inventores",
        "quantidade_despachos",
        "quantidade_classificacoes",
        "quantidade_prioridades",
        "possui_pct",
        "classificacao_ipc",
        "campo_tecnologico",
    ]

    rows = [
        {
            "numero_pedido": "1",
            "ano_fonte": "2024",
            "ano_deposito": "2020",
            "quantidade_depositantes": "2",
            "quantidade_inventores": "3",
            "quantidade_despachos": "4",
            "quantidade_classificacoes": "2",
            "quantidade_prioridades": "1",
            "possui_pct": "sim",
            "classificacao_ipc": "A61K 31/00",
            "campo_tecnologico": "14",
        },
        {
            "numero_pedido": "2",
            "ano_fonte": "2024",
            "ano_deposito": "2099",
            "quantidade_depositantes": "1",
            "quantidade_inventores": "1",
            "quantidade_despachos": "2",
            "quantidade_classificacoes": "1",
            "quantidade_prioridades": "0",
            "possui_pct": "0",
            "classificacao_ipc": "H04L 12/00",
            "campo_tecnologico": "4",
        },
    ]

    _write_csv(
        source,
        fields,
        rows,
    )

    count = (
        build_patent_ml_dataset(
            source,
            output,
        )
    )

    assert count == 2

    with output.open(
        encoding="utf-8",
        newline="",
    ) as file:
        result = list(
            csv.DictReader(
                file
            )
        )

    assert len(result) == 2

    first = result[0]

    assert (
        first["ano_deposito"]
        == "2020"
    )

    assert (
        first["ano_deposito_valido"]
        == "1"
    )

    assert (
        first["possui_pct"]
        == "1"
    )

    assert (
        first["ipc_subclasse"]
        == "A61K"
    )

    assert (
        first["ipc_secao"]
        == "A"
    )

    assert (
        first["ipc_secao_nome"]
        == "Necessidades humanas"
    )

    assert (
        first[
            "campo_tecnologico_principal"
        ]
        == "14"
    )

    assert (
        first[
            "campo_tecnologico_nome"
        ]
        == "Química orgânica fina"
    )

    second = result[1]

    assert (
        second["ano_deposito"]
        == ""
    )

    assert (
        second["ano_deposito_valido"]
        == "0"
    )


def test_build_social_technology_ml_dataset(
    tmp_path: Path,
) -> None:
    source = (
        tmp_path
        / "tecnologias.csv"
    )

    structured = (
        tmp_path
        / "tecnologias_ml.csv"
    )

    texts = (
        tmp_path
        / "textos.jsonl"
    )

    fields = [
        "id_registro",
        "fonte_registro",
        "titulo",
        "organizacao",
        "ano_inicio",
        "ano_premio",
        "tipo_status",
        "status_registro",
        "qtd_ods",
        "ods_codigos",
        "qtd_publicos",
        "publicos",
        "temas",
        "modalidades",
        "descricao",
        "texto_analitico",
        "completude_cadastro",
    ]

    rows = [
        {
            "id_registro": "ts-1",
            "fonte_registro": "fbb_transforma",
            "titulo": "Tecnologia A",
            "organizacao": "Organização A",
            "ano_inicio": "2018",
            "ano_premio": "2022",
            "tipo_status": "premiação",
            "status_registro": "premiada",
            "qtd_ods": "2",
            "ods_codigos": "4;10",
            "qtd_publicos": "2",
            "publicos": "Jovens;Mulheres",
            "temas": "Educação;Inclusão",
            "modalidades": (
                "Presencial;Digital"
            ),
            "descricao": "Descrição",
            "texto_analitico": (
                "Texto para análise."
            ),
            "completude_cadastro": "0.8",
        }
    ]

    _write_csv(
        source,
        fields,
        rows,
    )

    (
        structured_count,
        text_count,
    ) = (
        build_social_technology_ml_dataset(
            source,
            structured,
            texts,
        )
    )

    assert structured_count == 1
    assert text_count == 1

    with structured.open(
        encoding="utf-8",
        newline="",
    ) as file:
        result = next(
            csv.DictReader(
                file
            )
        )

    assert result["qtd_temas"] == "2"

    assert (
        result["qtd_modalidades"]
        == "2"
    )

    assert (
        result["completude_cadastro"]
        == "80.0"
    )

    assert (
        result["tem_descricao"]
        == "1"
    )

    assert (
        result["tem_texto_analitico"]
        == "1"
    )

    text_lines = (
        texts.read_text(
            encoding="utf-8"
        )
        .splitlines()
    )

    assert len(text_lines) == 1

    text_record = json.loads(
        text_lines[0]
    )

    assert (
        text_record["id_registro"]
        == "ts-1"
    )

    assert (
        text_record["titulo"]
        == "Tecnologia A"
    )

    assert (
        text_record[
            "texto_analitico"
        ]
        == "Texto para análise."
    )


def test_build_ml_datasets(
    tmp_path: Path,
) -> None:
    inpi = tmp_path / "inpi.csv"

    social = (
        tmp_path
        / "social.csv"
    )

    _write_csv(
        inpi,
        [
            "numero_pedido",
            "ano_fonte",
            "ano_deposito",
            "quantidade_depositantes",
            "quantidade_inventores",
            "quantidade_despachos",
            "quantidade_classificacoes",
            "quantidade_prioridades",
            "possui_pct",
            "classificacao_ipc",
            "campo_tecnologico",
        ],
        [
            {
                "numero_pedido": "1",
                "ano_fonte": "2024",
                "ano_deposito": "2020",
                "quantidade_depositantes": "1",
                "quantidade_inventores": "2",
                "quantidade_despachos": "3",
                "quantidade_classificacoes": "1",
                "quantidade_prioridades": "0",
                "possui_pct": "1",
                "classificacao_ipc": "A61K",
                "campo_tecnologico": "13",
            }
        ],
    )

    _write_csv(
        social,
        [
            "id_registro",
            "fonte_registro",
            "titulo",
            "organizacao",
            "ano_inicio",
            "ano_premio",
            "tipo_status",
            "status_registro",
            "qtd_ods",
            "ods_codigos",
            "qtd_publicos",
            "publicos",
            "temas",
            "modalidades",
            "descricao",
            "texto_analitico",
            "completude_cadastro",
        ],
        [
            {
                "id_registro": "ts-1",
                "fonte_registro": "feac_casa_hacker",
                "titulo": "TS",
                "organizacao": "Org",
                "ano_inicio": "2020",
                "ano_premio": "",
                "tipo_status": "cadastro",
                "status_registro": "ativa",
                "qtd_ods": "1",
                "ods_codigos": "4",
                "qtd_publicos": "1",
                "publicos": "Jovens",
                "temas": "Educação",
                "modalidades": "Presencial",
                "descricao": "Descrição",
                "texto_analitico": "Texto",
                "completude_cadastro": "100",
            }
        ],
    )

    output = tmp_path / "ml"

    paths = build_ml_datasets(
        inpi_path=inpi,
        social_technologies_path=(
            social
        ),
        output_directory=output,
    )

    for path in paths.values():
        assert path.exists()

    metadata = json.loads(
        paths["metadata"].read_text(
            encoding="utf-8"
        )
    )

    assert (
        metadata[
            "target_variable"
        ]
        is None
    )

    assert (
        metadata[
            "outputs"
        ][
            "patentes_ml"
        ][
            "records"
        ]
        == 1
    )

    assert (
        metadata[
            "outputs"
        ][
            "tecnologias_sociais_ml"
        ][
            "records"
        ]
        == 1
    )

    assert (
        metadata[
            "outputs"
        ][
            "tecnologias_sociais_textos"
        ][
            "records"
        ]
        == 1
    )