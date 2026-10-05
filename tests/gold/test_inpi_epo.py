import csv
import json

from savits_etl.gold.inpi_epo import (
    build_inpi_epo_gold,
)


def test_build_inpi_epo_gold(
    tmp_path,
) -> None:
    inpi_path = (
        tmp_path
        / "inpi.csv"
    )

    epo_path = (
        tmp_path
        / "epo.csv"
    )

    output_path = (
        tmp_path
        / "integrado.csv"
    )

    metadata_path = (
        tmp_path
        / "metadata.json"
    )

    with inpi_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "numero_pedido",
                "titulo",
                "primeira_publicacao_rpi",
            ],
        )

        writer.writeheader()

        writer.writerows(
            [
                {
                    "numero_pedido": (
                        "102012011453"
                    ),
                    "titulo": (
                        "Título INPI"
                    ),
                    "primeira_publicacao_rpi": (
                        "2012-01-01"
                    ),
                },
                {
                    "numero_pedido": (
                        "122019026070"
                    ),
                    "titulo": (
                        "Outro título"
                    ),
                    "primeira_publicacao_rpi": (
                        "2019-01-01"
                    ),
                },
            ]
        )

    with epo_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "numero_pedido",
                "epo_status",
                "epo_epodoc_aplicacao",
                "epo_primeira_publicacao",
            ],
        )

        writer.writeheader()

        writer.writerows(
            [
                {
                    "numero_pedido": (
                        "102012011453"
                    ),
                    "epo_status": (
                        "matched"
                    ),
                    "epo_epodoc_aplicacao": (
                        "BR20121011453"
                    ),
                    "epo_primeira_publicacao": (
                        "20140408"
                    ),
                },
                {
                    "numero_pedido": (
                        "122019026070"
                    ),
                    "epo_status": (
                        "no_bibliography"
                    ),
                    "epo_epodoc_aplicacao": "",
                    "epo_primeira_publicacao": "",
                },
            ]
        )

    build_inpi_epo_gold(
        inpi_path=inpi_path,
        epo_path=epo_path,
        output_path=output_path,
        metadata_path=metadata_path,
        only_epo_records=True,
    )

    with output_path.open(
        encoding="utf-8",
        newline="",
    ) as file:
        rows = list(
            csv.DictReader(file)
        )

    assert len(rows) == 2

    assert (
        rows[0]["titulo"]
        == "Título INPI"
    )

    assert (
        rows[0][
            "primeira_publicacao_rpi"
        ]
        == "2012-01-01"
    )

    assert (
        rows[0][
            "epo_primeira_publicacao"
        ]
        == "20140408"
    )

    assert (
        rows[0][
            "epo_status"
        ]
        == "matched"
    )

    with metadata_path.open(
        encoding="utf-8",
    ) as file:
        metadata = json.load(
            file
        )

    assert (
        metadata[
            "output_records"
        ]
        == 2
    )

    assert (
        metadata[
            "enriched_records"
        ]
        == 2
    )

    assert (
        metadata[
            "matched_records"
        ]
        == 1
    )

    assert (
        metadata[
            "no_bibliography_records"
        ]
        == 1
    )

    assert (
        metadata[
            "epo_records_missing_in_inpi"
        ]
        == 0
    )