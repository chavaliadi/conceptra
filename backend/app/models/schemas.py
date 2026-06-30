from datetime import date, datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class Concept(BaseModel):
    id: str
    name: str
    description: str


class Edge(BaseModel):
    from_id: str
    to_id: str


class Graph(BaseModel):
    concepts: list[Concept]
    edges: list[Edge]


class ScheduleItem(BaseModel):
    concept_id: str
    week: int
    day: int
    priority: Literal["high", "medium", "low"] = "medium"


class QuizQuestion(BaseModel):
    type: Literal["mcq", "short_answer"]
    question: str
    options: list[str] | None = None
    answer: str


class Resource(BaseModel):
    type: Literal["video", "docs", "article"]
    title: str
    url: str


class ConceptContent(BaseModel):
    concept_id: str
    explanation: str
    quiz: list[QuizQuestion]
    resources: list[Resource]


class CreatePlanRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=200)
    exam_date: date | None = Field(None)
    hours_per_day: int = Field(ge=1, le=8, default=2)


class CreatePlanResponse(BaseModel):
    id: UUID


class PlanResponse(BaseModel):
    id: UUID
    topic: str
    exam_date: date
    hours_per_day: int
    graph: Graph
    schedule: list[ScheduleItem]
    content: dict[str, ConceptContent]
    created_at: datetime
    status: str = "active"


class DueReviewItem(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    explanation: str
    quiz: list[QuizQuestion]
    resources: list[Resource]
    status: str
    next_review_at: datetime | None = None


class AnalyticsResponse(BaseModel):
    total_concepts: int
    learned_count: int
    struggling_count: int
    untouched_count: int
    skipped_count: int
    progress_percentage: float
    days_left: int
    daily_velocity_needed: float
    projected_completion_date: date
    status_assessment: Literal["On Track", "Behind", "Critical"]


# ── Phase 4: Knowledge Sharing ──────────────────────────────────────────────

class LibraryPlanItem(BaseModel):
    """A public plan entry shown in the community library grid."""
    id: UUID
    topic: str
    hours_per_day: int
    exam_date: date | None = None
    created_at: datetime
    concept_count: int
    clerk_user_id: str | None = None
    forked_from_id: UUID | None = None

    class Config:
        from_attributes = True


class ForkResponse(BaseModel):
    """Returned when a user forks a public plan into their own dashboard."""
    original_plan_id: UUID
    new_plan_id: UUID
    topic: str


# ── Phase 5: Conversational AI Learning & Memory ───────────────────────────

class ChatMessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


class QuizGradeRequest(BaseModel):
    question_id: str
    question_text: str
    student_answer: str
    correct_answer: str
    confidence_reported: Optional[float] = None


class QuizGradeResponse(BaseModel):
    correct: bool
    score: float
    feedback: str


class EdgeExplanationResponse(BaseModel):
    explanation: str


class LearningProfileResponse(BaseModel):
    mastery_score: float
    confidence_score: float
    retention_score: float
    difficulty_score: float
    recommended_action: str | None = None

    class Config:
        from_attributes = True





