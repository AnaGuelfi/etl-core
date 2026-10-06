from __future__ import annotations

import argparse
import csv
import html
import json
import re
from collections import Counter
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

DEFAULT_INPI = Path(
    "data/gold/inpi/pedidos_patentes/"
    "consolidado/patentes_analitico.csv"
)

DEFAULT_TECNOLOGIAS_SOCIAIS = Path(
    "data/gold/tecnologias_sociais/"
    "consolidado/tecnologias_sociais.csv"
)

DEFAULT_REPORTS = Path("reports")

WIPO_TECHNOLOGY_FIELDS = {
    "1": "Máquinas e aparelhos elétricos; energia",
    "2": "Tecnologia audiovisual",
    "3": "Telecomunicações",
    "4": "Comunicação digital",
    "5": "Processos básicos de comunicação",
    "6": "Tecnologia da computação",
    "7": "Métodos de TI para gestão",
    "8": "Semicondutores",
    "9": "Óptica",
    "10": "Medição",
    "11": "Análise de materiais biológicos",
    "12": "Controle",
    "13": "Tecnologia médica",
    "14": "Química orgânica fina",
    "15": "Biotecnologia",
    "16": "Farmacêutica",
    "17": "Química macromolecular e polímeros",
    "18": "Química de alimentos",
    "19": "Química de materiais básicos",
    "20": "Materiais e metalurgia",
    "21": "Tecnologia de superfícies e revestimentos",
    "22": "Microestrutura e nanotecnologia",
    "23": "Engenharia química",
    "24": "Tecnologia ambiental",
    "25": "Manuseio",
    "26": "Máquinas-ferramenta",
    "27": "Motores, bombas e turbinas",
    "28": "Máquinas têxteis e de papel",
    "29": "Outras máquinas especiais",
    "30": "Processos e aparelhos térmicos",
    "31": "Elementos mecânicos",
    "32": "Transporte",
    "33": "Mobiliário e jogos",
    "34": "Outros bens de consumo",
    "35": "Engenharia civil",
}


IPC_SECTIONS = {
    "A": "Necessidades humanas",
    "B": "Operações e transporte",
    "C": "Química e metalurgia",
    "D": "Têxteis e papel",
    "E": "Construções fixas",
    "F": "Engenharia mecânica",
    "G": "Física",
    "H": "Eletricidade",
    "Y": "Tecnologias emergentes / marcação transversal",
}


def _sha256_file(path: Path) -> str:
    digest = sha256()

    with path.open("rb") as file:
        while chunk := file.read(1024 * 1024):
            digest.update(chunk)

    return digest.hexdigest()


def _has_text(value: str | None) -> bool:
    return bool((value or "").strip())


def _to_int(value: str | None) -> int | None:
    text = (value or "").strip()

    if not text:
        return None

    try:
        return int(float(text.replace(",", ".")))
    except ValueError:
        return None


def _to_float(value: str | None) -> float | None:
    text = (value or "").strip()

    if not text:
        return None

    try:
        return float(text.replace(",", "."))
    except ValueError:
        return None


def _truthy(value: str | None) -> bool:
    return (value or "").strip().casefold() in {
        "1",
        "true",
        "sim",
        "yes",
        "s",
        "y",
    }


def _split_multivalue(
    value: str | None,
) -> list[str]:
    text = (value or "").strip()

    if not text:
        return []

    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = json.loads(text)

            if isinstance(parsed, list):
                return [
                    str(item).strip()
                    for item in parsed
                    if str(item).strip()
                ]

        except json.JSONDecodeError:
            pass

    for separator in (
        "|",
        ";",
    ):
        if separator in text:
            return [
                item.strip()
                for item in text.split(separator)
                if item.strip()
            ]

    if "," in text:
        parts = [
            item.strip()
            for item in text.split(",")
            if item.strip()
        ]

        if len(parts) > 1:
            return parts

    return [text]


def _percentage(
    part: int,
    total: int,
) -> float:
    if total == 0:
        return 0.0

    return round(
        part / total * 100,
        2,
    )


