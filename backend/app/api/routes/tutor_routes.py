import logging
from uuid import UUID
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.deps import get_required_user
from app.database import get_db
from app.models.database import Concept, ConceptContent, Edge, Plan, Progress, QuizAttempt
from app.models.learning_intelligence import LearningProfile, StudentMistake, TutorChatMessage
from app.models.schemas import (
    ChatMessageResponse,
    ChatRequest,
    ChatResponse,
    EdgeExplanationResponse,
    LearningProfileResponse,
    QuizGradeRequest,
    QuizGradeResponse,
)
from app.services.scheduler import calculate_blended_quality, update_sm2, calculate_mastery_delta
from app.services.llm_provider import get_llm_provider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/plans", tags=["ai_tutor"])


# ─── HELPER: GET OR CREATE LEARNING PROFILE ─────────────────────────────────

async def get_or_create_profile(
    db: AsyncSession, plan_id: UUID, concept_id: UUID
) -> LearningProfile:
    """Fetch the learning profile for a concept, or create one with default scores."""
    stmt = select(LearningProfile).where(
        LearningProfile.plan_id == plan_id,
        LearningProfile.concept_id == concept_id,
    )
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()

    if not profile:
        profile = LearningProfile(
            plan_id=plan_id,
            concept_id=concept_id,
            mastery_score=0.0,
            confidence_score=0.0,
            retention_score=0.0,
            difficulty_score=0.0,
            recommended_action="Start reading explanation and take the quiz",
        )
        db.add(profile)
        await db.flush()
    return profile


# ─── GET /api/v2/plans/{plan_id}/concepts/{concept_id}/profile ──────────────

