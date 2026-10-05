from savits_etl.transforms.epo_silver import (
    build_epo_silver_record,
)


def test_epo_silver_canonicaliza_application_epodoc() -> None:
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<ops:world-patent-data
    xmlns:ops="http://ops.epo.org"
    xmlns="http://www.epo.org/exchange">
  <exchange-documents>
    <exchange-document
        system="ops.epo.org"
        family-id="37001406"
        country="BR"
        doc-number="MU8500158"
        kind="U">
      <bibliographic-data>
        <publication-reference>
          <document-id document-id-type="docdb">
            <country>BR</country>
            <doc-number>MU8500158</doc-number>
            <kind>U</kind>
            <date>20060815</date>
          </document-id>
        </publication-reference>

        <application-reference>
          <document-id document-id-type="epodoc">
            <doc-number>
              BR2005MU00158U
            </doc-number>
            <date>20050120</date>
          </document-id>
        </application-reference>

        <invention-title lang="ol">
          TESTE
        </invention-title>

        <parties>
          <applicants>
            <applicant
                sequence="1"
                data-format="epodoc">
              <applicant-name>
                <name>EMPRESA [BR]</name>
              </applicant-name>
            </applicant>
          </applicants>

          <inventors>
            <inventor
                sequence="1"
                data-format="epodoc">
              <inventor-name>
                <name>AUTOR [BR]</name>
              </inventor-name>
            </inventor>
          </inventors>
        </parties>

        <priority-claims>
          <priority-claim sequence="1">
            <document-id document-id-type="epodoc">
              <doc-number>
                BR2005MU00158U
              </doc-number>
            </document-id>
          </priority-claim>
        </priority-claims>

        <classifications-ipcr>
          <classification-ipcr>
            <text>A01B 1/00 A I</text>
          </classification-ipcr>
        </classifications-ipcr>
      </bibliographic-data>
    </exchange-document>
  </exchange-documents>
</ops:world-patent-data>
"""

    link = {
        "numero_pedido": "MU8500158",
        "status": "matched",
        "original_ops": (
            "BR.MU8500158.A"
        ),
        "epodoc_consulta": (
            "BRMU8500158"
        ),
        "xml_file": "teste.xml",
        "xml_sha256": "abc",
    }

    result = (
        build_epo_silver_record(
            link,
            xml=xml,
        )
    )

    assert (
        result[
            "epodoc_consulta"
        ]
        == "BRMU8500158"
    )

    assert (
        result[
            "epodoc_aplicacao_canonico"
        ]
        == "BR2005MU00158U"
    )

    assert (
        result[
            "epodoc_consulta_diverge_canonico"
        ]
        is True
    )

    assert result[
        "epodoc_aplicacoes"
    ] == [
        "BR2005MU00158U"
    ]

    assert (
        result[
            "bibliography"
        ][
            "family_ids"
        ]
        == [
            "37001406"
        ]
    )


def test_epo_silver_preserva_no_bibliography() -> None:
    link = {
        "numero_pedido": (
            "122019026070"
        ),
        "status": (
            "no_bibliography"
        ),
        "original_ops": (
            "BR.12 2019 026070.A"
        ),
        "epodoc_consulta": (
            "BR20191226070"
        ),
        "xml_file": "",
        "xml_sha256": "",
    }

    result = (
        build_epo_silver_record(
            link
        )
    )

    assert (
        result["status"]
        == "no_bibliography"
    )

    assert (
        result[
            "epodoc_consulta"
        ]
        == "BR20191226070"
    )

    assert (
        result[
            "epodoc_aplicacao_canonico"
        ]
        == ""
    )

    assert (
        result[
            "bibliography"
        ][
            "exchange_document_count"
        ]
        == 0
    )

    assert (
        result[
            "bibliography"
        ][
            "titles"
        ]
        == []
    )