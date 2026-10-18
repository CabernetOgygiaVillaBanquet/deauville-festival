from abc import ABC, abstractmethod
import json
from pathlib import Path
from typing import Any

from deauville.errors import InvalidValueError, NotFoundError
from deauville.festival import Festival


class Storage(ABC):
    """Abstract interface for festival persistence."""

    @abstractmethod
    def load(self) -> Festival:
        pass

    @abstractmethod
    def save(self, festival: Festival) -> None:
        pass


class JSONStorage(Storage):
    """JSON file storage implementation."""

    def __init__(self, path: str | Path = "data/festival.json") -> None:
        self.path = Path(path)

    def load(self) -> Festival:
        if not self.path.exists():
            raise NotFoundError(f"Festival file '{self.path}' not found.")
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise InvalidValueError(f"Corrupted festival data file: {e}") from e
        return Festival.from_dict(data)

    def save(self, festival: Festival) -> None:
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(festival.to_dict(), f, ensure_ascii=False, indent=2)


class MemoryStorage(Storage):
    """In-memory storage for testing without touching disk."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = dict(data)

    def load(self) -> Festival:
        return Festival.from_dict(self._data)

    def save(self, festival: Festival) -> None:
        self._data = festival.to_dict()