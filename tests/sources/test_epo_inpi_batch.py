import csv
import json

from savits_etl.sources.epo import EPOSource
from savits_etl.sources.epo_inpi_batch import (
    coletar_bronze_inpi_epo_batch,
)


def _write_input(
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
                "122019026070"
            ),
            "ano_fonte": "2024",
            "ano_deposito": "2019",
            "data_deposito": (
                "2016-02-12"
            ),
            "possui_pct": "1",
        },
        {
            "numero_pedido": (
                "MU8500158"
            ),
            "ano_fonte": "2024",
            "ano_deposito": "2005",
            "data_deposito": (
                "2005-01-20"
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
        writer.writerows(rows)


def _fake_batch_xml() -> bytes:
    return b"""<?xml version="1.0" encoding="UTF-8"?>
<ops:world-patent-data
    xmlns="http://www.epo.org/exchange"
    xmlns:ops="http://ops.epo.org">
  <exchange-documents>

    <exchange-document
        country="BR"
        doc-number="102012011453"
        kind="A2"
        family-id="50397467">
      <bibliographic-data>
        <application-reference>
          <document-id document-id-type="epodoc">
            <doc-number>
              BR20121011453
            </doc-number>
          </document-id>
        </application-reference>
      </bibliographic-data>
    </exchange-document>

    <exchange-document
        country="BR"
        doc-number=""
        kind="">
      <bibliographic-data>
        <application-reference>
          <document-id document-id-type="epodoc">
            <doc-number>
              BR20191226070
            </doc-number>
          </document-id>
        </application-reference>
      </bibliographic-data>
    </exchange-document>

    <exchange-document
        country="BR"
        doc-number="MU8500158"
        kind="U"
        family-id="37001406">
      <bibliographic-data>
        <application-reference>
          <document-id document-id-type="epodoc">
            <doc-number>
              BR2005MU00158U
            </doc-number>
          </document-id>
        </application-reference>
      </bibliographic-data>
    </exchange-document>

  </exchange-documents>
</ops:world-patent-data>
"""


def test_coletor_batch_classifica_respostas(
    tmp_path,
    monkeypatch,
) -> None:
    input_path = (
        tmp_path / "inpi.csv"
    )

    _write_input(
        input_path
    )

    source = EPOSource(
        consumer_key="test-key",
        consumer_secret="test-secret",
        request_interval=0,
    )

    calls = []

    def fake_fetch(
        identifiers,
    ):
        calls.append(
            list(
                identifiers
            )
        )

        return _fake_batch_xml()

    monkeypatch.setattr(
        source,
        "fetch_application_biblio_batch",
        fake_fetch,
    )

    links_path, metadata_path = (
        coletar_bronze_inpi_epo_batch(
            reference=20261004,
            inpi_path=input_path,
            bronze_root=tmp_path,
            batch_size=3,
            request_interval=0,
            source=source,
        )
    )

    with links_path.open(
        encoding="utf-8",
    ) as file:
        links = [
            json.loads(line)
            for line in file
            if line.strip()
        ]

    assert len(calls) == 1
    assert len(links) == 4

    statuses = {
        row["numero_pedido"]: (
            row["status"]
        )
        for row in links
    }

    assert statuses == {
        "102012011453": "matched",
        "122019026070": (
            "no_bibliography"
        ),
        "MU8500158": "matched",
        "C10000061": (
            "unsupported_inpi_format"
        ),
    }

    mu = next(
        row
        for row in links
        if row["numero_pedido"]
        == "MU8500158"
    )

    assert (
        mu[
            "epodoc_aplicacao_resposta"
        ]
        == "BR2005MU00158U"
    )

    with metadata_path.open(
        encoding="utf-8",
    ) as file:
        metadata = json.load(file)

    assert metadata[
        "records"
    ] == 4

    assert metadata[
        "technical_failures"
    ] == 0

    assert metadata[
        "response_batches"
    ] == 1

    assert metadata[
        "status"
    ] == "complete"


def test_coletor_batch_retomada(
    tmp_path,
    monkeypatch,
) -> None:
    input_path = (
        tmp_path / "inpi.csv"
    )

    _write_input(
        input_path
    )

    source = EPOSource(
        consumer_key="test-key",
        consumer_secret="test-secret",
        request_interval=0,
    )

    calls = []

    def fake_fetch(
        identifiers,
    ):
        calls.append(
            list(
                identifiers
            )
        )

        return _fake_batch_xml()

    monkeypatch.setattr(
        source,
        "fetch_application_biblio_batch",
        fake_fetch,
    )

    for _ in range(2):
        coletar_bronze_inpi_epo_batch(
            reference=20261004,
            inpi_path=input_path,
            bronze_root=tmp_path,
            batch_size=3,
            request_interval=0,
            source=source,
        )

    assert len(calls) == 1