def _counter_items(
    counter: Counter[str],
    limit: int = 12,
) -> list[dict[str, object]]:
    ordered = sorted(
        counter.items(),
        key=lambda item: (
            -item[1],
            item[0].casefold(),
        ),
    )

    return [
        {
            "label": label,
            "quantidade": count,
        }
        for label, count in ordered[:limit]
    ]


def _ipc_group(
    value: str | None,
) -> str:
    text = (value or "").strip().upper()

    if not text:
        return ""

    match = re.search(
        r"([A-HY]\d{2}[A-Z])",
        text,
    )

    if match:
        return match.group(1)

    return text[:12]

def _technology_field_label(
    value: str,
) -> str:
    code = value.strip()

    label = WIPO_TECHNOLOGY_FIELDS.get(
        code
    )

    if label:
        return f"{code} — {label}"

    return code


def _ipc_section(
    value: str | None,
) -> str:
    text = (
        value or ""
    ).strip().upper()

    if not text:
        return ""

    section = text[0]

    label = IPC_SECTIONS.get(
        section
    )

    if not label:
        return ""

    return f"{section} — {label}"

def build_inpi_indicators(
    path: Path | str,
) -> dict[str, object]:
    source = Path(path)

    total = 0
    com_titulo = 0
    com_pct = 0
    com_ipc = 0
    com_campo = 0
    com_publicacao_rpi = 0

    soma_depositantes = 0
    qtd_depositantes_validos = 0
    multiplos_depositantes = 0

    soma_inventores = 0
    qtd_inventores_validos = 0
    multiplos_inventores = 0

    soma_despachos = 0
    qtd_despachos_validos = 0

    soma_classificacoes = 0
    qtd_classificacoes_validas = 0

    anos: Counter[int] = Counter()
    campos: Counter[str] = Counter()
    ipc: Counter[str] = Counter()

    ipc_sections: Counter[str] = Counter()
    anos_fonte: list[int] = []
    anos_deposito_brutos: Counter[int] = Counter()

    with source.open(
        encoding="utf-8",
        newline="",
    ) as file:
        reader = csv.DictReader(file)

        for row in reader:
            total += 1

            if _has_text(row.get("titulo")):
                com_titulo += 1

            if _truthy(row.get("possui_pct")):
                com_pct += 1

            if _has_text(
                row.get(
                    "primeira_publicacao_rpi"
                )
            ):
                com_publicacao_rpi += 1

            source_year = _to_int(
                row.get(
                    "ano_fonte"
                )
            )

            if (
                source_year is not None
                and 1800 <= source_year <= 2100
            ):
                anos_fonte.append(
                    source_year
                )

            year = _to_int(
                row.get(
                    "ano_deposito"
                )
            )

            if (
                year is not None
                and 1800 <= year <= 2200
            ):
                anos_deposito_brutos[
                    year
                ] += 1

            campo_values = _split_multivalue(
                row.get(
                    "campo_tecnologico"
                )
            )

            if campo_values:
                com_campo += 1

                for value in campo_values:
                    campos[
                        _technology_field_label(
                            value
                        )
                    ] += 1
            ipc_value = _ipc_group(
                row.get(
                    "classificacao_ipc"
                )
            )

            ipc_section = _ipc_section(
                row.get(
                    "classificacao_ipc"
                )
            )

            if ipc_section:
                ipc_sections[
                    ipc_section
                ] += 1

            if ipc_value:
                com_ipc += 1
                ipc[ipc_value] += 1

            depositantes = _to_int(
                row.get(
                    "quantidade_depositantes"
                )
            )

            if depositantes is not None:
                soma_depositantes += depositantes
                qtd_depositantes_validos += 1

                if depositantes >= 2:
                    multiplos_depositantes += 1

            inventores = _to_int(
                row.get(
                    "quantidade_inventores"
                )
            )

            if inventores is not None:
                soma_inventores += inventores
                qtd_inventores_validos += 1

                if inventores >= 2:
                    multiplos_inventores += 1

            despachos = _to_int(
                row.get(
                    "quantidade_despachos"
                )
            )

            if despachos is not None:
                soma_despachos += despachos
                qtd_despachos_validos += 1

            classificacoes = _to_int(
                row.get(
                    "quantidade_classificacoes"
                )
            )

            if classificacoes is not None:
                soma_classificacoes += classificacoes
                qtd_classificacoes_validas += 1

            media_despachos = (
                round(
                    soma_despachos
                    / qtd_despachos_validos,
                    2,
                )
                if qtd_despachos_validos
                else 0.0
            )

            media_classificacoes = (
                round(
                    soma_classificacoes
                    / qtd_classificacoes_validas,
                    2,
                )
                if qtd_classificacoes_validas
                else 0.0
            )

    ano_limite_fonte = (
        max(anos_fonte)
        if anos_fonte
        else datetime.now(
            UTC
        ).year
    )

    anos_fora_cobertura = 0

    for year, count in (
        anos_deposito_brutos.items()
    ):
        if (
            1800
            <= year
            <= ano_limite_fonte
        ):
            anos[year] += count
        else:
            anos_fora_cobertura += count

    serie = [
        {
            "ano": year,
            "quantidade": anos[year],
        }
        for year in sorted(anos)
    ]

    media_depositantes = (
        round(
            soma_depositantes
            / qtd_depositantes_validos,
            2,
        )
        if qtd_depositantes_validos
        else 0.0
    )

    media_inventores = (
        round(
            soma_inventores
            / qtd_inventores_validos,
            2,
        )
        if qtd_inventores_validos
        else 0.0
    )

    return {
        "total_pedidos": total,
        "com_titulo": com_titulo,
        "percentual_com_titulo": _percentage(
            com_titulo,
            total,
        ),
        "com_pct": com_pct,
        "percentual_pct": _percentage(
            com_pct,
            total,
        ),
        "com_ipc": com_ipc,
        "percentual_com_ipc": _percentage(
            com_ipc,
            total,
        ),
        "com_campo_tecnologico": com_campo,
        "percentual_com_campo_tecnologico": (
            _percentage(
                com_campo,
                total,
            )
        ),
        "com_publicacao_rpi": (
            com_publicacao_rpi
        ),
        "percentual_com_publicacao_rpi": (
            _percentage(
                com_publicacao_rpi,
                total,
            )
        ),
        "media_depositantes": (
            media_depositantes
        ),
        "media_inventores": (
            media_inventores
        ),
        "ano_limite_fonte": (
            ano_limite_fonte
        ),
        "anos_deposito_fora_cobertura": (
            anos_fora_cobertura
        ),
        "serie_ano_deposito": serie,
        "top_campos_tecnologicos": (
            _counter_items(
                campos,
                limit=12,
            )
        ),
        "ipc_secoes": (
            _counter_items(
                ipc_sections,
                limit=9,
            )
        ),
        "top_ipc": (
            _counter_items(
                ipc,
                limit=12,
            )
        ),
                "multiplos_inventores": (
            multiplos_inventores
        ),
        "percentual_multiplos_inventores": (
            _percentage(
                multiplos_inventores,
                total,
            )
        ),
        "multiplos_depositantes": (
            multiplos_depositantes
        ),
        "percentual_multiplos_depositantes": (
            _percentage(
                multiplos_depositantes,
                total,
            )
        ),
        "media_despachos": (
            media_despachos
        ),
        "media_classificacoes": (
            media_classificacoes
        ),
    }


