import json

from savits_etl.sources.epo import (
    EPOSource,
)


def test_epo_normaliza_identificadores() -> None:
    identifiers = (
        EPOSource.normalize_identifiers(
            [
                " ep1000000.a1 ",
                "EP1000000.A1",
                "ep2000000.a1",
                "",
            ]
        )
    )

    assert identifiers == [
        "EP1000000.A1",
        "EP2000000.A1",
    ]


def test_epo_download_local(
    tmp_path,
    monkeypatch,
) -> None:
    source = EPOSource(
        bronze_root=tmp_path,
        consumer_key="test-key",
        consumer_secret="test-secret",
        batch_size=25,
        request_interval=0,
    )

    calls = []

    def fake_fetch_batch(
        identifiers,
    ):
        calls.append(
            list(
                identifiers
            )
        )

        return (
            (
                b"<ops:world-patent-data>"
                b"<exchange-documents/>"
                b"</ops:world-patent-data>"
            ),
            {
                "X-Throttling-Control": (
                    "green"
                ),
            },
        )

    monkeypatch.setattr(
        source,
        "_fetch_batch",
        fake_fetch_batch,
    )

    manifest_path = source.download(
        reference=20260930,
        identifiers=[
            "EP1000000.A1",
            "EP2000000.A1",
            "EP1000000.A1",
        ],
    )

    assert manifest_path.exists()

    assert calls == [
        [
            "EP1000000.A1",
            "EP2000000.A1",
        ]
    ]

    directory = (
        tmp_path
        / "epo"
        / "ops"
        / "20260930"
    )

    identifiers_path = (
        directory
        / "identificadores.jsonl"
    )

    metadata_path = (
        directory
        / "metadata.json"
    )

    assert identifiers_path.exists()
    assert metadata_path.exists()

    with metadata_path.open(
        encoding="utf-8",
    ) as file:
        metadata = json.load(
            file
        )

    assert (
        metadata[
            "requested_identifiers"
        ]
        == 2
    )

    assert (
        metadata[
            "completed_identifiers"
        ]
        == 2
    )

    assert (
        metadata[
            "failed_identifiers"
        ]
        == 0
    )

    assert (
        metadata["status"]
        == "complete"
    )

    assert (
        metadata[
            "credentials_stored"
        ]
        is False
    )


def test_epo_read(
    tmp_path,
    monkeypatch,
) -> None:
    source = EPOSource(
        bronze_root=tmp_path,
        consumer_key="test-key",
        consumer_secret="test-secret",
        request_interval=0,
    )

    xml = (
        "<ops:world-patent-data>"
        "<exchange-documents>"
        "<exchange-document "
        'country="EP" '
        'doc-number="1000000" '
        'kind="A1"/>'
        "</exchange-documents>"
        "</ops:world-patent-data>"
    )

    def fake_fetch_batch(
        identifiers,
    ):
        del identifiers

        return (
            xml.encode(
                "utf-8"
            ),
            {},
        )

    monkeypatch.setattr(
        source,
        "_fetch_batch",
        fake_fetch_batch,
    )

    source.download(
        reference=20260930,
        identifiers=[
            "EP1000000.A1",
        ],
    )

    rows = list(
        source.read(
            20260930
        )
    )

    assert len(rows) == 1

    assert (
        rows[0]["batch_sequence"]
        == "1"
    )

    assert (
        json.loads(
            rows[0]["identifiers"]
        )
        == [
            "EP1000000.A1",
        ]
    )

    assert (
        "EP"
        in rows[0]["xml"]
    )


def test_epo_retomada_nao_repete_ids(
    tmp_path,
    monkeypatch,
) -> None:
    source = EPOSource(
        bronze_root=tmp_path,
        consumer_key="test-key",
        consumer_secret="test-secret",
        request_interval=0,
    )

    calls = []

    def fake_fetch_batch(
        identifiers,
    ):
        calls.append(
            list(
                identifiers
            )
        )

        return (
            b"<xml/>",
            {},
        )

    monkeypatch.setattr(
        source,
        "_fetch_batch",
        fake_fetch_batch,
    )

    identifiers = [
        "EP1000000.A1",
        "EP2000000.A1",
    ]

    source.download(
        reference=20260930,
        identifiers=identifiers,
    )

    source.download(
        reference=20260930,
        identifiers=identifiers,
    )

    assert len(calls) == 1

