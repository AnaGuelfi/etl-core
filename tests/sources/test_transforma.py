import json

from savits_etl.sources.transforma import (
    TransformaSource,
)


def test_transforma_extract_detail_links() -> None:
    html = """
    <html>
        <a href="/tecnologia-social/tecnologia-a">
            Tecnologia A
        </a>
        <a href="/tecnologia-social/tecnologia-b">
            Tecnologia B
        </a>
        <a href="/tecnologia-social/pesquisa?page=2">
            Página 2
        </a>
        <a href="/tecnologia-social/tema/educacao">
            Educação
        </a>
        <a href="/tecnologia-social/tecnologia-a">
            Tecnologia A
        </a>
    </html>
    """

    links = (
        TransformaSource
        .extract_detail_links(html)
    )

    assert links == [
        (
            "https://transforma.fbb.org.br/"
            "tecnologia-social/tecnologia-a"
        ),
        (
            "https://transforma.fbb.org.br/"
            "tecnologia-social/tecnologia-b"
        ),
    ]


def test_transforma_read(tmp_path) -> None:
    directory = (
        tmp_path
        / "fbb"
        / "transforma"
        / "20260927"
    )

    details = directory / "detalhes"
    details.mkdir(parents=True)

    source_url = (
        "https://transforma.fbb.org.br/"
        "tecnologia-social/"
        "tecnologia-exemplo"
    )

    source = TransformaSource(
        bronze_root=tmp_path,
    )

    detail_filename = (
        source._detail_filename(
            source_url
        )
    )

    detail_file = (
        details
        / detail_filename
    )

    detail_file.write_text(
        "<html>Tecnologia Exemplo</html>",
        encoding="utf-8",
    )

    manifest = (
        directory
        / "manifesto.jsonl"
    )

    manifest.write_text(
        (
            json.dumps(
                {
                    "sequence": 1,
                    "listing_page": 1,
                    "slug": "tecnologia-exemplo",
                    "source_url": source_url,
                    "file": detail_filename,
                    "size_bytes": (
                        detail_file.stat().st_size
                    ),
                    "sha256": (
                        source._sha256(
                            detail_file
                        )
                    ),
                }
            )
            + "\n"
        ),
        encoding="utf-8",
    )

    rows = list(
        source.read(20260927)
    )

    assert len(rows) == 1

    assert (
        rows[0]["slug"]
        == "tecnologia-exemplo"
    )

    assert (
        rows[0]["source_url"]
        == source_url
    )

    assert (
        rows[0]["listing_page"]
        == "1"
    )

    assert (
        "Tecnologia Exemplo"
        in rows[0]["html"]
    )