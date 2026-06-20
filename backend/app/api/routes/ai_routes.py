from fastapi import APIRouter, HTTPException, Depends
from typing import List
from app.schemas.ai_schemas import AIConceptItem, AIEdge, ConceptContentAI
from app.services import ai_service
from app.services.dag_service import validate_and_sort_dag, generate_schedule

router = APIRouter(prefix="/api/v2/ai", tags=["ai_pipeline_test"])

@router.post("/extract", response_model=List[AIConceptItem])
async def extract_concepts_endpoint(topic: str, num_concepts: int = 8):
    try:
        return await ai_service.extract_concepts(topic, num_concepts)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/graph", response_model=List[AIEdge])
async def build_graph_endpoint(concepts: List[AIConceptItem]):
    try:
        return await ai_service.build_graph(concepts)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/schedule")
def generate_schedule_endpoint(concepts: List[AIConceptItem], edges: List[AIEdge]):
    try:
        sorted_ids = validate_and_sort_dag(
            [{"id": c.id} for c in concepts],
            [{"from_id": e.from_id, "to_id": e.to_id} for e in edges]
        )
        return generate_schedule(sorted_ids)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/content", response_model=List[ConceptContentAI])
async def generate_content_endpoint(concepts: List[AIConceptItem]):
    try:
        return await ai_service.generate_content(concepts)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
