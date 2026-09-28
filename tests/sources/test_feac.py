from savits_etl.sources.feac import FEACSource


def test_feac_read(tmp_path) -> None:
    path = (
        tmp_path
        / "feac"
        / "tecnologias_sociais"
        / "2024"
        / "tecnologias_sociais.csv"
    )

    path.parent.mkdir(parents=True)

    path.write_text(
        (
            "ID,Organizacao,Nome_Tecnologia_Social\n"
            "TS-001,Organização Exemplo,Tecnologia Exemplo\n"
        ),
        encoding="utf-8-sig",
    )

    source = FEACSource(
        bronze_root=tmp_path,
    )

    rows = list(source.read(2024))

    assert len(rows) == 1
    assert rows[0]["ID"] == "TS-001"
    assert rows[0]["Organizacao"] == "Organização Exemplo"