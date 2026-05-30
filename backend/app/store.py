from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.fixtures.sample_plans import get_fixture_for_topic
from app.models.schemas import ConceptContent, CreatePlanRequest, PlanResponse

plans: dict[UUID, PlanResponse] = {}


def create_plan(request: CreatePlanRequest) -> PlanResponse:
    fixture = get_fixture_for_topic(request.topic)
    plan_id = uuid4()
    plan = PlanResponse(
        id=plan_id,
        topic=request.topic.strip(),
        exam_date=request.exam_date,
        hours_per_day=request.hours_per_day,
        graph=fixture["graph"],
        schedule=fixture["schedule"],
        content=fixture["content"],
        created_at=datetime.now(timezone.utc),
    )
    plans[plan_id] = plan
    return plan


def get_plan(plan_id: UUID) -> PlanResponse | None:
    return plans.get(plan_id)


def get_concept_content(plan_id: UUID, concept_id: str) -> ConceptContent | None:
    plan = plans.get(plan_id)
    if plan is None:
        return None
    return plan.content.get(concept_id)
