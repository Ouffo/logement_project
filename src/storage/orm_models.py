from datetime import UTC, datetime

from sqlalchemy import Boolean, Float, Integer, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from src.storage.db import Base


class RentalListingORM(Base):
    __tablename__ = "rental_listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    source: Mapped[str] = mapped_column(String(100))
    source_id: Mapped[str] = mapped_column(String(255), unique=True)
    url: Mapped[str] = mapped_column(Text)

    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)

    city: Mapped[str] = mapped_column(String(100))
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    district_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    price_eur: Mapped[int] = mapped_column(Integer)
    surface_m2: Mapped[float] = mapped_column(Float)
    rooms: Mapped[int | None] = mapped_column(Integer)
    bedrooms: Mapped[int | None] = mapped_column(Integer)

    furnished: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    parking: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    quiet: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    relevance_score: Mapped[float | None] = mapped_column(Float)

    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC)
    )