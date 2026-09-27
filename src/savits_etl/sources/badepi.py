from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterator
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import ClassVar
from urllib.request import Request, urlopen
from zipfile import ZipFile, is_zipfile

from savits_etl.sources.base import BaseSource


class BADEPISource(BaseSource):
    """Acesso aos microdados de patentes da BADEPI."""

    name = "INPI BADEPI"
    dataset = "badepi_patentes"

    versions: ClassVar[dict[int, str]] = {
        11: (
            "https://inpidrive.inpi.gov.br/"
            "index.php/s/tIkguEiqp8cSfeD/download"
        ),
    }

    files: ClassVar[dict[str, tuple[str, str]]] = {
        "depositos": (
            "badepiv11_ptn_deposito.csv",
            "utf-8-sig",
        ),
        "depositantes": (
            "badepiv11_ptn_depositante.csv",
            "cp1252",
        ),
        "inventores": (
            "badepiv11_ptn_inventor.csv",
            "cp1252",
        ),
        "despachos": (
            "badepiv11_ptn_despacho.csv",
            "cp1252",
        ),
        "pct": (
            "badepiv11_ptn_pct.csv",
            "utf-8-sig",
        ),
        "classificacoes": (
            "badepiv11_ptn_ipc_campo_tec.csv",
            "utf-8-sig",
        ),
        "prioridades": (
            "badepiv11_ptn_prioridade.csv",
            "cp1252",
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
        """Obtém o ZIP de uma versão da BADEPI."""

        if reference not in self.versions:
            raise ValueError(
                f"Versão BADEPI não configurada: {reference}"
            )

        destination = self._zip_path(reference)
        destination.parent.mkdir(parents=True, exist_ok=True)

        if destination.exists() and not overwrite:
            metadata_path = destination.parent / "metadata.json"

            if not metadata_path.exists():
                self._write_metadata(reference, destination)

            return destination

        temporary = destination.with_suffix(".zip.part")

        request = Request(
            self.versions[reference],
            headers={"User-Agent": "savits-etl/0.1"},
        )

        try:
            with (
                urlopen(request) as response,
                temporary.open("wb") as file,
            ):
                while chunk := response.read(1024 * 1024):
                    file.write(chunk)

            if not is_zipfile(temporary):
                raise ValueError(
                    "Arquivo obtido da BADEPI não é um ZIP válido."
                )

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
        table = kwargs.get("table", "depositos")
        """Lê registros de uma tabela da BADEPI."""

        if table not in self.files:
            raise ValueError(
                f"Tabela BADEPI não configurada: {table}"
            )

        zip_path = self._zip_path(reference)

        if not zip_path.exists():
            raise FileNotFoundError(
                f"Arquivo Bronze não encontrado: {zip_path}"
            )

        filename, encoding = self.files[table]

        with (
            ZipFile(zip_path) as archive,
            archive.open(filename) as raw,
            io.TextIOWrapper(
                raw,
                encoding=encoding,
                newline="",
            ) as text,
        ):
            reader = csv.DictReader(
                text,
                delimiter=";",
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

    def _directory(self, reference: int) -> Path:
        return (
            self.bronze_root
            / "inpi"
            / self.dataset
            / f"v{reference}.0"
        )

    def _zip_path(self, reference: int) -> Path:
        return (
            self._directory(reference)
            / f"badepiv{reference}_ptn.zip"
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
        with ZipFile(path) as archive:
            contents = archive.namelist()

        metadata = {
            "source": self.name,
            "dataset": self.dataset,
            "version": f"{reference}.0",
            "source_url": self.versions[reference],
            "retrieved_at": datetime.now(UTC).isoformat(),
            "file": path.name,
            "size_bytes": path.stat().st_size,
            "sha256": self._sha256(path),
            "contents": contents,
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