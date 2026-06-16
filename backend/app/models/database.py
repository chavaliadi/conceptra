"""
SQLAlchemy ORM models for Conceptra.

Tables: plans, concepts, edges, concept_content, progress
Note: schedule and schedule_history are deferred to Wave 2D and Phase 3 respectively.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    topic: Mapped[str] = mapped_column(String(200), nullable=False)
    exam_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    hours_per_day: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    concepts: Mapped[list["Concept"]] = relationship(
        "Concept", back_populates="plan", cascade="all, delete-orphan"
    )
    edges: Mapped[list["Edge"]] = relationship(
        "Edge", back_populates="plan", cascade="all, delete-orphan"
    )
    progress: Mapped[list["Progress"]] = relationship(
        "Progress", back_populates="plan", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("hours_per_day >= 1 AND hours_per_day <= 8", name="ck_hours_valid"),
        CheckConstraint(
            "status IN ('active', 'archived', 'completed', 'generating', 'failed')",
            name="ck_status_valid",
        ),
        Index("idx_plans_created_at", "created_at"),
        Index("idx_plans_status", "status"),
    )


class Concept(Base):
    __tablename__ = "concepts"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    plan_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    plan: Mapped["Plan"] = relationship("Plan", back_populates="concepts")
    content: Mapped["ConceptContent | None"] = relationship(
        "ConceptContent", back_populates="concept", uselist=False, cascade="all, delete-orphan"
    )
    outgoing_edges: Mapped[list["Edge"]] = relationship(
        "Edge",
        foreign_keys="Edge.from_concept_id",
        back_populates="from_concept",
        cascade="all, delete-orphan",
    )
    incoming_edges: Mapped[list["Edge"]] = relationship(
        "Edge",
        foreign_keys="Edge.to_concept_id",
        back_populates="to_concept",
        cascade="all, delete-orphan",
    )
    progress: Mapped[list["Progress"]] = relationship(
        "Progress", back_populates="concept", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("plan_id", "name", name="uq_concept_plan_name"),
        Index("idx_concepts_plan_id", "plan_id"),
    )


class Edge(Base):
    __tablename__ = "edges"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    plan_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_concept_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("concepts.id", ondelete="CASCADE"),
        nullable=False,
    )
    to_concept_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("concepts.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    plan: Mapped["Plan"] = relationship("Plan", back_populates="edges")
    from_concept: Mapped["Concept"] = relationship(
        "Concept", foreign_keys=[from_concept_id], back_populates="outgoing_edges"
    )
    to_concept: Mapped["Concept"] = relationship(
        "Concept", foreign_keys=[to_concept_id], back_populates="incoming_edges"
    )

    __table_args__ = (
        UniqueConstraint(
            "plan_id", "from_concept_id", "to_concept_id", name="uq_edge_unique"
        ),
        CheckConstraint("from_concept_id != to_concept_id", name="ck_no_self_loop"),
        Index("idx_edges_plan_id", "plan_id"),
        Index("idx_edges_from", "from_concept_id"),
        Index("idx_edges_to", "to_concept_id"),
    )


class ConceptContent(Base):
    __tablename__ = "concept_content"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    concept_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("concepts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    # JSONB: [{"type": "mcq", "question": "...", "options": [...], "answer": "..."}]
    quiz: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # JSONB: [{"type": "video", "title": "...", "url": "..."}]
    resources: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    concept: Mapped["Concept"] = relationship("Concept", back_populates="content")

    __table_args__ = (Index("idx_content_concept_id", "concept_id"),)


class Progress(Base):
    __tablename__ = "progress"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    plan_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    concept_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("concepts.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="untouched")
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    plan: Mapped["Plan"] = relationship("Plan", back_populates="progress")
    concept: Mapped["Concept"] = relationship("Concept", back_populates="progress")

    __table_args__ = (
        UniqueConstraint("plan_id", "concept_id", name="uq_progress_plan_concept"),
        CheckConstraint(
            "status IN ('untouched', 'learned', 'struggling', 'skipped')",
            name="ck_progress_status",
        ),
        Index("idx_progress_plan_concept", "plan_id", "concept_id"),
    )
