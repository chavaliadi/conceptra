import logging
from uuid import UUID
# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, BackgroundTasks
from pypdf import PdfReader
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db, AsyncSessionLocal
from app.models.schemas import (
    CreatePlanRequest,
    CreatePlanResponse,
    PlanResponse,
    Graph,
    Concept as SchemaConcept,
    Edge as SchemaEdge,
    ConceptContent as SchemaConceptContent,
    QuizQuestion,
    Resource,
    ScheduleItem as SchemaScheduleItem
)
from app.models.database import Concept, Edge, ConceptContent, Progress, Schedule

from app.repositories.plan_repository import PlanRepository, ContentRepository, ProgressRepository
from app.fixtures.sample_plans import TOPIC_FIXTURES, get_fixture_for_topic
from app.services.dag_service import validate_and_sort_dag, generate_schedule
from app.services import ai_service

from app.services.cache_service import get_plan_cache, set_plan_cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/plans", tags=["plans_v2"])

async def generate_plan_background(plan_id: UUID, topic: str, num_concepts: int = 8, hours_per_day: int = 2):
    """Background task to run the 4-stage AI pipeline, save to DB, and store in Redis."""
    async with AsyncSessionLocal() as db:
        try:
            logger.info(f"Starting background plan generation for ID {plan_id}: topic='{topic}'")
            # Stage 1: Concept Extraction
            concepts = await ai_service.extract_concepts(topic, num_concepts)
            
            # Maps string IDs from the LLM (e.g. c1) to database UUIDs
            id_map: dict[str, UUID] = {}
            
            # Insert concepts
            for c in concepts:
                concept = Concept(
                    plan_id=plan_id,
                    name=c.name,
                    description=c.description
                )
                db.add(concept)
                await db.flush()
                id_map[c.id] = concept.id
                
            # Stage 2: Dependency Graph
            edges = await ai_service.build_graph(concepts)
            for e in edges:
                from_uuid = id_map.get(e.from_id)
                to_uuid = id_map.get(e.to_id)
                if from_uuid and to_uuid:
                    edge = Edge(
                        plan_id=plan_id,
                        from_concept_id=from_uuid,
                        to_concept_id=to_uuid
                    )
                    db.add(edge)
                    
            # Stage 3: Generate Schedule (Topological Sort)
            concepts_list = [
                SchemaConcept(id=str(c.id), name=c.name, description=c.description)
                for c in concepts
            ]
            edges_list = [
                SchemaEdge(from_id=e.from_id, to_id=e.to_id)
                for e in edges
            ]
            sorted_ids = validate_and_sort_dag(
                [{"id": c.id} for c in concepts_list],
                [{"from_id": e.from_id, "to_id": e.to_id} for e in edges_list]
            )
            schedule_items = generate_schedule(sorted_ids, hours_per_day=hours_per_day)
            
            # Save schedule to DB
            for s in schedule_items:
                concept_uuid = id_map.get(s.concept_id)
                if concept_uuid:
                    db.add(Schedule(
                        plan_id=plan_id,
                        concept_id=concept_uuid,
                        week=s.week,
                        day=s.day,
                        priority=s.priority
                    ))
                    
            # Stage 4: Content Generation
            content_items = await ai_service.generate_content(concepts)
            for item in content_items:
                concept_uuid = id_map.get(item.concept_id)
                if concept_uuid:
                    quiz_dicts = [q.model_dump() for q in item.quiz]
                    res_dicts = [r.model_dump() for r in item.resources]
                    await ContentRepository.upsert_content(
                        db,
                        concept_id=concept_uuid,
                        explanation=item.explanation,
                        quiz=quiz_dicts,
                        resources=res_dicts
                    )
                    
            # Initialize progress records
            for concept_uuid in id_map.values():
                db.add(Progress(plan_id=plan_id, concept_id=concept_uuid, status="untouched"))
                
            # Mark plan as completed
            await PlanRepository.update_status(db, plan_id, "completed")
            await db.commit()
            logger.info(f"Successfully generated plan {plan_id} in background")
            
            # Save to Redis Cache
            try:
                cache_payload = {
                    "concepts": [{"id": c.id, "name": c.name, "description": c.description} for c in concepts],
                    "edges": [{"from_id": e.from_id, "to_id": e.to_id} for e in edges],
                    "schedule": [{"concept_id": s.concept_id, "week": s.week, "day": s.day, "priority": s.priority} for s in schedule_items],
                    "content": {
                        item.concept_id: {
                            "explanation": item.explanation,
                            "quiz": [q.model_dump() for q in item.quiz],
                            "resources": [r.model_dump() for r in item.resources]
                        }
                        for item in content_items
                    }
                }
                await set_plan_cache(topic, num_concepts, cache_payload)
            except Exception as cache_err:
                logger.warning(f"Failed to cache generated plan: {cache_err}")
            
        except Exception as e:
            logger.error(f"Failed to generate plan {plan_id} in background: {e}", exc_info=True)
            await PlanRepository.update_status(db, plan_id, "failed")
            await db.commit()


