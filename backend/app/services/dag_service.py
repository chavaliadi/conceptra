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

def generate_schedule(sorted_concept_ids: List[str], hours_per_day: int = 2) -> List[ScheduleItem]:
    """
    Generates a schedule (week, day, priority) for a sorted list of concepts.
    Assumes 5 days of study per week.
    """
    schedule = []
    day_index = 0
    total_concepts = len(sorted_concept_ids)
    
    for i, cid in enumerate(sorted_concept_ids):
        week = (day_index // 5) + 1
        day = (day_index % 5) + 1
        
        # High priority for early concepts, low for later
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
        day_index += 1
        
    return schedule
