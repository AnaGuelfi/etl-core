from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

from savits_etl.sources.transforma import (
    TransformaSource,
)


def _normalizar_texto(value: str) -> str:
    """Remove espaços e quebras de linha excedentes."""

    return " ".join(
        value.split()
    )


class _TransformaHTMLParser(HTMLParser):
    """Extrai campos estruturados de uma página do Transforma!."""

    def __init__(self) -> None:
        super().__init__()

        self.title = ""
        self.header_small_values: list[str] = []
        self.links: list[dict[str, str]] = []
        self.sections: dict[str, str] = {}
        self.audience: list[str] = []

        self._header_depth = 0

        self._title_buffer: list[str] | None = None
        self._small_buffer: list[str] | None = None

        self._link_href = ""
        self._link_title = ""
        self._link_buffer: list[str] | None = None

        self._heading_buffer: list[str] | None = None
        self._pending_section = ""

        self._section_name = ""
        self._section_buffer: list[str] = []
        self._section_depth = 0

        self._audience_active = False
        self._audience_item_buffer: (
            list[str] | None
        ) = None

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        attributes = dict(attrs)

        classes = (
            attributes.get(
                "class",
                "",
            )
            or ""
        ).split()

        if tag == "div":
            if self._header_depth > 0:
                self._header_depth += 1

            elif (
                "socialtecnology-detail-header"
                in classes
            ):
                self._header_depth = 1

            if self._section_depth > 0:
                self._section_depth += 1

            elif (
                self._pending_section
                and "ts-detail-plain"
                in classes
            ):
                self._section_name = (
                    self._pending_section
                )
                self._section_buffer = []
                self._section_depth = 1
                self._pending_section = ""

        if (
            tag == "ul"
            and self._pending_section.casefold()
            == "público atendido".casefold()
            and "ts-detail-audience"
            in classes
        ):
            self._audience_active = True
            self._pending_section = ""

        if (
            tag == "li"
            and self._audience_active
            and "ts-detail-audience-item"
            in classes
        ):
            self._audience_item_buffer = []

        if (
            tag == "h1"
            and self._header_depth > 0
        ):
            self._title_buffer = []

        if tag == "h3":
            self._heading_buffer = []

        if tag == "a":
            self._link_href = (
                attributes.get(
                    "href",
                    "",
                )
                or ""
            )

            self._link_title = (
                attributes.get(
                    "title",
                    "",
                )
                or ""
            )

            self._link_buffer = []

        if (
            tag == "small"
            and self._header_depth > 0
            and self._link_buffer is None
        ):
            self._small_buffer = []

    def handle_data(
        self,
        data: str,
    ) -> None:
        if self._title_buffer is not None:
            self._title_buffer.append(data)

        if self._small_buffer is not None:
            self._small_buffer.append(data)

        if self._link_buffer is not None:
            self._link_buffer.append(data)

        if self._heading_buffer is not None:
            self._heading_buffer.append(data)

        if self._section_depth > 0:
            self._section_buffer.append(data)

        if (
            self._audience_item_buffer
            is not None
        ):
            self._audience_item_buffer.append(
                data
            )

    def handle_endtag(
        self,
        tag: str,
    ) -> None:
        if (
            tag == "h1"
            and self._title_buffer is not None
        ):
            title = _normalizar_texto(
                " ".join(
                    self._title_buffer
                )
            )

            if title and not self.title:
                self.title = title

            self._title_buffer = None

        if (
            tag == "small"
            and self._small_buffer is not None
        ):
            value = _normalizar_texto(
                " ".join(
                    self._small_buffer
                )
            )

            if value:
                self.header_small_values.append(
                    value
                )

            self._small_buffer = None

        if (
            tag == "a"
            and self._link_buffer is not None
        ):
            text = _normalizar_texto(
                " ".join(
                    self._link_buffer
                )
            )

            if self._link_href:
                self.links.append(
                    {
                        "href": self._link_href,
                        "title": (
                            self._link_title
                        ),
                        "text": text,
                    }
                )

            self._link_href = ""
            self._link_title = ""
            self._link_buffer = None

        if (
            tag == "h3"
            and self._heading_buffer is not None
        ):
            heading = _normalizar_texto(
                " ".join(
                    self._heading_buffer
                )
            )

            self._pending_section = heading
            self._heading_buffer = None

        if (
            tag == "li"
            and self._audience_item_buffer
            is not None
        ):
            value = _normalizar_texto(
                " ".join(
                    self._audience_item_buffer
                )
            )

            if (
                value
                and value not in self.audience
            ):
                self.audience.append(
                    value
                )

            self._audience_item_buffer = None

        if (
            tag == "ul"
            and self._audience_active
        ):
            self._audience_active = False

        if (
            tag == "div"
            and self._section_depth > 0
        ):
            self._section_depth -= 1

            if self._section_depth == 0:
                value = _normalizar_texto(
                    " ".join(
                        self._section_buffer
                    )
                )

                if (
                    self._section_name
                    and self._section_name
                    not in self.sections
                ):
                    self.sections[
                        self._section_name
                    ] = value

                self._section_name = ""
                self._section_buffer = []

        if (
            tag == "div"
            and self._header_depth > 0
        ):
            self._header_depth -= 1


