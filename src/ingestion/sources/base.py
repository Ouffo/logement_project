from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.storage.models import RentalListing


class RentalListingSource(ABC):
    name: str

    @abstractmethod
    def fetch_listings(self) -> list[RentalListing]:
        pass


@dataclass
class Source:
    name: str
    base_url: str