def test_epo_preserva_apenas_headers_de_uso() -> None:
    headers = {
        "X-Throttling-Control": (
            "idle (retrieval=green:50)"
        ),
        "X-IndividualQuotaPerHour-Used": "123",
        "X-RegisteredQuotaPerWeek-Used": "456",
        "X-EPO-Client-IP": "192.0.2.1",
        "X-EPO-Forwarded": "192.0.2.1",
        "X-Request-ID": "abc-123",
    }

    result = EPOSource._usage_headers(
        headers
    )

    assert result == {
        "x-throttling-control": (
            "idle (retrieval=green:50)"
        ),
        "x-individualquotaperhour-used": "123",
        "x-registeredquotaperweek-used": "456",
    }

def test_epo_parse_standardized_epodoc() -> None:
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<ops:world-patent-data
    xmlns="http://www.epo.org/exchange"
    xmlns:ops="http://ops.epo.org">
    <ops:standardization
        inputFormat="original"
        outputFormat="epodoc">
        <ops:output>
            <ops:application-reference>
                <document-id
                    document-id-type="epodoc">
                    <doc-number>
                        BR20121011453
                    </doc-number>
                    <kind>A</kind>
                    <date>20120515</date>
                </document-id>
            </ops:application-reference>
        </ops:output>
    </ops:standardization>
</ops:world-patent-data>
"""

    result = (
        EPOSource._parse_standardized_epodoc(
            xml
        )
    )

    assert result == "BR20121011453"


def test_epo_standardize_application_original(
    monkeypatch,
) -> None:
    source = EPOSource(
        consumer_key="test-key",
        consumer_secret="test-secret",
        request_interval=0,
    )

    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<ops:world-patent-data
    xmlns="http://www.epo.org/exchange"
    xmlns:ops="http://ops.epo.org">
    <ops:standardization>
        <ops:output>
            <ops:application-reference>
                <document-id
                    document-id-type="epodoc">
                    <doc-number>
                        BR20121011453
                    </doc-number>
                </document-id>
            </ops:application-reference>
        </ops:output>
    </ops:standardization>
</ops:world-patent-data>
"""

    captured = {}

    def fake_post_ops(
        url,
        body,
        accept,
        not_found_is_none=False,
    ):
        captured["url"] = url
        captured["body"] = body
        captured["accept"] = accept
        captured["not_found"] = (
            not_found_is_none
        )

        return xml

    monkeypatch.setattr(
        source,
        "_post_ops",
        fake_post_ops,
    )

    result = (
        source.standardize_application_original(
            "BR.10 2012 011453-4.A.20120515"
        )
    )

    assert result == "BR20121011453"

    assert (
        captured["body"]
        == b"BR.10 2012 011453-4.A.20120515"
    )

    assert (
        "number-service/application/"
        "original/epodoc"
        in captured["url"]
    )

    assert captured["not_found"] is True


