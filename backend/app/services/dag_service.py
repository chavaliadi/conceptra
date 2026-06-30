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

def generate_schedule(sorted_concepts: List[Dict[str, Any]], hours_per_day: int = 2) -> List[ScheduleItem]:
    """
    Generates a schedule (week, day, priority) for a sorted list of concepts.
    Uses greedy bin-packing to pack concepts into 5 days per week (Days 1 to 5).
    Each concept difficulty maps to study time:
    - easy -> 30 min (0.5 hours)
    - medium -> 60 min (1.0 hours)
    - hard -> 90 min (1.5 hours)
    """
    difficulty_minutes = {"easy": 30, "medium": 60, "hard": 90}
    schedule = []
    
    day_index = 0
    remaining_minutes = hours_per_day * 60
    
    total_concepts = len(sorted_concepts)
    
    for i, c in enumerate(sorted_concepts):
        cid = c["id"]
        diff = c.get("difficulty", "medium").lower()
        cost = difficulty_minutes.get(diff, 60)
        
        # Greedy packing: if the concept does not fit in remaining minutes, move to next day
        # Exception: if it's the start of the day (remaining == budget), we must allocate it anyway
        if cost > remaining_minutes and remaining_minutes < (hours_per_day * 60):
            day_index += 1
            remaining_minutes = hours_per_day * 60
            
        week = (day_index // 5) + 1
        day = (day_index % 5) + 1
        
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
