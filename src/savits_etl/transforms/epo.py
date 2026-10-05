from __future__ import annotations

import json
import xml.etree.ElementTree as ET


def _local_name(
    tag: str,
) -> str:
    return tag.rsplit(
        "}",
        1,
    )[-1]


def _attribute(
    element: ET.Element,
    name: str,
) -> str:
    for key, value in element.attrib.items():
        if _local_name(key) == name:
            return value.strip()

    return ""


def _element_text(
    element: ET.Element,
) -> str:
    return " ".join(
        part.strip()
        for part in element.itertext()
        if part.strip()
    )


def _child_text(
    element: ET.Element,
    name: str,
) -> str:
    for child in element:
        if _local_name(
            child.tag
        ) == name:
            return _element_text(
                child
            )

    return ""


def _descendants(
    element: ET.Element,
    name: str,
):
    return (
        child
        for child in element.iter()
        if _local_name(
            child.tag
        ) == name
    )


def _unique_strings(
    values,
) -> list[str]:
    result = []
    seen = set()

    for value in values:
        value = str(
            value
        ).strip()

        if not value:
            continue

        if value in seen:
            continue

        seen.add(
            value
        )
        result.append(
            value
        )

    return result


def _unique_records(
    records: list[dict[str, object]],
) -> list[dict[str, object]]:
    result = []
    seen = set()

    for record in records:
        key = json.dumps(
            record,
            ensure_ascii=False,
            sort_keys=True,
        )

        if key in seen:
            continue

        seen.add(
            key
        )
        result.append(
            record
        )

    return result


def _document_ids(
    element: ET.Element,
) -> list[dict[str, str]]:
    records = []

    for document_id in _descendants(
        element,
        "document-id",
    ):
        records.append(
            {
                "document_id_type": (
                    _attribute(
                        document_id,
                        "document-id-type",
                    )
                ),
                "country": _child_text(
                    document_id,
                    "country",
                ),
                "doc_number": (
                    _child_text(
                        document_id,
                        "doc-number",
                    )
                ),
                "kind": _child_text(
                    document_id,
                    "kind",
                ),
                "date": _child_text(
                    document_id,
                    "date",
                ),
            }
        )

    return _unique_records(
        records
    )


def _reference_records(
    exchange_document: ET.Element,
    reference_name: str,
) -> list[dict[str, str]]:
    records = []

    for reference in _descendants(
        exchange_document,
        reference_name,
    ):
        records.extend(
            _document_ids(
                reference
            )
        )

    return _unique_records(
        records
    )


def _party_records(
    exchange_document: ET.Element,
    *,
    party_name: str,
    name_container: str,
) -> list[dict[str, str]]:
    records = []

    for party in _descendants(
        exchange_document,
        party_name,
    ):
        sequence = _attribute(
            party,
            "sequence",
        )

        data_format = _attribute(
            party,
            "data-format",
        )

        for container in _descendants(
            party,
            name_container,
        ):
            for name_element in _descendants(
                container,
                "name",
            ):
                name = _element_text(
                    name_element
                )

                if not name:
                    continue

                records.append(
                    {
                        "name": name,
                        "sequence": sequence,
                        "data_format": data_format,
                    }
                )

    return _unique_records(
        records
    )


def _title_records(
    exchange_document: ET.Element,
) -> list[dict[str, str]]:
    records = []

    for title in _descendants(
        exchange_document,
        "invention-title",
    ):
        text = _element_text(
            title
        )

        if not text:
            continue

        records.append(
            {
                "lang": _attribute(
                    title,
                    "lang",
                ),
                "text": text,
            }
        )

    return _unique_records(
        records
    )


def _abstract_records(
    exchange_document: ET.Element,
) -> list[dict[str, str]]:
    records = []

    for abstract in _descendants(
        exchange_document,
        "abstract",
    ):
        paragraphs = [
            _element_text(
                paragraph
            )
            for paragraph in _descendants(
                abstract,
                "p",
            )
        ]

        paragraphs = [
            paragraph
            for paragraph in paragraphs
            if paragraph
        ]

        if paragraphs:
            text = "\n".join(
                paragraphs
            )
        else:
            text = _element_text(
                abstract
            )

        if not text:
            continue

        records.append(
            {
                "lang": _attribute(
                    abstract,
                    "lang",
                ),
                "text": text,
            }
        )

    return _unique_records(
        records
    )


def _priority_records(
    exchange_document: ET.Element,
) -> list[dict[str, object]]:
    records = []

    for priority in _descendants(
        exchange_document,
        "priority-claim",
    ):
        records.append(
            {
                "sequence": _attribute(
                    priority,
                    "sequence",
                ),
                "kind": _attribute(
                    priority,
                    "kind",
                ),
                "document_ids": (
                    _document_ids(
                        priority
                    )
                ),
            }
        )

    return _unique_records(
        records
    )


