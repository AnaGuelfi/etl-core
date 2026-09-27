"""Geração da camada Gold unificada de patentes do INPI."""

from __future__ import annotations

import csv
import json
import sqlite3
from collections.abc import Iterable, Iterator
from datetime import UTC, date, datetime
from pathlib import Path

GOLD_FIELDS = (
    "numero_pedido",
    "fonte_registro",
    "ano_fonte",
    "ano_deposito",
    "data_entrada_inpi",
    "data_deposito",
    "titulo",
    "quantidade_depositantes",
    "quantidade_inventores",
    "quantidade_despachos",
    "quantidade_classificacoes",
    "quantidade_prioridades",
    "possui_pct",
    "primeira_publicacao_rpi",
    "ultima_publicacao_rpi",
    "ultimo_codigo_despacho",
    "classificacao_ipc",
    "campo_tecnologico",
)

DATE_FORMATS = (
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y",
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
)


def normalizar_data(value: str) -> str:
    """Normaliza datas conhecidas para YYYY-MM-DD."""

    value = value.strip()

    if not value:
        return ""

    date_part = value[:10]

    try:
        if "/" in date_part:
            day, month, year = date_part.split("/")

            parsed = date(
                int(year),
                int(month),
                int(day),
            )
        else:
            parsed = date.fromisoformat(date_part)

    except ValueError:
        return value

    if parsed.year <= 1:
        return ""

    return parsed.isoformat()


def ano_da_data(value: str) -> str:
    """Obtém o ano de uma data normalizada."""

    normalized = normalizar_data(value)

    if (
        len(normalized) >= 10
        and normalized[4] == "-"
        and normalized[:4].isdigit()
    ):
        return normalized[:4]

    return ""


def ler_csv(path: Path) -> Iterator[dict[str, str]]:
    """Lê um CSV UTF-8 de forma incremental."""

    with path.open(
        encoding="utf-8",
        newline="",
    ) as file:
        yield from csv.DictReader(file)


def executar_em_lote(
    connection: sqlite3.Connection,
    sql: str,
    params: Iterable[tuple[object, ...]],
) -> tuple[int, int]:
    """Executa parâmetros incrementalmente e retorna total e correspondências."""

    total = 0

    def counted_params() -> Iterator[tuple[object, ...]]:
        nonlocal total

        for item in params:
            total += 1
            yield item

    before = connection.total_changes

    connection.executemany(
        sql,
        counted_params(),
    )
    connection.commit()

    matched = connection.total_changes - before

    return total, matched


def criar_banco(connection: sqlite3.Connection) -> None:
    """Cria a estrutura temporária usada na consolidação."""

    connection.execute(
        """
        CREATE TABLE gold (
            numero_pedido TEXT PRIMARY KEY,
            fonte_registro TEXT NOT NULL,
            ano_fonte TEXT,
            ano_deposito TEXT,
            data_entrada_inpi TEXT,
            data_deposito TEXT,
            titulo TEXT,
            quantidade_depositantes INTEGER,
            quantidade_inventores INTEGER,
            quantidade_despachos INTEGER,
            quantidade_classificacoes INTEGER,
            quantidade_prioridades INTEGER,
            possui_pct INTEGER,
            primeira_publicacao_rpi TEXT,
            ultima_publicacao_rpi TEXT,
            ultimo_codigo_despacho TEXT,
            classificacao_ipc TEXT,
            campo_tecnologico TEXT
        )
        """
    )


