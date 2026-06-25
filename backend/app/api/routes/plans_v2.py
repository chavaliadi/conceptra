import logging
import asyncio
import io
import json
from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Response, UploadFile, File, BackgroundTasks, Request, Form
from app.limiter import limiter
from fastapi.responses import StreamingResponse
from pypdf import PdfReader
from sqlalchemy import select, or_, func, delete
from sqlalchemy.orm import selectinload
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
    ScheduleItem as SchemaScheduleItem,
    DueReviewItem,
    AnalyticsResponse
)
from app.models.database import Concept, Edge, ConceptContent, Progress, Schedule, ScheduleHistory

from app.repositories.plan_repository import PlanRepository, ContentRepository, ProgressRepository
from app.fixtures.sample_plans import TOPIC_FIXTURES, get_fixture_for_topic
from app.services.dag_service import validate_and_sort_dag, generate_schedule
from app.services import ai_service

from app.services.cache_service import get_plan_cache, set_plan_cache
from app.api.routes.deps import get_current_user, get_required_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/plans", tags=["plans_v2"])

async def publish_progress(plan_id: UUID, stage: str, status: str = "generating", **kwargs):
    from app.services.cache_service import redis_client
    if redis_client:
        try:
            channel = f"plan_generation:{plan_id}"
            payload = {"status": status, "stage": stage, **kwargs}
            await redis_client.publish(channel, json.dumps(payload))
        except Exception as e:
            logger.warning(f"Failed to publish progress for plan {plan_id}: {e}")

async def generate_plan_background(plan_id: UUID, topic: str, num_concepts: int = 8, hours_per_day: int = 2):
    """Background task to run the 4-stage AI pipeline, save to DB, and store in Redis."""
    async with AsyncSessionLocal() as db:
        try:
            logger.info(f"Starting background plan generation for ID {plan_id}: topic='{topic}'")
            await publish_progress(plan_id, "generating_concepts", message="Extracting core concepts from curriculum...")
            
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
                
            concepts_payload = [
                {"id": str(id_map[c.id]), "name": c.name, "description": c.description}
                for c in concepts
            ]
            await publish_progress(plan_id, "concepts_extracted", concepts=concepts_payload)
            
            await publish_progress(plan_id, "generating_graph", message="Assembling dependency graph edges...")
            
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
                    
            edges_payload = [
                {"from_id": str(id_map[e.from_id]), "to_id": str(id_map[e.to_id])}
                for e in edges if e.from_id in id_map and e.to_id in id_map
            ]
            await publish_progress(plan_id, "graph_generated", edges=edges_payload)
            
            await publish_progress(plan_id, "generating_schedule", message="Optimizing topological study calendar...")
            
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
                    
            schedule_payload = [
                {"concept_id": str(id_map[s.concept_id]), "week": s.week, "day": s.day, "priority": s.priority}
                for s in schedule_items if s.concept_id in id_map
            ]
            await publish_progress(plan_id, "schedule_generated", schedule=schedule_payload)
            
            await publish_progress(plan_id, "generating_content", message="Synthesizing explanation & resource guides...")
            
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
                    
            content_payload = {
                str(id_map[item.concept_id]): {
                    "concept_id": str(id_map[item.concept_id]),
                    "explanation": item.explanation,
                    "quiz": [q.model_dump() for q in item.quiz],
                    "resources": [r.model_dump() for r in item.resources]
                }
                for item in content_items if item.concept_id in id_map
            }
            await publish_progress(plan_id, "content_generated", content=content_payload)
            
            # Initialize progress records
            for concept_uuid in id_map.values():
                db.add(Progress(plan_id=plan_id, concept_id=concept_uuid, status="untouched"))
                
            # Mark plan as completed
            await PlanRepository.update_status(db, plan_id, "completed")
            await db.commit()
            logger.info(f"Successfully generated plan {plan_id} in background")
            await publish_progress(plan_id, "completed", status="completed", plan_id=str(plan_id))
            
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
            await publish_progress(plan_id, "failed", status="failed", error=str(e))


def generate_plan_background_sync(plan_id_str: str, topic: str, num_concepts: int = 8, hours_per_day: int = 2):
    """Synchronous entry point for RQ worker."""
    import asyncio
    from uuid import UUID
    async def wrapper():
        from app.services.cache_service import init_redis, close_redis
        await init_redis()
        try:
            await generate_plan_background(UUID(plan_id_str), topic, num_concepts, hours_per_day)
        finally:
            await close_redis()
            
    asyncio.run(wrapper())


