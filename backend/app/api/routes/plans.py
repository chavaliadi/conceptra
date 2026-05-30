from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.models.schemas import ConceptContent, CreatePlanRequest, CreatePlanResponse, PlanResponse
from app.store import create_plan, get_concept_content, get_plan

router = APIRouter(prefix="/api/plans", tags=["plans"])


@router.post("", response_model=CreatePlanResponse, status_code=201)
def create_plan_endpoint(request: CreatePlanRequest) -> CreatePlanResponse:
    plan = create_plan(request)
    return CreatePlanResponse(id=plan.id)


@router.get("/{plan_id}", response_model=PlanResponse)
def get_plan_endpoint(plan_id: UUID) -> PlanResponse:
    plan = get_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


@router.get("/{plan_id}/concepts/{concept_id}/content", response_model=ConceptContent)
def get_concept_content_endpoint(plan_id: UUID, concept_id: str) -> ConceptContent:
    content = get_concept_content(plan_id, concept_id)
    if content is None:
        raise HTTPException(status_code=404, detail="Concept content not found")
    return content
