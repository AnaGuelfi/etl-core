from __future__ import annotations

import csv
import json
import re
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

PEDIDO_FIELDS = {
    "Numero_Pedido": "numero_pedido",
    "Titulo": "titulo",
    "Data_Deposito": "data_deposito",
    "Data_Publicacao": "data_publicacao",
    "Data_Fase_Nacional": "data_fase_nacional",
    "Prioridade_Unionista_Pais": "prioridade_unionista_pais",
    "Prioridade_Unionista_Numero": "prioridade_unionista_numero",
    "Prioridade_Unionista_Data": "prioridade_unionista_data",
    "Classificacao_IPC": "classificacao_ipc",
    "Depositante": "depositante",
    "Autor": "autor",
    "Procurador": "procurador",
    "Numero_Pct": "numero_pct",
    "Data_Pct": "data_pct",
    "Codigo_Wo": "codigo_wo",
    "Data_Wo": "data_wo",
}

EVENTO_FIELDS = {
    "Numero_Pedido": "numero_pedido",
    "Rpi": "rpi",
    "Data_Rpi": "data_rpi",
    "Despacho": "despacho",
    "Descricao_Despacho": "descricao_despacho",
    "Complemento_Despacho": "complemento_despacho",
}


def limpar_texto(value: str | None) -> str:
    """Remove espaços excedentes e marcações simples de quebra de linha."""
    if not value:
        return ""

    value = re.sub(r"<br\s*/?>", " ", value, flags=re.IGNORECASE)
    return " ".join(value.split())


def construir_pedidos(
    rows: Iterable[dict[str, str]],
) -> list[dict[str, str]]:
    """Consolida os registros em uma linha por número de pedido."""

    grouped: dict[str, list[dict[str, str]]] = {}

    for row in rows:
        numero = limpar_texto(row.get("Numero_Pedido"))

        if not numero:
            continue

        grouped.setdefault(numero, []).append(row)

    pedidos = []

    for numero, registros in grouped.items():
        # Data_Rpi já está no formato ISO YYYY-MM-DD.
        registros.sort(key=lambda row: row.get("Data_Rpi", ""))

        pedido = {
            silver_name: ""
            for silver_name in PEDIDO_FIELDS.values()
        }
        pedido["numero_pedido"] = numero

        # Para cada campo, mantém o último valor não vazio disponível.
        for row in registros:
            for raw_name, silver_name in PEDIDO_FIELDS.items():
                value = limpar_texto(row.get(raw_name))

                if value:
                    pedido[silver_name] = value

        pedidos.append(pedido)

    pedidos.sort(key=lambda row: row["numero_pedido"])

    return pedidos


def construir_eventos(
    rows: Iterable[dict[str, str]],
) -> list[dict[str, str]]:
    """Cria o dataset de eventos e despachos da RPI."""

    eventos = []

    for row in rows:
        evento = {
            silver_name: limpar_texto(row.get(raw_name))
            for raw_name, silver_name in EVENTO_FIELDS.items()
        }

        if evento["numero_pedido"]:
            eventos.append(evento)

    eventos.sort(
        key=lambda row: (
            row["numero_pedido"],
            row["data_rpi"],
            row["rpi"],
            row["despacho"],
        )
    )

    return eventos


def salvar_csv(
    rows: list[dict[str, str]],
    path: Path,
) -> None:
    """Salva registros da Silver como CSV UTF-8."""

    if not rows:
        raise ValueError("Não há registros para salvar.")

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=list(rows[0]),
        )

        writer.writeheader()
        writer.writerows(rows)

def salvar_metadata(
    path: Path,
    reference: int,
    source_records: int,
    pedidos: list[dict[str, str]],
    eventos: list[dict[str, str]],
) -> Path:
    """Registra metadados básicos da geração da camada Silver."""

    metadata = {
        "source": "INPI Dados Abertos",
        "dataset": "pedidos_patentes",
        "layer": "silver",
        "reference_year": reference,
        "generated_at": datetime.now(UTC).isoformat(),
        "source_records": source_records,
        "format": "csv",
        "encoding": "utf-8",
        "datasets": {
            "pedidos": {
                "file": "pedidos.csv",
                "records": len(pedidos),
                "unique_numero_pedido": len(
                    {row["numero_pedido"] for row in pedidos}
                ),
                "missing_titulo": sum(
                    not row["titulo"] for row in pedidos
                ),
                "missing_depositante": sum(
                    not row["depositante"] for row in pedidos
                ),
            },
            "eventos_rpi": {
                "file": "eventos_rpi.csv",
                "records": len(eventos),
                "missing_despacho": sum(
                    not row["despacho"] for row in eventos
                ),
            },
        },
    }

    metadata_path = path / "metadata.json"

    with metadata_path.open("w", encoding="utf-8") as file:
        json.dump(
            metadata,
            file,
            ensure_ascii=False,
            indent=2,
        )

    return metadata_path

def gerar_silver_inpi(
    rows: Iterable[dict[str, str]],
    reference: int,
    silver_root: Path | str = "data/silver",
) -> tuple[Path, Path, Path]:
    """Gera os datasets Silver do INPI."""

    rows = list(rows)

    pedidos = construir_pedidos(rows)
    eventos = construir_eventos(rows)

    base = (
        Path(silver_root)
        / "inpi"
        / "pedidos_patentes"
        / str(reference)
    )

    pedidos_path = base / "pedidos.csv"
    eventos_path = base / "eventos_rpi.csv"

    salvar_csv(pedidos, pedidos_path)
    salvar_csv(eventos, eventos_path)

    metadata_path = salvar_metadata(
        base,
        reference,
        len(rows),
        pedidos,
        eventos,
    )

    return pedidos_path, eventos_path, metadata_path