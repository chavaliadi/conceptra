import networkx as nx
from typing import List, Dict, Any
from app.models.schemas import ScheduleItem

def validate_and_sort_dag(concepts: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> List[str]:
    """
    Validates that the given concepts and edges form a Directed Acyclic Graph.
    Returns the topologically sorted list of concept IDs.
    Raises ValueError if there is a cycle.
    """
    G = nx.DiGraph()
    for c in concepts:
        G.add_node(c["id"])
    for e in edges:
        G.add_edge(e["from_id"], e["to_id"])
        
    if not nx.is_directed_acyclic_graph(G):
        raise ValueError("The dependency graph contains cycles!")
        
    return list(nx.topological_sort(G))

def generate_schedule(
    sorted_concepts: List[Dict[str, Any]], 
    hours_per_day: int = 2,
    calendar_timetable: List[Dict[str, Any]] | None = None
) -> List[ScheduleItem]:
    """
    Generates a schedule (week, day, priority) for a sorted list of concepts.
    Uses greedy bin-packing to pack concepts into a weekly study schedule.
    If calendar_timetable is provided, it dictates the hours available on each day (Day 1 to 7).
    Rest days (hours = 0) are automatically skipped.
    """
    difficulty_minutes = {"easy": 30, "medium": 60, "hard": 90}
    schedule = []
    
    # Default to 5 study days (hours_per_day) and 2 rest days (0 hours) if no timetable is provided
    if not calendar_timetable:
        timetable = [
            {"day": 1, "hours": hours_per_day},
            {"day": 2, "hours": hours_per_day},
            {"day": 3, "hours": hours_per_day},
            {"day": 4, "hours": hours_per_day},
            {"day": 5, "hours": hours_per_day},
            {"day": 6, "hours": 0},
            {"day": 7, "hours": 0}
        ]
    else:
        timetable = calendar_timetable

    # Extract daily budgets in minutes (Days 1 to 7 corresponding to indices 0 to 6)
    daily_budgets = [int(item.get("hours", 0) * 60) for item in timetable]
    
    # Safety check: if all budgets are 0, fall back to standard budget to prevent infinite loops
    if sum(daily_budgets) == 0:
        daily_budgets = [hours_per_day * 60] * 5 + [0] * 2

    # Helper: Find the next available study day index
    def get_next_study_day(current_idx: int) -> int:
        idx = current_idx
        while daily_budgets[idx % 7] == 0:
            idx += 1
        return idx

    day_index = get_next_study_day(0)
    remaining_minutes = daily_budgets[day_index % 7]
    
    total_concepts = len(sorted_concepts)
    
    for i, c in enumerate(sorted_concepts):
        cid = c["id"]
        diff = c.get("difficulty", "medium").lower()
        cost = difficulty_minutes.get(diff, 60)
        
        # Greedy packing: if the concept does not fit in remaining minutes of the day,
        # advance to the next study day.
        # Exception: if it's the start of the day (remaining == budget), we must allocate it
        # to prevent deadlock when a concept cost exceeds the single-day budget limit.
        day_budget = daily_budgets[day_index % 7]
        if cost > remaining_minutes and remaining_minutes < day_budget:
            day_index = get_next_study_day(day_index + 1)
            remaining_minutes = daily_budgets[day_index % 7]
            day_budget = remaining_minutes
            
        week = (day_index // 7) + 1
        day = (day_index % 7) + 1
        
        # Priority mapping: early in topological order = high, later = low
        if i < total_concepts * 0.3:
            priority = "high"
        elif i < total_concepts * 0.7:
            priority = "medium"
        else:
            priority = "low"
            
        schedule.append(
            ScheduleItem(
                concept_id=cid,
                week=week,
                day=day,
                priority=priority
            )
        )
        
        # Deduct cost from day's budget
        remaining_minutes = max(0, remaining_minutes - cost)
        
    return schedule