def build_social_technology_indicators(
    path: Path | str,
) -> dict[str, object]:
    source = Path(path)

    total = 0

    com_titulo = 0
    com_organizacao = 0
    com_ods = 0
    com_publicos = 0
    com_descricao = 0
    com_texto_analitico = 0

    fontes: Counter[str] = Counter()
    ods: Counter[str] = Counter()
    publicos: Counter[str] = Counter()
    temas: Counter[str] = Counter()
    modalidades: Counter[str] = Counter()
    status: Counter[str] = Counter()

    completudes: list[float] = []

    with source.open(
        encoding="utf-8",
        newline="",
    ) as file:
        reader = csv.DictReader(file)

        for row in reader:
            total += 1

            fonte = (
                row.get(
                    "fonte_registro",
                    "",
                )
                .strip()
            )

            if fonte:
                fontes[fonte] += 1

            status_value = (
                row.get(
                    "status_registro",
                    "",
                )
                .strip()
            )

            if status_value:
                status[
                    status_value
                ] += 1

            if _has_text(
                row.get("titulo")
            ):
                com_titulo += 1

            if _has_text(
                row.get(
                    "organizacao"
                )
            ):
                com_organizacao += 1

            if _has_text(
                row.get(
                    "descricao"
                )
            ):
                com_descricao += 1

            if _has_text(
                row.get(
                    "texto_analitico"
                )
            ):
                com_texto_analitico += 1

            ods_values = _split_multivalue(
                row.get(
                    "ods_nomes"
                )
            )

            if not ods_values:
                ods_values = (
                    _split_multivalue(
                        row.get(
                            "ods_codigos"
                        )
                    )
                )

            if ods_values:
                com_ods += 1

                for value in ods_values:
                    ods[value] += 1

            publico_values = (
                _split_multivalue(
                    row.get(
                        "publicos"
                    )
                )
            )

            if publico_values:
                com_publicos += 1

                for value in publico_values:
                    publicos[value] += 1

            for value in _split_multivalue(
                row.get(
                    "temas"
                )
            ):
                temas[value] += 1

            for value in _split_multivalue(
                row.get(
                    "modalidades"
                )
            ):
                modalidades[value] += 1

            completude = _to_float(
                row.get(
                    "completude_cadastro"
                )
            )

            if completude is not None:
                if 0 <= completude <= 1:
                    completude *= 100

                completudes.append(
                    completude
                )

    media_completude = (
        round(
            sum(completudes)
            / len(completudes),
            2,
        )
        if completudes
        else 0.0
    )

    return {
        "total_tecnologias_sociais": total,
        "com_titulo": com_titulo,
        "percentual_com_titulo": (
            _percentage(
                com_titulo,
                total,
            )
        ),
        "com_organizacao": com_organizacao,
        "percentual_com_organizacao": (
            _percentage(
                com_organizacao,
                total,
            )
        ),
        "com_ods": com_ods,
        "percentual_com_ods": (
            _percentage(
                com_ods,
                total,
            )
        ),
        "com_publicos": com_publicos,
        "percentual_com_publicos": (
            _percentage(
                com_publicos,
                total,
            )
        ),
        "com_descricao": com_descricao,
        "percentual_com_descricao": (
            _percentage(
                com_descricao,
                total,
            )
        ),
        "com_texto_analitico": (
            com_texto_analitico
        ),
        "percentual_com_texto_analitico": (
            _percentage(
                com_texto_analitico,
                total,
            )
        ),
        "media_completude_cadastro": (
            media_completude
        ),
        "por_fonte": _counter_items(
            fontes,
            limit=20,
        ),
        "por_status": _counter_items(
            status,
            limit=20,
        ),
        "top_ods": _counter_items(
            ods,
            limit=17,
        ),
        "top_publicos": _counter_items(
            publicos,
            limit=15,
        ),
        "top_temas": _counter_items(
            temas,
            limit=15,
        ),
        "top_modalidades": _counter_items(
            modalidades,
            limit=15,
        ),
    }


