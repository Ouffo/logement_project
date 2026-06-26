from datetime import datetime, UTC
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl

class RentalListing(BaseModel):
    source: str
    source_id: str
    url: HttpUrl

    title: str
    description: Optional[str] = None

    city: str = "Paris"
    postal_code: Optional[str] = None
    address: Optional[str] = None
    district_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    price_eur: int = Field(gt=0)
    surface_m2: float = Field(gt=0)
    rooms: Optional[int] = None
    bedrooms: Optional[int] = None

    furnished: Optional[bool] = None
    parking: Optional[bool] = None
    quiet: Optional[bool] = None

    image_url: Optional[str] = None
    posted_at: Optional[datetime] = None
    collected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    construction_year: int | None = None
    energy_class: str | None = None
    details_fetched_at: datetime | None = None

    image_score: float | None = None

    relevance_score: Optional[float] = None