"""
Phase 4 – Knowledge Sharing Routes
===================================
Endpoints:
  POST /api/v2/plans/{plan_id}/publish   → Toggle public visibility
  POST /api/v2/plans/{plan_id}/fork      → Clone a public plan for the current user
  GET  /api/v2/library                   → Browse / search public plans

Design decisions:
  - Forking deep-copies concepts, edges, concept_content, and initialises
    a fresh progress + schedule — nothing is shared by reference so edits
    are fully independent (GitHub-style async collaboration).
  - library endpoint is read-only and does NOT require authentication so
    anyone (even unauthenticated) can browse and decide whether to sign up.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.routes.deps import get_current_user, get_required_user
from app.database import get_db
from app.models.database import (
    Concept,
    ConceptContent,
    Edge,
    Plan,
    Progress,
    Schedule,
)
from app.models.schemas import ForkResponse, LibraryPlanItem

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2", tags=["knowledge_sharing"])


# ─── POST /api/v2/plans/{plan_id}/publish ───────────────────────────────────

@router.post("/plans/{plan_id}/publish")
async def publish_plan(
    plan_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_required_user),
) -> dict:
    """Toggle a plan between private and public visibility.

    Only the plan owner (matched via clerk_user_id) can publish or unpublish.
    """
    plan: Plan | None = await db.get(Plan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    clerk_uid: str = current_user.get("sub", "")
    if plan.clerk_user_id and plan.clerk_user_id != clerk_uid:
        raise HTTPException(status_code=403, detail="Not authorized to publish this plan")

    plan.is_public = not plan.is_public
    await db.commit()
    await db.refresh(plan)

    action = "published" if plan.is_public else "unpublished"
    logger.info(f"Plan {plan_id} {action} by user {clerk_uid}")
    return {"plan_id": str(plan_id), "is_public": plan.is_public, "action": action}


# ─── POST /api/v2/plans/{plan_id}/fork ──────────────────────────────────────

@router.post("/plans/{plan_id}/fork", response_model=ForkResponse)
async def fork_plan(
    plan_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_required_user),
) -> ForkResponse:
    """Deep-clone a public plan into the current user's workspace.

    Creates a new Plan row pointing forked_from_id → original. Copies concepts,
    edges, concept_content, and creates a clean progress record per concept.
    The user can then modify their fork independently.
    """
    # Load source plan with all needed relations
    result = await db.execute(
        select(Plan)
        .where(Plan.id == plan_id)
        .options(
            selectinload(Plan.concepts).selectinload(Concept.content),
            selectinload(Plan.edges),
            selectinload(Plan.schedule),
        )
    )
    source: Plan | None = result.unique().scalar_one_or_none()

    if not source:
        raise HTTPException(status_code=404, detail="Plan not found")
    if not source.is_public:
        raise HTTPException(
            status_code=403, detail="This plan is private and cannot be forked"
        )

    clerk_uid: str = current_user.get("sub", "")

    # 1. Create the new (forked) plan shell
    forked_plan = Plan(
        topic=source.topic,
        exam_date=source.exam_date,
        hours_per_day=source.hours_per_day,
        status="completed",
        clerk_user_id=clerk_uid,
        is_public=False,           # forks start private
        forked_from_id=source.id,
    )
    db.add(forked_plan)
    await db.flush()  # get forked_plan.id

    # 2. Copy concepts and build an id mapping (old_id → new_id)
    concept_id_map: dict[UUID, UUID] = {}
    for src_concept in source.concepts:
        new_concept = Concept(
            plan_id=forked_plan.id,
            name=src_concept.name,
            description=src_concept.description,
        )
        db.add(new_concept)
        await db.flush()
        concept_id_map[src_concept.id] = new_concept.id

        # 3. Copy content for each concept
        if src_concept.content:
            db.add(
                ConceptContent(
                    concept_id=new_concept.id,
                    explanation=src_concept.content.explanation,
                    quiz=src_concept.content.quiz,
                    resources=src_concept.content.resources,
                )
            )

        # 4. Initialise fresh progress
        db.add(
            Progress(
                plan_id=forked_plan.id,
                concept_id=new_concept.id,
                status="untouched",
            )
        )

    # 5. Copy edges using the id mapping
    for src_edge in source.edges:
        from_id = concept_id_map.get(src_edge.from_concept_id)
        to_id = concept_id_map.get(src_edge.to_concept_id)
        if from_id and to_id:
            db.add(
                Edge(
                    plan_id=forked_plan.id,
                    from_concept_id=from_id,
                    to_concept_id=to_id,
                )
            )

    # 6. Copy schedule using the id mapping
    for src_item in source.schedule:
        new_concept_id = concept_id_map.get(src_item.concept_id)
        if new_concept_id:
            db.add(
                Schedule(
                    plan_id=forked_plan.id,
                    concept_id=new_concept_id,
                    week=src_item.week,
                    day=src_item.day,
                    priority=src_item.priority,
                )
            )

    await db.commit()
    logger.info(
        f"User {clerk_uid} forked plan {plan_id} → new plan {forked_plan.id}"
    )
    return ForkResponse(
        original_plan_id=source.id,
        new_plan_id=forked_plan.id,
        topic=forked_plan.topic,
    )


# ─── GET /api/v2/library ────────────────────────────────────────────────────

@router.get("/library", response_model=list[LibraryPlanItem])
async def list_library(
    q: str | None = Query(None, description="Keyword search on topic"),
    sort: str = Query("newest", regex="^(newest|oldest)$"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    # optional auth — unauthenticated users can browse
    _current_user: dict | None = Depends(get_current_user),
) -> list[LibraryPlanItem]:
    """Browse public plans in the community library.

    Supports:
    - Keyword search on topic
    - Sort by newest / oldest
    - Cursor-style pagination via limit/offset
    """
    # Base query: only completed public plans
    stmt = select(
        Plan,
        func.count(Concept.id).label("concept_count"),
    ).join(
        Concept, Concept.plan_id == Plan.id, isouter=True
    ).where(
        Plan.is_public.is_(True),
        Plan.status == "completed",
    ).group_by(Plan.id)

    if q:
        stmt = stmt.where(Plan.topic.ilike(f"%{q}%"))

    order_col = Plan.created_at.desc() if sort == "newest" else Plan.created_at.asc()
    stmt = stmt.order_by(order_col).offset(offset).limit(limit)

    rows = (await db.execute(stmt)).all()

    return [
        LibraryPlanItem(
            id=plan.id,
            topic=plan.topic,
            hours_per_day=plan.hours_per_day,
            exam_date=plan.exam_date.date() if plan.exam_date else None,
            created_at=plan.created_at,
            concept_count=concept_count,
            clerk_user_id=plan.clerk_user_id,
            forked_from_id=plan.forked_from_id,
        )
        for plan, concept_count in rows
    ]
