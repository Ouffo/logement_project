from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from src.storage.orm_models import RentalListingORM
from src.storage.models import RentalListing


class RentalListingSource(ABC):
    name: str
    search_url: str
    storage_path: str | None = None
    detail_storage_path: str | None = None
    parser: Callable[[str], list[RentalListing]] | None = None
    detail_parser: Callable[[str], RentalListing] | None = None

    @abstractmethod
    def fetch_html(self):
        pass

    def fetch_detail_htmls(self, _: list[RentalListingORM],) -> list[tuple[RentalListingORM, str]]:
        pass

    def enrich_listing(self):
        pass

@dataclass
class Source:
    name: str
    base_url: str

