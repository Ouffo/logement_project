from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass

from src.storage.models import RentalListing
from src.storage.orm_models import RentalListingORM


class RentalListingSource(ABC):
    name: str
    search_url: str
    storage_path: str = ""
    detail_storage_path: str = ""
    parser: Callable[[str], list[RentalListing]] | None = None
    detail_parser: Callable[[str], RentalListing] | None = None

    @abstractmethod
    def fetch_html(self):
        pass

    @abstractmethod
    def fetch_detail_htmls(
        self,
        listings: list[RentalListingORM],
    ) -> list[tuple[RentalListingORM, str]]:
        pass

    @abstractmethod
    def enrich_listing(
        self,
        listing: RentalListingORM,
        html: str,
    ) -> None:
        pass


@dataclass
class Source:
    name: str
    base_url: str
