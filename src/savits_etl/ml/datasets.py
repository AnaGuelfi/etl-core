from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from savits_etl.analytics.indicadores import (
    IPC_SECTIONS,
    WIPO_TECHNOLOGY_FIELDS,
)

DEFAULT_INPI = Path(
    "data/gold/inpi/pedidos_patentes/"
    "consolidado/patentes_analitico.csv"
)

DEFAULT_TECNOLOGIAS_SOCIAIS = Path(
    "data/gold/tecnologias_sociais/"
    "consolidado/tecnologias_sociais.csv"
)

DEFAULT_OUTPUT = Path(
    "data/gold/ml"
)


PATENT_FIELDS = [
    "numero_pedido",
    "ano_deposito",
    "ano_deposito_valido",
    "quantidade_depositantes",
    "quantidade_inventores",
    "quantidade_despachos",
    "quantidade_classificacoes",
    "quantidade_prioridades",
    "possui_pct",
    "classificacao_ipc",
    "ipc_subclasse",
    "ipc_secao",
    "ipc_secao_nome",
    "campo_tecnologico",
    "campo_tecnologico_principal",
    "campo_tecnologico_nome",
]


SOCIAL_TECHNOLOGY_FIELDS = [
    "id_registro",
    "fonte_registro",
    "ano_inicio",
    "ano_premio",
    "tipo_status",
    "status_registro",
    "qtd_ods",
    "ods_codigos",
    "qtd_publicos",
    "publicos",
    "qtd_temas",
    "temas",
    "qtd_modalidades",
    "modalidades",
    "completude_cadastro",
    "tem_descricao",
    "tem_texto_analitico",
]


def _sha256_file(
    path: Path,
) -> str:
    digest = sha256()

    with path.open("rb") as file:
        while chunk := file.read(
            1024 * 1024
        ):
            digest.update(chunk)

    return digest.hexdigest()


def _text(
    value: object,
) -> str:
    if value is None:
        return ""

    return str(value).strip()


def _integer(
    value: object,
) -> int | None:
    text = _text(value)

    if not text:
        return None

    try:
        return int(
            float(
                text.replace(
                    ",",
                    ".",
                )
            )
        )
    except ValueError:
        return None


def _number_or_blank(
    value: object,
) -> int | str:
    parsed = _integer(value)

    if parsed is None:
        return ""

    return parsed


def _binary(
    value: object,
) -> int:
    text = (
        _text(value)
        .casefold()
    )

    return int(
        text
        in {
            "1",
            "true",
            "sim",
            "s",
            "yes",
            "y",
        }
    )


def _split_multivalue(
    value: object,
) -> list[str]:
    text = _text(value)

    if not text:
        return []

    if (
        text.startswith("[")
        and text.endswith("]")
    ):
        try:
            parsed = json.loads(
                text
            )

            if isinstance(
                parsed,
                list,
            ):
                return [
                    _text(item)
                    for item in parsed
                    if _text(item)
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
                for item in text.split(
                    separator
                )
                if item.strip()
            ]

    return [text]


def _ipc_subclass(
    value: object,
) -> str:
    text = (
        _text(value)
        .upper()
    )

    if not text:
        return ""

    match = re.search(
        r"([A-HY]\d{2}[A-Z])",
        text,
    )

    if match:
        return match.group(1)

    return ""


def _ipc_section(
    subclass: str,
) -> tuple[str, str]:
    if not subclass:
        return "", ""

    code = subclass[0]

    return (
        code,
        IPC_SECTIONS.get(
            code,
            "",
        ),
    )


def _technology_field_code(
    value: object,
) -> str:
    values = _split_multivalue(
        value
    )

    if not values:
        return ""

    for item in values:
        match = re.search(
            r"\b([1-9]|[12]\d|3[0-5])\b",
            item,
        )

        if match:
            return match.group(1)

    return ""


def _normalize_completeness(
    value: object,
) -> float | str:
    text = _text(value)

    if not text:
        return ""

    try:
        number = float(
            text.replace(
                ",",
                ".",
            )
        )
    except ValueError:
        return ""

    if 0 <= number <= 1:
        number *= 100

    return round(
        number,
        2,
    )


def _max_source_year(
    path: Path,
) -> int:
    maximum = 0

    with path.open(
        encoding="utf-8",
        newline="",
    ) as file:
        reader = csv.DictReader(
            file
        )

        for row in reader:
            value = _integer(
                row.get(
                    "ano_fonte"
                )
            )

            if (
                value is not None
                and 1800 <= value <= 2100
            ):
                maximum = max(
                    maximum,
                    value,
                )

    if maximum:
        return maximum

    return datetime.now(
        UTC
    ).year