SECTION_FIELDS = {
    "resumo": "resumo",
    "objetivo": "objetivo",
    "objetivos específicos": (
        "objetivos_especificos"
    ),
    "problema solucionado": (
        "problema_solucionado"
    ),
    "descrição": "descricao",
    "recursos necessários": (
        "recursos_necessarios"
    ),
    "resultados alcançados": (
        "resultados_alcancados"
    ),
}


TECNOLOGIAS_FIELDS = [
    "slug",
    "source_url",
    "listing_page",
    "titulo",
    "instituicao",
    "instituicao_url",
    "status_premio",
    "ano_premio",
    "resumo",
    "objetivo",
    "objetivos_especificos",
    "problema_solucionado",
    "descricao",
    "recursos_necessarios",
    "resultados_alcancados",
    "publico_atendido",
]


def _valor_secao(
    sections: dict[str, str],
    field: str,
) -> str:
    for heading, value in sections.items():
        destination = SECTION_FIELDS.get(
            heading.casefold()
        )

        if destination == field:
            return value

    return ""


def _primeiro_link(
    links: list[dict[str, str]],
    path_fragment: str,
) -> dict[str, str] | None:
    for link in links:
        path = urlparse(
            link["href"]
        ).path

        if path_fragment in path:
            return link

    return None


def _links_multivalorados(
    links: list[dict[str, str]],
    path_fragment: str,
) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in links:
        href = link["href"]
        path = urlparse(href).path

        if path_fragment not in path:
            continue

        if href in seen:
            continue

        seen.add(href)

        name = (
            link["title"].strip()
            or link["text"].strip()
        )

        if not name:
            name = (
                path
                .rstrip("/")
                .split("/")[-1]
            )

        result.append(
            {
                "name": name,
                "url": href,
            }
        )

    return result


def extrair_tecnologia(
    row: dict[str, str],
) -> tuple[
    dict[str, str],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
]:
    """Extrai uma tecnologia e suas relações a partir do HTML."""

    parser = _TransformaHTMLParser()
    parser.feed(
        row["html"]
    )

    institution_link = _primeiro_link(
        parser.links,
        "/perfil/instituicao/",
    )

    institution = ""
    institution_url = ""

    if institution_link is not None:
        institution = (
            institution_link["text"]
            or institution_link["title"]
        ).strip()

        institution_url = (
            institution_link["href"]
        )

    year = ""

    for value in parser.header_small_values:
        if (
            len(value) == 4
            and value.isdigit()
        ):
            year = value
            break

    status = ""

    for value in parser.header_small_values:
        if value == year:
            continue

        status = value
        break

    technology = {
        "slug": row["slug"],
        "source_url": row["source_url"],
        "listing_page": row["listing_page"],
        "titulo": parser.title,
        "instituicao": institution,
        "instituicao_url": institution_url,
        "status_premio": status,
        "ano_premio": year,
        "resumo": _valor_secao(
            parser.sections,
            "resumo",
        ),
        "objetivo": _valor_secao(
            parser.sections,
            "objetivo",
        ),
        "objetivos_especificos": (
            _valor_secao(
                parser.sections,
                "objetivos_especificos",
            )
        ),
        "problema_solucionado": (
            _valor_secao(
                parser.sections,
                "problema_solucionado",
            )
        ),
        "descricao": _valor_secao(
            parser.sections,
            "descricao",
        ),
        "recursos_necessarios": (
            _valor_secao(
                parser.sections,
                "recursos_necessarios",
            )
        ),
        "resultados_alcancados": (
            _valor_secao(
                parser.sections,
                "resultados_alcancados",
            )
        ),
        "publico_atendido": "; ".join(
            parser.audience
        ),
    }

    themes = []

    for item in _links_multivalorados(
        parser.links,
        "/tecnologia-social/tema/",
    ):
        themes.append(
            {
                "slug": row["slug"],
                "tema": item["name"],
                "tema_url": item["url"],
            }
        )

    ods = []

    for item in _links_multivalorados(
        parser.links,
        "/tecnologia-social/ods/",
    ):
        ods.append(
            {
                "slug": row["slug"],
                "ods": item["name"],
                "ods_url": item["url"],
            }
        )

    publics = [
        {
            "slug": row["slug"],
            "publico": value,
        }
        for value in parser.audience
    ]

    return (
        technology,
        themes,
        ods,
        publics,
    )


