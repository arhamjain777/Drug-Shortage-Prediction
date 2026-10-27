"""Database tables. Source facts (ShortageRecord), user operational data (Inventory*), and derived
data (Scenario results, model output) live in separate tables. is_demo marks simulated rows."""
from datetime import date, datetime, timezone
from typing import Optional
from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.session import Base


def now():
    return datetime.now(timezone.utc)


ROLES = ("admin", "analyst", "inventory_manager", "viewer")


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120), default="")
    password_hash: Mapped[str] = mapped_column(String(300))
    role: Mapped[str] = mapped_column(String(30), default="viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(60), default="openfda_drug_shortages")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="running")  # running|success|failed
    fetched: Mapped[int] = mapped_column(Integer, default=0)
    inserted: Mapped[int] = mapped_column(Integer, default=0)
    updated: Mapped[int] = mapped_column(Integer, default=0)
    unchanged: Mapped[int] = mapped_column(Integer, default=0)
    duplicates: Mapped[int] = mapped_column(Integer, default=0)
    rejected: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[Optional[str]] = mapped_column(Text)
    triggered_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))


class ShortageRecord(Base):
    """OFFICIAL source record (FDA). Never edited by users."""
    __tablename__ = "shortage_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_key: Mapped[str] = mapped_column(String(64), unique=True)
    content_hash: Mapped[str] = mapped_column(String(64))
    generic_name: Mapped[str] = mapped_column(String(300), index=True)
    company_name: Mapped[Optional[str]] = mapped_column(String(300), index=True)
    status: Mapped[Optional[str]] = mapped_column(String(80), index=True)
    availability: Mapped[Optional[str]] = mapped_column(String(300))
    shortage_reason: Mapped[Optional[str]] = mapped_column(Text)
    presentation: Mapped[Optional[str]] = mapped_column(Text)
    dosage_form: Mapped[Optional[str]] = mapped_column(String(200), index=True)
    strength: Mapped[list] = mapped_column(JSON, default=list)
    therapeutic_category: Mapped[list] = mapped_column(JSON, default=list)
    related_info: Mapped[Optional[str]] = mapped_column(Text)
    initial_posting_date: Mapped[Optional[date]] = mapped_column(Date, index=True)
    update_date: Mapped[Optional[date]] = mapped_column(Date, index=True)
    change_date: Mapped[Optional[date]] = mapped_column(Date)
    discontinued_date: Mapped[Optional[date]] = mapped_column(Date)
    brand_names: Mapped[list] = mapped_column(JSON, default=list)
    package_ndc: Mapped[list] = mapped_column(JSON, default=list)
    raw: Mapped[dict] = mapped_column(JSON, default=dict)          # original source payload
    first_seen_run_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ingestion_runs.id"))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Location(Base):
    __tablename__ = "locations"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class InventoryItem(Base):
    __tablename__ = "inventory_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), index=True)
    drug_name: Mapped[str] = mapped_column(String(300), index=True)
    unit: Mapped[str] = mapped_column(String(30), default="units")
    avg_daily_consumption: Mapped[float] = mapped_column(Float, default=0)
    lead_time_days: Mapped[float] = mapped_column(Float, default=0)
    safety_stock_days: Mapped[float] = mapped_column(Float, default=0)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    location: Mapped[Location] = relationship()
    batches: Mapped[list["Batch"]] = relationship(cascade="all, delete-orphan")
    orders: Mapped[list["Order"]] = relationship(cascade="all, delete-orphan")
    movements: Mapped[list["Movement"]] = relationship(cascade="all, delete-orphan", order_by="Movement.id")
    __table_args__ = (Index("ix_item_loc_drug", "location_id", "drug_name", unique=True),)


class Batch(Base):
    __tablename__ = "batches"
    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("inventory_items.id"), index=True)
    quantity: Mapped[float] = mapped_column(Float)
    expiry: Mapped[Optional[date]] = mapped_column(Date)
    lot: Mapped[Optional[str]] = mapped_column(String(80))


class Movement(Base):
    """Append-only ledger. Current stock = sum of batches, kept consistent with this ledger."""
    __tablename__ = "movements"
    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("inventory_items.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    quantity: Mapped[float] = mapped_column(Float)
    balance_after: Mapped[float] = mapped_column(Float)
    reason: Mapped[str] = mapped_column(String(300), default="")
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("inventory_items.id"), index=True)
    quantity: Mapped[float] = mapped_column(Float)
    expected_date: Mapped[date] = mapped_column(Date)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    received: Mapped[bool] = mapped_column(Boolean, default=False)


class Scenario(Base):
    """HYPOTHETICAL. Never modifies inventory."""
    __tablename__ = "scenarios"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    item_id: Mapped[int] = mapped_column(ForeignKey("inventory_items.id"), index=True)
    assumptions: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(80))
    detail: Mapped[str] = mapped_column(String(500), default="")
