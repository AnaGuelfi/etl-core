from savits_etl.transforms.feac import (
    normalizar_linha,
    separar_valores,
)


def test_normalizar_linha_feac() -> None:
    row = {
        "ID": " TS-001 ",
        "Organizacao": " Organização ",
        "Nome_Tecnologia_Social": " Tecnologia ",
    }

    result = normalizar_linha(row)

    assert result == {
        "id_tecnologia": "TS-001",
        "organizacao": "Organização",
        "nome_tecnologia_social": "Tecnologia",
    }


def test_separar_valores_feac() -> None:
    assert separar_valores(
        "4; 8; 10"
    ) == [
        "4",
        "8",
        "10",
    ]