def carregar_depositos(
    connection: sqlite3.Connection,
    path: Path,
) -> int:
    """Carrega os pedidos da BADEPI como entidade mestre."""

    def params() -> Iterator[tuple[object, ...]]:
        for row in ler_csv(path):
            data_deposito = normalizar_data(
                row["data_deposito"]
            )

            yield (
                row["numero_pedido"],
                "badepi",
                row["ano"],
                ano_da_data(data_deposito),
                normalizar_data(row["data_entrada_inpi"]),
                data_deposito,
                row["titulo"],
                0,
                0,
                0,
                0,
                0,
                0,
                "",
                "",
                "",
                "",
                "",
            )

    total, _ = executar_em_lote(
        connection,
        """
        INSERT INTO gold VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        params(),
    )

    return total


def carregar_contagem(
    connection: sqlite3.Connection,
    path: Path,
    column: str,
) -> dict[str, int]:
    """Atualiza uma contagem por pedido."""

    def params() -> Iterator[tuple[object, ...]]:
        for row in ler_csv(path):
            yield (row["numero_pedido"],)

    total, matched = executar_em_lote(
        connection,
        f"""
        UPDATE gold
        SET {column} = {column} + 1
        WHERE numero_pedido = ?
          AND fonte_registro = 'badepi'
        """,
        params(),
    )

    return {
        "records": total,
        "matched": matched,
        "orphan_records": total - matched,
    }


def carregar_pct(
    connection: sqlite3.Connection,
    path: Path,
) -> dict[str, int]:
    """Marca pedidos que possuem registro PCT."""

    def params() -> Iterator[tuple[object, ...]]:
        for row in ler_csv(path):
            yield (row["numero_pedido"],)

    total, matched = executar_em_lote(
        connection,
        """
        UPDATE gold
        SET possui_pct = 1
        WHERE numero_pedido = ?
          AND fonte_registro = 'badepi'
        """,
        params(),
    )

    return {
        "records": total,
        "matched": matched,
        "orphan_records": total - matched,
    }


def carregar_classificacoes(
    connection: sqlite3.Connection,
    path: Path,
) -> dict[str, int]:
    """Agrega classificações e seleciona a classificação de ordem 1."""

    def params() -> Iterator[tuple[object, ...]]:
        for row in ler_csv(path):
            yield (
                row["numero_ordem_classe"],
                row["classificacao_ipc"],
                row["numero_ordem_classe"],
                row["campo_tecnologico"],
                row["numero_pedido"],
            )

    total, matched = executar_em_lote(
        connection,
        """
        UPDATE gold
        SET
            quantidade_classificacoes =
                quantidade_classificacoes + 1,
            classificacao_ipc =
                CASE
                    WHEN ? = '1' THEN ?
                    ELSE classificacao_ipc
                END,
            campo_tecnologico =
                CASE
                    WHEN ? = '1' THEN ?
                    ELSE campo_tecnologico
                END
        WHERE numero_pedido = ?
          AND fonte_registro = 'badepi'
        """,
        params(),
    )

    return {
        "records": total,
        "matched": matched,
        "orphan_records": total - matched,
    }


def carregar_despachos(
    connection: sqlite3.Connection,
    path: Path,
    source: str = "badepi",
) -> dict[str, int]:
    """Agrega os eventos da RPI por pedido."""

    def params() -> Iterator[tuple[object, ...]]:
        for row in ler_csv(path):
            date_field = (
                "data_publicacao"
                if source == "badepi"
                else "data_rpi"
            )
            code_field = (
                "codigo_despacho"
                if source == "badepi"
                else "despacho"
            )

            publication_date = normalizar_data(
                row.get(date_field, "")
            )

            dispatch_code = row.get(code_field, "")

            yield (
                publication_date,
                publication_date,
                publication_date,
                publication_date,
                publication_date,
                dispatch_code,
                publication_date,
                publication_date,
                publication_date,
                row["numero_pedido"],
            )

    total, matched = executar_em_lote(
        connection,
        f"""
        UPDATE gold
        SET
            quantidade_despachos =
                quantidade_despachos + 1,

            primeira_publicacao_rpi =
                CASE
                    WHEN ? <> ''
                     AND (
                        primeira_publicacao_rpi = ''
                        OR ? < primeira_publicacao_rpi
                     )
                    THEN ?
                    ELSE primeira_publicacao_rpi
                END,

            ultimo_codigo_despacho =
                CASE
                    WHEN ? <> ''
                     AND (
                        ultima_publicacao_rpi = ''
                        OR ? >= ultima_publicacao_rpi
                     )
                    THEN ?
                    ELSE ultimo_codigo_despacho
                END,

            ultima_publicacao_rpi =
                CASE
                    WHEN ? <> ''
                     AND (
                        ultima_publicacao_rpi = ''
                        OR ? > ultima_publicacao_rpi
                     )
                    THEN ?
                    ELSE ultima_publicacao_rpi
                END

        WHERE numero_pedido = ?
          AND fonte_registro = '{source}'
        """,
        params(),
    )

    return {
        "records": total,
        "matched": matched,
        "orphan_records": total - matched,
    }

def parametros_buscaweb(
    pedidos_path: Path,
    reference: int,
) -> Iterator[tuple[object, ...]]:
    """Prepara registros complementares do BuscaWeb."""

    for row in ler_csv(pedidos_path):
        data_deposito = normalizar_data(
            row["data_deposito"]
        )

        yield (
            row["numero_pedido"],
            "buscaweb",
            str(reference),
            ano_da_data(data_deposito),
            "",
            data_deposito,
            row["titulo"],
            None,
            None,
            0,
            None,
            None,
            1 if row.get("numero_pct") else 0,
            "",
            "",
            "",
            row.get("classificacao_ipc", ""),
            "",
        )

def incorporar_buscaweb(
    connection: sqlite3.Connection,
    silver_root: Path,
    references: tuple[int, ...],
) -> int:
    """Inclui apenas pedidos do BuscaWeb ausentes da BADEPI."""

    inserted = 0

    for reference in references:
        base = (
            silver_root
            / "inpi"
            / "pedidos_patentes"
            / str(reference)
        )

        pedidos_path = base / "pedidos.csv"

        before = connection.total_changes

        connection.executemany(
            """
            INSERT OR IGNORE INTO gold VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            parametros_buscaweb(
                pedidos_path,
                reference,
            ),
        )

        connection.commit()

        inserted += connection.total_changes - before

    return inserted


