import csv
import sqlite3

from savits_etl.gold.inpi import (
    ano_da_data,
    criar_banco,
    incorporar_buscaweb,
    normalizar_data,
)


def test_normalizar_data_badepi() -> None:
    assert (
        normalizar_data("04/11/2008 00:00:00")
        == "2008-11-04"
    )

    assert (
        normalizar_data("2020-01-03 00:00:00.000")
        == "2020-01-03"
    )


def test_data_sentinela_fica_vazia() -> None:
    assert normalizar_data("01/01/0001 00:00:00") == ""
    assert ano_da_data("01/01/0001 00:00:00") == ""


def test_buscaweb_inclui_apenas_pedido_complementar(
    tmp_path,
) -> None:
    silver_root = tmp_path / "silver"

    pedidos_dir = (
        silver_root
        / "inpi"
        / "pedidos_patentes"
        / "2018"
    )

    pedidos_dir.mkdir(parents=True)

    pedidos_path = pedidos_dir / "pedidos.csv"

    fieldnames = [
        "numero_pedido",
        "titulo",
        "data_deposito",
        "numero_pct",
        "classificacao_ipc",
    ]

    with pedidos_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        writer.writerow(
            {
                "numero_pedido": "PEDIDO_BADEPI",
                "titulo": "Já existente",
                "data_deposito": "2018-01-01",
                "numero_pct": "",
                "classificacao_ipc": "",
            }
        )

        writer.writerow(
            {
                "numero_pedido": "PEDIDO_NOVO",
                "titulo": "Complementar",
                "data_deposito": "2018-02-01",
                "numero_pct": "",
                "classificacao_ipc": "A01B",
            }
        )

    connection = sqlite3.connect(":memory:")

    try:
        criar_banco(connection)

        connection.execute(
            """
            INSERT INTO gold (
                numero_pedido,
                fonte_registro
            )
            VALUES (?, ?)
            """,
            (
                "PEDIDO_BADEPI",
                "badepi",
            ),
        )

        inserted = incorporar_buscaweb(
            connection,
            silver_root,
            (2018,),
        )

        assert inserted == 1

        rows = connection.execute(
            """
            SELECT numero_pedido, fonte_registro
            FROM gold
            ORDER BY numero_pedido
            """
        ).fetchall()

        assert rows == [
            ("PEDIDO_BADEPI", "badepi"),
            ("PEDIDO_NOVO", "buscaweb"),
        ]

    finally:
        connection.close()