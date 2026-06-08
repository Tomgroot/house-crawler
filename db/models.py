from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.engine import Base


class Neighborhood(Base):
    __tablename__ = "neighborhoods"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    district: Mapped[str | None] = mapped_column(String(100))
    postal_codes: Mapped[str | None] = mapped_column(Text)  # JSON array
    lat_center: Mapped[float | None] = mapped_column(Float)
    lon_center: Mapped[float | None] = mapped_column(Float)
    distance_to_station_km: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    listings: Mapped[list["Listing"]] = relationship("Listing", back_populates="neighborhood")
    snapshots: Mapped[list["NeighborhoodSnapshot"]] = relationship(
        "NeighborhoodSnapshot", back_populates="neighborhood"
    )

    def __repr__(self) -> str:
        return f"<Neighborhood {self.name}>"


class Listing(Base):
    __tablename__ = "listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    funda_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    address: Mapped[str | None] = mapped_column(String(200))
    postal_code: Mapped[str | None] = mapped_column(String(10), index=True)
    neighborhood_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("neighborhoods.id"), index=True)

    price: Mapped[int | None] = mapped_column(Integer)
    size_m2: Mapped[float | None] = mapped_column(Float)
    price_per_m2: Mapped[float | None] = mapped_column(Float)
    num_rooms: Mapped[int | None] = mapped_column(Integer)
    num_bedrooms: Mapped[int | None] = mapped_column(Integer)
    property_type: Mapped[str | None] = mapped_column(String(20))  # house / apartment / unknown
    build_year: Mapped[int | None] = mapped_column(Integer)
    energy_label: Mapped[str | None] = mapped_column(String(5))

    status: Mapped[str] = mapped_column(String(10), default="for_sale", index=True)  # for_sale / sold
    listing_date: Mapped[date | None] = mapped_column(Date, index=True)
    sold_date: Mapped[date | None] = mapped_column(Date)
    sold_price: Mapped[int | None] = mapped_column(Integer)

    first_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    neighborhood: Mapped["Neighborhood | None"] = relationship("Neighborhood", back_populates="listings")
    price_history: Mapped[list["PriceHistory"]] = relationship(
        "PriceHistory", back_populates="listing", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Listing {self.funda_id} {self.address} €{self.price}>"


class PriceHistory(Base):
    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    listing_id: Mapped[int] = mapped_column(Integer, ForeignKey("listings.id", ondelete="CASCADE"), nullable=False, index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    price: Mapped[int | None] = mapped_column(Integer)
    days_on_market: Mapped[int | None] = mapped_column(Integer)
    price_reduction_pct: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str | None] = mapped_column(String(10))
    crawl_run_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("crawl_runs.id"))

    listing: Mapped["Listing"] = relationship("Listing", back_populates="price_history")


class NeighborhoodSnapshot(Base):
    __tablename__ = "neighborhood_snapshots"
    __table_args__ = (UniqueConstraint("neighborhood_id", "snapshot_month"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    neighborhood_id: Mapped[int] = mapped_column(Integer, ForeignKey("neighborhoods.id"), nullable=False, index=True)
    snapshot_month: Mapped[date] = mapped_column(Date, nullable=False)  # YYYY-MM-01

    median_price_per_m2: Mapped[float | None] = mapped_column(Float)
    avg_price_per_m2: Mapped[float | None] = mapped_column(Float)
    avg_days_on_market: Mapped[float | None] = mapped_column(Float)
    transaction_volume: Mapped[int | None] = mapped_column(Integer)
    active_listings: Mapped[int | None] = mapped_column(Integer)
    price_reduction_frequency: Mapped[float | None] = mapped_column(Float)
    avg_price_reduction_pct: Mapped[float | None] = mapped_column(Float)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    neighborhood: Mapped["Neighborhood"] = relationship("Neighborhood", back_populates="snapshots")


class CrawlRun(Base):
    __tablename__ = "crawl_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    spider_name: Mapped[str | None] = mapped_column(String(50))
    listings_found: Mapped[int] = mapped_column(Integer, default=0)
    listings_new: Mapped[int] = mapped_column(Integer, default=0)
    listings_updated: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="running")  # running / completed / failed
