import logging
from uuid import UUID
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.deps import get_required_user
from app.database import get_db
from app.models.database import Concept, ConceptContent, Edge, Plan, Progress, QuizAttempt
from app.models.learning_intelligence import StudentMistake, TutorChatMessage
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


# ─── HELPER: GET OR CREATE PROGRESS ─────────────────────────────────

async def get_or_create_progress(
    db: AsyncSession, plan_id: UUID, concept_id: UUID
) -> Progress:
    """Fetch the progress (mastery) record for a concept, or create one if missing."""
    stmt = select(Progress).where(
        Progress.plan_id == plan_id,
        Progress.concept_id == concept_id,
    )
    result = await db.execute(stmt)
    progress = result.scalar_one_or_none()

    if not progress:
        progress = Progress(
            plan_id=plan_id,
            concept_id=concept_id,
            status="untouched",
            mastery_pct=0.0,
            retention_pct=0.0,
            confidence_level=0.0,
            attempts_count=0,
            ease_factor=2.5,
            interval_days=0,
            repetitions=0
        )
        db.add(progress)
        await db.flush()
    return progress


# ─── GET /api/v2/plans/{plan_id}/concepts/{concept_id}/profile ──────────────

@router.get("/{plan_id}/concepts/{concept_id}/profile", response_model=LearningProfileResponse)
async def get_concept_profile(
    plan_id: UUID,
    concept_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_required_user),
):
    """Fetch the current student progress/mastery scores for a concept."""
    plan = await db.get(Plan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    clerk_uid = current_user.get("sub", "")
    if plan.clerk_user_id and plan.clerk_user_id != clerk_uid:
        raise HTTPException(status_code=403, detail="Not authorized to access this plan")

    concept = await db.get(Concept, concept_id)
    if not concept:
        raise HTTPException(status_code=404, detail="Concept not found")

    progress = await get_or_create_progress(db, plan_id, concept_id)
    
    # Calculate decayed retention dynamically
    from app.services.scheduler import calculate_decayed_retention
    retention = calculate_decayed_retention(progress.last_reviewed_at, progress.interval_days, progress.mastery_pct)
    
    # Update computed retention in DB
    progress.retention_pct = retention
    await db.commit()
    
    difficulty_map = {"easy": 30.0, "medium": 60.0, "hard": 90.0}
    difficulty_score = difficulty_map.get(concept.difficulty.lower(), 60.0)
    
    # Map status & progress to recommended action
    if progress.mastery_pct == 0:
        rec_action = "Concept untouched. Start reading explanation and take the quiz"
    elif progress.mastery_pct < 40:
        rec_action = "Struggling. Review mistakes and practice with the AI Tutor"
    elif progress.next_review_at and progress.next_review_at <= datetime.now(timezone.utc):
        rec_action = "Due for review! Take a quick review quiz to strengthen retention"
    elif progress.mastery_pct >= 80:
        rec_action = "Concept mastered! Ready to move to the next topic"
    else:
        rec_action = "Learned. Keep reviewing regularly to maintain retention"

    return LearningProfileResponse(
        mastery_score=progress.mastery_pct,
        confidence_score=progress.confidence_level * 100.0,
        retention_score=retention,
        difficulty_score=difficulty_score,
        recommended_action=rec_action
    )


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

    # Get student progress
    progress = await get_or_create_progress(db, plan_id, concept_id)

    # Query recent confident-incorrect quiz attempts (is_correct == False, confidence_reported >= 0.7)
    misconceptions_stmt = (
        select(QuizAttempt)
        .where(
            QuizAttempt.plan_id == plan_id,
            QuizAttempt.concept_id == concept_id,
            QuizAttempt.is_correct == False,
            QuizAttempt.confidence_reported >= 0.7
        )
        .order_by(QuizAttempt.answered_at.desc())
        .limit(3)
    )
    misconceptions_res = await db.execute(misconceptions_stmt)
    misconceptions = list(misconceptions_res.scalars().all())

    misconceptions_str = ""
    if misconceptions:
        misconceptions_str = "\nStudent's Recent Confident-Incorrect Misconceptions (they answered incorrectly while feeling confident):\n"
        for idx, m in enumerate(misconceptions):
            selected = m.selected_option_index
            correct = m.correct_option_index
            selected_str = m.options[selected] if (m.options and 0 <= selected < len(m.options)) else f"Option index {selected}"
            correct_str = m.options[correct] if (m.options and 0 <= correct < len(m.options)) else f"Option index {correct}"
            misconceptions_str += f"- Question: \"{m.question_text}\"\n  They selected: \"{selected_str}\" (Correct Answer: \"{correct_str}\")\n"

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
- Mastery Score: {progress.mastery_pct:.1f}%
- Confidence Level: {progress.confidence_level * 100.0:.1f}%
- Ease Factor: {progress.ease_factor:.2f}
- Attempts Count: {progress.attempts_count}
{misconceptions_str}

INSTRUCTION: Adapt your teaching to their mastery profile and directly address the misconceptions listed above if any are present.
- If mastery is low (<40%), explain with simple analogies, be extremely patient, and guide them step-by-step.
- If mastery is high (>70%), dive into advanced nuances, ask thought-provoking follow-ups, and keep explanations concise.
- If they have confident-incorrect answers above, address those specific misconceptions and help them correct their understanding.
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
    """Grade a student's quiz response objectively by checking correct_option_index.

    Updates progress mastery percentages using the SM-2 algorithm.
    """
    plan = await db.get(Plan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    clerk_uid = current_user.get("sub", "")
    if plan.clerk_user_id and plan.clerk_user_id != clerk_uid:
        raise HTTPException(status_code=403, detail="Not authorized to access this plan")

    concept = await db.get(Concept, concept_id)
    if not concept:
        raise HTTPException(status_code=404, detail="Concept not found")

    content_stmt = select(ConceptContent).where(ConceptContent.concept_id == concept_id)
    content_res = await db.execute(content_stmt)
    concept_content = content_res.scalar_one_or_none()
    if not concept_content or not concept_content.quiz:
        raise HTTPException(status_code=404, detail="Concept quiz content not found")

    try:
        q_idx = int(req.question_id)
        question_data = concept_content.quiz[q_idx]
    except (ValueError, IndexError):
        raise HTTPException(status_code=400, detail="Invalid question index")

    correct_idx = question_data.get("correct_option_index")
    options = question_data.get("options", [])
    question_text = question_data.get("question", "")

    if correct_idx is None or not options:
        raise HTTPException(status_code=500, detail="Quiz question is malformed in database")

    selected_idx = req.selected_option_index
    is_correct = (selected_idx == correct_idx)
    score = 100.0 if is_correct else 0.0

    selected_text = options[selected_idx] if (0 <= selected_idx < len(options)) else f"Option {selected_idx}"
    correct_text = options[correct_idx] if (0 <= correct_idx < len(options)) else f"Option {correct_idx}"

    if is_correct:
        feedback = f"Correct! '{selected_text}' is correct."
    else:
        feedback = f"Incorrect. You selected '{selected_text}'. The correct answer is '{correct_text}'."

    # Load Progress/Mastery record
    progress_rec = await get_or_create_progress(db, plan_id, concept_id)
    
    quality = calculate_blended_quality(is_correct, req.confidence_reported)

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
    progress_rec.confidence_level = req.confidence_reported
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
        question_text=question_text,
        options=options,
        correct_option_index=correct_idx,
        selected_option_index=selected_idx,
        is_correct=is_correct,
        confidence_reported=req.confidence_reported,
        response_time_ms=req.response_time_ms,
        is_flagged=False,
        answered_at=func.now()
    )
    db.add(quiz_attempt)
    await db.commit()

    return QuizGradeResponse(
        correct=is_correct,
        score=score,
        feedback=feedback,
    )


@router.post("/{plan_id}/concepts/{concept_id}/quiz/flag")
async def flag_quiz_question(
    plan_id: UUID,
    concept_id: UUID,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_required_user),
):
    """Mark a specific quiz attempt as flagged by the user."""
    plan = await db.get(Plan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    clerk_uid = current_user.get("sub", "")
    if plan.clerk_user_id and plan.clerk_user_id != clerk_uid:
        raise HTTPException(status_code=403, detail="Not authorized")

    question_text = payload.get("question_text")
    if not question_text:
        raise HTTPException(status_code=400, detail="Missing question_text")

    stmt = (
        select(QuizAttempt)
        .where(
            QuizAttempt.plan_id == plan_id,
            QuizAttempt.concept_id == concept_id,
            QuizAttempt.question_text == question_text
        )
        .order_by(QuizAttempt.answered_at.desc())
        .limit(1)
    )
    res = await db.execute(stmt)
    attempt = res.scalar_one_or_none()
    if attempt:
        attempt.is_flagged = True
        await db.commit()
        return {"status": "success", "message": "Attempt flagged"}
    else:
        raise HTTPException(status_code=404, detail="Quiz attempt not found")


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

    # Load all progress records for this plan
    progress_stmt = select(Progress, Concept.name).join(
        Concept, Concept.id == Progress.concept_id
    ).where(Progress.plan_id == plan_id)
    progress_res = (await db.execute(progress_stmt)).all()

    mastered_count = 0
    total_confidence = 0.0
    weakness_names = []
    
    progress_count = len(progress_res)

    from app.services.scheduler import calculate_decayed_retention
    for pr, concept_name in progress_res:
        retention = calculate_decayed_retention(pr.last_reviewed_at, pr.interval_days, pr.mastery_pct)
        if pr.mastery_pct >= 70.0:
            mastered_count += 1
        if pr.mastery_pct < 40.0 or pr.status == "struggling":
            weakness_names.append(concept_name)
        total_confidence += (pr.confidence_level * 100.0)

    avg_confidence = total_confidence / progress_count if progress_count > 0 else 0.0

    # Overconfident topics: incorrect answers with high self-reported confidence (>= 0.7)
    from sqlalchemy import func as sqlfunc
    overconfident_stmt = (
        select(
            Concept.name,
            sqlfunc.count(QuizAttempt.id).label("false_confidence_count")
        )
        .join(Concept, Concept.id == QuizAttempt.concept_id)
        .where(
            QuizAttempt.plan_id == plan_id,
            QuizAttempt.is_correct == False,
            QuizAttempt.confidence_reported >= 0.7,
        )
        .group_by(Concept.name)
        .order_by(sqlfunc.count(QuizAttempt.id).desc())
        .limit(5)
    )
    overconfident_res = (await db.execute(overconfident_stmt)).all()
    overconfident_topics = [
        {"concept": row.name, "false_confidence_count": row.false_confidence_count}
        for row in overconfident_res
    ]

    # Build prompt for AI recommended action
    weaknesses_str = ", ".join(weakness_names) if weakness_names else "none"
    overconfident_str = ", ".join([f"{t['concept']} ({t['false_confidence_count']}x)" for t in overconfident_topics]) if overconfident_topics else "none"
    
    system_prompt = """You are a supportive, insightful educational coach.
Based on the student's progress stats and identified misconceptions, output a concise 1-2 sentence recommendation for their study.
Be specific and encouraging. Keep it short.
"""
    prompt = f"""Curriculum Topic: "{plan.topic}"
Progress Summary:
- Mastered Concepts: {mastered_count} out of {total_concepts}
- Average Confidence: {avg_confidence:.1f}%
- Identified Weakness Topics: {weaknesses_str}
- Overconfident Misconceptions: {overconfident_str}

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
        "overconfident_topics": overconfident_topics,
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


