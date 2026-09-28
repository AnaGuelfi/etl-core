from savits_etl.gold.tecnologias_sociais import (
    construir_gold,
    construir_registro_feac,
    construir_registro_transforma,
    construir_texto_feac,
)


def test_construir_registro_feac() -> None:
    row = {
        "id_tecnologia": "TS-001",
        "ano_referencia": "2024",
        "nome_tecnologia_social": (
            "Educar para Protagonismo"
        ),
        "organizacao": "Organização Exemplo",
        "status_ativa": "Sim",
        "ano_inicio": "2006",
        "publico_final": "Adolescentes",
        "ods_lista": "4; 8; 10",
        "modalidade_todas": (
            "Formação/Capacitação; "
            "Articulação/Mobilização/Advocacy"
        ),
        "desc_tecnologia": (
            "Descrição da tecnologia."
        ),
        "completude_cadastro": "95.00",
    }

    result = construir_registro_feac(
        row
    )

    assert (
        result["id_registro"]
        == "feac_casa_hacker:TS-001"
    )

    assert (
        result["fonte_registro"]
        == "feac_casa_hacker"
    )

    assert result["id_fonte"] == "TS-001"

    assert (
        result["titulo"]
        == "Educar para Protagonismo"
    )

    assert (
        result["tipo_referencia"]
        == "ano"
    )

    assert (
        result["tipo_status"]
        == "atividade"
    )

    assert result["qtd_ods"] == "3"

    assert (
        result["ods_codigos"]
        == "4; 8; 10"
    )

    assert (
        result["ods_nomes"]
        == (
            "Educação de Qualidade; "
            "Trabalho Decente e Crescimento Econômico; "
            "Redução das Desigualdades"
        )
    )

    assert result["qtd_publicos"] == "1"

    assert (
        result["publicos"]
        == "Adolescentes"
    )

    assert result["temas"] == ""

    assert (
        "Formação/Capacitação"
        in result["modalidades"]
    )

    assert (
        result["descricao"]
        == "Descrição da tecnologia."
    )

    assert (
        result["texto_analitico"]
        == "Descrição da tecnologia."
    )


def test_texto_feac_fallback() -> None:
    row = {
        "desc_tecnologia": "",
        "categoria_tecnologia": (
            "Inclusão produtiva"
        ),
        "modalidade_todas": (
            "Formação/Capacitação; "
            "Geração de renda/Inclusão produtiva"
        ),
        "publico_final": "Adultos",
        "palavras_chave_tec": (
            "trabalho; renda"
        ),
    }

    result = construir_texto_feac(
        row
    )

    assert (
        "Categoria: Inclusão produtiva"
        in result
    )

    assert (
        "Modalidades: Formação/Capacitação; "
        "Geração de renda/Inclusão produtiva"
        in result
    )

    assert (
        "Público: Adultos"
        in result
    )

    assert (
        "Palavras-chave: trabalho; renda"
        in result
    )


def test_texto_feac_prefere_descricao_original() -> None:
    row = {
        "desc_tecnologia": (
            "Descrição original."
        ),
        "categoria_tecnologia": (
            "Categoria alternativa"
        ),
        "publico_final": "Adultos",
    }

    result = construir_texto_feac(
        row
    )

    assert result == "Descrição original."


def test_texto_feac_ignora_valores_nao_informados() -> None:
    row = {
        "desc_tecnologia": "",
        "categoria_tecnologia": (
            "Não informado"
        ),
        "modalidade_todas": "",
        "publico_final": "Não informado",
        "palavras_chave_tec": "",
    }

    result = construir_texto_feac(
        row
    )

    assert result == ""


def test_construir_registro_transforma() -> None:
    row = {
        "id_tecnologia": (
            "fbb_transforma:"
            "tecnologia-exemplo"
        ),
        "snapshot_reference": "20260927",
        "slug": "tecnologia-exemplo",
        "titulo": "Tecnologia Exemplo",
        "instituicao": "Instituição Exemplo",
        "status_premio": "Certificada",
        "ano_premio": "2024",
        "qtd_temas": "2",
        "temas": "Educação; Renda",
        "qtd_ods": "2",
        "ods": (
            "Educação de Qualidade; "
            "Trabalho Decente e Crescimento Econômico"
        ),
        "qtd_publicos": "2",
        "publicos": "Adulto; Jovens",
        "resumo": "Resumo.",
        "objetivo": "Objetivo.",
        "problema_solucionado": "Problema.",
        "descricao": "Descrição.",
        "resultados_alcancados": "Resultados.",
        "source_url": (
            "https://example.org/tecnologia"
        ),
        "completude_cadastro": "100.00",
    }

    result = (
        construir_registro_transforma(
            row
        )
    )

    assert (
        result["id_registro"]
        == (
            "fbb_transforma:"
            "tecnologia-exemplo"
        )
    )

    assert (
        result["fonte_registro"]
        == "fbb_transforma"
    )

    assert (
        result["tipo_referencia"]
        == "data_snapshot"
    )

    assert (
        result["tipo_status"]
        == "premiacao"
    )

    assert result["qtd_ods"] == "2"

    assert (
        result["ods_codigos"]
        == "4; 8"
    )

    assert (
        result["ods_nomes"]
        == (
            "Educação de Qualidade; "
            "Trabalho Decente e Crescimento Econômico"
        )
    )

    assert (
        result["qtd_publicos"]
        == "2"
    )

    assert (
        result["publicos"]
        == "Adulto; Jovens"
    )

    assert (
        result["temas"]
        == "Educação; Renda"
    )

    assert result["modalidades"] == ""

    assert (
        "Resumo: Resumo."
        in result["texto_analitico"]
    )

    assert (
        "Resultados alcançados: Resultados."
        in result["texto_analitico"]
    )


def test_feac_nao_informado_nao_conta_publico() -> None:
    row = {
        "id_tecnologia": "TS-002",
        "publico_final": "Não informado",
    }

    result = construir_registro_feac(
        row
    )

    assert result["qtd_publicos"] == "0"
    assert result["publicos"] == ""


def test_construir_gold_multifonte() -> None:
    feac_rows = [
        {
            "id_tecnologia": "TS-001",
            "nome_tecnologia_social": (
                "Tecnologia FEAC"
            ),
            "ano_referencia": "2024",
        }
    ]

    transforma_rows = [
        {
            "slug": "tecnologia-transforma",
            "titulo": "Tecnologia Transforma",
            "snapshot_reference": "20260927",
        }
    ]

    gold = construir_gold(
        feac_rows=feac_rows,
        transforma_rows=transforma_rows,
    )

    assert len(gold) == 2

    ids = {
        row["id_registro"]
        for row in gold
    }

    assert ids == {
        "feac_casa_hacker:TS-001",
        (
            "fbb_transforma:"
            "tecnologia-transforma"
        ),
    }

    sources = {
        row["fonte_registro"]
        for row in gold
    }

    assert sources == {
        "feac_casa_hacker",
        "fbb_transforma",
    }