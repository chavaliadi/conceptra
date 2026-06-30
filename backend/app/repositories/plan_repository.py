from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.models.database import Plan, Concept, Edge, ConceptContent, Progress

class PlanRepository:
    @staticmethod
    async def create_plan(
        db: AsyncSession,
        topic: str,
        exam_date = None,
        hours_per_day: int = 2,
        status: str = "active",
        clerk_user_id: str | None = None,
        **kwargs
    ) -> Plan:
        plan = Plan(
            topic=topic.strip(),
            exam_date=exam_date,
            hours_per_day=hours_per_day,
            status=status,
            clerk_user_id=clerk_user_id,
            **kwargs
        )
        db.add(plan)
        await db.flush() # get plan.id
        return plan

    @staticmethod
    async def get_by_id(db: AsyncSession, plan_id: UUID) -> Plan | None:
        result = await db.execute(
            select(Plan)
            .where(Plan.id == plan_id)
            .options(
                selectinload(Plan.concepts).selectinload(Concept.content),
                selectinload(Plan.edges),
                selectinload(Plan.progress),
                selectinload(Plan.schedule)
            )

        )
        return result.scalars().first()

    @staticmethod
    async def get_all_active(db: AsyncSession) -> list[Plan]:
        result = await db.execute(
            select(Plan)
            .where(Plan.status == "active")
            .order_by(Plan.created_at.desc())
            .options(
                selectinload(Plan.concepts),
                selectinload(Plan.edges)
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_all_by_user(db: AsyncSession, clerk_user_id: str) -> list[Plan]:
        result = await db.execute(
            select(Plan)
            .where(Plan.clerk_user_id == clerk_user_id)
            .order_by(Plan.created_at.desc())
            .options(
                selectinload(Plan.concepts),
                selectinload(Plan.edges)
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def delete(db: AsyncSession, plan_id: UUID) -> bool:
        plan = await PlanRepository.get_by_id(db, plan_id)
        if plan:
            await db.delete(plan)
            await db.commit()
            return True
        return False

    @staticmethod
    async def update_status(db: AsyncSession, plan_id: UUID, status: str) -> Plan | None:
        plan = await PlanRepository.get_by_id(db, plan_id)
        if plan:
            plan.status = status
            await db.commit()
            return plan
        return None


class ContentRepository:
    @staticmethod
    async def upsert_content(
        db: AsyncSession,
        concept_id: UUID,
        explanation: str,
        quiz: list,
        resources: list
    ) -> ConceptContent:
        result = await db.execute(
            select(ConceptContent).where(ConceptContent.concept_id == concept_id)
        )
        content = result.scalars().first()
        if content:
            content.explanation = explanation
            content.quiz = quiz
            content.resources = resources
        else:
            content = ConceptContent(
                concept_id=concept_id,
                explanation=explanation,
                quiz=quiz,
                resources=resources
            )
            db.add(content)
        await db.flush()
        return content


class ProgressRepository:
    @staticmethod
    async def update_status(
        db: AsyncSession,
        plan_id: UUID,
        concept_id: UUID,
        status: str
    ) -> Progress:
        result = await db.execute(
            select(Progress)
            .where(Progress.plan_id == plan_id, Progress.concept_id == concept_id)
        )
        prog = result.scalars().first()
        if prog:
            prog.status = status
        else:
            prog = Progress(
                plan_id=plan_id,
                concept_id=concept_id,
                status=status
            )
            db.add(prog)
        await db.commit()
        return prog

    @staticmethod
    async def get_progress(db: AsyncSession, plan_id: UUID) -> dict[UUID, str]:
        result = await db.execute(
            select(Progress).where(Progress.plan_id == plan_id)
        )
        progress_items = result.scalars().all()
        return {item.concept_id: item.status for item in progress_items}
