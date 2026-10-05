from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path


def _sha256_file(
    path: Path,
) -> str:
    digest = sha256()

    with path.open(
        "rb",
    ) as file:
        while chunk := file.read(
            1024 * 1024
        ):
            digest.update(
                chunk
            )

    return digest.hexdigest()


def build_inpi_epo_gold(
    *,
    inpi_path: Path | str,
    epo_path: Path | str,
    output_path: Path | str,
    metadata_path: Path | str,
    only_epo_records: bool = False,
) -> tuple[Path, Path]:
    """
    Integra a Gold INPI com o enriquecimento EPO.

    A entidade principal permanece sendo o pedido INPI.
    Nenhum campo INPI é sobrescrito.

    only_epo_records=True:
        gera somente pedidos presentes na Gold EPO,
        útil para diagnóstico.

    only_epo_records=False:
        gera todos os pedidos INPI,
        enriquecendo quando houver registro EPO.
    """

    inpi_file = Path(
        inpi_path
    )

    epo_file = Path(
        epo_path
    )

    output_file = Path(
        output_path
    )

    metadata_file = Path(
        metadata_path
    )

    if not inpi_file.exists():
        raise FileNotFoundError(
            "Gold INPI não encontrada: "
            f"{inpi_file}"
        )

    if not epo_file.exists():
        raise FileNotFoundError(
            "Gold EPO não encontrada: "
            f"{epo_file}"
        )

    with epo_file.open(
        encoding="utf-8",
        newline="",
    ) as file:
        reader = csv.DictReader(
            file
        )

        epo_rows = {
            row["numero_pedido"]: row
            for row in reader
            if row.get(
                "numero_pedido",
                ""
            )
        }

    if not epo_rows:
        raise ValueError(
            "Gold EPO sem registros."
        )

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    metadata_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    inpi_records = 0
    output_records = 0
    enriched_records = 0
    matched_records = 0
    no_bibliography_records = 0

    epo_fields: list[str] = []

    first_epo = next(
        iter(
            epo_rows.values()
        )
    )

    epo_fields = [
        field
        for field in first_epo
        if field != "numero_pedido"
    ]

    with inpi_file.open(
        encoding="utf-8",
        newline="",
    ) as source:
        reader = csv.DictReader(
            source
        )

        if reader.fieldnames is None:
            raise ValueError(
                "Gold INPI sem cabeçalho."
            )

        inpi_fields = list(
            reader.fieldnames
        )

        collisions = (
            set(inpi_fields)
            & set(epo_fields)
        )

        if collisions:
            raise ValueError(
                "Colisão de campos INPI/EPO: "
                + ", ".join(
                    sorted(
                        collisions
                    )
                )
            )

        fieldnames = (
            inpi_fields
            + epo_fields
        )

        temporary = (
            output_file.with_suffix(
                output_file.suffix
                + ".part"
            )
        )

        try:
            with temporary.open(
                "w",
                encoding="utf-8",
                newline="",
            ) as destination:
                writer = csv.DictWriter(
                    destination,
                    fieldnames=fieldnames,
                )

                writer.writeheader()

                for inpi_row in reader:
                    inpi_records += 1

                    numero_pedido = (
                        inpi_row.get(
                            "numero_pedido",
                            "",
                        )
                        .strip()
                    )

                    epo_row = (
                        epo_rows.get(
                            numero_pedido
                        )
                    )

                    if (
                        only_epo_records
                        and epo_row is None
                    ):
                        continue

                    output_row = dict(
                        inpi_row
                    )

                    if epo_row is None:
                        for field in epo_fields:
                            output_row[
                                field
                            ] = ""

                    else:
                        enriched_records += 1

                        for field in epo_fields:
                            output_row[
                                field
                            ] = epo_row.get(
                                field,
                                "",
                            )

                        status = epo_row.get(
                            "epo_status",
                            "",
                        )

                        if status == "matched":
                            matched_records += 1

                        elif (
                            status
                            == "no_bibliography"
                        ):
                            (
                                no_bibliography_records
                            ) += 1

                    writer.writerow(
                        output_row
                    )

                    output_records += 1

            temporary.replace(
                output_file
            )

        finally:
            if temporary.exists():
                temporary.unlink()

    missing_in_inpi = sorted(
        set(
            epo_rows
        )
        - _read_inpi_identifiers(
            inpi_file
        )
    )

    metadata = {
        "source": (
            "INPI Gold enriquecida "
            "com European Patent "
            "Office OPS"
        ),
        "layer": "gold",
        "dataset": (
            "patentes_inpi_epo"
        ),
        "generated_at": datetime.now(
            UTC
        ).isoformat(),
        "mode": (
            "epo_records_only"
            if only_epo_records
            else "all_inpi"
        ),
        "inpi_records": (
            inpi_records
        ),
        "epo_records": len(
            epo_rows
        ),
        "output_records": (
            output_records
        ),
        "enriched_records": (
            enriched_records
        ),
        "matched_records": (
            matched_records
        ),
        "no_bibliography_records": (
            no_bibliography_records
        ),
        "epo_records_missing_in_inpi": (
            len(
                missing_in_inpi
            )
        ),
        "missing_in_inpi": (
            missing_in_inpi
        ),
        "input": {
            "inpi_file": str(
                inpi_file
            ),
            "inpi_sha256": (
                _sha256_file(
                    inpi_file
                )
            ),
            "epo_file": str(
                epo_file
            ),
            "epo_sha256": (
                _sha256_file(
                    epo_file
                )
            ),
        },
        "output": {
            "file": str(
                output_file
            ),
            "sha256": (
                _sha256_file(
                    output_file
                )
            ),
        },
        "integration_policy": {
            "primary_entity": (
                "numero_pedido INPI"
            ),
            "inpi_fields_overwritten": (
                False
            ),
            "epo_prefix": "epo_",
            "rpi_publication_semantics": (
                "Campos de publicação RPI "
                "do INPI são preservados e "
                "não são substituídos por "
                "datas bibliográficas EPO."
            ),
        },
    }

    with metadata_file.open(
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
        output_file,
        metadata_file,
    )


def _read_inpi_identifiers(
    path: Path,
) -> set[str]:
    identifiers = set()

    with path.open(
        encoding="utf-8",
        newline="",
    ) as file:
        reader = csv.DictReader(
            file
        )

        for row in reader:
            numero = (
                row.get(
                    "numero_pedido",
                    "",
                )
                .strip()
            )

            if numero:
                identifiers.add(
                    numero
                )

    return identifiers