def test_epo_fetch_application_biblio(
    monkeypatch,
) -> None:
    source = EPOSource(
        consumer_key="test-key",
        consumer_secret="test-secret",
        request_interval=0,
    )

    captured = {}

    def fake_get_ops(
        url,
        accept,
        not_found_is_none=False,
    ):
        captured["url"] = url
        captured["accept"] = accept
        captured["not_found"] = (
            not_found_is_none
        )

        return b"<xml/>"

    monkeypatch.setattr(
        source,
        "_get_ops",
        fake_get_ops,
    )

    result = source.fetch_application_biblio(
        "BR20121011453"
    )

    assert result == b"<xml/>"

    assert (
        "published-data/application/"
        "epodoc/BR20121011453/biblio"
        in captured["url"]
    )

    assert captured["not_found"] is True

    def fetch_application_biblio_batch(
        self,
        identifiers: list[str],
    ) -> bytes:
        """
        Obtém bibliografia de múltiplas aplicações EPODOC.

        O retorno bruto é preservado para que o coletor
        possa separar os resultados por aplicação.
        """

        normalized = (
            self.normalize_identifiers(
                identifiers
            )
        )

        if not normalized:
            raise ValueError(
                "Lote de aplicações EPO vazio."
            )

        if len(normalized) > 100:
            raise ValueError(
                "O lote de aplicações EPO "
                "não pode exceder 100 IDs."
            )

        url = (
            f"{self.rest_url}/"
            "published-data/application/"
            "epodoc/biblio"
        )

        content = self._post_ops(
            url=url,
            body=",".join(
                normalized
            ).encode(
                "ascii"
            ),
            accept="application/exchange+xml",
        )

        if content is None:
            raise RuntimeError(
                "A OPS não retornou conteúdo "
                "para o lote de aplicações."
            )

        return content

    @staticmethod
    def parse_application_batch_status(
        content: bytes,
    ) -> dict[str, str]:
        """
        Classifica cada aplicação presente numa resposta
        em lote da OPS.

        matched:
            há pelo menos um exchange-document com
            doc-number de publicação.

        no_bibliography:
            a aplicação foi devolvida apenas como
            placeholder, sem publicação bibliográfica.
        """

        import xml.etree.ElementTree as ET

        root = ET.fromstring(
            content
        )

        def local_name(
            tag: str,
        ) -> str:
            return tag.rsplit(
                "}",
                1,
            )[-1]

        statuses: dict[
            str,
            str,
        ] = {}

        for document in root.iter():
            if (
                local_name(document.tag)
                != "exchange-document"
            ):
                continue

            application_epodocs = []

            for reference in document.iter():
                if (
                    local_name(reference.tag)
                    != "application-reference"
                ):
                    continue

                for document_id in reference:
                    if (
                        local_name(
                            document_id.tag
                        )
                        != "document-id"
                    ):
                        continue

                    if (
                        document_id.attrib.get(
                            "document-id-type"
                        )
                        != "epodoc"
                    ):
                        continue

                    for child in document_id:
                        if (
                            local_name(
                                child.tag
                            )
                            == "doc-number"
                            and child.text
                        ):
                            application_epodocs.append(
                                child.text.strip().upper()
                            )

            if not application_epodocs:
                continue

            publication_number = (
                document.attrib.get(
                    "doc-number",
                    ""
                ).strip()
            )

            status = (
                "matched"
                if publication_number
                else "no_bibliography"
            )

            for epodoc in application_epodocs:
                previous = statuses.get(
                    epodoc
                )

                # Se qualquer variante possuir publicação,
                # matched prevalece sobre placeholder.
                if (
                    previous == "matched"
                    or status == "matched"
                ):
                    statuses[
                        epodoc
                    ] = "matched"
                else:
                    statuses[
                        epodoc
                    ] = (
                        "no_bibliography"
                    )

        return statuses

def test_epo_ausencia_bibliografica_retorna_none(
    monkeypatch,
) -> None:
    source = EPOSource(
        consumer_key="test-key",
        consumer_secret="test-secret",
        request_interval=0,
    )

    def fake_get_ops(
        url,
        accept,
        not_found_is_none=False,
    ):
        del url
        del accept

        assert not_found_is_none is True


    monkeypatch.setattr(
        source,
        "_get_ops",
        fake_get_ops,
    )

    result = source.fetch_application_biblio(
        "BR20121000009"
    )

    assert result is None

def test_epo_calcula_dv_inpi() -> None:
    result = EPOSource.calcular_dv_inpi(
        "102012000009"
    )

    assert result == "1"


def test_epo_calcula_dv_inpi_segundo_caso() -> None:
    result = EPOSource.calcular_dv_inpi(
        "102012011453"
    )

    assert result == "4"

def test_epo_aceita_pedido_inpi_moderno() -> None:
    assert (
        EPOSource.pedido_inpi_compativel(
            numero_pedido="102012011453",
            data_deposito="2012-05-15",
        )
        is True
    )


def test_epo_rejeita_pedido_inpi_antigo() -> None:
    assert (
        EPOSource.pedido_inpi_compativel(
            numero_pedido="00 000022110",
            data_deposito="2011-07-08",
        )
        is False
    )

def test_epo_valida_application_epodoc() -> None:
    assert (
        EPOSource.epodoc_application_valido(
            "BR20121011453"
        )
        is True
    )

    assert (
        EPOSource.epodoc_application_valido(
            "BR10 2010 034088-1"
        )
        is False
    )


def test_epo_descarta_conversao_epodoc_invalida(
    monkeypatch,
) -> None:
    source = EPOSource(
        consumer_key="test-key",
        consumer_secret="test-secret",
        request_interval=0,
    )

    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<ops:world-patent-data
    xmlns="http://www.epo.org/exchange"
    xmlns:ops="http://ops.epo.org">
    <ops:standardization>
        <ops:output>
            <ops:application-reference>
                <document-id
                    document-id-type="epodoc">
                    <doc-number>
                        BR10 2010 034088-1
                    </doc-number>
                </document-id>
            </ops:application-reference>
        </ops:output>
    </ops:standardization>
