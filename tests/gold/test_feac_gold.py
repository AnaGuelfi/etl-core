from savits_etl.gold.feac import construir_gold


def test_construir_gold_feac() -> None:
    rows = [
        {
            "id_tecnologia": "TS-001",
            "organizacao": "Organização",
            "nome_tecnologia_social": "Tecnologia",
            "status_ativa": "Sim",
            "qtd_ods": "3",
            "indice_consolidacao": "66.6",
        }
    ]

    gold = construir_gold(
        rows,
        reference=2024,
    )

    assert len(gold) == 1

    assert gold[0]["id_tecnologia"] == "TS-001"
    assert (
        gold[0]["fonte_registro"]
        == "feac_casa_hacker"
    )
    assert gold[0]["ano_referencia"] == "2024"
    assert gold[0]["qtd_ods"] == "3"
    assert gold[0]["indice_consolidacao"] == "66.6"


def test_gold_feac_preserva_campos_ausentes() -> None:
    rows = [
        {
            "id_tecnologia": "TS-002",
            "nome_tecnologia_social": "",
        }
    ]

    gold = construir_gold(
        rows,
        reference=2024,
    )

    assert gold[0]["nome_tecnologia_social"] == ""
    assert gold[0]["organizacao"] == ""