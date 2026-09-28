from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path

GOLD_FIELDS = (
    "id_tecnologia",
    "fonte_registro",
    "ano_referencia",
    "organizacao",
    "nome_tecnologia_social",
    "status_ativa",
    "regiao_sede",
    "revs_bairro",
    "bairros_atuacao",
    "vulnerabilidade_regiao_sede",
    "publico_final",
    "categoria_instituicao",
    "categoria_tecnologia",
    "ano_inicio",
    "maturidade_anos",
    "maturidade_categoria",
    "qtd_ods",
    "ods_lista",
    "ods_dimensoes",
    "apoio_feac",
    "qtd_parceiros",
    "faixa_parceiros",
    "amplitude_territorial_qtd",
    "amplitude_territorial_cat",
    "plataforma_digital",
    "tem_site_proprio",
    "tem_presenca_digital",
    "alcance_numero",
    "alcance_unidade",
    "alcance_faixa",
    "tem_indicador_alcance",
    "modalidade_primaria",
    "modalidade_todas",
    "qtd_modalidades",
    "fase_da_vida",
    "foco_genero_mulheres",
    "foco_deficiencia",
    "foco_racial",
    "foco_lgbtqia",
    "foco_situacao_rua",
    "foco_migrantes",
    "qtd_recortes_especificos",
    "grau_conexoes",
    "papel_na_rede",
    "indice_dependencia_feac",
    "indice_articulacao_rede",
    "indice_presenca_digital",
    "indice_amplitude_tematica",
    "indice_consolidacao",
    "cluster_id",
    "arquetipo",
    "completude_cadastro",
    "desc_tecnologia",
    "palavras_chave_tec",
)


SOURCE_ANALYTICAL_FIELDS = (
    "grau_conexoes",
    "papel_na_rede",
    "indice_dependencia_feac",
    "indice_articulacao_rede",
    "indice_presenca_digital",
    "indice_amplitude_tematica",
    "indice_consolidacao",
    "cluster_id",
    "arquetipo",
    "completude_cadastro",
)


def carregar_csv(
    path: Path,
) -> list[dict[str, str]]:
    """Carrega um CSV UTF-8."""

    with path.open(
        encoding="utf-8",
        newline="",
    ) as file:
        return list(csv.DictReader(file))


def construir_gold(
    rows: list[dict[str, str]],
    reference: int,
) -> list[dict[str, str]]:
    """Seleciona campos analíticos da Silver."""

    gold = []

    for row in rows:
        record = {
            "id_tecnologia": row["id_tecnologia"],
            "fonte_registro": "feac_casa_hacker",
            "ano_referencia": str(reference),
        }

        for field in GOLD_FIELDS:
            if field in record:
                continue

            record[field] = row.get(field, "")

        gold.append(record)

    gold.sort(
        key=lambda row: row["id_tecnologia"]
    )

    return gold


def gerar_gold_feac(
    reference: int = 2024,
    silver_root: Path | str = "data/silver",
    gold_root: Path | str = "data/gold",
) -> tuple[Path, Path]:
    """Gera o dataset analítico de tecnologias sociais."""

    silver_path = (
        Path(silver_root)
        / "feac"
        / "tecnologias_sociais"
        / str(reference)
        / "tecnologias.csv"
    )

    if not silver_path.exists():
        raise FileNotFoundError(
            f"Dataset Silver não encontrado: {silver_path}"
        )

    rows = carregar_csv(silver_path)

    gold = construir_gold(
        rows,
        reference,
    )

    ids = [
        row["id_tecnologia"]
        for row in gold
    ]

    if len(ids) != len(set(ids)):
        raise ValueError(
            "Foram encontrados IDs duplicados na Gold."
        )

    output_dir = (
        Path(gold_root)
        / "feac"
        / "tecnologias_sociais"
        / "consolidado"
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    dataset_path = (
        output_dir
        / "tecnologias_sociais_analitico.csv"
    )

    with dataset_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=GOLD_FIELDS,
        )

        writer.writeheader()
        writer.writerows(gold)

    metadata = {
        "source": "FEAC / Casa Hacker",
        "dataset": "tecnologias_sociais",
        "layer": "gold",
        "scope": "Campinas, SP",
        "reference_year": reference,
        "generated_at": datetime.now(UTC).isoformat(),
        "file": dataset_path.name,
        "format": "csv",
        "encoding": "utf-8",
        "records": len(gold),
        "unique_ids": len(set(ids)),
        "active_records": sum(
            row["status_ativa"] == "Sim"
            for row in gold
        ),
        "missing_nome_tecnologia": sum(
            not row["nome_tecnologia_social"]
            for row in gold
        ),
        "source_analytical_fields": list(
            SOURCE_ANALYTICAL_FIELDS
        ),
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

    return dataset_path, metadata_path