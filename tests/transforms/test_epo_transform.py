from savits_etl.transforms.epo import (
    parse_epo_biblio,
)


def test_parse_epo_biblio_multiplas_publicacoes() -> None:
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<ops:world-patent-data
    xmlns:ops="http://ops.epo.org"
    xmlns="http://www.epo.org/exchange">

  <exchange-documents>

    <exchange-document
        system="ops.epo.org"
        family-id="48612331"
        country="BR"
        doc-number="112014014126"
        kind="A2">

      <bibliographic-data>

        <publication-reference>
          <document-id document-id-type="docdb">
            <country>BR</country>
            <doc-number>112014014126</doc-number>
            <kind>A2</kind>
            <date>20170613</date>
          </document-id>
        </publication-reference>

        <application-reference>
          <document-id document-id-type="epodoc">
            <doc-number>BR20141114126</doc-number>
            <date>20121109</date>
          </document-id>
        </application-reference>

        <classifications-ipcr>
          <classification-ipcr>
            <text>G07D 9/00 A I</text>
          </classification-ipcr>
        </classifications-ipcr>

        <priority-claims>
          <priority-claim sequence="1">
            <document-id document-id-type="docdb">
              <country>JP</country>
              <doc-number>2011272216</doc-number>
              <kind>A</kind>
              <date>20111213</date>
            </document-id>
          </priority-claim>
        </priority-claims>

        <parties>
          <applicants>
            <applicant
                sequence="1"
                data-format="epodoc">
              <applicant-name>
                <name>
                  OKI ELECTRIC IND CO LTD [JP]
                </name>
              </applicant-name>
            </applicant>
          </applicants>

          <inventors>
            <inventor
                sequence="1"
                data-format="epodoc">
              <inventor-name>
                <name>
                  YUKIHIRO NEMOTO [JP]
                </name>
              </inventor-name>
            </inventor>
          </inventors>
        </parties>

        <invention-title lang="en">
          BANKNOTE HANDLING APPARATUS
        </invention-title>

        <abstract lang="en">
          <p>
            Example abstract.
          </p>
        </abstract>

      </bibliographic-data>
    </exchange-document>

    <exchange-document
        system="ops.epo.org"
        family-id="48612331"
        country="BR"
        doc-number="112014014126"
        kind="A8">

      <bibliographic-data>

        <publication-reference>
          <document-id document-id-type="docdb">
            <country>BR</country>
            <doc-number>112014014126</doc-number>
            <kind>A8</kind>
            <date>20170613</date>
          </document-id>
        </publication-reference>

        <application-reference>
          <document-id document-id-type="epodoc">
            <doc-number>BR20141114126</doc-number>
            <date>20121109</date>
          </document-id>
        </application-reference>

        <invention-title lang="en">
          BANKNOTE HANDLING APPARATUS
        </invention-title>

      </bibliographic-data>
    </exchange-document>

  </exchange-documents>
</ops:world-patent-data>
"""

    result = parse_epo_biblio(
        xml,
        numero_pedido_inpi=(
            "112014014126"
        ),
        epodoc_consulta=(
            "BR20141114126"
        ),
        xml_file="teste.xml",
    )

    assert (
        result[
            "numero_pedido_inpi"
        ]
        == "112014014126"
    )

    assert (
        result[
            "epodoc_consulta"
        ]
        == "BR20141114126"
    )

    assert (
        result[
            "exchange_document_count"
        ]
        == 2
    )

    assert result[
        "family_ids"
    ] == [
        "48612331"
    ]

    assert result[
        "exchange_documents"
    ] == [
        {
            "country": "BR",
            "doc_number": (
                "112014014126"
            ),
            "kind": "A2",
            "family_id": "48612331",
        },
        {
            "country": "BR",
            "doc_number": (
                "112014014126"
            ),
            "kind": "A8",
            "family_id": "48612331",
        },
    ]

    publication_kinds = {
        row["kind"]
        for row in result[
            "publication_references"
        ]
    }

    assert publication_kinds == {
        "A2",
        "A8",
    }

    assert result[
        "application_references"
    ] == [
        {
            "document_id_type": (
                "epodoc"
            ),
            "country": "",
            "doc_number": (
                "BR20141114126"
            ),
            "kind": "",
            "date": "20121109",
        }
    ]

    assert result[
        "titles"
    ] == [
        {
            "lang": "en",
            "text": (
                "BANKNOTE HANDLING "
                "APPARATUS"
            ),
        }
    ]

    assert result[
        "applicants"
    ] == [
        {
            "name": (
                "OKI ELECTRIC IND "
                "CO LTD [JP]"
            ),
            "sequence": "1",
            "data_format": "epodoc",
        }
    ]

    assert result[
        "inventors"
    ] == [
        {
            "name": (
                "YUKIHIRO NEMOTO [JP]"
            ),
            "sequence": "1",
            "data_format": "epodoc",
        }
    ]

    assert result[
        "abstracts"
    ] == [
        {
            "lang": "en",
            "text": (
                "Example abstract."
            ),
        }
    ]

    assert (
        result[
            "classifications"
        ][0]["source"]
        == "classification-ipcr"
    )

    assert (
        result[
            "classifications"
        ][0]["symbol"]
        == "G07D 9/00 A I"
    )

    assert len(
        result[
            "priorities"
        ]
    ) == 1


def test_parse_epo_biblio_sem_exchange_document() -> None:
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<ops:world-patent-data
    xmlns:ops="http://ops.epo.org"
/>
"""

    result = parse_epo_biblio(
        xml,
        numero_pedido_inpi=(
            "102012000009"
        ),
        epodoc_consulta=(
            "BR20121000009"
        ),
    )

    assert (
        result[
            "exchange_document_count"
        ]
        == 0
    )

    assert (
        result[
            "exchange_documents"
        ]
        == []
    )

    assert result[
        "titles"
    ] == []

    assert result[
        "applicants"
    ] == []

    assert result[
        "inventors"
    ] == []