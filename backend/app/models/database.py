"""
SQLAlchemy ORM models for Conceptra.

Tables: plans, concepts, edges, concept_content, progress, schedule, schedule_history
Phase 4 additions: is_public + forked_from_id on plans (Knowledge Sharing).
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
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
    clerk_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Phase 4: Knowledge Sharing
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    forked_from_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("plans.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Layer 1 additions
    subject_domain: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source_books: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)

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
    schedule: Mapped[list["Schedule"]] = relationship(
        "Schedule", back_populates="plan", cascade="all, delete-orphan"
    )
    schedule_history: Mapped[list["ScheduleHistory"]] = relationship(
        "ScheduleHistory", back_populates="plan", cascade="all, delete-orphan"
    )
    quiz_attempts: Mapped[list["QuizAttempt"]] = relationship(
        "QuizAttempt", back_populates="plan", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("hours_per_day >= 1 AND hours_per_day <= 8", name="ck_hours_valid"),
        CheckConstraint(
            "status IN ('active', 'archived', 'completed', 'generating', 'failed')",
            name="ck_status_valid",
        ),
        Index("idx_plans_created_at", "created_at"),
        Index("idx_plans_status", "status"),
        Index("idx_plans_clerk_user_id", "clerk_user_id"),
        Index("idx_plans_is_public", "is_public"),
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
    
    # Layer 1 additions
    difficulty: Mapped[str] = mapped_column(String(50), nullable=False, default="medium")
    difficulty_source: Mapped[str] = mapped_column(String(50), nullable=False, default="llm_assigned")
    content_generation_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    source_hint: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    is_inferred_reading: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    recommended_reading: Mapped[list | None] = mapped_column(JSONB, nullable=True)

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
    quiz_attempts: Mapped[list["QuizAttempt"]] = relationship(
        "QuizAttempt", back_populates="concept", cascade="all, delete-orphan"
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
    # Layer 1 additions
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="llm_inferred")

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
    
    # SRS scheduling variables
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    interval_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ease_factor: Mapped[float] = mapped_column(Float, nullable=False, default=2.5)
    repetitions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Layer 2 Student mastery additions
    mastery_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    retention_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    confidence_level: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    attempts_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

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
        Index("idx_progress_next_review", "next_review_at"),
    )


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

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
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list] = mapped_column(JSONB, nullable=False)
    correct_option_index: Mapped[int] = mapped_column(Integer, nullable=False)
    selected_option_index: Mapped[int] = mapped_column(Integer, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    confidence_reported: Mapped[float] = mapped_column(Float, nullable=False)
    response_time_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_flagged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    answered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    plan: Mapped["Plan"] = relationship("Plan", back_populates="quiz_attempts")
    concept: Mapped["Concept"] = relationship("Concept", back_populates="quiz_attempts")

    __table_args__ = (
        Index("idx_quiz_attempts_plan_id", "plan_id"),
        Index("idx_quiz_attempts_concept_id", "concept_id"),
    )


class Schedule(Base):
    __tablename__ = "schedule"

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
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    day: Mapped[int] = mapped_column(Integer, nullable=False)
    priority: Mapped[str] = mapped_column(String(50), nullable=False, default="medium")

    # Relationships
    plan: Mapped["Plan"] = relationship("Plan", back_populates="schedule")
    concept: Mapped["Concept"] = relationship("Concept")

    __table_args__ = (
        UniqueConstraint("plan_id", "concept_id", name="uq_schedule_plan_concept"),
        CheckConstraint("priority IN ('high', 'medium', 'low')", name="ck_schedule_priority"),
        Index("idx_schedule_plan_id", "plan_id"),
    )


class ScheduleHistory(Base):
    __tablename__ = "schedule_history"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    plan_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    original_schedule: Mapped[list] = mapped_column(JSONB, nullable=False)
    new_schedule: Mapped[list] = mapped_column(JSONB, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    plan: Mapped["Plan"] = relationship("Plan", back_populates="schedule_history")

    __table_args__ = (
        Index("idx_schedule_history_plan_id", "plan_id"),
    )

# Register Phase 5 intelligence models in metadata
from app.models.learning_intelligence import TutorChatMessage, StudentMistake

# Register Phase 6 observability models in metadata
from app.models.api_usage_logs import ApiUsageLog

