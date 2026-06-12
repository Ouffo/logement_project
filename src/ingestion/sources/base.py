from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass

from src.storage.models import RentalListing


class RentalListingSource(ABC):
    name: str
    search_url: str
    storage_path: str | None = None
    parser: Callable[[str], list[RentalListing]] | None = None
    detail_parser: Callable[[str], RentalListing] | None = None

    @abstractmethod
    def fetch_html(self):
        pass


@dataclass
class Source:
    name: str
    base_url: str