def build_indicators(
    *,
    inpi_path: Path | str = DEFAULT_INPI,
    social_technologies_path: Path | str = (
        DEFAULT_TECNOLOGIAS_SOCIAIS
    ),
) -> dict[str, object]:
    inpi = Path(inpi_path)

    technologies = Path(
        social_technologies_path
    )

    if not inpi.exists():
        raise FileNotFoundError(
            f"Gold INPI não encontrada: {inpi}"
        )

    if not technologies.exists():
        raise FileNotFoundError(
            "Gold de tecnologias sociais "
            f"não encontrada: {technologies}"
        )

    return {
        "metadata": {
            "generated_at": (
                datetime.now(
                    UTC
                ).isoformat()
            ),
            "scope": (
                "Indicadores analíticos "
                "descritivos do SAVITS"
            ),
            "methodological_note": (
                "Os indicadores são "
                "descritivos e não representam "
                "medidas causais de impacto "
                "social ou inovação frugal."
            ),
            "sources": {
                "inpi": {
                    "file": str(inpi),
                    "sha256": (
                        _sha256_file(
                            inpi
                        )
                    ),
                },
                "tecnologias_sociais": {
                    "file": str(
                        technologies
                    ),
                    "sha256": (
                        _sha256_file(
                            technologies
                        )
                    ),
                },
            },
        },
        "patentes": (
            build_inpi_indicators(
                inpi
            )
        ),
        "tecnologias_sociais": (
            build_social_technology_indicators(
                technologies
            )
        ),
    }


