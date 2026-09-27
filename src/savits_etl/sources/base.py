from abc import ABC, abstractmethod
from collections.abc import Iterator
from pathlib import Path


class BaseSource(ABC):
    """Interface básica para fontes utilizadas pelo ETL."""

    @abstractmethod
    def download(self, reference: int, overwrite: bool = False) -> Path:
        """Obtém os dados brutos da fonte."""

    @abstractmethod
    def read(
        self,
        reference: int,
        **kwargs: str,
    ) -> Iterator[dict[str, str]]:
        """Lê registros da camada Bronze."""