@router.post("", response_model=CreatePlanResponse, status_code=status.HTTP_201_CREATED)
async def create_plan_endpoint(
    request: CreatePlanRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
) -> CreatePlanResponse:
    normalized = request.topic.strip().lower()
    has_fixture = any(key in normalized or normalized in key for key in TOPIC_FIXTURES.keys())
    
    if has_fixture:
        # Load fixture data
        fixture = get_fixture_for_topic(request.topic)
        plan = await PlanRepository.create_plan(
            db,
            topic=fixture.get("topic", request.topic),
            exam_date=request.exam_date,
            hours_per_day=request.hours_per_day,
            status="completed"
        )
        
        # Maps fixture string ID to DB UUID
        id_map: dict[str, UUID] = {}
        
        # Insert concepts
        fixture_graph: Graph = fixture["graph"]
        for c in fixture_graph.concepts:
            concept = Concept(
                plan_id=plan.id,
                name=c.name,
                description=c.description
            )
            db.add(concept)
            await db.flush() # populated concept.id UUID
            id_map[c.id] = concept.id
            
        # Insert edges
        for e in fixture_graph.edges:
            from_uuid = id_map.get(e.from_id)
            to_uuid = id_map.get(e.to_id)
            if from_uuid and to_uuid:
                edge = Edge(
                    plan_id=plan.id,
                    from_concept_id=from_uuid,
                    to_concept_id=to_uuid
                )
                db.add(edge)
                
        # Insert content
        fixture_content = fixture["content"]
        for fixture_cid, content_item in fixture_content.items():
            concept_uuid = id_map.get(fixture_cid)
            if concept_uuid:
                # convert QuizQuestion & Resource schemas to dict list for JSONB compatibility
                quiz_dicts = [q.model_dump() for q in content_item.quiz]
                res_dicts = [r.model_dump() for r in content_item.resources]
                await ContentRepository.upsert_content(
                    db,
                    concept_id=concept_uuid,
                    explanation=content_item.explanation,
                    quiz=quiz_dicts,
                    resources=res_dicts
                )
                
        # Insert progress initialization
        for concept_uuid in id_map.values():
            db.add(Progress(plan_id=plan.id, concept_id=concept_uuid, status="untouched"))
            
        await db.commit()
        return CreatePlanResponse(id=plan.id)
    else:
        # Check cache
        num_concepts = 8
        cached = await get_plan_cache(request.topic, num_concepts)
        if cached is not None:
            logger.info(f"Cache hit for topic '{request.topic}'! Building plan instantly.")
            plan = await PlanRepository.create_plan(
                db,
                topic=request.topic,
                exam_date=request.exam_date,
                hours_per_day=request.hours_per_day,
                status="completed"
            )
            
            # Map cached temp ID to DB UUID
            id_map: dict[str, UUID] = {}
            
            # Insert concepts
            for c in cached["concepts"]:
                concept = Concept(
                    plan_id=plan.id,
                    name=c["name"],
                    description=c["description"]
                )
                db.add(concept)
                await db.flush()
                id_map[c["id"]] = concept.id
                
            # Insert edges
            for e in cached["edges"]:
                from_uuid = id_map.get(e["from_id"])
                to_uuid = id_map.get(e["to_id"])
                if from_uuid and to_uuid:
                    edge = Edge(
                        plan_id=plan.id,
                        from_concept_id=from_uuid,
                        to_concept_id=to_uuid
                    )
                    db.add(edge)
                    
            # Insert content
            for temp_cid, content_data in cached["content"].items():
                concept_uuid = id_map.get(temp_cid)
                if concept_uuid:
                    await ContentRepository.upsert_content(
                        db,
                        concept_id=concept_uuid,
                        explanation=content_data["explanation"],
                        quiz=content_data["quiz"],
                        resources=content_data["resources"]
                    )
                    
            # Initialize progress records
            for concept_uuid in id_map.values():
                db.add(Progress(plan_id=plan.id, concept_id=concept_uuid, status="untouched"))
                
            await db.commit()
            return CreatePlanResponse(id=plan.id)
            
        # Cache miss -> Create a pending generation plan and start background worker
        plan = await PlanRepository.create_plan(
            db,
            topic=request.topic,
            exam_date=request.exam_date,
            hours_per_day=request.hours_per_day,
            status="generating"
        )
        await db.commit()
        background_tasks.add_task(
            generate_plan_background,
            plan.id,
            request.topic,
            num_concepts,
            hours_per_day=request.hours_per_day
        )
        return CreatePlanResponse(id=plan.id)




