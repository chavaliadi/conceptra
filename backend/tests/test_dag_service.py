import pytest
from app.services.dag_service import validate_and_sort_dag, generate_schedule
from app.schemas.ai_schemas import GraphResponse

def test_dag_topological_sort_correctness():
    """Verify topological sort places prerequisite concepts before dependents."""
    concepts = [
        {"id": "c1", "name": "Basics"},
        {"id": "c2", "name": "Intermediate"},
        {"id": "c3", "name": "Advanced"}
    ]
    edges = [
        {"from_id": "c1", "to_id": "c2"},
        {"from_id": "c2", "to_id": "c3"}
    ]
    sorted_ids = validate_and_sort_dag(concepts, edges)
    assert sorted_ids == ["c1", "c2", "c3"]

def test_dag_cycle_rejection_service():
    """Verify validate_and_sort_dag raises ValueError when graph contains cycles."""
    concepts = [{"id": "c1"}, {"id": "c2"}, {"id": "c3"}]
    cyclic_edges = [
        {"from_id": "c1", "to_id": "c2"},
        {"from_id": "c2", "to_id": "c3"},
        {"from_id": "c3", "to_id": "c1"}
    ]
    with pytest.raises(ValueError, match="The dependency graph contains cycles!"):
        validate_and_sort_dag(concepts, cyclic_edges)

def test_dag_cycle_rejection_pydantic_schema():
    """Verify Pydantic GraphResponse validator rejects cyclic edges and self-loops."""
    # Self-loop test
    self_loop = [{"from_id": "c1", "to_id": "c1", "confidence": 1.0, "source": "llm_inferred"}]
    with pytest.raises(ValueError, match="Self-loops are not allowed"):
        GraphResponse.model_validate({"edges": self_loop})

    # Cycle test
    cyclic_edges = [
        {"from_id": "c1", "to_id": "c2", "confidence": 1.0, "source": "llm_inferred"},
        {"from_id": "c2", "to_id": "c3", "confidence": 1.0, "source": "llm_inferred"},
        {"from_id": "c3", "to_id": "c1", "confidence": 1.0, "source": "llm_inferred"},
    ]
    with pytest.raises(ValueError, match="The dependency graph contains cycles!"):
        GraphResponse.model_validate({"edges": cyclic_edges})

def test_scheduler_skips_zero_hour_days():
    """Verify greedy bin-packing skips days with 0 allocated study hours."""
    concepts = [
        {"id": "c1", "difficulty": "medium"},  # 60m
        {"id": "c2", "difficulty": "medium"},  # 60m -> fits in Day 1 (120m budget)
        {"id": "c3", "difficulty": "medium"},  # 60m -> should go to Day 3 (Day 2 has 0h)
        {"id": "c4", "difficulty": "medium"},  # 60m -> Day 3
        {"id": "c5", "difficulty": "medium"},  # 60m -> Day 4
    ]
    timetable = [
        {"day": 1, "hours": 2},
        {"day": 2, "hours": 0},  # Blocked day
        {"day": 3, "hours": 2},
        {"day": 4, "hours": 2},
        {"day": 5, "hours": 2},
        {"day": 6, "hours": 0},
        {"day": 7, "hours": 0},
    ]
    schedule = generate_schedule(concepts, hours_per_day=2, calendar_timetable=timetable)
    
    assert len(schedule) == 5
    # Day 1 concepts
    assert schedule[0].concept_id == "c1" and schedule[0].week == 1 and schedule[0].day == 1
    assert schedule[1].concept_id == "c2" and schedule[1].week == 1 and schedule[1].day == 1
    # Day 3 concepts (Day 2 was skipped)
    assert schedule[2].concept_id == "c3" and schedule[2].week == 1 and schedule[2].day == 3
    assert schedule[3].concept_id == "c4" and schedule[3].week == 1 and schedule[3].day == 3
    # Day 4 concepts
    assert schedule[4].concept_id == "c5" and schedule[4].week == 1 and schedule[4].day == 4

def test_scheduler_difficulty_costs():
    """Verify easy=30m, medium=60m, hard=90m packing under 2-hour (120m) budget."""
    concepts = [
        {"id": "c_easy", "difficulty": "easy"},     # 30m
        {"id": "c_hard", "difficulty": "hard"},     # 90m -> Total 120m, fills Day 1 exactly
        {"id": "c_med", "difficulty": "medium"},   # 60m -> Spills to Day 2
    ]
    timetable = [
        {"day": 1, "hours": 2},
        {"day": 2, "hours": 2},
        {"day": 3, "hours": 2},
        {"day": 4, "hours": 2},
        {"day": 5, "hours": 2},
        {"day": 6, "hours": 0},
        {"day": 7, "hours": 0},
    ]
    schedule = generate_schedule(concepts, hours_per_day=2, calendar_timetable=timetable)
    assert schedule[0].day == 1
    assert schedule[1].day == 1
    assert schedule[2].day == 2
