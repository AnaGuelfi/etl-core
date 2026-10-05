from savits_etl.gold.epo import (
    build_epo_gold_record,
)


def test_epo_gold_matched() -> None:
    silver = {
        "numero_pedido_inpi": (
            "MU8500158"
        ),
        "status": "matched",
        "original_ops": (
            "BR.MU8500158.A"
        ),
        "epodoc_consulta": (
            "BRMU8500158"
        ),
        "epodoc_aplicacao_canonico": (
            "BR2005MU00158U"
        ),
        "epodoc_consulta_diverge_canonico": (
            True
        ),
        "xml_sha256": "abc",
        "bibliography": {
            "exchange_document_count": 1,
            "family_ids": [
                "37001406",
            ],
            "publication_references": [
                {
                    "document_id_type": (
                        "docdb"
                    ),
                    "country": "BR",
                    "doc_number": (
                        "MU8500158"
                    ),
                    "kind": "U",
                    "date": "20060815",
                },
                {
                    "document_id_type": (
                        "epodoc"
                    ),
                    "country": "",
                    "doc_number": (
                        "BRMU8500158"
                    ),
                    "kind": "",
                    "date": "20060815",
                },
            ],
            "application_references": [
                {
                    "document_id_type": (
                        "epodoc"
                    ),
                    "country": "",
                    "doc_number": (
                        "BR2005MU00158U"
                    ),
                    "kind": "",
                    "date": "20050120",
                }
            ],
            "titles": [
                {
                    "lang": "ol",
                    "text": "TESTE",
                }
            ],
            "abstracts": [
                {
                    "lang": "ol",
                    "text": "RESUMO",
                }
            ],
            "applicants": [
                {
                    "name": "EMPRESA [BR]",
                    "sequence": "1",
                    "data_format": "epodoc",
                },
                {
                    "name": "Empresa Ltda.",
                    "sequence": "1",
                    "data_format": "original",
                },
            ],
            "inventors": [
                {
                    "name": "AUTOR [BR]",
                    "sequence": "1",
                    "data_format": "epodoc",
                },
                {
                    "name": "Autor",
                    "sequence": "1",
                    "data_format": "original",
                },
            ],
            "priorities": [
                {
                    "sequence": "1",
                    "kind": "",
                    "document_ids": [],
                }
            ],
            "classifications": [
                {
                    "source": (
                        "classification-ipcr"
                    ),
                    "symbol": (
                        "A01B 1/00 A I"
                    ),
                }
            ],
        },
    }

    result = build_epo_gold_record(
        silver
    )

    assert (
        result["numero_pedido"]
        == "MU8500158"
    )

    assert (
        result[
            "epo_epodoc_aplicacao"
        ]
        == "BR2005MU00158U"
    )

    assert (
        result[
            "epo_data_aplicacao"
        ]
        == "20050120"
    )

    assert (
        result[
            "epo_epodoc_diverge"
        ]
        is True
    )

    assert (
        result[
            "epo_quantidade_familias"
        ]
        == 1
    )

    assert (
        result[
            "epo_quantidade_publicacoes"
        ]
        == 1
    )

    assert (
        result[
            "epo_primeira_publicacao"
        ]
        == "20060815"
    )

    assert (
        result[
            "epo_quantidade_depositantes"
        ]
        == 1
    )

    assert (
        result[
            "epo_quantidade_inventores"
        ]
        == 1
    )

    assert (
        result[
            "epo_possui_resumo"
        ]
        is True
    )


def test_epo_gold_no_bibliography() -> None:
    silver = {
        "numero_pedido_inpi": (
            "122019026070"
        ),
        "status": (
            "no_bibliography"
        ),
        "epodoc_consulta": (
            "BR20191226070"
        ),
        "bibliography": {
            "exchange_document_count": 0,
            "family_ids": [],
            "publication_references": [],
            "application_references": [],
            "titles": [],
            "abstracts": [],
            "applicants": [],
            "inventors": [],
            "priorities": [],
            "classifications": [],
        },
    }

    result = build_epo_gold_record(
        silver
    )

    assert (
        result["epo_status"]
        == "no_bibliography"
    )

    assert (
        result[
            "epo_quantidade_publicacoes"
        ]
        == 0
    )

    assert (
        result[
            "epo_possui_resumo"
        ]
        is False
    )

    assert (
        result[
            "epo_quantidade_classificacoes"
        ]
        == 0
    )