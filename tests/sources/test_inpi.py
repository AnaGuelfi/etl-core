from pathlib import Path
from zipfile import ZipFile

from savits_etl.sources.inpi import INPISource


def test_read_bronze(tmp_path: Path) -> None:
    source = INPISource(bronze_root=tmp_path)

    directory = (
        tmp_path
        / "inpi"
        / "pedidos_patentes"
        / "2020"
    )
    directory.mkdir(parents=True)

    zip_path = directory / "2020.zip"

    csv_content = (
        "Numero_Pedido |Titulo |Data_Deposito \n"
        "102020000017 |TÍTULO DE TESTE |2020-01-02 \n"
    )

    with ZipFile(zip_path, "w") as archive:
        archive.writestr(
            "dados.csv",
            csv_content.encode("cp1252"),
        )

    rows = list(source.read(2020))

    assert len(rows) == 1
    assert rows[0]["Numero_Pedido"] == "102020000017"
    assert rows[0]["Titulo"] == "TÍTULO DE TESTE"
    assert rows[0]["Data_Deposito"] == "2020-01-02"