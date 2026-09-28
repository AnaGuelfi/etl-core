from __future__ import annotations

import csv
import json
from collections.abc import Iterator
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import ClassVar
from urllib.request import Request, urlopen

from savits_etl.sources.base import BaseSource


class FEACSource(BaseSource):
    """Acesso ao Banco de Tecnologias Sociais da FEAC."""

    name = "FEAC / Casa Hacker"
    dataset = "tecnologias_sociais"
    encoding = "utf-8-sig"
    delimiter = ","

    urls: ClassVar[dict[int, str]] = {
        2024: (
            "https://casahacker.org/dados/"
            "base-tecnologias-sociais-campinas-2024.csv"
        ),
    }

    def __init__(
        self,
        bronze_root: Path | str = "data/bronze",
    ) -> None:
        self.bronze_root = Path(bronze_root)

    def download(
        self,
        reference: int,
        overwrite: bool = False,
    ) -> Path:
        """Obtém o CSV original da fonte."""

        if reference not in self.urls:
            raise ValueError(
                f"Ano FEAC não configurado: {reference}"
            )

        destination = self._csv_path(reference)
        destination.parent.mkdir(parents=True, exist_ok=True)

        if destination.exists() and not overwrite:
            metadata_path = destination.parent / "metadata.json"

            if not metadata_path.exists():
                self._write_metadata(
                    reference,
                    destination,
                )

            return destination

        temporary = destination.with_suffix(".csv.part")

        request = Request(
            self.urls[reference],
            headers={"User-Agent": "savits-etl/0.1"},
        )

        try:
            with (
                urlopen(request) as response,
                temporary.open("wb") as file,
            ):
                while chunk := response.read(1024 * 1024):
                    file.write(chunk)

            if temporary.stat().st_size == 0:
                raise ValueError(
                    "Arquivo obtido da FEAC está vazio."
                )

            temporary.replace(destination)

        finally:
            if temporary.exists():
                temporary.unlink()

        self._write_metadata(
            reference,
            destination,
        )

        return destination

    def read(
        self,
        reference: int,
        **kwargs: str,
    ) -> Iterator[dict[str, str]]:
        """Lê registros da camada Bronze."""

        path = self._csv_path(reference)

        if not path.exists():
            raise FileNotFoundError(
                f"Arquivo Bronze não encontrado: {path}"
            )

        with path.open(
            encoding=self.encoding,
            newline="",
        ) as file:
            reader = csv.DictReader(
                file,
                delimiter=self.delimiter,
            )

            for row in reader:
                yield {
                    str(key).strip(): (
                        value.strip()
                        if value is not None
                        else ""
                    )
                    for key, value in row.items()
                }

    def _directory(
        self,
        reference: int,
    ) -> Path:
        return (
            self.bronze_root
            / "feac"
            / self.dataset
            / str(reference)
        )

    def _csv_path(
        self,
        reference: int,
    ) -> Path:
        return (
            self._directory(reference)
            / "tecnologias_sociais.csv"
        )

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = sha256()

        with path.open("rb") as file:
            while chunk := file.read(1024 * 1024):
                digest.update(chunk)

        return digest.hexdigest()

    def _write_metadata(
        self,
        reference: int,
        path: Path,
    ) -> None:
        records = 0
        columns = 0

        with path.open(
            encoding=self.encoding,
            newline="",
        ) as file:
            reader = csv.DictReader(
                file,
                delimiter=self.delimiter,
            )

            columns = len(reader.fieldnames or [])

            for _ in reader:
                records += 1

        metadata = {
            "source": self.name,
            "dataset": self.dataset,
            "reference_year": reference,
            "source_url": self.urls[reference],
            "retrieved_at": datetime.now(UTC).isoformat(),
            "file": path.name,
            "size_bytes": path.stat().st_size,
            "sha256": self._sha256(path),
            "encoding": self.encoding,
            "delimiter": self.delimiter,
            "records": records,
            "columns": columns,
            "scope": "Campinas, SP",
            "status": "historical",
        }

        metadata_path = path.parent / "metadata.json"

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