@router.post("", response_model=CreatePlanResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/hour")
async def create_plan_endpoint(
    request: Request,
    payload: CreatePlanRequest,
    current_user: dict | None = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> CreatePlanResponse:
    return await _create_plan_logic(payload=payload, current_user=current_user, db=db)


async def _create_plan_logic(
    payload: CreatePlanRequest,
    current_user: dict | None,
    db: AsyncSession,
) -> CreatePlanResponse:
    """Shared plan-creation logic used by both the topic endpoint and PDF upload."""
    normalized = payload.topic.strip().lower()
    has_fixture = any(key in normalized or normalized in key for key in TOPIC_FIXTURES.keys())
    clerk_user_id = current_user["sub"] if current_user else None
    
    if has_fixture:
        # Load fixture data
        fixture = get_fixture_for_topic(payload.topic)
        plan = await PlanRepository.create_plan(
            db,
            topic=fixture.get("topic", payload.topic),
            exam_date=payload.exam_date,
            hours_per_day=payload.hours_per_day,
            status="completed",
            clerk_user_id=clerk_user_id
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
        cached = await get_plan_cache(payload.topic, num_concepts)
        if cached is not None:
            logger.info(f"Cache hit for topic '{payload.topic}'! Building plan instantly.")
            plan = await PlanRepository.create_plan(
                db,
                topic=payload.topic,
                exam_date=payload.exam_date,
                hours_per_day=payload.hours_per_day,
                status="completed",
                clerk_user_id=clerk_user_id
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
            topic=payload.topic,
            exam_date=payload.exam_date,
            hours_per_day=payload.hours_per_day,
            status="generating",
            clerk_user_id=clerk_user_id
        )
        await db.commit()
        from app.worker import queue
        queue.enqueue(
            generate_plan_background_sync,
            str(plan.id),
            payload.topic,
            num_concepts,
            payload.hours_per_day
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
    current_user: dict | None = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> list[PlanResponse]:
    if not current_user:
        return []
    plans = await PlanRepository.get_all_by_user(db, current_user["sub"])
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
    current_user: dict = Depends(get_required_user),
    db: AsyncSession = Depends(get_db)
):
    plan = await PlanRepository.get_by_id(db, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    if plan.clerk_user_id is not None and plan.clerk_user_id != current_user["sub"]:
        raise HTTPException(status_code=403, detail="Not authorized to delete this plan")
        
    await PlanRepository.delete(db, plan_id)

@router.post("/{plan_id}/claim", response_model=dict)
async def claim_plan_endpoint(
    plan_id: UUID,
    current_user: dict = Depends(get_required_user),
    db: AsyncSession = Depends(get_db)
):
    plan = await PlanRepository.get_by_id(db, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    if plan.clerk_user_id is not None:
        if plan.clerk_user_id == current_user["sub"]:
            return {"status": "already_claimed", "plan_id": plan_id}
        raise HTTPException(status_code=403, detail="Plan belongs to another user")
    
    plan.clerk_user_id = current_user["sub"]
    await db.commit()
    return {"status": "claimed", "plan_id": plan_id}

@router.patch("/{plan_id}/concepts/{concept_id}/progress", response_model=dict[str, str])
async def update_progress_endpoint(
    plan_id: UUID,
    concept_id: UUID,
    payload: dict[str, str], # {"status": "learned"}
    current_user: dict | None = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    plan = await PlanRepository.get_by_id(db, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
        
    if plan.clerk_user_id is not None:
        if not current_user or plan.clerk_user_id != current_user["sub"]:
            raise HTTPException(status_code=403, detail="Not authorized to update progress on this plan")

    status_val = payload.get("status")
    if not status_val or status_val not in ["untouched", "learned", "struggling", "skipped"]:
        raise HTTPException(status_code=400, detail="Invalid status value")
        
    await ProgressRepository.update_status(db, plan_id, concept_id, status_val)
    return {"status": status_val}

@router.post("/{plan_id}/replan", response_model=list[SchemaScheduleItem])
async def replan_schedule_endpoint(
    plan_id: UUID,
    current_user: dict | None = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> list[SchemaScheduleItem]:
    plan = await PlanRepository.get_by_id(db, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
        
    if plan.clerk_user_id is not None:
        if not current_user or plan.clerk_user_id != current_user["sub"]:
            raise HTTPException(status_code=403, detail="Not authorized to replan this plan")

    # Fetch progress
    progress_map = await ProgressRepository.get_progress(db, plan_id)
    struggling_ids = [str(k) for k, v in progress_map.items() if v == "struggling"]
    
    if not struggling_ids:
        return [
            SchemaScheduleItem(
                concept_id=str(s.concept_id),
                week=s.week,
                day=s.day,
                priority=s.priority
            )
            for s in plan.schedule
        ]

    # Calculate remaining days
    remaining_days = 14
    if plan.exam_date:
        remaining_days = (plan.exam_date.date() - datetime.now().date()).days
        if remaining_days <= 0:
            remaining_days = 7

    # Format data for LLM
    concepts_input = [{"id": str(c.id), "name": c.name, "description": c.description or ""} for c in plan.concepts]
    edges_input = [{"from_id": str(e.from_concept_id), "to_id": str(e.to_concept_id)} for e in plan.edges]
    current_schedule_input = [
        {
            "concept_id": str(s.concept_id),
            "week": s.week,
            "day": s.day,
            "priority": s.priority
        }
        for s in plan.schedule
    ]

    try:
        new_schedule_items = await ai_service.replan_schedule(
            topic=plan.topic,
            concepts=concepts_input,
            edges=edges_input,
            current_schedule=current_schedule_input,
            struggling_ids=struggling_ids,
            remaining_days=remaining_days
        )
        
        # Save ScheduleHistory
        original_schedule_json = current_schedule_input
        new_schedule_json = [
            {
                "concept_id": item.concept_id,
                "week": item.week,
                "day": item.day,
                "priority": item.priority
            }
            for item in new_schedule_items
        ]
        
        history_entry = ScheduleHistory(
            plan_id=plan_id,
            original_schedule=original_schedule_json,
            new_schedule=new_schedule_json,
            reason=f"Adaptive replan triggered for {len(struggling_ids)} struggling concepts."
        )
        db.add(history_entry)
        
        # Delete old schedule and save new schedule in database
        await db.execute(delete(Schedule).where(Schedule.plan_id == plan_id))
        
        for item in new_schedule_items:
            concept_uuid = UUID(item.concept_id)
            db.add(Schedule(
                plan_id=plan_id,
                concept_id=concept_uuid,
                week=item.week,
                day=item.day,
                priority=item.priority
            ))
            
        await db.commit()
        
        return [
            SchemaScheduleItem(
                concept_id=item.concept_id,
                week=item.week,
                day=item.day,
                priority=item.priority
            )
            for item in new_schedule_items
        ]
    except Exception as e:
        logger.error(f"Failed to replan schedule: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to replan schedule: {str(e)}")

@router.get("/{plan_id}/progress", response_model=dict[str, str])
async def get_all_progress_endpoint(
    plan_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> dict[str, str]:
    prog_map = await ProgressRepository.get_progress(db, plan_id)
    # convert UUID keys to string representation
    return {str(k): v for k, v in prog_map.items()}

@router.get("/{plan_id}/reviews/due", response_model=list[DueReviewItem])
async def get_due_reviews_endpoint(
    plan_id: UUID,
    current_user: dict | None = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> list[DueReviewItem]:
    plan = await PlanRepository.get_by_id(db, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
        
    if plan.clerk_user_id is not None:
        if not current_user or plan.clerk_user_id != current_user["sub"]:
            raise HTTPException(status_code=403, detail="Not authorized to access reviews for this plan")

    stmt = (
        select(Progress)
        .where(
            Progress.plan_id == plan_id,
            Progress.status.in_(["learned", "struggling"]),
            or_(
                Progress.next_review_at <= func.now(),
                Progress.next_review_at.is_(None)
            )
        )
        .options(
            selectinload(Progress.concept).selectinload(Concept.content)
        )
    )
    result = await db.execute(stmt)
    progress_records = result.scalars().all()

    due_items = []
    for pr in progress_records:
        concept = pr.concept
        if concept and concept.content:
            due_items.append(
                DueReviewItem(
                    id=concept.id,
                    name=concept.name,
                    description=concept.description,
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
                    ],
                    status=pr.status,
                    next_review_at=pr.next_review_at
                )
            )
            
    return due_items

@router.post("/{plan_id}/concepts/{concept_id}/review")
async def review_concept_endpoint(
    plan_id: UUID,
    concept_id: UUID,
    payload: dict, # {"rating": int}
    current_user: dict | None = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    rating = payload.get("rating")
    if rating is None or not isinstance(rating, int) or not (1 <= rating <= 5):
        raise HTTPException(status_code=400, detail="Rating must be an integer between 1 and 5")

    plan = await PlanRepository.get_by_id(db, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
        
    if plan.clerk_user_id is not None:
        if not current_user or plan.clerk_user_id != current_user["sub"]:
            raise HTTPException(status_code=403, detail="Not authorized to submit reviews for this plan")

    stmt = select(Progress).where(Progress.plan_id == plan_id, Progress.concept_id == concept_id)
    res = await db.execute(stmt)
    progress_rec = res.scalars().first()

    if not progress_rec:
        raise HTTPException(status_code=404, detail="Progress record not found for this concept")

    from app.services.srs import calculate_next_review
    new_rep, new_ef, new_interval, next_review_at = calculate_next_review(
        rating=rating,
        current_repetitions=progress_rec.repetitions,
        current_ease_factor=progress_rec.ease_factor,
        current_interval_days=progress_rec.interval_days
    )

    progress_rec.repetitions = new_rep
    progress_rec.ease_factor = new_ef
    progress_rec.interval_days = new_interval
    progress_rec.next_review_at = next_review_at
    
    if rating < 3:
        progress_rec.status = "struggling"
    else:
        progress_rec.status = "learned"

    await db.commit()
    
    return {
        "status": progress_rec.status,
        "repetitions": progress_rec.repetitions,
        "ease_factor": progress_rec.ease_factor,
        "interval_days": progress_rec.interval_days,
        "next_review_at": progress_rec.next_review_at
    }

@router.get("/{plan_id}/analytics", response_model=AnalyticsResponse)
async def get_plan_analytics_endpoint(
    plan_id: UUID,
    current_user: dict | None = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> AnalyticsResponse:
    plan = await PlanRepository.get_by_id(db, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
        
    if plan.clerk_user_id is not None:
        if not current_user or plan.clerk_user_id != current_user["sub"]:
            raise HTTPException(status_code=403, detail="Not authorized to access analytics for this plan")

    total_concepts = len(plan.concepts)
    
    # Get progress counts
    progress_map = await ProgressRepository.get_progress(db, plan_id)
    
    from datetime import date as d_date
    learned_count = sum(1 for v in progress_map.values() if v == "learned")
    struggling_count = sum(1 for v in progress_map.values() if v == "struggling")
    skipped_count = sum(1 for v in progress_map.values() if v == "skipped")
    untouched_count = total_concepts - (learned_count + struggling_count + skipped_count)
    
    progress_percentage = 0.0
    if total_concepts > 0:
        progress_percentage = round((learned_count / total_concepts) * 100.0, 2)
        
    # Calculate days left
    days_left = 14
    if plan.exam_date:
        days_left = (plan.exam_date.date() - d_date.today()).days
        if days_left < 0:
            days_left = 0
            
    # Daily velocity needed (concepts per day)
    remaining_to_learn = total_concepts - learned_count
    daily_velocity_needed = 0.0
    if days_left > 0:
        daily_velocity_needed = round(remaining_to_learn / days_left, 2)
        
    # Projected completion
    concepts_per_day = max(0.5, plan.hours_per_day / 3.0)
    days_to_complete = remaining_to_learn / concepts_per_day
    
    from datetime import timedelta
    projected_date = d_date.today() + timedelta(days=round(days_to_complete))
    
    # Status Assessment
    if remaining_to_learn == 0:
        status_assessment = "On Track"
    elif days_left == 0:
        status_assessment = "Critical"
    else:
        if days_to_complete <= days_left:
            status_assessment = "On Track"
        elif days_to_complete <= days_left * 1.25:
            status_assessment = "Behind"
        else:
            status_assessment = "Critical"
            
    return AnalyticsResponse(
        total_concepts=total_concepts,
        learned_count=learned_count,
        struggling_count=struggling_count,
        untouched_count=untouched_count,
        skipped_count=skipped_count,
        progress_percentage=progress_percentage,
        days_left=days_left,
        daily_velocity_needed=daily_velocity_needed,
        projected_completion_date=projected_date,
        status_assessment=status_assessment
    )

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
@limiter.limit("5/hour")
async def upload_syllabus(
    request: Request,
    file: UploadFile = File(...),
    exam_date: str = Form(""),
    hours_per_day: int = Form(2),
    current_user: dict | None = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> CreatePlanResponse:
    if not file.filename or not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    try:
        pdf_content = await file.read()
        reader = PdfReader(io.BytesIO(pdf_content))

        # Check for selectable text layer
        text = ""
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text += t
        if not text.strip():
            raise HTTPException(
                status_code=422,
                detail="NON_SEARCHABLE_PDF"
            )

        topic = file.filename.replace('.pdf', '').strip()

        if not topic:
            raise HTTPException(status_code=400, detail="Could not extract topic from filename")

        payload = CreatePlanRequest(
            topic=topic,
            exam_date=exam_date if exam_date else None,
            hours_per_day=hours_per_day,
        )
        return await _create_plan_logic(payload=payload, current_user=current_user, db=db)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to process PDF: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Failed to process PDF: {str(e)}")


@router.get("/{plan_id}/stream")
async def stream_plan_endpoint(
    plan_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """SSE endpoint to stream plan generation progress in real-time."""
    async def event_generator():
        # Start listening to pubsub before reading database to avoid missing any messages
        pubsub = None
        channel = f"plan_generation:{plan_id}"
        
        from app.services.cache_service import redis_client
        if redis_client:
            pubsub = redis_client.pubsub()
            await pubsub.subscribe(channel)
            
        try:
            # Check current status in DB
            plan = await PlanRepository.get_by_id(db, plan_id)
            if not plan:
                yield f"event: error\ndata: {json.dumps({'error': 'Plan not found'})}\n\n"
                return
                
            if plan.status == "completed":
                yield f"event: completed\ndata: {json.dumps({'status': 'completed', 'plan_id': str(plan_id)})}\n\n"
                return
            elif plan.status == "failed":
                yield f"event: failed\ndata: {json.dumps({'status': 'failed', 'error': 'Plan generation failed'})}\n\n"
                return
                
            # If generating, wait for messages or check DB occasionally
            if pubsub:
                while True:
                    try:
                        msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                        if msg:
                            data_str = msg["data"]
                            data_json = json.loads(data_str)
                            event_type = data_json.get("stage", "update")
                            yield f"event: {event_type}\ndata: {data_str}\n\n"
                            if data_json.get("status") in ["completed", "failed"]:
                                break
                        else:
                            await asyncio.sleep(0.5)
                    except asyncio.CancelledError:
                        break
                    except Exception as e:
                        logger.error(f"Error in pubsub stream loop: {e}")
                        yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
                        break
            else:
                # Polling fallback if Redis is not connected
                while True:
                    await asyncio.sleep(1.0)
                    plan = await PlanRepository.get_by_id(db, plan_id)
                    if not plan:
                        yield f"event: error\ndata: {json.dumps({'error': 'Plan not found'})}\n\n"
                        break
                    if plan.status == "completed":
                        yield f"event: completed\ndata: {json.dumps({'status': 'completed', 'plan_id': str(plan_id)})}\n\n"
                        break
                    elif plan.status == "failed":
                        yield f"event: failed\ndata: {json.dumps({'status': 'failed', 'error': 'Plan generation failed'})}\n\n"
                        break
                    yield f"event: generating\ndata: {json.dumps({'status': 'generating'})}\n\n"
        finally:
            if pubsub:
                await pubsub.unsubscribe(channel)
                await pubsub.close()
                
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/{plan_id}/export/pdf")
async def export_pdf_endpoint(
    plan_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Export the study plan as a printable PDF study guide."""
    from app.services.export_service import generate_study_guide_pdf
    
    plan = await PlanRepository.get_by_id(db, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
        
    try:
        pdf_data = generate_study_guide_pdf(plan)
        filename = f"study_guide_{plan_id}.pdf"
        return Response(
            content=pdf_data,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        logger.error(f"Failed to generate study guide PDF: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {str(e)}")


@router.get("/{plan_id}/export/ics")
async def export_ics_endpoint(
    plan_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Export the study calendar as an iCalendar (.ics) subscription."""
    from app.services.export_service import generate_study_schedule_ics
    
    plan = await PlanRepository.get_by_id(db, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
        
    try:
        ics_data = generate_study_schedule_ics(plan)
        filename = f"study_schedule_{plan_id}.ics"
        return Response(
            content=ics_data,
            media_type="text/calendar",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        logger.error(f"Failed to generate iCalendar schedule: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate calendar: {str(e)}")


