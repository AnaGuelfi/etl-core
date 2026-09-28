from savits_etl.gold.transforma import (
    construir_gold,
)


def test_construir_gold_transforma() -> None:
    rows = [
        {
            "slug": "tecnologia-exemplo",
            "titulo": "Tecnologia Exemplo",
            "instituicao": "Instituição Exemplo",
            "instituicao_url": (
                "https://example.org/instituicao"
            ),
            "status_premio": "Certificada",
            "ano_premio": "2024",
            "resumo": "Resumo",
            "objetivo": "Objetivo",
            "objetivos_especificos": "",
            "problema_solucionado": "Problema",
            "descricao": "Descrição",
            "recursos_necessarios": "Recursos",
            "resultados_alcancados": "Resultados",
            "source_url": (
                "https://example.org/tecnologia"
            ),
        }
    ]

    themes = [
        {
            "slug": "tecnologia-exemplo",
            "tema": "Educação",
        },
        {
            "slug": "tecnologia-exemplo",
            "tema": "Renda",
        },
    ]

    ods = [
        {
            "slug": "tecnologia-exemplo",
            "ods": "Educação de Qualidade",
        }
    ]

    publics = [
        {
            "slug": "tecnologia-exemplo",
            "publico": "Adulto",
        },
        {
            "slug": "tecnologia-exemplo",
            "publico": "Jovens",
        },
    ]

    gold = construir_gold(
        rows=rows,
        themes=themes,
        ods=ods,
        publics=publics,
        reference=20260927,
    )

    assert len(gold) == 1

    record = gold[0]

    assert (
        record["id_tecnologia"]
        == (
            "fbb_transforma:"
            "tecnologia-exemplo"
        )
    )

    assert (
        record["fonte_registro"]
        == "fbb_transforma"
    )

    assert (
        record["snapshot_reference"]
        == "20260927"
    )

    assert record["qtd_temas"] == "2"

    assert (
        record["temas"]
        == "Educação; Renda"
    )

    assert record["qtd_ods"] == "1"

    assert (
        record["ods"]
        == "Educação de Qualidade"
    )

    assert (
        record["qtd_publicos"]
        == "2"
    )

    assert (
        record["publicos"]
        == "Adulto; Jovens"
    )

    assert (
        record["completude_cadastro"]
        == "100.00"
    )


def test_gold_transforma_preserva_campos_ausentes() -> None:
    rows = [
        {
            "slug": "tecnologia-incompleta",
            "titulo": "Tecnologia Incompleta",
        }
    ]

    gold = construir_gold(
        rows=rows,
        themes=[],
        ods=[],
        publics=[],
        reference=20260927,
    )

    record = gold[0]

    assert (
        record["instituicao"]
        == ""
    )

    assert (
        record["status_premio"]
        == ""
    )

    assert (
        record["qtd_temas"]
        == "0"
    )

    assert record["temas"] == ""

    assert (
        record["qtd_ods"]
        == "0"
    )

    assert record["ods"] == ""

    assert (
        record["qtd_publicos"]
        == "0"
    )

    assert record["publicos"] == ""

    assert (
        record["completude_cadastro"]
        != "100.00"
    )


def test_gold_transforma_remove_relacoes_duplicadas() -> None:
    rows = [
        {
            "slug": "tecnologia-exemplo",
            "titulo": "Tecnologia",
        }
    ]

    themes = [
        {
            "slug": "tecnologia-exemplo",
            "tema": "Educação",
        },
        {
            "slug": "tecnologia-exemplo",
            "tema": "Educação",
        },
    ]

    gold = construir_gold(
        rows=rows,
        themes=themes,
        ods=[],
        publics=[],
        reference=20260927,
    )

    assert (
        gold[0]["qtd_temas"]
        == "1"
    )

    assert (
        gold[0]["temas"]
        == "Educação"
    )