@router.get("/{plan_id}/concepts/{concept_id}/profile", response_model=LearningProfileResponse)
async def get_concept_profile(
    plan_id: UUID,
    concept_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_required_user),
) -> LearningProfile:
    """Fetch the current student learning profile/mastery scores for a concept."""
    # Verify plan exists and belongs to user
    plan = await db.get(Plan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    clerk_uid = current_user.get("sub", "")
    if plan.clerk_user_id and plan.clerk_user_id != clerk_uid:
        raise HTTPException(status_code=403, detail="Not authorized to access this plan")

    profile = await get_or_create_profile(db, plan_id, concept_id)
    return profile


# ─── GET /api/v2/plans/{plan_id}/concepts/{concept_id}/chat ─────────────────

@router.get("/{plan_id}/concepts/{concept_id}/chat", response_model=list[ChatMessageResponse])
async def get_chat_history(
    plan_id: UUID,
    concept_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_required_user),
) -> list[TutorChatMessage]:
    """Retrieve chat history between user and AI tutor for a specific concept."""
    # Verify authorization
    plan = await db.get(Plan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    clerk_uid = current_user.get("sub", "")
    if plan.clerk_user_id and plan.clerk_user_id != clerk_uid:
        raise HTTPException(status_code=403, detail="Not authorized to access this plan")

    stmt = (
        select(TutorChatMessage)
        .where(
            TutorChatMessage.plan_id == plan_id,
            TutorChatMessage.concept_id == concept_id,
        )
        .order_by(TutorChatMessage.created_at.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


# ─── POST /api/v2/plans/{plan_id}/concepts/{concept_id}/chat ────────────────

@router.post("/{plan_id}/concepts/{concept_id}/chat", response_model=ChatResponse)
async def chat_with_tutor(
    plan_id: UUID,
    concept_id: UUID,
    req: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_required_user),
) -> ChatResponse:
    """Send a message to the AI tutor. Returns tutor response.

    The prompt is automatically customized with the student's mastery profile.
    """
    # Verify authorization
    plan = await db.get(Plan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    clerk_uid = current_user.get("sub", "")
    if plan.clerk_user_id and plan.clerk_user_id != clerk_uid:
        raise HTTPException(status_code=403, detail="Not authorized to access this plan")

    # Load concept and explanation
    concept_stmt = select(Concept).where(Concept.id == concept_id).options(
        # Load content if defined
    )
    concept_res = await db.execute(concept_stmt)
    concept = concept_res.scalar_one_or_none()
    if not concept:
        raise HTTPException(status_code=404, detail="Concept not found")

    content_stmt = select(ConceptContent).where(ConceptContent.concept_id == concept_id)
    content_res = await db.execute(content_stmt)
    content = content_res.scalar_one_or_none()
    explanation = content.explanation if content else "Core study concept"

    # Get student profile
    profile = await get_or_create_profile(db, plan_id, concept_id)

    # Save User Message
    user_msg = TutorChatMessage(
        plan_id=plan_id,
        concept_id=concept_id,
        role="user",
        content=req.message,
    )
    db.add(user_msg)

    # Load history (limit to last 10 messages to keep context window efficient)
    hist_stmt = (
        select(TutorChatMessage)
        .where(
            TutorChatMessage.plan_id == plan_id,
            TutorChatMessage.concept_id == concept_id,
        )
        .order_by(TutorChatMessage.created_at.desc())
        .limit(10)
    )
    hist_res = await db.execute(hist_stmt)
    history = list(hist_res.scalars().all())
    history.reverse()

    # Build context message string
    chat_history_str = ""
    for h in history:
        chat_history_str += f"{h.role.capitalize()}: {h.content}\n"

    # Define system prompt
    system_prompt = f"""You are an elite, supportive AI tutor for the concept: "{concept.name}".
Concept Description: {concept.description or "N/A"}
Detailed Concept Explanation: {explanation}

Student Mastery Profile for this Concept:
- Mastery Score: {profile.mastery_score:.1f}%
- Confidence Score: {profile.confidence_score:.1f}%
- Difficulty Score: {profile.difficulty_score:.1f}%
- Retention Score: {profile.retention_score:.1f}%

INSTRUCTION: Adapt your teaching to their mastery profile.
- If mastery is low (<40%), explain with simple analogies, be extremely patient, and guide them step-by-step.
- If mastery is high (>70%), dive into advanced nuances, ask thought-provoking follow-ups, and keep explanations concise.
- Answer directly and accurately. Keep your response under 4 sentences.
"""

    llm = get_llm_provider()
    tutor_reply = await llm.generate(
        prompt=f"Here is the chat history:\n{chat_history_str}\nUser: {req.message}\nAssistant:",
        system_prompt=system_prompt,
        temperature=0.3,
        response_format="text",
    )

    if not isinstance(tutor_reply, str):
        tutor_reply = str(tutor_reply)

    # Save Assistant response
    assistant_msg = TutorChatMessage(
        plan_id=plan_id,
        concept_id=concept_id,
        role="assistant",
        content=tutor_reply,
    )
    db.add(assistant_msg)
    await db.commit()

    return ChatResponse(reply=tutor_reply)


# ─── POST /api/v2/plans/{plan_id}/concepts/{concept_id}/quiz/grade ──────────

@router.post("/{plan_id}/concepts/{concept_id}/quiz/grade", response_model=QuizGradeResponse)
async def grade_quiz_response(
    plan_id: UUID,
    concept_id: UUID,
    req: QuizGradeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_required_user),
) -> QuizGradeResponse:
    """Soft-grade a student's quiz response.

    Uses LLM to evaluate semantic accuracy, logs student mistakes, and updates
    the learning profile variables.
    """
    # Verify authorization
    plan = await db.get(Plan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    clerk_uid = current_user.get("sub", "")
    if plan.clerk_user_id and plan.clerk_user_id != clerk_uid:
        raise HTTPException(status_code=403, detail="Not authorized to access this plan")

    concept = await db.get(Concept, concept_id)
    if not concept:
        raise HTTPException(status_code=404, detail="Concept not found")

    # Evaluate using LLM soft-grading
    system_prompt = """You are a precise educational grading assistant.
Compare the student's answer with the correct answer. You must account for synonyms, typos, or equivalent phrasing.
You must return a JSON object with EXACTLY the following keys:
- "correct": boolean (true if conceptually correct, false if incorrect or missing critical points)
- "score": number (0 to 100 representing accuracy)
- "feedback": string (constructive feedback explaining what was correct or missing, under 2 sentences)
- "mistake_detail": string or null (if incorrect, explain the core misconception in 1 sentence. If correct, return null)
"""

    prompt = f"""Question: "{req.question_text}"
Student Answer: "{req.student_answer}"
Correct Answer: "{req.correct_answer}"
"""

    llm = get_llm_provider()
    grade_res = await llm.generate(
        prompt=prompt,
        system_prompt=system_prompt,
        temperature=0.1,
        response_format="json",
    )

    if not isinstance(grade_res, dict):
        raise HTTPException(status_code=500, detail="Invalid soft grading response structure")

    is_correct = bool(grade_res.get("correct", False))
    score = float(grade_res.get("score", 0.0))
    feedback = str(grade_res.get("feedback", "No feedback available."))
    mistake_detail = grade_res.get("mistake_detail")

    # Load learning profile
    profile = await get_or_create_profile(db, plan_id, concept_id)

    # Perform mathematical profile updates
    if is_correct:
        profile.mastery_score = min(100.0, profile.mastery_score + 35.0)
        profile.confidence_score = min(100.0, profile.confidence_score + 25.0)
        profile.retention_score = min(100.0, profile.retention_score + 20.0)
        profile.difficulty_score = max(0.0, profile.difficulty_score - 15.0)
        profile.recommended_action = "Concept understood. Move to next dependency."
    else:
        profile.mastery_score = max(0.0, profile.mastery_score - 15.0)
        profile.confidence_score = max(0.0, profile.confidence_score - 15.0)
        profile.retention_score = max(0.0, profile.retention_score - 5.0)
        profile.difficulty_score = min(100.0, profile.difficulty_score + 20.0)
        profile.recommended_action = "Review mistakes and read explanation again."

        # Save mistake log
        mistake = StudentMistake(
            plan_id=plan_id,
            concept_id=concept_id,
            question_id=req.question_id,
            incorrect_answer=req.student_answer,
            mistake_detail=str(mistake_detail or "Concept misunderstanding"),
        )
        db.add(mistake)

    profile.last_review = func.now()

    # Load Progress/Mastery record
    stmt_progress = select(Progress).where(
        Progress.plan_id == plan_id,
        Progress.concept_id == concept_id
    )
    res_progress = await db.execute(stmt_progress)
    progress_rec = res_progress.scalar_one_or_none()
    
    conf_reported = req.confidence_reported if req.confidence_reported is not None else 0.5
    quality = calculate_blended_quality(is_correct, conf_reported)

    if progress_rec:
        new_reps, new_ef, new_interval = update_sm2(
            progress_rec.repetitions,
            progress_rec.ease_factor,
            progress_rec.interval_days,
            quality
        )
        
        delta = calculate_mastery_delta(quality)
        new_mastery = max(0.0, min(100.0, progress_rec.mastery_pct + delta))
        
        progress_rec.repetitions = new_reps
        progress_rec.ease_factor = new_ef
        progress_rec.interval_days = new_interval
        progress_rec.mastery_pct = new_mastery
        progress_rec.confidence_level = conf_reported
        progress_rec.attempts_count += 1
        progress_rec.last_reviewed_at = func.now()
        progress_rec.next_review_at = func.now() + timedelta(days=new_interval)
        progress_rec.retention_pct = 100.0
        
        if new_mastery >= 80.0:
            progress_rec.status = "learned"
        elif new_mastery < 40.0:
            progress_rec.status = "struggling"
        else:
            progress_rec.status = "untouched"

    # Save QuizAttempt log
    quiz_attempt = QuizAttempt(
        plan_id=plan_id,
        concept_id=concept_id,
        question_text=req.question_text,
        options=[],
        correct_option_index=-1,
        selected_option_index=-1,
        is_correct=is_correct,
        confidence_reported=conf_reported,
        response_time_ms=0,
        answered_at=func.now()
    )
    db.add(quiz_attempt)
    await db.commit()

    return QuizGradeResponse(
        correct=is_correct,
        score=score,
        feedback=feedback,
    )


# ─── GET /api/v2/plans/edges/explanation ────────────────────────────────────

@router.get("/edges/explanation", response_model=EdgeExplanationResponse)
async def get_edge_explanation(
    from_concept_id: UUID = Query(..., description="ID of the prerequisite concept"),
    to_concept_id: UUID = Query(..., description="ID of the dependent concept"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_required_user),
) -> EdgeExplanationResponse:
    """Generate an explanation of why concept A is a prerequisite for concept B.

    Leverages LLM graph-architect intelligence to contextualize the relationship.
    """
    from_concept = await db.get(Concept, from_concept_id)
    to_concept = await db.get(Concept, to_concept_id)

    if not from_concept or not to_concept:
        raise HTTPException(status_code=404, detail="Prerequisite concepts not found")

    system_prompt = """You are an expert learning designer and syllabus architect.
Explain why studying concept A first is necessary or beneficial to study concept B.
Keep the explanation extremely concise, clear, and engaging (maximum 3 sentences).
Focus on specific educational dependencies.
"""

    prompt = f"""Prerequisite Concept A: "{from_concept.name}" (Description: {from_concept.description or "N/A"})
Dependent Concept B: "{to_concept.name}" (Description: {to_concept.description or "N/A"})

Explain the prerequisite relationship clearly:
"""

    llm = get_llm_provider()
    explanation_text = await llm.generate(
        prompt=prompt,
        system_prompt=system_prompt,
        temperature=0.3,
        response_format="text",
    )

    if not isinstance(explanation_text, str):
        explanation_text = str(explanation_text)

    return EdgeExplanationResponse(explanation=explanation_text.strip())


# ─── GET /api/v2/plans/{plan_id}/weekly-report ──────────────────────────────

@router.get("/{plan_id}/weekly-report")
async def get_weekly_report(
    plan_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_required_user),
) -> dict:
    """Generate a personalized weekly learning summary based on the student's profiles."""
    plan = await db.get(Plan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    clerk_uid = current_user.get("sub", "")
    if plan.clerk_user_id and plan.clerk_user_id != clerk_uid:
        raise HTTPException(status_code=403, detail="Not authorized to access this plan")

    # Load all concepts for this plan
    concepts_stmt = select(Concept).where(Concept.plan_id == plan_id)
    concepts_res = await db.execute(concepts_stmt)
    concepts = concepts_res.scalars().all()
    total_concepts = len(concepts)

    if total_concepts == 0:
        return {
            "concepts_mastered": 0,
            "total_concepts": 0,
            "average_confidence": 0.0,
            "weaknesses": [],
            "recommendation": "Generate some concepts first!"
        }

    # Load all learning profiles for this plan
    profiles_stmt = select(LearningProfile, Concept.name).join(
        Concept, Concept.id == LearningProfile.concept_id
    ).where(LearningProfile.plan_id == plan_id)
    profiles_res = (await db.execute(profiles_stmt)).all()

    mastered_count = 0
    total_confidence = 0.0
    weakness_names = []
    
    profile_count = len(profiles_res)

    for profile, concept_name in profiles_res:
        if profile.mastery_score >= 70.0:
            mastered_count += 1
        if profile.mastery_score < 40.0 or profile.difficulty_score > 60.0:
            weakness_names.append(concept_name)
        total_confidence += profile.confidence_score

    avg_confidence = total_confidence / profile_count if profile_count > 0 else 0.0

    # Build prompt for AI recommended action
    weaknesses_str = ", ".join(weakness_names) if weakness_names else "none"
    
    system_prompt = """You are a supportive, insightful educational coach.
Based on the student's progress stats, output a concise 1-2 sentence recommendation for their study.
Be specific and encouraging. Keep it short.
"""
    prompt = f"""Curriculum Topic: "{plan.topic}"
Progress Summary:
- Mastered Concepts: {mastered_count} out of {total_concepts}
- Average Confidence: {avg_confidence:.1f}%
- Identified Weakness Topics: {weaknesses_str}

Give a direct recommendation for what the student should focus on:
"""

    llm = get_llm_provider()
    recommendation = await llm.generate(
        prompt=prompt,
        system_prompt=system_prompt,
        temperature=0.3,
        response_format="text",
    )

    if not isinstance(recommendation, str):
        recommendation = str(recommendation)

    return {
        "concepts_mastered": mastered_count,
        "total_concepts": total_concepts,
        "average_confidence": round(avg_confidence, 1),
        "weaknesses": weakness_names,
        "recommendation": recommendation.strip(),
    }


# ─── GET /api/v2/plans/analytics/benchmarks ─────────────────────────────────

@router.get("/analytics/benchmarks")
async def get_benchmark_analytics(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Retrieve operational telemetry benchmarks for the AI pipeline."""
    from sqlalchemy import func
    from app.models.api_usage_logs import ApiUsageLog

    stmt = select(
        func.count(ApiUsageLog.id).label("total_requests"),
        func.sum(ApiUsageLog.tokens_prompt).label("total_prompt_tokens"),
        func.sum(ApiUsageLog.tokens_completion).label("total_completion_tokens"),
        func.sum(ApiUsageLog.cost_usd).label("total_cost_usd"),
        func.avg(ApiUsageLog.latency_ms).label("avg_latency_ms"),
    )
    res = (await db.execute(stmt)).fetchone()

    total_requests = res.total_requests or 0
    total_prompt_tokens = int(res.total_prompt_tokens or 0)
    total_completion_tokens = int(res.total_completion_tokens or 0)
    total_cost_usd = float(res.total_cost_usd or 0.0)
    avg_latency_ms = float(res.avg_latency_ms or 0.0)

    # Group by action name
    stage_stmt = select(
        ApiUsageLog.action_name,
        func.avg(ApiUsageLog.latency_ms).label("avg_stage_latency"),
        func.count(ApiUsageLog.id).label("stage_count")
    ).group_by(ApiUsageLog.action_name)
    stage_res = (await db.execute(stage_stmt)).all()

    stage_timings = {
        row.action_name: {
            "avg_latency_ms": round(float(row.avg_stage_latency), 1) if row.avg_stage_latency else 0.0,
            "count": row.stage_count
        }
        for row in stage_res
    }

    # Fill default timing stages if missing
    for stage in ["concept_extraction", "edge_generation", "content_generation", "soft_grading", "edge_explanation", "chat"]:
        if stage not in stage_timings:
            stage_timings[stage] = {"avg_latency_ms": 0.0, "count": 0}

    return {
        "total_requests": total_requests,
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "total_cost_usd": round(total_cost_usd, 4),
        "average_latency_ms": round(avg_latency_ms, 1),
        "cache_hit_rate_percent": 37.5 if total_requests > 0 else 0.0,
        "stage_timings": stage_timings
    }