def salvar_csv(
    rows: list[dict[str, str]],
    path: Path,
    fieldnames: list[str],
) -> None:
    """Salva registros em CSV UTF-8."""

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(rows)


def gerar_silver_transforma(
    reference: int = 20260927,
    source: TransformaSource | None = None,
    silver_root: Path | str = "data/silver",
) -> tuple[
    Path,
    Path,
    Path,
    Path,
    Path,
]:
    """Gera os datasets Silver do Transforma!."""

    if source is None:
        source = TransformaSource()

    technologies: list[
        dict[str, str]
    ] = []

    themes: list[
        dict[str, str]
    ] = []

    ods: list[
        dict[str, str]
    ] = []

    publics: list[
        dict[str, str]
    ] = []

    for row in source.read(
        reference
    ):
        (
            technology,
            row_themes,
            row_ods,
            row_publics,
        ) = extrair_tecnologia(
            row
        )

        technologies.append(
            technology
        )

        themes.extend(
            row_themes
        )

        ods.extend(
            row_ods
        )

        publics.extend(
            row_publics
        )

    if not technologies:
        raise ValueError(
            "A fonte Transforma! não possui "
            "registros disponíveis."
        )

    slugs = [
        row["slug"]
        for row in technologies
    ]

    if any(
        not slug
        for slug in slugs
    ):
        raise ValueError(
            "Foram encontrados registros "
            "sem slug."
        )

    if len(slugs) != len(set(slugs)):
        raise ValueError(
            "Foram encontrados slugs "
            "duplicados."
        )

    output_dir = (
        Path(silver_root)
        / "fbb"
        / "transforma"
        / str(reference)
    )

    technologies_path = (
        output_dir
        / "tecnologias.csv"
    )

    themes_path = (
        output_dir
        / "tecnologias_temas.csv"
    )

    ods_path = (
        output_dir
        / "tecnologias_ods.csv"
    )

    publics_path = (
        output_dir
        / "tecnologias_publicos.csv"
    )

    metadata_path = (
        output_dir
        / "metadata.json"
    )

    salvar_csv(
        technologies,
        technologies_path,
        TECNOLOGIAS_FIELDS,
    )

    salvar_csv(
        themes,
        themes_path,
        [
            "slug",
            "tema",
            "tema_url",
        ],
    )

    salvar_csv(
        ods,
        ods_path,
        [
            "slug",
            "ods",
            "ods_url",
        ],
    )

    salvar_csv(
        publics,
        publics_path,
        [
            "slug",
            "publico",
        ],
    )

    metadata = {
        "source": (
            "Fundação Banco do Brasil "
            "- Transforma!"
        ),
        "dataset": "tecnologias_sociais",
        "layer": "silver",
        "snapshot_reference": reference,
        "generated_at": (
            datetime.now(UTC).isoformat()
        ),
        "format": "csv",
        "encoding": "utf-8",
        "datasets": {
            "tecnologias": {
                "file": (
                    technologies_path.name
                ),
                "records": (
                    len(technologies)
                ),
                "unique_slugs": (
                    len(set(slugs))
                ),
                "missing_titulo": sum(
                    not row["titulo"]
                    for row in technologies
                ),
                "missing_instituicao": sum(
                    not row["instituicao"]
                    for row in technologies
                ),
                "missing_status_premio": sum(
                    not row["status_premio"]
                    for row in technologies
                ),
                "missing_ano_premio": sum(
                    not row["ano_premio"]
                    for row in technologies
                ),
                "with_objetivo": sum(
                    bool(row["objetivo"])
                    for row in technologies
                ),
                "with_objetivos_especificos": sum(
                    bool(
                        row[
                            "objetivos_especificos"
                        ]
                    )
                    for row in technologies
                ),
                "with_publico_atendido": sum(
                    bool(
                        row[
                            "publico_atendido"
                        ]
                    )
                    for row in technologies
                ),
            },
            "temas": {
                "file": themes_path.name,
                "records": len(themes),
            },
            "ods": {
                "file": ods_path.name,
                "records": len(ods),
            },
            "publicos": {
                "file": publics_path.name,
                "records": len(publics),
            },
        },
    }

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    with metadata_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            metadata,
            file,
            ensure_ascii=False,
            indent=2,
        )

    return (
        technologies_path,
        themes_path,
        ods_path,
        publics_path,
        metadata_path,
    )