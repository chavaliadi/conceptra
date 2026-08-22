import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException

from app.api.routes.tutor_routes import grade_quiz_response, chat_with_tutor
from app.models.schemas import QuizGradeRequest, ChatRequest
from app.models.database import Plan, Concept, ConceptContent, Edge, Progress

@pytest.mark.asyncio
async def test_quiz_grade_returns_409_when_prerequisite_in_review_debt():
    """Verify that attempting to grade a quiz for a concept whose prerequisite is in Review Debt returns HTTP 409."""
    plan_id = uuid4()
    c1_id = uuid4()  # Prereq Concept A
    c2_id = uuid4()  # Dependent Concept B

    mock_plan = MagicMock(spec=Plan, id=plan_id, clerk_user_id="user_123")
    mock_c2 = MagicMock(spec=Concept, id=c2_id)
    mock_c2.name = "Dependent Concept B"
    mock_c2_content = MagicMock(
        spec=ConceptContent,
        concept_id=c2_id,
        quiz=[{
            "type": "mcq",
            "question": "Sample Question",
            "options": ["Opt 0", "Opt 1", "Opt 2", "Opt 3"],
            "correct_option_index": 1
        }]
    )
    mock_c2_progress = MagicMock(
        spec=Progress,
        plan_id=plan_id,
        concept_id=c2_id,
        repetitions=0,
        ease_factor=2.5,
        interval_days=0,
        mastery_pct=0.0,
        retention_pct=0.0,
        status="untouched",
        attempts_count=0
    )

    # Edge A -> B
    mock_edge = MagicMock(spec=Edge, from_concept_id=c1_id, to_concept_id=c2_id)

    # Prerequisite A is 'learned' but has decayed retention (30% < 50%) -> Review Debt
    mock_c1 = MagicMock(spec=Concept, id=c1_id)
    mock_c1.name = "Prerequisite A"
    mock_c1_progress = MagicMock(
        spec=Progress,
        plan_id=plan_id,
        concept_id=c1_id,
        status="learned",
        mastery_pct=80.0,
        retention_pct=30.0,
        interval_days=1,
        last_reviewed_at=datetime.now(timezone.utc) - timedelta(days=10),
        next_review_at=datetime.now(timezone.utc) - timedelta(days=5)  # Overdue
    )

    mock_db = MagicMock()
    mock_db.get = AsyncMock(return_value=mock_plan)
    mock_db.commit = AsyncMock()

    async def mock_execute(stmt):
        stmt_str = str(stmt)
        res = MagicMock()
        if "JOIN progress" in stmt_str:
            res.all.return_value = [(mock_c1, mock_c1_progress)]
            res.__iter__.return_value = [(mock_c1, mock_c1_progress)]
        elif "FROM concepts" in stmt_str:
            res.scalar_one_or_none.return_value = mock_c2
        elif "FROM concept_content" in stmt_str:
            res.scalar_one_or_none.return_value = mock_c2_content
        elif "FROM progress" in stmt_str:
            res.scalar_one_or_none.return_value = mock_c2_progress
        elif "FROM edges" in stmt_str:
            res.scalars.return_value.all.return_value = [mock_edge]
        else:
            res.all.return_value = [(mock_c1, mock_c1_progress)]
        return res

    mock_db.execute = mock_execute
    current_user = {"sub": "user_123"}
    grade_req = QuizGradeRequest(question_id="0", selected_option_index=1, confidence_reported=0.9)

    # Must raise HTTPException 409 Conflict
    with pytest.raises(HTTPException) as exc_info:
        await grade_quiz_response(plan_id, c2_id, grade_req, db=mock_db, current_user=current_user)

    assert exc_info.value.status_code == 409
    assert "Concept is locked" in exc_info.value.detail
    assert "Prerequisite 'Prerequisite A' is in Review Debt" in exc_info.value.detail

