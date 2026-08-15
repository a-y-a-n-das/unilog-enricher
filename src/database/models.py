from __future__ import annotations

import uuid
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    TypeDecorator,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone
from database.connection import Base


class JSONType(TypeDecorator):
    """Dialect-aware JSON type: JSONB on PostgreSQL, JSON on SQLite."""
    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(SQLiteJSON())


class UUIDType(TypeDecorator):
    """Dialect-aware UUID type: UUID on PostgreSQL, String on SQLite."""
    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        return uuid.UUID(value)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(),
        primary_key=True,
        default=uuid.uuid4,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="queued",
    )

    input_filename: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )

    input_format: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )

    total_rows: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    processed_rows: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    successful_rows: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    failed_rows: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    input_file_path: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    output_file_path: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    rows: Mapped[list["JobRow"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
    )


class JobRow(Base):
    __tablename__ = "job_rows"

    __table_args__ = (
        UniqueConstraint(
            "job_id",
            "row_number",
            name="uq_job_row_number",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(),
        primary_key=True,
        default=uuid.uuid4,
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
    )

    row_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
    )

    input_data: Mapped[dict] = mapped_column(
        JSONType(),
        nullable=False,
    )

    result_data: Mapped[dict | None] = mapped_column(
        JSONType(),
        nullable=True,
    )

    attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    research_seconds: Mapped[float | None] = mapped_column(
        Numeric,
        nullable=True,
    )

    evidence_seconds: Mapped[float | None] = mapped_column(
        Numeric,
        nullable=True,
    )

    extraction_seconds: Mapped[float | None] = mapped_column(
        Numeric,
        nullable=True,
    )

    total_seconds: Mapped[float | None] = mapped_column(
        Numeric,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    job: Mapped["Job"] = relationship(
        back_populates="rows",
    )