def _format_number(
    value: object,
) -> str:
    if isinstance(
        value,
        int,
    ):
        return (
            f"{value:,}"
            .replace(
                ",",
                ".",
            )
        )

    if isinstance(
        value,
        float,
    ):
        return (
            f"{value:,.2f}"
            .replace(
                ",",
                "X",
            )
            .replace(
                ".",
                ",",
            )
            .replace(
                "X",
                ".",
            )
        )

    return html.escape(
        str(value)
    )


def _bar_chart(
    title: str,
    items: list[dict[str, object]],
) -> str:
    if not items:
        return (
            "<section class='panel'>"
            f"<h3>{html.escape(title)}</h3>"
            "<p>Sem dados disponíveis.</p>"
            "</section>"
        )

    max_value = max(
        int(
            item["quantidade"]
        )
        for item in items
    )

    rows = []

    for item in items:
        label = html.escape(
            str(
                item["label"]
            )
        )

        value = int(
            item["quantidade"]
        )

        width = (
            value / max_value * 100
            if max_value
            else 0
        )

        rows.append(
            "<div class='bar-row'>"
            "<div class='bar-label'>"
            f"{label}"
            "</div>"
            "<div class='bar-track'>"
            "<div class='bar-fill' "
            f"style='width:{width:.2f}%'>"
            "</div>"
            "</div>"
            "<div class='bar-value'>"
            f"{_format_number(value)}"
            "</div>"
            "</div>"
        )

    return (
        "<section class='panel'>"
        f"<h3>{html.escape(title)}</h3>"
        + "".join(rows)
        + "</section>"
    )


def _line_chart(
    series: list[dict[str, object]],
) -> str:
    if not series:
        return (
            "<section class='panel wide'>"
            "<h3>Pedidos por ano de depósito</h3>"
            "<p>Sem dados disponíveis.</p>"
            "</section>"
        )

    width = 1000
    height = 280
    left = 55
    top = 20
    bottom = 45

    usable_width = width - left - 20

    usable_height = (
        height - top - bottom
    )

    values = [
        int(
            item["quantidade"]
        )
        for item in series
    ]

    maximum = max(values)

    denominator = max(
        len(series) - 1,
        1,
    )

    points = []

    for index, item in enumerate(
        series
    ):
        x = (
            left
            + usable_width
            * index
            / denominator
        )

        value = int(
            item["quantidade"]
        )

        y = (
            top
            + usable_height
            * (
                1
                - (
                    value / maximum
                    if maximum
                    else 0
                )
            )
        )

        points.append(
            f"{x:.1f},{y:.1f}"
        )

    label_indexes = {
        0,
        len(series) // 4,
        len(series) // 2,
        len(series) * 3 // 4,
        len(series) - 1,
    }

    labels = []

    for index in sorted(
        label_indexes
    ):
        item = series[index]

        x = (
            left
            + usable_width
            * index
            / denominator
        )

        labels.append(
            "<text "
            f"x='{x:.1f}' "
            f"y='{height - 12}' "
            "text-anchor='middle' "
            "class='axis-label'>"
            f"{html.escape(str(item['ano']))}"
            "</text>"
        )

    return (
        "<section class='panel wide'>"
        "<h3>Pedidos por ano de depósito</h3>"
        "<svg "
        f"viewBox='0 0 {width} {height}' "
        "role='img' "
        "aria-label='Evolução anual dos "
        "pedidos de patente'>"
        "<line "
        f"x1='{left}' y1='{top}' "
        f"x2='{left}' "
        f"y2='{top + usable_height}' "
        "class='axis'/>"
        "<line "
        f"x1='{left}' "
        f"y1='{top + usable_height}' "
        f"x2='{width - 20}' "
        f"y2='{top + usable_height}' "
        "class='axis'/>"
        "<polyline "
        "fill='none' "
        "class='trend-line' "
        f"points='{' '.join(points)}'/>"
        + "".join(labels)
        + "</svg>"
        "</section>"
    )


