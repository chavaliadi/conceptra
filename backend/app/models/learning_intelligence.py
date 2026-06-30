from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database import Base

class TutorChatMessage(Base):
    __tablename__ = "tutor_chat_messages"

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
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    plan: Mapped["Plan"] = relationship("Plan")
    concept: Mapped["Concept"] = relationship("Concept")


class StudentMistake(Base):
    __tablename__ = "student_mistakes"

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
    question_id: Mapped[str] = mapped_column(Text, nullable=False)
    incorrect_answer: Mapped[str] = mapped_column(Text, nullable=False)
    mistake_detail: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    plan: Mapped["Plan"] = relationship("Plan")
    concept: Mapped["Concept"] = relationship("Concept")