def build_patent_ml_dataset(
    source_path: Path | str,
    output_path: Path | str,
) -> int:
    source = Path(
        source_path
    )

    output = Path(
        output_path
    )

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    maximum_year = (
        _max_source_year(
            source
        )
    )

    count = 0

    with (
        source.open(
            encoding="utf-8",
            newline="",
        ) as input_file,
        output.open(
            "w",
            encoding="utf-8",
            newline="",
        ) as output_file,
    ):
        reader = csv.DictReader(
            input_file
        )

        writer = csv.DictWriter(
            output_file,
            fieldnames=PATENT_FIELDS,
        )

        writer.writeheader()

        for row in reader:
            raw_year = _integer(
                row.get(
                    "ano_deposito"
                )
            )

            valid_year = (
                raw_year is not None
                and 1800
                <= raw_year
                <= maximum_year
            )

            subclass = _ipc_subclass(
                row.get(
                    "classificacao_ipc"
                )
            )

            (
                ipc_section,
                ipc_section_name,
            ) = _ipc_section(
                subclass
            )

            technology_code = (
                _technology_field_code(
                    row.get(
                        "campo_tecnologico"
                    )
                )
            )

            technology_name = (
                WIPO_TECHNOLOGY_FIELDS.get(
                    technology_code,
                    "",
                )
            )

            writer.writerow(
                {
                    "numero_pedido": _text(
                        row.get(
                            "numero_pedido"
                        )
                    ),
                    "ano_deposito": (
                        raw_year
                        if valid_year
                        else ""
                    ),
                    "ano_deposito_valido": int(
                        valid_year
                    ),
                    "quantidade_depositantes": (
                        _number_or_blank(
                            row.get(
                                "quantidade_depositantes"
                            )
                        )
                    ),
                    "quantidade_inventores": (
                        _number_or_blank(
                            row.get(
                                "quantidade_inventores"
                            )
                        )
                    ),
                    "quantidade_despachos": (
                        _number_or_blank(
                            row.get(
                                "quantidade_despachos"
                            )
                        )
                    ),
                    "quantidade_classificacoes": (
                        _number_or_blank(
                            row.get(
                                "quantidade_classificacoes"
                            )
                        )
                    ),
                    "quantidade_prioridades": (
                        _number_or_blank(
                            row.get(
                                "quantidade_prioridades"
                            )
                        )
                    ),
                    "possui_pct": _binary(
                        row.get(
                            "possui_pct"
                        )
                    ),
                    "classificacao_ipc": (
                        _text(
                            row.get(
                                "classificacao_ipc"
                            )
                        )
                    ),
                    "ipc_subclasse": (
                        subclass
                    ),
                    "ipc_secao": (
                        ipc_section
                    ),
                    "ipc_secao_nome": (
                        ipc_section_name
                    ),
                    "campo_tecnologico": (
                        _text(
                            row.get(
                                "campo_tecnologico"
                            )
                        )
                    ),
                    "campo_tecnologico_principal": (
                        technology_code
                    ),
                    "campo_tecnologico_nome": (
                        technology_name
                    ),
                }
            )

            count += 1

    return count


def build_social_technology_ml_dataset(
    source_path: Path | str,
    output_path: Path | str,
    text_output_path: Path | str,
) -> tuple[int, int]:
    source = Path(
        source_path
    )

    output = Path(
        output_path
    )

    text_output = Path(
        text_output_path
    )

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    text_output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    structured_count = 0
    text_count = 0

    with (
        source.open(
            encoding="utf-8",
            newline="",
        ) as input_file,
        output.open(
            "w",
            encoding="utf-8",
            newline="",
        ) as output_file,
        text_output.open(
            "w",
            encoding="utf-8",
        ) as text_file,
    ):
        reader = csv.DictReader(
            input_file
        )

        writer = csv.DictWriter(
            output_file,
            fieldnames=(
                SOCIAL_TECHNOLOGY_FIELDS
            ),
        )

        writer.writeheader()

        for row in reader:
            themes = _split_multivalue(
                row.get(
                    "temas"
                )
            )

            modalities = (
                _split_multivalue(
                    row.get(
                        "modalidades"
                    )
                )
            )

            description = _text(
                row.get(
                    "descricao"
                )
            )

            analytical_text = _text(
                row.get(
                    "texto_analitico"
                )
            )

            writer.writerow(
                {
                    "id_registro": _text(
                        row.get(
                            "id_registro"
                        )
                    ),
                    "fonte_registro": _text(
                        row.get(
                            "fonte_registro"
                        )
                    ),
                    "ano_inicio": (
                        _number_or_blank(
                            row.get(
                                "ano_inicio"
                            )
                        )
                    ),
                    "ano_premio": (
                        _number_or_blank(
                            row.get(
                                "ano_premio"
                            )
                        )
                    ),
                    "tipo_status": _text(
                        row.get(
                            "tipo_status"
                        )
                    ),
                    "status_registro": _text(
                        row.get(
                            "status_registro"
                        )
                    ),
                    "qtd_ods": (
                        _number_or_blank(
                            row.get(
                                "qtd_ods"
                            )
                        )
                    ),
                    "ods_codigos": _text(
                        row.get(
                            "ods_codigos"
                        )
                    ),
                    "qtd_publicos": (
                        _number_or_blank(
                            row.get(
                                "qtd_publicos"
                            )
                        )
                    ),
                    "publicos": _text(
                        row.get(
                            "publicos"
                        )
                    ),
                    "qtd_temas": len(
                        themes
                    ),
                    "temas": _text(
                        row.get(
                            "temas"
                        )
                    ),
                    "qtd_modalidades": len(
                        modalities
                    ),
                    "modalidades": _text(
                        row.get(
                            "modalidades"
                        )
                    ),
                    "completude_cadastro": (
                        _normalize_completeness(
                            row.get(
                                "completude_cadastro"
                            )
                        )
                    ),
                    "tem_descricao": int(
                        bool(
                            description
                        )
                    ),
                    "tem_texto_analitico": int(
                        bool(
                            analytical_text
                        )
                    ),
                }
            )

            structured_count += 1

            text_record = {
                "id_registro": _text(
                    row.get(
                        "id_registro"
                    )
                ),
                "fonte_registro": _text(
                    row.get(
                        "fonte_registro"
                    )
                ),
                "titulo": _text(
                    row.get(
                        "titulo"
                    )
                ),
                "organizacao": _text(
                    row.get(
                        "organizacao"
                    )
                ),
                "descricao": description,
                "texto_analitico": (
                    analytical_text
                ),
            }

            text_file.write(
                json.dumps(
                    text_record,
                    ensure_ascii=False,
                )
            )

            text_file.write(
                "\n"
            )

            text_count += 1

    return (
        structured_count,
        text_count,
    )


