"""Base adapter interface for data sources."""

from abc import ABC, abstractmethod
from typing import Iterator


class DataAdapter(ABC):
    """Abstract base class for data adapters."""

    @abstractmethod
    def read_units(self) -> Iterator[dict[str, str]]:
        """
        Read data units from source.

        Yields:
            Data units as dictionaries.
        """
        pass

    @abstractmethod
    def write_results(self, results: list[dict[str, str]]) -> None:
        """
        Write processed results to output.

        Args:
            results: List of result dictionaries.
        """
        pass

    @abstractmethod
    def get_schema(self) -> dict[str, str]:
        """
        Get schema information about the data source.

        Returns:
            Schema metadata as dictionary.
        """
        pass