@pytest.mark.asyncio
async def test_quiz_grade_returns_200_when_prerequisite_is_healthy():
    """Verify that quiz grading proceeds normally (HTTP 200) when all prerequisites are healthy."""
    plan_id = uuid4()
    c1_id = uuid4()
    c2_id = uuid4()

    mock_plan = MagicMock(spec=Plan, id=plan_id, clerk_user_id="user_123")
    mock_c2 = MagicMock(spec=Concept, id=c2_id)
    mock_c2.name = "Dependent Concept B"
    mock_c2_content = MagicMock(
        spec=ConceptContent,
        concept_id=c2_id,
        quiz=[{
            "type": "mcq",
            "question": "Sample Question",
            "options": ["Opt 0", "Opt 1", "Opt 2", "Opt 3"],
            "correct_option_index": 1
        }]
    )
    mock_c2_progress = MagicMock(
        spec=Progress,
        plan_id=plan_id,
        concept_id=c2_id,
        repetitions=0,
        ease_factor=2.5,
        interval_days=0,
        mastery_pct=0.0,
        retention_pct=0.0,
        status="untouched",
        attempts_count=0
    )

    mock_edge = MagicMock(spec=Edge, from_concept_id=c1_id, to_concept_id=c2_id)

    # Prerequisite A is learned and healthy (recent review, high retention, future next_review_at)
    mock_c1 = MagicMock(spec=Concept, id=c1_id)
    mock_c1.name = "Prerequisite A"
    mock_c1_progress = MagicMock(
        spec=Progress,
        plan_id=plan_id,
        concept_id=c1_id,
        status="learned",
        mastery_pct=90.0,
        retention_pct=90.0,
        interval_days=6,
        last_reviewed_at=datetime.now(timezone.utc),
        next_review_at=datetime.now(timezone.utc) + timedelta(days=6)
    )

    mock_db = MagicMock()
    mock_db.get = AsyncMock(return_value=mock_plan)
    mock_db.commit = AsyncMock()
    mock_db.add = MagicMock()

    async def mock_execute(stmt):
        stmt_str = str(stmt)
        res = MagicMock()
        if "JOIN progress" in stmt_str:
            res.all.return_value = [(mock_c1, mock_c1_progress)]
            res.__iter__.return_value = [(mock_c1, mock_c1_progress)]
        elif "FROM concepts" in stmt_str:
            res.scalar_one_or_none.return_value = mock_c2
        elif "FROM concept_content" in stmt_str:
            res.scalar_one_or_none.return_value = mock_c2_content
        elif "FROM progress" in stmt_str:
            res.scalar_one_or_none.return_value = mock_c2_progress
        elif "FROM edges" in stmt_str:
            res.scalars.return_value.all.return_value = [mock_edge]
        elif "FROM quiz_attempts" in stmt_str:
            res.scalars.return_value.all.return_value = []
        else:
            res.all.return_value = [(mock_c1, mock_c1_progress)]
        return res

    mock_db.execute = mock_execute
    current_user = {"sub": "user_123"}
    grade_req = QuizGradeRequest(question_id="0", selected_option_index=1, confidence_reported=0.9)

    response = await grade_quiz_response(plan_id, c2_id, grade_req, db=mock_db, current_user=current_user)

    assert response.correct is True
    assert response.score == 100.0
    assert "Correct!" in response.feedback