</ops:world-patent-data>
"""

    def fake_post_ops(
        url,
        body,
        accept,
        not_found_is_none=False,
    ):
        del url
        del body
        del accept

        assert not_found_is_none is True

        return xml

    monkeypatch.setattr(
        source,
        "_post_ops",
        fake_post_ops,
    )

    result = (
        source.standardize_application_original(
            "BR.10 2010 034088-1.A.20100119"
        )
    )

    assert result is None

def test_epo_estado_epodoc_nao_utilizavel() -> None:
    assert (
        EPOSource.epodoc_application_valido(
            "BR10 2010 034088-1"
        )
        is False
    )


def test_epo_estado_epodoc_utilizavel() -> None:
    assert (
        EPOSource.epodoc_application_valido(
            "BR20121000009"
        )
        is True
    )


def test_epo_estado_epodoc_com_bibliografia() -> None:
    assert (
        EPOSource.epodoc_application_valido(
            "BR20121011453"
        )
        is True
    )

def test_epo_aceita_pi_legado() -> None:
    assert (
        EPOSource.pedido_inpi_legado_compativel(
            "PI9714779"
        )
        is True
    )


def test_epo_aceita_mu_legado() -> None:
    assert (
        EPOSource.pedido_inpi_legado_compativel(
            "MU8403134"
        )
        is True
    )


def test_epo_rejeita_pp_no_adaptador_legado() -> None:
    assert (
        EPOSource.pedido_inpi_legado_compativel(
            "PP1234567"
        )
        is False
    )


def test_epo_constroi_original_pi_legado() -> None:
    result = (
        EPOSource.construir_numero_original_inpi_legado(
            "PI9714779"
        )
    )

    assert result == "BR.PI9714779.A"


def test_epo_constroi_original_mu_legado() -> None:
    result = (
        EPOSource.construir_numero_original_inpi_legado(
            "MU8403134"
        )
    )

    assert result == "BR.MU8403134.A"

def test_epo_constroi_original_moderno_tipo_10() -> None:
    result = (
        EPOSource.construir_numero_original_inpi(
            numero_pedido="102012011453",
            data_deposito="2012-05-15",
        )
    )

    assert result == (
        "BR.10 2012 011453.A"
    )


def test_epo_constroi_original_moderno_tipo_11() -> None:
    result = (
        EPOSource.construir_numero_original_inpi(
            numero_pedido="112015021022",
            data_deposito="2014-03-23",
        )
    )

    assert result == (
        "BR.11 2015 021022.A"
    )


def test_epo_constroi_original_moderno_tipo_12() -> None:
    result = (
        EPOSource.construir_numero_original_inpi(
            numero_pedido="122019026070",
            data_deposito="2016-02-12",
        )
    )

    assert result == (
        "BR.12 2019 026070.A"
    )


def test_epo_constroi_original_moderno_tipo_13() -> None:
    result = (
        EPOSource.construir_numero_original_inpi(
            numero_pedido="132016020265",
            data_deposito="2016-09-01",
        )
    )

    assert result == (
        "BR.13 2016 020265.A"
    )


def test_epo_constroi_original_moderno_tipo_20() -> None:
    result = (
        EPOSource.construir_numero_original_inpi(
            numero_pedido="202016001280",
            data_deposito="2016-01-20",
        )
    )

    assert result == (
        "BR.20 2016 001280.U"
    )


def test_epo_constroi_original_moderno_tipo_21() -> None:
    result = (
        EPOSource.construir_numero_original_inpi(
            numero_pedido="212016000354",
            data_deposito="2014-11-26",
        )
    )

    assert result == (
        "BR.21 2016 000354.U"
    )


def test_epo_constroi_original_moderno_tipo_22() -> None:
    result = (
        EPOSource.construir_numero_original_inpi(
            numero_pedido="222019017573",
            data_deposito="2018-11-22",
        )
    )

    assert result == (
        "BR.22 2019 017573.U"
    )


def test_epo_moderno_nao_depende_da_data() -> None:
    result = (
        EPOSource.construir_numero_original_inpi(
            numero_pedido="112024017909",
            data_deposito="",
        )
    )

    assert result == (
        "BR.11 2024 017909.A"
    )


def test_epo_aceita_moderno_sem_data() -> None:
    assert (
        EPOSource.pedido_inpi_compativel(
            numero_pedido="112024017909",
            data_deposito="",
        )
        is True
    )


def test_epo_rejeita_pedido_inpi_antigo_no_adaptador_moderno() -> None:
    assert (
        EPOSource.pedido_inpi_compativel(
            numero_pedido="PI9714779",
            data_deposito="1997-12-30",
        )
        is False
    )


def test_epo_seleciona_adaptador_inpi() -> None:
    moderno_a = (
        EPOSource.construir_numero_original_inpi_ops(
            numero_pedido="112015021022",
            data_deposito="2014-03-23",
        )
    )

    moderno_u = (
        EPOSource.construir_numero_original_inpi_ops(
            numero_pedido="212016000354",
            data_deposito="2014-11-26",
        )
    )

    pi = (
        EPOSource.construir_numero_original_inpi_ops(
            numero_pedido="PI9714779",
            data_deposito="1998-12-30",
        )
    )

    mu = (
        EPOSource.construir_numero_original_inpi_ops(
            numero_pedido="MU8403134",
            data_deposito="2005-12-28",
        )
    )

    assert moderno_a == (
        "BR.11 2015 021022.A"
    )

    assert moderno_u == (
        "BR.21 2016 000354.U"
    )

    assert pi == "BR.PI9714779.A"
    assert mu == "BR.MU8403134.A"

def test_epo_deriva_epodoc_moderno_tipo_10() -> None:
    result = (
        EPOSource.construir_epodoc_inpi_direto(
            numero_pedido="102012011453",
            data_deposito="2012-05-15",
        )
    )

    assert result == "BR20121011453"


def test_epo_deriva_epodoc_moderno_tipo_11() -> None:
    result = (
        EPOSource.construir_epodoc_inpi_direto(
            numero_pedido="112014022311",
            data_deposito="2013-03-08",
        )
    )

    assert result == "BR20141122311"


def test_epo_deriva_epodoc_moderno_tipo_20() -> None:
    result = (
        EPOSource.construir_epodoc_inpi_direto(
            numero_pedido="202016001280",
            data_deposito="2016-01-20",
        )
    )

    assert result == "BR20162001280U"


def test_epo_deriva_epodoc_pi_legado() -> None:
    result = (
        EPOSource.construir_epodoc_inpi_direto(
            numero_pedido="PI0502776",
            data_deposito="2005-07-05",
        )
    )

    assert result == "BR2005PI02776"


def test_epo_deriva_epodoc_mu_legado() -> None:
    result = (
        EPOSource.construir_epodoc_inpi_direto(
            numero_pedido="MU8500158",
            data_deposito="2005-01-20",
        )
    )

    assert result == "BRMU8500158"


def test_epo_derivacao_direta_rejeita_formato_nao_suportado() -> None:
    result = (
        EPOSource.construir_epodoc_inpi_direto(
            numero_pedido="C10000061",
            data_deposito="2007-05-16",
        )
    )

    assert result is None

def test_epo_parse_application_batch_status() -> None:
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<ops:world-patent-data
    xmlns="http://www.epo.org/exchange"
    xmlns:ops="http://ops.epo.org">

    <exchange-documents>

        <exchange-document
            country="BR"
            doc-number=""
            kind="">
            <bibliographic-data>
                <application-reference>
                    <document-id
                        document-id-type="epodoc">
                        <doc-number>
                            BR20191226070
                        </doc-number>
                    </document-id>
                </application-reference>
            </bibliographic-data>
        </exchange-document>

        <exchange-document
            country="BR"
            doc-number="102012011453"
            kind="A2"
            family-id="50397467">
            <bibliographic-data>
                <application-reference>
                    <document-id
                        document-id-type="epodoc">
                        <doc-number>
                            BR20121011453
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
                    <document-id
                        document-id-type="epodoc">
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

    result = (
        EPOSource.parse_application_batch_status(
            xml
        )
    )

    assert result == {
        "BR20191226070": (
            "no_bibliography"
        ),
        "BR20121011453": "matched",
        "BR2005MU00158U": "matched",
    }

def test_epo_fetch_application_biblio_batch(
    monkeypatch,
) -> None:
    source = EPOSource(
        consumer_key="test-key",
        consumer_secret="test-secret",
        request_interval=0,
    )

    captured = {}

    def fake_post_ops(
        url,
        body,
        accept,
        not_found_is_none=False,
    ):
        captured["url"] = url
        captured["body"] = body
        captured["accept"] = accept
        captured["not_found"] = (
            not_found_is_none
        )

        return b"<xml/>"

    monkeypatch.setattr(
        source,
        "_post_ops",
        fake_post_ops,
    )

    result = (
        source.fetch_application_biblio_batch(
            [
                "BR20121011453",
                "BR20141122311",
                "BR20162001280U",
            ]
        )
    )

    assert result == b"<xml/>"

    assert (
        captured["body"]
        == (
            b"BR20121011453,"
            b"BR20141122311,"
            b"BR20162001280U"
        )
    )

    assert (
        "published-data/application/"
        "epodoc/biblio"
        in captured["url"]
    )

    assert (
        captured["accept"]
        == "application/exchange+xml"
    )