def _metric_card(
    title: str,
    value: object,
    subtitle: str = "",
) -> str:
    return (
        "<article class='metric'>"
        "<div class='metric-title'>"
        f"{html.escape(title)}"
        "</div>"
        "<div class='metric-value'>"
        f"{_format_number(value)}"
        "</div>"
        "<div class='metric-subtitle'>"
        f"{html.escape(subtitle)}"
        "</div>"
        "</article>"
    )


def render_dashboard(
    indicators: dict[str, object],
) -> str:
    patents = indicators[
        "patentes"
    ]

    technologies = indicators[
        "tecnologias_sociais"
    ]

    metadata = indicators[
        "metadata"
    ]

    if not isinstance(
        patents,
        dict,
    ):
        raise TypeError(
            "Indicadores de patentes inválidos."
        )

    if not isinstance(
        technologies,
        dict,
    ):
        raise TypeError(
            "Indicadores de tecnologias sociais "
            "inválidos."
        )

    if not isinstance(
        metadata,
        dict,
    ):
        raise TypeError(
            "Metadados de indicadores inválidos."
        )

    patent_cards = "".join(
        [
            _metric_card(
                "Pedidos de patentes",
                patents[
                    "total_pedidos"
                ],
                "Pedidos consolidados do INPI",
            ),
            _metric_card(
                "Via PCT",
                (
                    f"{patents['percentual_pct']}%"
                ),
                "Pedidos internacionais identificados",
            ),
            _metric_card(
                "Com múltiplos inventores",
                (
                    f"{patents['percentual_multiplos_inventores']}%"
                ),
                "Pedidos com dois ou mais inventores",
            ),
            _metric_card(
                "Com múltiplos depositantes",
                (
                    f"{patents['percentual_multiplos_depositantes']}%"
                ),
                "Pedidos com dois ou mais depositantes",
            ),
            _metric_card(
                "Média de despachos",
                patents[
                    "media_despachos"
                ],
                "Despachos registrados por pedido",
            ),
            _metric_card(
                "Média de classificações",
                patents[
                    "media_classificacoes"
                ],
                "Classificações registradas por pedido",
            ),
        ]
    )

    social_cards = "".join(
        [
            _metric_card(
                "Tecnologias sociais",
                technologies[
                    "total_tecnologias_sociais"
                ],
                "FEAC + Transforma",
            ),
            _metric_card(
                "Com ODS",
                (
                    f"{technologies['percentual_com_ods']}%"
                ),
                (
                    "Registros relacionados "
                    "a ODS"
                ),
            ),
            _metric_card(
                "Com públicos",
                (
                    f"{technologies['percentual_com_publicos']}%"
                ),
                "Públicos identificados",
            ),
            _metric_card(
                "Com organização",
                (
                    f"{technologies['percentual_com_organizacao']}%"
                ),
                "Organização identificada",
            ),
            _metric_card(
                "Texto analítico",
                (
                    f"{technologies['percentual_com_texto_analitico']}%"
                ),
                (
                    "Cobertura para análises "
                    "textuais"
                ),
            ),
            _metric_card(
                "Completude média",
                (
                    f"{technologies['media_completude_cadastro']}%"
                ),
                (
                    "Indicador de qualidade "
                    "cadastral"
                ),
            ),
        ]
    )

    patent_series = patents.get(
        "serie_ano_deposito",
        [],
    )

    patent_fields = patents.get(
        "top_campos_tecnologicos",
        [],
    )

    patent_ipc = patents.get(
        "top_ipc",
        [],
    )

    sources = technologies.get(
        "por_fonte",
        [],
    )

    ods = technologies.get(
        "top_ods",
        [],
    )

    publics = technologies.get(
        "top_publicos",
        [],
    )

    themes = technologies.get(
        "top_temas",
        [],
    )

    modalities = technologies.get(
        "top_modalidades",
        [],
    )

    statuses = technologies.get(
        "por_status",
        [],
    )

    if not isinstance(
        patent_series,
        list,
    ):
        patent_series = []

    if not isinstance(
        patent_fields,
        list,
    ):
        patent_fields = []

    if not isinstance(
        patent_ipc,
        list,
    ):
        patent_ipc = []

    if not isinstance(
        sources,
        list,
    ):
        sources = []

    if not isinstance(
        ods,
        list,
    ):
        ods = []

    if not isinstance(
        publics,
        list,
    ):
        publics = []

    if not isinstance(
        themes,
        list,
    ):
        themes = []

    if not isinstance(
        modalities,
        list,
    ):
        modalities = []

    if not isinstance(
        statuses,
        list,
    ):
        statuses = []

    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta
    name="viewport"
    content="width=device-width, initial-scale=1"
