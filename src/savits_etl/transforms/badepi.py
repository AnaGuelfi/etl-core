from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path

from savits_etl.sources.badepi import BADEPISource

TABLES: dict[str, dict[str, object]] = {
    "depositos": {
        "filename": "depositos.csv",
        "fields": {
            "NO_PEDIDO": "numero_pedido",
            "ANO": "ano",
            "DT_ENTRADA_INPI": "data_entrada_inpi",
            "DT_DEPOSITO": "data_deposito",
            "NM_TITULO_PATENTE": "titulo",
        },
    },
    "depositantes": {
        "filename": "depositantes.csv",
        "fields": {
            "NO_PEDIDO": "numero_pedido",
            "NO_ORDEM": "numero_ordem",
            "NO_CNPJ_CPF": "cnpj_cpf",
            "CD_TIPO_PFPJ": "tipo_pessoa",
            "NM_COMPLET_PFPJ": "nome",
            "CD_PAIS_PFPJ": "pais",
            "CD_UF_PFPJ": "uf",
            "NM_CIDADE_PFPJ": "cidade",
            "CD_IBGE_CIDADE": "codigo_ibge_cidade",
        },
    },
    "inventores": {
        "filename": "inventores.csv",
        "fields": {
            "NO_PEDIDO": "numero_pedido",
            "NO_ORDEM": "numero_ordem",
            "CD_ANONIMA": "anonimo",
            "NO_CNPJ_CPF": "cnpj_cpf",
            "NM_COMPLET_PFPJ": "nome",
            "CD_PAIS_PFPJ": "pais",
            "CD_UF_PFPJ": "uf",
            "NM_CIDADE_PFPJ": "cidade",
            "CD_IBGE_CIDADE": "codigo_ibge_cidade",
        },
    },
    "despachos": {
        "filename": "despachos.csv",
        "fields": {
            "NO_PEDIDO": "numero_pedido",
            "NO_RPI": "numero_rpi",
            "DT_PUBLICACAO": "data_publicacao",
            "CD_DESPACH_RPI": "codigo_despacho",
            "DS_TIPO_DESPACH": "descricao_despacho",
        },
    },
    "pct": {
        "filename": "pct.csv",
        "fields": {
            "NO_PEDIDO": "numero_pedido",
            "NO_PCT": "numero_pct",
            "DT_PCT": "data_pct",
            "CD_OMPI": "codigo_ompi",
            "DT_OMPI": "data_ompi",
        },
    },
    "classificacoes": {
        "filename": "classificacoes.csv",
        "fields": {
            "NO_PEDIDO": "numero_pedido",
            "NO_ORDEM_CLASSE": "numero_ordem_classe",
            "CD_CLASSIF_CASE": "classificacao_ipc",
            "VERSION_INDICATOR_CASE": "versao_ipc",
            "CAMPO_TEC_CASE": "campo_tecnologico",
            "DT_ENTRADA_INPI": "data_entrada_inpi",
        },
    },
    "prioridades": {
        "filename": "prioridades.csv",
        "fields": {
            "NO_PEDIDO": "numero_pedido",
            "NO_PEDIDO_ORIGEM": "numero_pedido_origem",
            "DT_PEDIDO_ORIGEM": "data_pedido_origem",
            "CD_PAIS": "pais",
        },
    },
}


def transformar_linha(
    row: dict[str, str],
    fields: dict[str, str],
) -> dict[str, str]:
    """Padroniza nomes e remove espaços excedentes."""

    return {
        target: row.get(source, "").strip()
        for source, target in fields.items()
    }


def gerar_silver_badepi(
    reference: int = 11,
    source: BADEPISource | None = None,
    silver_root: Path | str = "data/silver",
) -> Path:
    """Gera as tabelas Silver da BADEPI em streaming."""

    if source is None:
        source = BADEPISource()

    output_dir = (
        Path(silver_root)
        / "inpi"
        / "badepi_patentes"
        / f"v{reference}.0"
    )

    output_dir.mkdir(parents=True, exist_ok=True)

    metadata_tables = {}

    for table, config in TABLES.items():
        fields = config["fields"]
        filename = config["filename"]

        if not isinstance(fields, dict):
            raise TypeError("Configuração de campos inválida.")

        if not isinstance(filename, str):
            raise TypeError("Nome de arquivo inválido.")

        destination = output_dir / filename

        written = 0
        skipped_invalid_number = 0

        fieldnames = list(fields.values())

        with destination.open(
            "w",
            encoding="utf-8",
            newline="",
        ) as file:
            writer = csv.DictWriter(
                file,
                fieldnames=fieldnames,
            )

            writer.writeheader()

            for raw_row in source.read(
                reference,
                table=table,
            ):
                row = transformar_linha(
                    raw_row,
                    fields,
                )

                numero = row.get("numero_pedido", "")

                if not numero or numero == "0":
                    skipped_invalid_number += 1
                    continue

                writer.writerow(row)
                written += 1

        metadata_tables[table] = {
            "file": filename,
            "records": written,
            "skipped_invalid_numero_pedido": (
                skipped_invalid_number
            ),
        }

    metadata = {
        "source": "INPI BADEPI",
        "dataset": "badepi_patentes",
        "layer": "silver",
        "version": f"{reference}.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "format": "csv",
        "encoding": "utf-8",
        "tables": metadata_tables,
    }

    metadata_path = output_dir / "metadata.json"

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

    return metadata_path