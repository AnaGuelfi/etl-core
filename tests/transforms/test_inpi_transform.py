from savits_etl.transforms.inpi import (
    construir_eventos,
    construir_pedidos,
)


def test_construir_pedidos() -> None:
    rows = [
        {
            "Numero_Pedido": "123",
            "Titulo": "Título",
            "Data_Rpi": "2020-01-01",
            "Depositante": "",
        },
        {
            "Numero_Pedido": "123",
            "Titulo": "",
            "Data_Rpi": "2020-02-01",
            "Depositante": "Instituição",
        },
    ]

    pedidos = construir_pedidos(rows)

    assert len(pedidos) == 1
    assert pedidos[0]["numero_pedido"] == "123"
    assert pedidos[0]["titulo"] == "Título"
    assert pedidos[0]["depositante"] == "Instituição"


def test_construir_eventos() -> None:
    rows = [
        {
            "Numero_Pedido": "123",
            "Rpi": "2500",
            "Data_Rpi": "2020-01-01",
            "Despacho": "2.1",
            "Descricao_Despacho": "Texto<br><br>do despacho",
            "Complemento_Despacho": "",
        }
    ]

    eventos = construir_eventos(rows)

    assert len(eventos) == 1
    assert eventos[0]["numero_pedido"] == "123"
    assert eventos[0]["descricao_despacho"] == "Texto do despacho"