@router.get("/{plan_id}", response_model=PlanResponse)
async def get_plan_endpoint(
    plan_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> PlanResponse:
    plan = await PlanRepository.get_by_id(db, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
        
    # Format concepts
    concepts_list = [
        SchemaConcept(id=str(c.id), name=c.name, description=c.description or "")
        for c in plan.concepts
    ]
    
    # Format edges
    edges_list = [
        SchemaEdge(from_id=str(e.from_concept_id), to_id=str(e.to_concept_id))
        for e in plan.edges
    ]
    
    # Build schedule dynamically from topological sort
    if concepts_list:
        try:
            sorted_ids = validate_and_sort_dag(
                [{"id": c.id} for c in concepts_list],
                [{"from_id": e.from_id, "to_id": e.to_id} for e in edges_list]
            )
            schedule_items = generate_schedule(sorted_ids, hours_per_day=plan.hours_per_day)
        except ValueError:
            # Fallback if cycle somehow exists
            schedule_items = [
                generate_schedule([c.id for c in concepts_list], hours_per_day=plan.hours_per_day)[i]
                for i in range(len(concepts_list))
            ]
    else:
        schedule_items = []
        
    # Format content dict
    content_dict = {}
    for c in plan.concepts:
        if c.content:
            content_dict[str(c.id)] = SchemaConceptContent(
                concept_id=str(c.id),
                explanation=c.content.explanation,
                quiz=[
                    QuizQuestion(
                        type=q["type"],
                        question=q["question"],
                        options=q.get("options"),
                        answer=q["answer"]
                    )
                    for q in c.content.quiz
                ],
                resources=[
                    Resource(
                        type=r["type"],
                        title=r["title"],
                        url=r["url"]
                    )
                    for r in c.content.resources
                ]
            )
            
    return PlanResponse(
        id=plan.id,
        topic=plan.topic,
        exam_date=plan.exam_date.date() if plan.exam_date else None,
        hours_per_day=plan.hours_per_day,
        graph=Graph(concepts=concepts_list, edges=edges_list),
        schedule=schedule_items,
        content=content_dict,
        created_at=plan.created_at,
        status=plan.status
    )

@router.get("", response_model=list[PlanResponse])
async def list_plans_endpoint(
    db: AsyncSession = Depends(get_db)
) -> list[PlanResponse]:
    plans = await PlanRepository.get_all_active(db)
    result = []
    for plan in plans:
        # Lightweight representation for listing (no full schedule/content serialization needed)
        concepts_list = [
            SchemaConcept(id=str(c.id), name=c.name, description=c.description or "")
            for c in plan.concepts
        ]
        edges_list = [
            SchemaEdge(from_id=str(e.from_concept_id), to_id=str(e.to_concept_id))
            for e in plan.edges
        ]
        result.append(
            PlanResponse(
                id=plan.id,
                topic=plan.topic,
                exam_date=plan.exam_date.date() if plan.exam_date else None,
                hours_per_day=plan.hours_per_day,
                graph=Graph(concepts=concepts_list, edges=edges_list),
                schedule=[],
                content={},
                created_at=plan.created_at,
                status=plan.status
            )
        )
    return result

@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plan_endpoint(
    plan_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    deleted = await PlanRepository.delete(db, plan_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Plan not found")

@router.patch("/{plan_id}/concepts/{concept_id}/progress", response_model=dict[str, str])
async def update_progress_endpoint(
    plan_id: UUID,
    concept_id: UUID,
    payload: dict[str, str], # {"status": "learned"}
    db: AsyncSession = Depends(get_db)
):
    status_val = payload.get("status")
    if not status_val or status_val not in ["untouched", "learned", "struggling", "skipped"]:
        raise HTTPException(status_code=400, detail="Invalid status value")
        
    await ProgressRepository.update_status(db, plan_id, concept_id, status_val)
    return {"status": status_val}

@router.get("/{plan_id}/progress", response_model=dict[str, str])
async def get_all_progress_endpoint(
    plan_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> dict[str, str]:
    prog_map = await ProgressRepository.get_progress(db, plan_id)
    # convert UUID keys to string representation
    return {str(k): v for k, v in prog_map.items()}

@router.get("/{plan_id}/concepts/{concept_id}/content", response_model=SchemaConceptContent)
async def get_concept_content_endpoint(
    plan_id: UUID,
    concept_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> SchemaConceptContent:
    plan = await PlanRepository.get_by_id(db, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
        
    concept = next((c for c in plan.concepts if c.id == concept_id), None)
    if not concept or not concept.content:
        raise HTTPException(status_code=404, detail="Concept or content not found")
        
    return SchemaConceptContent(
        concept_id=str(concept.id),
        explanation=concept.content.explanation,
        quiz=[
            QuizQuestion(
                type=q["type"],
                question=q["question"],
                options=q.get("options"),
                answer=q["answer"]
            )
            for q in concept.content.quiz
        ],
        resources=[
            Resource(
                type=r["type"],
                title=r["title"],
                url=r["url"]
            )
            for r in concept.content.resources
        ]
    )

@router.post("/upload-syllabus", response_model=CreatePlanResponse, status_code=status.HTTP_201_CREATED)
async def upload_syllabus(
    file: UploadFile = File(...),
    exam_date: str = "",
    hours_per_day: int = 2,
    db: AsyncSession = Depends(get_db)
) -> CreatePlanResponse:
    if not file.filename or not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    try:
        pdf_content = await file.read()
        reader = PdfReader(stream=pdf_content)
        topic = file.filename.replace('.pdf', '').strip()

        if not topic:
            raise HTTPException(status_code=400, detail="Could not extract topic from filename")

        request = CreatePlanRequest(
            topic=topic,
            exam_date=exam_date if exam_date else None,
            hours_per_day=hours_per_day,
        )
        return await create_plan_endpoint(request, db)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to process PDF: {str(e)}")