def atualizar_eventos_buscaweb(
    connection: sqlite3.Connection,
    silver_root: Path,
    references: tuple[int, ...],
) -> dict[str, int]:
    """Agrega eventos do BuscaWeb apenas para registros complementares."""

    total = 0
    matched = 0

    for reference in references:
        path = (
            silver_root
            / "inpi"
            / "pedidos_patentes"
            / str(reference)
            / "eventos_rpi.csv"
        )

        result = carregar_despachos(
            connection,
            path,
            source="buscaweb",
        )

        total += result["records"]
        matched += result["matched"]

    return {
        "records": total,
        "matched": matched,
        "orphan_records": total - matched,
    }


def escrever_gold(
    connection: sqlite3.Connection,
    destination: Path,
) -> int:
    """Exporta o banco temporário para CSV."""

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    cursor = connection.execute(
        f"""
        SELECT {", ".join(GOLD_FIELDS)}
        FROM gold
        ORDER BY numero_pedido
        """
    )

    with destination.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        writer = csv.writer(file)

        writer.writerow(GOLD_FIELDS)

        count = 0

        for row in cursor:
            writer.writerow(row)
            count += 1

    return count


def gerar_gold_inpi(
    badepi_version: int = 11,
    buscaweb_references: tuple[int, ...] = (
        2018,
        2019,
        2020,
    ),
    silver_root: Path | str = "data/silver",
    gold_root: Path | str = "data/gold",
) -> tuple[Path, Path]:
    """Gera a Gold única de patentes do INPI."""

    silver_root = Path(silver_root)
    gold_root = Path(gold_root)

    badepi_base = (
        silver_root
        / "inpi"
        / "badepi_patentes"
        / f"v{badepi_version}.0"
    )

    output_dir = (
        gold_root
        / "inpi"
        / "pedidos_patentes"
        / "consolidado"
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    database_path = output_dir / ".gold_inpi.sqlite"
    dataset_path = output_dir / "patentes_analitico.csv"
    metadata_path = output_dir / "metadata.json"

    database_path.unlink(missing_ok=True)

    connection = sqlite3.connect(database_path)

    try:
        connection.execute(
            "PRAGMA journal_mode = MEMORY"
        )
        connection.execute(
            "PRAGMA synchronous = OFF"
        )
        connection.execute(
            "PRAGMA temp_store = MEMORY"
        )

        criar_banco(connection)

        badepi_records = carregar_depositos(
            connection,
            badepi_base / "depositos.csv",
        )

        integrity = {}

        integrity["depositantes"] = carregar_contagem(
            connection,
            badepi_base / "depositantes.csv",
            "quantidade_depositantes",
        )

        integrity["inventores"] = carregar_contagem(
            connection,
            badepi_base / "inventores.csv",
            "quantidade_inventores",
        )

        integrity["despachos"] = carregar_despachos(
            connection,
            badepi_base / "despachos.csv",
        )

        integrity["pct"] = carregar_pct(
            connection,
            badepi_base / "pct.csv",
        )

        integrity["classificacoes"] = (
            carregar_classificacoes(
                connection,
                badepi_base / "classificacoes.csv",
            )
        )

        integrity["prioridades"] = carregar_contagem(
            connection,
            badepi_base / "prioridades.csv",
            "quantidade_prioridades",
        )

        buscaweb_inserted = incorporar_buscaweb(
            connection,
            silver_root,
            buscaweb_references,
        )

        buscaweb_events = atualizar_eventos_buscaweb(
            connection,
            silver_root,
            buscaweb_references,
        )

        records = escrever_gold(
            connection,
            dataset_path,
        )

        missing_title = connection.execute(
            """
            SELECT COUNT(*)
            FROM gold
            WHERE titulo = ''
            """
        ).fetchone()[0]

        source_counts = {
            row[0]: row[1]
            for row in connection.execute(
                """
                SELECT fonte_registro, COUNT(*)
                FROM gold
                GROUP BY fonte_registro
                ORDER BY fonte_registro
                """
            )
        }

        metadata = {
            "source": "INPI",
            "dataset": "pedidos_patentes",
            "layer": "gold",
            "scope": "consolidated",
            "generated_at": datetime.now(UTC).isoformat(),
            "file": dataset_path.name,
            "format": "csv",
            "encoding": "utf-8",
            "records": records,
            "unique_numero_pedido": records,
            "source_records": source_counts,
            "badepi_version": f"{badepi_version}.0",
            "badepi_master_records": badepi_records,
            "buscaweb_complementary_records": (
                buscaweb_inserted
            ),
            "badepi_relational_integrity": integrity,
            "buscaweb_event_processing": {
                "records_scanned": buscaweb_events["records"],
                "matched_complementary_records": (
                    buscaweb_events["matched"]
                ),
                "ignored_non_complementary_records": (
                    buscaweb_events["orphan_records"]
                ),
            },
            "missing_titulo": missing_title,
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

    finally:
        connection.close()
        database_path.unlink(missing_ok=True)

    return dataset_path, metadata_path