@pytest.mark.asyncio
async def test_tutor_chat_remains_accessible_when_prerequisite_in_review_debt():
    """Verify that tutor chat remains open (HTTP 200) even when a concept is locked by prerequisite Review Debt."""
    plan_id = uuid4()
    c1_id = uuid4()
    c2_id = uuid4()

    mock_plan = MagicMock(spec=Plan, id=plan_id, clerk_user_id="user_123")
    mock_c2 = MagicMock(spec=Concept, id=c2_id, description="Desc")
    mock_c2.name = "Dependent Concept B"
    mock_c2_content = MagicMock(spec=ConceptContent, concept_id=c2_id, explanation="Full explanation")
    mock_c2_progress = MagicMock(
        spec=Progress,
        plan_id=plan_id,
        concept_id=c2_id,
        mastery_pct=0.0,
        retention_pct=0.0,
        attempts_count=0,
        status="untouched"
    )

    mock_edge = MagicMock(spec=Edge, from_concept_id=c1_id, to_concept_id=c2_id)
    mock_c1 = MagicMock(spec=Concept, id=c1_id)
    mock_c1.name = "Prerequisite A"
    mock_c1_progress = MagicMock(
        spec=Progress,
        plan_id=plan_id,
        concept_id=c1_id,
        status="learned",
        mastery_pct=40.0,
        retention_pct=35.0,
        interval_days=1,
        last_reviewed_at=datetime.now(timezone.utc) - timedelta(days=5),
        next_review_at=datetime.now(timezone.utc) - timedelta(days=2)
    )

    mock_db = MagicMock()
    mock_db.get = AsyncMock(return_value=mock_plan)
    mock_db.commit = AsyncMock()
    mock_db.add = MagicMock()

    async def mock_execute(stmt):
        stmt_str = str(stmt)
        res = MagicMock()
        if "JOIN progress" in stmt_str:
            res.all.return_value = [(mock_c1, mock_c1_progress)]
            res.__iter__.return_value = [(mock_c1, mock_c1_progress)]
        elif "FROM concepts" in stmt_str:
            res.scalar_one_or_none.return_value = mock_c2
        elif "FROM concept_content" in stmt_str:
            res.scalar_one_or_none.return_value = mock_c2_content
        elif "FROM progress" in stmt_str:
            res.scalar_one_or_none.return_value = mock_c2_progress
        elif "FROM edges" in stmt_str:
            res.scalars.return_value.all.return_value = [mock_edge]
        elif "FROM quiz_attempts" in stmt_str:
            res.scalars.return_value.all.return_value = []
        elif "FROM tutor_chat_messages" in stmt_str:
            res.scalars.return_value.all.return_value = []
        else:
            res.all.return_value = [(mock_c1, mock_c1_progress)]
        return res

    mock_db.execute = mock_execute
    current_user = {"sub": "user_123"}
    chat_req = ChatRequest(message="Can you help me understand this concept?")

    with patch("app.api.routes.tutor_routes.get_llm_provider") as mock_llm_getter:
        mock_provider = MagicMock()
        mock_provider.generate = AsyncMock(return_value="Tutor guidance helping bridge prerequisite understanding.")
        mock_llm_getter.return_value = mock_provider

        response = await chat_with_tutor(plan_id, c2_id, chat_req, db=mock_db, current_user=current_user)

    assert response.reply == "Tutor guidance helping bridge prerequisite understanding."

from app.api.routes.plans_v2 import review_concept_endpoint, update_progress_endpoint

@pytest.mark.asyncio
async def test_review_rating_returns_409_when_prerequisite_in_review_debt():
    """Verify that submitting a rating (>=3) on a concept with prerequisite in Review Debt returns HTTP 409."""
    plan_id = uuid4()
    c1_id = uuid4()
    c2_id = uuid4()

    mock_plan = MagicMock(spec=Plan, id=plan_id, clerk_user_id="user_123")
    mock_c1 = MagicMock(spec=Concept, id=c1_id)
    mock_c1.name = "Prerequisite A"
    mock_c1_progress = MagicMock(
        spec=Progress,
        plan_id=plan_id,
        concept_id=c1_id,
        status="learned",
        mastery_pct=80.0,
        retention_pct=25.0,
        interval_days=1,
        last_reviewed_at=datetime.now(timezone.utc) - timedelta(days=10),
        next_review_at=datetime.now(timezone.utc) - timedelta(days=5)
    )

    mock_c2_progress = MagicMock(
        spec=Progress,
        plan_id=plan_id,
        concept_id=c2_id,
        repetitions=0,
        ease_factor=2.5,
        interval_days=0,
        status="untouched"
    )
    mock_edge = MagicMock(spec=Edge, from_concept_id=c1_id, to_concept_id=c2_id)

    mock_db = MagicMock()
    mock_db.commit = AsyncMock()

    async def mock_execute(stmt):
        stmt_str = str(stmt)
        res = MagicMock()
        if "JOIN progress" in stmt_str:
            res.all.return_value = [(mock_c1, mock_c1_progress)]
            res.__iter__.return_value = [(mock_c1, mock_c1_progress)]
        elif "FROM edges" in stmt_str:
            res.scalars.return_value.all.return_value = [mock_edge]
        elif "FROM progress" in stmt_str:
            res.scalars.return_value.first.return_value = mock_c2_progress
        return res

    mock_db.execute = mock_execute
    current_user = {"sub": "user_123"}

    with patch("app.repositories.plan_repository.PlanRepository.get_by_id", AsyncMock(return_value=mock_plan)):
        with pytest.raises(HTTPException) as exc_info:
            await review_concept_endpoint(plan_id, c2_id, {"rating": 5}, current_user=current_user, db=mock_db)

    assert exc_info.value.status_code == 409
    assert "Concept is locked" in exc_info.value.detail

