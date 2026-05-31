from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class MetricCollector(ABC):
    """Contrato para lectores de métricas del SO."""

    @abstractmethod
    def collect(self) -> T:
        ...
