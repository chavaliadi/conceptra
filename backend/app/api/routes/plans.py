from uuid import UUID

from fastapi import APIRouter, HTTPException, UploadFile, File
from pypdf import PdfReader

from app.models.schemas import ConceptContent, CreatePlanRequest, CreatePlanResponse, PlanResponse
from app.store import create_plan, get_concept_content, get_plan

router = APIRouter(prefix="/api/plans", tags=["plans"])


@router.post("", response_model=CreatePlanResponse, status_code=201)
def create_plan_endpoint(request: CreatePlanRequest) -> CreatePlanResponse:
    plan = create_plan(request)
    return CreatePlanResponse(id=plan.id)


@router.post("/upload-syllabus", response_model=CreatePlanResponse, status_code=201)
async def upload_syllabus(
    file: UploadFile = File(...),
    exam_date: str = "",
    hours_per_day: int = 2,
) -> CreatePlanResponse:
    """
    Upload a syllabus PDF to create a study plan.
    Extracts topic name from filename and creates a plan.
    """
    if not file.filename or not file.filename.endswith('.pdf'):
        raise HTTPException(
            status_code=400, detail="Only PDF files are supported")

    try:
        # Read PDF and extract basic text
        pdf_content = await file.read()
        reader = PdfReader(stream=pdf_content)

        # Extract topic from filename (remove .pdf extension)
        topic = file.filename.replace('.pdf', '').strip()

        if not topic:
            raise HTTPException(
                status_code=400, detail="Could not extract topic from filename")

        # For Phase 1, we use the extracted filename as the topic
        # and load fixture data based on it
        request = CreatePlanRequest(
            topic=topic,
            exam_date=exam_date if exam_date else None,
            hours_per_day=hours_per_day,
        )
        plan = create_plan(request)
        return CreatePlanResponse(id=plan.id)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Failed to process PDF: {str(e)}")


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
        raise HTTPException(
            status_code=404, detail="Concept content not found")
    return content