@pytest.mark.asyncio
async def test_review_rating_returns_200_when_prerequisite_is_healthy():
    """Verify that submitting a rating on a healthy concept returns HTTP 200 and marks status learned."""
    plan_id = uuid4()
    c1_id = uuid4()
    c2_id = uuid4()

    mock_plan = MagicMock(spec=Plan, id=plan_id, clerk_user_id="user_123")
    mock_c1 = MagicMock(spec=Concept, id=c1_id)
    mock_c1.name = "Prerequisite A"
    mock_c1_progress = MagicMock(
        spec=Progress,
        plan_id=plan_id,
        concept_id=c1_id,
        status="learned",
        mastery_pct=95.0,
        retention_pct=90.0,
        interval_days=6,
        last_reviewed_at=datetime.now(timezone.utc),
        next_review_at=datetime.now(timezone.utc) + timedelta(days=6)
    )

    mock_c2_progress = MagicMock(
        spec=Progress,
        plan_id=plan_id,
        concept_id=c2_id,
        repetitions=0,
        ease_factor=2.5,
        interval_days=0,
        status="untouched"
    )
    mock_edge = MagicMock(spec=Edge, from_concept_id=c1_id, to_concept_id=c2_id)

    mock_db = MagicMock()
    mock_db.commit = AsyncMock()

    async def mock_execute(stmt):
        stmt_str = str(stmt)
        res = MagicMock()
        if "JOIN progress" in stmt_str:
            res.all.return_value = [(mock_c1, mock_c1_progress)]
            res.__iter__.return_value = [(mock_c1, mock_c1_progress)]
        elif "FROM edges" in stmt_str:
            res.scalars.return_value.all.return_value = [mock_edge]
        elif "FROM progress" in stmt_str:
            res.scalars.return_value.first.return_value = mock_c2_progress
        return res

    mock_db.execute = mock_execute
    current_user = {"sub": "user_123"}

    with patch("app.repositories.plan_repository.PlanRepository.get_by_id", AsyncMock(return_value=mock_plan)):
        res = await review_concept_endpoint(plan_id, c2_id, {"rating": 5}, current_user=current_user, db=mock_db)

    assert res["status"] == "learned"
    assert res["repetitions"] == 1

