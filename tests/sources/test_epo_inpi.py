import csv
import json

from savits_etl.sources.epo import EPOSource
from savits_etl.sources.epo_inpi import (
    coletar_bronze_inpi_epo,
)


def _write_inpi_csv(
    path,
) -> None:
    fields = [
        "numero_pedido",
        "ano_fonte",
        "ano_deposito",
        "data_deposito",
        "possui_pct",
    ]

    rows = [
        {
            "numero_pedido": (
                "102012011453"
            ),
            "ano_fonte": "2024",
            "ano_deposito": "2012",
            "data_deposito": (
                "2012-05-15"
            ),
            "possui_pct": "0",
        },
        {
            "numero_pedido": (
                "PI0502776"
            ),
            "ano_fonte": "2024",
            "ano_deposito": "2005",
            "data_deposito": (
                "2005-07-05"
            ),
            "possui_pct": "0",
        },
        {
            "numero_pedido": (
                "C10000061"
            ),
            "ano_fonte": "2024",
            "ano_deposito": "2007",
            "data_deposito": (
                "2007-05-16"
            ),
            "possui_pct": "0",
        },
    ]

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fields,
        )

        writer.writeheader()
        writer.writerows(
            rows
        )


def test_coletar_bronze_inpi_epo(
    tmp_path,
    monkeypatch,
) -> None:
    inpi_path = (
        tmp_path
        / "inpi.csv"
    )

    _write_inpi_csv(
        inpi_path
    )

    source = EPOSource(
        bronze_root=tmp_path,
        consumer_key="test-key",
        consumer_secret="test-secret",
        request_interval=0,
    )

    def fake_standardize(
        original,
    ):
        if original == (
            "BR.10 2012 011453.A"
        ):
            return "BR20121011453"

        if original == (
            "BR.PI0502776.A"
        ):
            return "BR2005PI02776"

        raise AssertionError(
            original
        )

    def fake_biblio(
        epodoc,
    ):
        if epodoc == "BR20121011453":
            return b"<xml>matched</xml>"

        if epodoc == "BR2005PI02776":
            return None

        raise AssertionError(
            epodoc
        )

    monkeypatch.setattr(
        source,
        "standardize_application_original",
        fake_standardize,
    )

    monkeypatch.setattr(
        source,
        "fetch_application_biblio",
        fake_biblio,
    )

    links_path, metadata_path = (
        coletar_bronze_inpi_epo(
            reference=20261004,
            inpi_path=inpi_path,
            bronze_root=tmp_path,
            request_interval=0,
            source=source,
        )
    )

    assert links_path.exists()
    assert metadata_path.exists()

    with links_path.open(
        encoding="utf-8",
    ) as file:
        links = [
            json.loads(line)
            for line in file
            if line.strip()
        ]

    assert len(links) == 3

    statuses = {
        row["numero_pedido"]: (
            row["status"]
        )
        for row in links
    }

    assert statuses == {
        "102012011453": "matched",
        "PI0502776": "no_bibliography",
        "C10000061": (
            "unsupported_inpi_format"
        ),
    }

    matched = next(
        row
        for row in links
        if row["status"]
        == "matched"
    )

    assert matched[
        "epodoc_consulta"
    ] == "BR20121011453"

    assert matched[
        "xml_file"
    ]

    xml_path = (
        tmp_path
        / "epo"
        / "inpi"
        / "20261004"
        / "xml"
        / matched["xml_file"]
    )

    assert xml_path.exists()

    with metadata_path.open(
        encoding="utf-8",
    ) as file:
        metadata = json.load(
            file
        )

    assert metadata[
        "records"
    ] == 3

    assert metadata[
        "status_counts"
    ] == {
        "matched": 1,
        "no_bibliography": 1,
        "unsupported_inpi_format": 1,
    }

    assert metadata[
        "technical_failures"
    ] == 0

    assert metadata[
        "xml_files"
    ] == 1

    assert metadata[
        "status"
    ] == "complete"


def test_coletor_retomada_nao_repete_registros(
    tmp_path,
    monkeypatch,
) -> None:
    inpi_path = (
        tmp_path
        / "inpi.csv"
    )

    _write_inpi_csv(
        inpi_path
    )

    source = EPOSource(
        bronze_root=tmp_path,
        consumer_key="test-key",
        consumer_secret="test-secret",
        request_interval=0,
    )

    calls = []

    def fake_standardize(
        original,
    ):
        calls.append(
            original
        )

        if original == (
            "BR.10 2012 011453.A"
        ):
            return "BR20121011453"

        if original == (
            "BR.PI0502776.A"
        ):
            return "BR2005PI02776"

        raise AssertionError(
            original
        )

    def fake_biblio(
        epodoc,
    ):
        del epodoc


    monkeypatch.setattr(
        source,
        "standardize_application_original",
        fake_standardize,
    )

    monkeypatch.setattr(
        source,
        "fetch_application_biblio",
        fake_biblio,
    )

    for _ in range(2):
        coletar_bronze_inpi_epo(
            reference=20261004,
            inpi_path=inpi_path,
            bronze_root=tmp_path,
            request_interval=0,
            source=source,
        )

    assert len(calls) == 2