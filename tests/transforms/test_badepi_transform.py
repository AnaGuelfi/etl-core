from savits_etl.transforms.badepi import transformar_linha


def test_transformar_linha_padroniza_campos() -> None:
    row = {
        "NO_PEDIDO": " PI0311748   ",
        "ANO": "2003 ",
        "NM_TITULO_PATENTE": " Exemplo ",
    }

    fields = {
        "NO_PEDIDO": "numero_pedido",
        "ANO": "ano",
        "NM_TITULO_PATENTE": "titulo",
    }

    result = transformar_linha(row, fields)

    assert result == {
        "numero_pedido": "PI0311748",
        "ano": "2003",
        "titulo": "Exemplo",
    }