>
<title>Dashboard SAVITS</title>
<style>
:root {{
    color-scheme: light;
    --bg: #f5f7fa;
    --panel: #ffffff;
    --text: #17202a;
    --muted: #5f6b76;
    --border: #dfe5eb;
    --accent: #2457a7;
    --accent-soft: #dbe8fa;
}}

* {{
    box-sizing: border-box;
}}

body {{
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font-family:
        system-ui,
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        sans-serif;
}}

main {{
    width: min(1400px, 96%);
    margin: 0 auto;
    padding: 32px 0 64px;
}}

header {{
    margin-bottom: 28px;
}}

h1 {{
    margin-bottom: 8px;
}}

h2 {{
    margin-top: 40px;
}}

h3 {{
    margin-top: 0;
}}

.metrics {{
    display: grid;
    grid-template-columns:
        repeat(
            auto-fit,
            minmax(180px, 1fr)
        );
    gap: 14px;
}}

.metric,
.panel {{
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 12px;
    box-shadow:
        0 2px 8px rgb(0 0 0 / 4%);
}}

.metric {{
    padding: 18px;
}}

.metric-title {{
    color: var(--muted);
    font-size: 0.9rem;
}}

.metric-value {{
    margin: 7px 0;
    font-size: 1.75rem;
    font-weight: 700;
}}

.metric-subtitle {{
    color: var(--muted);
    font-size: 0.78rem;
}}

.grid {{
    display: grid;
    grid-template-columns:
        repeat(
            auto-fit,
            minmax(420px, 1fr)
        );
    gap: 18px;
    margin-top: 18px;
}}

.panel {{
    padding: 20px;
}}

.wide {{
    margin-top: 18px;
}}

.bar-row {{
    display: grid;
    grid-template-columns:
        minmax(130px, 2fr)
        4fr
        80px;
    gap: 10px;
    align-items: center;
    margin: 10px 0;
}}

.bar-label {{
    overflow-wrap: anywhere;
    font-size: 0.85rem;
}}

.bar-track {{
    height: 13px;
    overflow: hidden;
    background: var(--accent-soft);
    border-radius: 8px;
}}

.bar-fill {{
    height: 100%;
    min-width: 2px;
    background: var(--accent);
    border-radius: 8px;
}}