def build_ml_datasets(
    *,
    inpi_path: Path | str = DEFAULT_INPI,
    social_technologies_path: Path | str = (
        DEFAULT_TECNOLOGIAS_SOCIAIS
    ),
    output_directory: Path | str = (
        DEFAULT_OUTPUT
    ),
) -> dict[str, Path]:
    inpi = Path(
        inpi_path
    )

    social = Path(
        social_technologies_path
    )

    output = Path(
        output_directory
    )

    if not inpi.exists():
        raise FileNotFoundError(
            f"Gold INPI não encontrada: {inpi}"
        )

    if not social.exists():
        raise FileNotFoundError(
            "Gold de tecnologias sociais "
            f"não encontrada: {social}"
        )

    output.mkdir(
        parents=True,
        exist_ok=True,
    )

    patent_path = (
        output
        / "patentes_ml.csv"
    )

    social_path = (
        output
        / "tecnologias_sociais_ml.csv"
    )

    text_path = (
        output
        / "tecnologias_sociais_textos.jsonl"
    )

    metadata_path = (
        output
        / "metadata.json"
    )

    patent_count = (
        build_patent_ml_dataset(
            inpi,
            patent_path,
        )
    )

    (
        social_count,
        text_count,
    ) = (
        build_social_technology_ml_dataset(
            social,
            social_path,
            text_path,
        )
    )

    metadata = {
        "generated_at": (
            datetime.now(
                UTC
            ).isoformat()
        ),
        "purpose": (
            "Datasets derivados das Golds "
            "oficiais do SAVITS para uso "
            "em modelagem exploratória, "
            "aprendizado de máquina e "
            "análise textual."
        ),
        "target_variable": None,
        "methodological_note": (
            "Nenhuma variável-alvo de impacto "
            "social ou inovação frugal foi "
            "criada. A definição e validação "
            "de targets deve ocorrer em etapa "
            "metodológica posterior."
        ),
        "sources": {
            "patentes_inpi": {
                "path": str(
                    inpi
                ),
                "sha256": (
                    _sha256_file(
                        inpi
                    )
                ),
            },
            "tecnologias_sociais": {
                "path": str(
                    social
                ),
                "sha256": (
                    _sha256_file(
                        social
                    )
                ),
            },
        },
        "outputs": {
            "patentes_ml": {
                "path": str(
                    patent_path
                ),
                "records": (
                    patent_count
                ),
                "fields": (
                    PATENT_FIELDS
                ),
                "sha256": (
                    _sha256_file(
                        patent_path
                    )
                ),
            },
            "tecnologias_sociais_ml": {
                "path": str(
                    social_path
                ),
                "records": (
                    social_count
                ),
                "fields": (
                    SOCIAL_TECHNOLOGY_FIELDS
                ),
                "sha256": (
                    _sha256_file(
                        social_path
                    )
                ),
            },
            "tecnologias_sociais_textos": {
                "path": str(
                    text_path
                ),
                "records": (
                    text_count
                ),
                "format": "jsonl",
                "sha256": (
                    _sha256_file(
                        text_path
                    )
                ),
            },
        },
    }

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

    return {
        "patentes_ml": (
            patent_path
        ),
        "tecnologias_sociais_ml": (
            social_path
        ),
        "tecnologias_sociais_textos": (
            text_path
        ),
        "metadata": (
            metadata_path
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Prepara datasets derivados "
            "das Golds do SAVITS para ML."
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
        default=DEFAULT_OUTPUT,
    )

    args = parser.parse_args()

    paths = build_ml_datasets(
        inpi_path=args.inpi,
        social_technologies_path=(
            args.tecnologias_sociais
        ),
        output_directory=(
            args.output
        ),
    )

    print(
        "Datasets preparados:"
    )

    for name, path in (
        paths.items()
    ):
        print(
            f"  {name}: {path}"
        )


if __name__ == "__main__":
    main()