def _classification_records(
    exchange_document: ET.Element,
) -> list[dict[str, str]]:
    records = []

    for classification in _descendants(
        exchange_document,
        "classification-ipcr",
    ):
        text = _element_text(
            classification
        )

        if text:
            records.append(
                {
                    "source": "classification-ipcr",
                    "symbol": text,
                    "scheme": "",
                    "section": "",
                    "class": "",
                    "subclass": "",
                    "main_group": "",
                    "subgroup": "",
                    "value": "",
                }
            )

    for classification in _descendants(
        exchange_document,
        "classification-ipc",
    ):
        text = _element_text(
            classification
        )

        if text:
            records.append(
                {
                    "source": "classification-ipc",
                    "symbol": text,
                    "scheme": "",
                    "section": "",
                    "class": "",
                    "subclass": "",
                    "main_group": "",
                    "subgroup": "",
                    "value": "",
                }
            )

    for classification in _descendants(
        exchange_document,
        "patent-classification",
    ):
        records.append(
            {
                "source": "patent-classification",
                "symbol": "",
                "scheme": (
                    _child_text(
                        classification,
                        "classification-scheme",
                    )
                    or _attribute(
                        classification,
                        "scheme",
                    )
                ),
                "section": _child_text(
                    classification,
                    "section",
                ),
                "class": _child_text(
                    classification,
                    "class",
                ),
                "subclass": _child_text(
                    classification,
                    "subclass",
                ),
                "main_group": _child_text(
                    classification,
                    "main-group",
                ),
                "subgroup": _child_text(
                    classification,
                    "subgroup",
                ),
                "value": _child_text(
                    classification,
                    "classification-value",
                ),
            }
        )

    return _unique_records(
        records
    )


def parse_epo_biblio(
    xml: bytes | str,
    *,
    numero_pedido_inpi: str,
    epodoc_consulta: str,
    xml_file: str = "",
) -> dict[str, object]:
    """
    Converte a resposta bibliográfica OPS em uma estrutura
    normalizada no nível do pedido INPI.

    Um XML pode conter mais de um exchange-document.
    Esses documentos são preservados como publicações/variantes
    do mesmo vínculo INPI -> EPO.
    """

    if isinstance(
        xml,
        bytes,
    ):
        root = ET.fromstring(
            xml
        )
    else:
        root = ET.fromstring(
            xml.encode(
                "utf-8"
            )
        )

    exchange_documents = [
        element
        for element in root.iter()
        if _local_name(
            element.tag
        )
        == "exchange-document"
    ]

    families = []
    document_variants = []
    publication_references = []
    application_references = []
    titles = []
    applicants = []
    inventors = []
    priorities = []
    classifications = []
    abstracts = []

    for document in exchange_documents:
        family_id = _attribute(
            document,
            "family-id",
        )

        if family_id:
            families.append(
                family_id
            )

        document_variants.append(
            {
                "country": _attribute(
                    document,
                    "country",
                ),
                "doc_number": _attribute(
                    document,
                    "doc-number",
                ),
                "kind": _attribute(
                    document,
                    "kind",
                ),
                "family_id": family_id,
            }
        )

        publication_references.extend(
            _reference_records(
                document,
                "publication-reference",
            )
        )

        application_references.extend(
            _reference_records(
                document,
                "application-reference",
            )
        )

        titles.extend(
            _title_records(
                document
            )
        )

        applicants.extend(
            _party_records(
                document,
                party_name="applicant",
                name_container="applicant-name",
            )
        )

        inventors.extend(
            _party_records(
                document,
                party_name="inventor",
                name_container="inventor-name",
            )
        )

        priorities.extend(
            _priority_records(
                document
            )
        )

        classifications.extend(
            _classification_records(
                document
            )
        )

        abstracts.extend(
            _abstract_records(
                document
            )
        )

    return {
        "numero_pedido_inpi": (
            numero_pedido_inpi
        ),
        "epodoc_consulta": (
            epodoc_consulta
        ),
        "xml_file": xml_file,
        "exchange_document_count": len(
            exchange_documents
        ),
        "family_ids": _unique_strings(
            families
        ),
        "exchange_documents": (
            _unique_records(
                document_variants
            )
        ),
        "publication_references": (
            _unique_records(
                publication_references
            )
        ),
        "application_references": (
            _unique_records(
                application_references
            )
        ),
        "titles": _unique_records(
            titles
        ),
        "applicants": _unique_records(
            applicants
        ),
        "inventors": _unique_records(
            inventors
        ),
        "priorities": _unique_records(
            priorities
        ),
        "classifications": (
            _unique_records(
                classifications
            )
        ),
        "abstracts": _unique_records(
            abstracts
        ),
    }