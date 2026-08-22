from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Concept, Edge, Progress
from app.services.scheduler import calculate_decayed_retention

async def check_prerequisite_review_debt(
    db: AsyncSession, plan_id: UUID, concept_id: UUID
) -> tuple[bool, str | None, str | None]:
    """
    Checks if any direct prerequisite of a concept has unresolved Review Debt
    (retention < 50% or next review date is overdue) or is incomplete.
    
    Returns:
        (is_blocked, blocking_concept_name, reason)
    """
    # 1. Fetch prerequisite edges
    prereq_stmt = select(Edge).where(Edge.plan_id == plan_id, Edge.to_concept_id == concept_id)
    prereq_res = await db.execute(prereq_stmt)
    prereq_edges = prereq_res.scalars().all()
    
    if not prereq_edges:
        return False, None, None
        
    prereq_ids = [edge.from_concept_id for edge in prereq_edges]
    
    # 2. Query prerequisite concepts and their progress records
    prereq_details_stmt = (
        select(Concept, Progress)
        .join(Progress, Progress.concept_id == Concept.id)
        .where(Progress.plan_id == plan_id, Concept.id.in_(prereq_ids))
    )
    prereq_details_res = await db.execute(prereq_details_stmt)
    prereq_rows = prereq_details_res.all()
    now_utc = datetime.now(timezone.utc)
    
    for p_concept, p_prog in prereq_rows:
        # Check incomplete status
        if p_prog.status not in ["learned", "skipped"]:
            return True, p_concept.name, f"Prerequisite '{p_concept.name}' is not completed (status: {p_prog.status})."
            
        # If learned, check Review Debt
        if p_prog.status == "learned":
            p_ret = calculate_decayed_retention(p_prog.last_reviewed_at, p_prog.interval_days, p_prog.mastery_pct)
            is_overdue = False
            if p_prog.next_review_at:
                next_rev = p_prog.next_review_at.replace(tzinfo=timezone.utc) if p_prog.next_review_at.tzinfo is None else p_prog.next_review_at
                is_overdue = next_rev <= now_utc
                
            if p_ret < 50.0 or is_overdue:
                reason_detail = f"retention decayed to {p_ret:.1f}%" if p_ret < 50.0 else "review is overdue"
                return True, p_concept.name, f"Prerequisite '{p_concept.name}' is in Review Debt ({reason_detail}). Complete its review quiz first."
                
    return False, None, None