@pytest.mark.asyncio
async def test_patch_progress_learned_returns_409_when_prerequisite_in_review_debt():
    """Verify that manual PATCH to learned returns HTTP 409 when prerequisite is in Review Debt."""
    plan_id = uuid4()
    c1_id = uuid4()
    c2_id = uuid4()

    mock_plan = MagicMock(spec=Plan, id=plan_id, clerk_user_id="user_123")
    mock_c1 = MagicMock(spec=Concept, id=c1_id)
    mock_c1.name = "Prerequisite A"
    mock_c1_progress = MagicMock(
        spec=Progress,
        plan_id=plan_id,
        concept_id=c1_id,
        status="learned",
        mastery_pct=80.0,
        retention_pct=25.0,
        interval_days=1,
        last_reviewed_at=datetime.now(timezone.utc) - timedelta(days=10),
        next_review_at=datetime.now(timezone.utc) - timedelta(days=5)
    )
    mock_edge = MagicMock(spec=Edge, from_concept_id=c1_id, to_concept_id=c2_id)

    mock_db = MagicMock()
    mock_db.commit = AsyncMock()

    async def mock_execute(stmt):
        stmt_str = str(stmt)
        res = MagicMock()
        if "JOIN progress" in stmt_str:
            res.all.return_value = [(mock_c1, mock_c1_progress)]
            res.__iter__.return_value = [(mock_c1, mock_c1_progress)]
        elif "FROM edges" in stmt_str:
            res.scalars.return_value.all.return_value = [mock_edge]
        return res

    mock_db.execute = mock_execute
    current_user = {"sub": "user_123"}

    with patch("app.repositories.plan_repository.PlanRepository.get_by_id", AsyncMock(return_value=mock_plan)):
        with pytest.raises(HTTPException) as exc_info:
            await update_progress_endpoint(plan_id, c2_id, {"status": "learned"}, current_user=current_user, db=mock_db)

    assert exc_info.value.status_code == 409
    assert "Concept is locked" in exc_info.value.detail

@pytest.mark.asyncio
async def test_patch_progress_learned_returns_200_when_prerequisite_is_healthy():
    """Verify that manual PATCH to learned succeeds (HTTP 200) when all prerequisites are healthy."""
    plan_id = uuid4()
    c1_id = uuid4()
    c2_id = uuid4()

    mock_plan = MagicMock(spec=Plan, id=plan_id, clerk_user_id="user_123")
    mock_c1 = MagicMock(spec=Concept, id=c1_id)
    mock_c1.name = "Prerequisite A"
    mock_c1_progress = MagicMock(
        spec=Progress,
        plan_id=plan_id,
        concept_id=c1_id,
        status="learned",
        mastery_pct=95.0,
        retention_pct=95.0,
        interval_days=6,
        last_reviewed_at=datetime.now(timezone.utc),
        next_review_at=datetime.now(timezone.utc) + timedelta(days=6)
    )
    mock_edge = MagicMock(spec=Edge, from_concept_id=c1_id, to_concept_id=c2_id)

    mock_db = MagicMock()
    mock_db.commit = AsyncMock()

    async def mock_execute(stmt):
        stmt_str = str(stmt)
        res = MagicMock()
        if "JOIN progress" in stmt_str:
            res.all.return_value = [(mock_c1, mock_c1_progress)]
            res.__iter__.return_value = [(mock_c1, mock_c1_progress)]
        elif "FROM edges" in stmt_str:
            res.scalars.return_value.all.return_value = [mock_edge]
        return res

    mock_db.execute = mock_execute
    current_user = {"sub": "user_123"}

    with patch("app.repositories.plan_repository.PlanRepository.get_by_id", AsyncMock(return_value=mock_plan)):
        with patch("app.repositories.plan_repository.ProgressRepository.update_status", AsyncMock()):
            res = await update_progress_endpoint(plan_id, c2_id, {"status": "learned"}, current_user=current_user, db=mock_db)

    assert res["status"] == "learned"

@pytest.mark.asyncio
async def test_patch_progress_skipped_allowed_even_with_prerequisite_in_debt():
    """Verify that manual PATCH to 'skipped' remains permitted without 409 block."""
    plan_id = uuid4()
    c2_id = uuid4()

    mock_plan = MagicMock(spec=Plan, id=plan_id, clerk_user_id="user_123")
    mock_db = MagicMock()

    current_user = {"sub": "user_123"}

    with patch("app.repositories.plan_repository.PlanRepository.get_by_id", AsyncMock(return_value=mock_plan)):
        with patch("app.repositories.plan_repository.ProgressRepository.update_status", AsyncMock()):
            res = await update_progress_endpoint(plan_id, c2_id, {"status": "skipped"}, current_user=current_user, db=mock_db)

    assert res["status"] == "skipped"