.bar-value {{
    text-align: right;
    font-variant-numeric:
        tabular-nums;
    font-size: 0.82rem;
}}

svg {{
    width: 100%;
    height: auto;
}}

.axis {{
    stroke: #8b98a5;
    stroke-width: 1;
}}

.trend-line {{
    stroke: var(--accent);
    stroke-width: 3;
}}

.axis-label {{
    fill: var(--muted);
    font-size: 12px;
}}

.institutional-footer {{
    margin-top: 48px;
    padding-top: 24px;
    border-top: 1px solid var(--border);
    text-align: center;
}}

.institutional-footer img {{
    width: min(100%, 1000px);
    height: auto;
    display: block;
    margin: 0 auto;
}}

@media (max-width: 650px) {{
    .grid {{
        grid-template-columns: 1fr;
    }}

    .bar-row {{
        grid-template-columns: 1fr;
    }}

    .bar-value {{
        text-align: left;
    }}
}}
</style>
</head>
<body>
<main>

<header>
<h1>Patentes e Tecnologias Sociais</h1>
</header>

<h2>Patentes — INPI</h2>

<section class="metrics">
{patent_cards}
</section>

{_line_chart(patent_series)}

<div class="grid">
{_bar_chart(
    "Principais campos tecnológicos",
    patent_fields,
)}
{_bar_chart(
    "Principais grupos IPC",
    patent_ipc,
)}
</div>

<h2>Tecnologias sociais</h2>

<section class="metrics">
{social_cards}
</section>

<div class="grid">
{_bar_chart(
    "Registros por fonte",
    sources,
)}
{_bar_chart(
    "ODS mais frequentes",
    ods,
)}
{_bar_chart(
    "Públicos mais frequentes",
    publics,
)}
{_bar_chart(
    "Temas mais frequentes",
    themes,
)}
{_bar_chart(
    "Modalidades mais frequentes",
    modalities,
)}
{_bar_chart(
    "Status dos registros",
    statuses,
)}
</div>

<footer class="institutional-footer">
<img
    src="assets/logo.jpg"
    alt="IBICT, Ministério da Ciência, Tecnologia e Inovação e Governo Federal"
>
</footer>

</main>
</body>
</html>
"""


def build_dashboard(
    *,
    inpi_path: Path | str = DEFAULT_INPI,
    social_technologies_path: Path | str = (
        DEFAULT_TECNOLOGIAS_SOCIAIS
    ),
    output_directory: Path | str = (
        DEFAULT_REPORTS
    ),
) -> tuple[Path, Path]:
    output = Path(
        output_directory
    )

    output.mkdir(
        parents=True,
        exist_ok=True,
    )

    indicators = build_indicators(
        inpi_path=inpi_path,
        social_technologies_path=(
            social_technologies_path
        ),
    )

    json_path = (
        output
        / "indicadores_savits.json"
    )

    html_path = (
        output
        / "dashboard_savits.html"
    )

    with json_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            indicators,
            file,
            ensure_ascii=False,
            indent=2,
        )

    html_path.write_text(
        render_dashboard(
            indicators
        ),
        encoding="utf-8",
    )

    return (
        json_path,
        html_path,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Gera indicadores e dashboard "
            "analítico do SAVITS."
        )
    )

    parser.add_argument(
        "--inpi",
        type=Path,
        default=DEFAULT_INPI,
    )

    parser.add_argument(
        "--tecnologias-sociais",
        type=Path,
        default=(
            DEFAULT_TECNOLOGIAS_SOCIAIS
        ),
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_REPORTS,
    )

    args = parser.parse_args()

    json_path, html_path = (
        build_dashboard(
            inpi_path=args.inpi,
            social_technologies_path=(
                args.tecnologias_sociais
            ),
            output_directory=(
                args.output
            ),
        )
    )

    print(
        "Indicadores:",
        json_path,
    )

    print(
        "Dashboard:",
        html_path,
    )


if __name__ == "__main__":
    main()