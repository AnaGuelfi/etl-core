from __future__ import annotations

import csv
import hashlib
import io
import json
import shutil
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar
from urllib.request import Request, urlopen
from zipfile import ZipFile, is_zipfile

from savits_etl.sources.base import BaseSource


class INPISource(BaseSource):
    """Acesso aos arquivos de pedidos de patentes do INPI."""

    name = "INPI Dados Abertos"
    dataset = "pedidos_patentes"

    encoding = "cp1252"
    delimiter = "|"

    urls: ClassVar[dict[int, str]] = {
        2018: (
            "https://www.gov.br/inpi/pt-br/acesso-a-informacao/"
            "dados-abertos/arquivos/documentos/pedidos-de-patentes/"
            "2018.zip/@@download/file"
        ),
        2019: (
            "https://www.gov.br/inpi/pt-br/acesso-a-informacao/"
            "dados-abertos/arquivos/documentos/pedidos-de-patentes/"
            "2019.zip/@@download/file"
        ),
        2020: (
            "https://www.gov.br/inpi/pt-br/acesso-a-informacao/"
            "dados-abertos/arquivos/documentos/pedidos-de-patentes/"
            "2020.zip/@@download/file"
        ),
    }

    def __init__(self, bronze_root: Path | str = "data/bronze") -> None:
        self.bronze_root = Path(bronze_root)

    def download(self, reference: int, overwrite: bool = False) -> Path:
        """Baixa o ZIP original do INPI para a camada Bronze."""

        if reference not in self.urls:
            raise ValueError(f"Ano não configurado: {reference}")

        destination = self._zip_path(reference)

        if destination.exists() and not overwrite:
            return destination

        destination.parent.mkdir(parents=True, exist_ok=True)

        temporary = destination.with_suffix(".zip.part")

        request = Request(
            self.urls[reference],
            headers={"User-Agent": "savits-etl/0.1"},
        )

        try:
            with (
                urlopen(request, timeout=120) as response,
                temporary.open("wb") as output,
            ):
                shutil.copyfileobj(response, output)

            if not is_zipfile(temporary):
                raise ValueError("O arquivo recebido não é um ZIP válido.")

            temporary.replace(destination)

        finally:
            if temporary.exists():
                temporary.unlink()

        self._write_metadata(reference, destination)

        return destination

    def read(
        self,
        reference: int,
        **kwargs: str,
    ) -> Iterator[dict[str, str]]:
        """Lê os registros do CSV existente dentro do ZIP da Bronze."""

        path = self._zip_path(reference)

        if not path.exists():
            raise FileNotFoundError(
                f"Arquivo Bronze não encontrado: {path}"
            )

        with ZipFile(path) as archive:
            csv_name = next(
                (
                    name
                    for name in archive.namelist()
                    if name.lower().endswith(".csv")
                ),
                None,
            )

            if csv_name is None:
                raise ValueError("Nenhum CSV encontrado no arquivo ZIP.")

            with archive.open(csv_name) as raw:
                text = io.TextIOWrapper(
                    raw,
                    encoding=self.encoding,
                    newline="",
                )

                reader = csv.DictReader(
                    text,
                    delimiter=self.delimiter,
                )

                for row in reader:
                    yield {
                        key.strip(): value.strip()
                        for key, value in row.items()
                    }

    def _directory(self, reference: int) -> Path:
        return (
            self.bronze_root
            / "inpi"
            / self.dataset
            / str(reference)
        )

    def _zip_path(self, reference: int) -> Path:
        return self._directory(reference) / f"{reference}.zip"

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()

        with path.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)

        return digest.hexdigest()

    def _write_metadata(
        self,
        reference: int,
        path: Path,
    ) -> None:
        with ZipFile(path) as archive:
            contents = archive.namelist()

        metadata = {
            "source": self.name,
            "dataset": self.dataset,
            "reference_year": reference,
            "source_url": self.urls[reference],
            "retrieved_at": datetime.now(UTC).isoformat(),
            "file": path.name,
            "size_bytes": path.stat().st_size,
            "sha256": self._sha256(path),
            "contents": contents,
        }

        metadata_path = self._directory(reference) / "metadata.json"

        with metadata_path.open("w", encoding="utf-8") as file:
            json.dump(
                metadata,
                file,
                ensure_ascii=False,
                indent=2,
            )