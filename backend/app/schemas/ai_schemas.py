import networkx as nx
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator

# --- Stage 1 schemas ---
class AIConceptItem(BaseModel):
    id: str = Field(description="Temporary ID like c1, c2, ...")
    name: str = Field(description="Name of the study concept")
    description: str = Field(description="Short 1-2 sentence description of the concept")

class ExtractResponse(BaseModel):
    concepts: List[AIConceptItem]

    @field_validator('concepts')
    @classmethod
    def validate_count(cls, v: List[AIConceptItem]) -> List[AIConceptItem]:
        if len(v) < 4 or len(v) > 12:
            raise ValueError("Expected 4 to 12 concepts")
        return v

# --- Stage 2 schemas ---
class AIEdge(BaseModel):
    from_id: str = Field(description="Origin concept ID")
    to_id: str = Field(description="Destination concept ID (which requires from_id)")

class GraphResponse(BaseModel):
    edges: List[AIEdge]

    @field_validator('edges')
    @classmethod
    def validate_dag(cls, edges: List[AIEdge]) -> List[AIEdge]:
        # Validate that the edges form a Directed Acyclic Graph (DAG)
        G = nx.DiGraph()
        for e in edges:
            if e.from_id == e.to_id:
                raise ValueError(f"Self-loops are not allowed! Cycle found on {e.from_id}")
            G.add_edge(e.from_id, e.to_id)
        if not nx.is_directed_acyclic_graph(G):
            raise ValueError("The dependency graph contains cycles!")
        return edges

# --- Stage 4 schemas ---
class AIQuizQuestion(BaseModel):
    type: Literal["mcq", "short_answer"]
    question: str
    options: Optional[List[str]] = None
    answer: str

class AIResource(BaseModel):
    type: Literal["video", "docs", "article"]
    title: str
    url: str

class ConceptContentAI(BaseModel):
    concept_id: str = Field(description="Must match one of the concept IDs from Stage 1")
    explanation: str = Field(description="Detailed explanation of the concept (2-3 sentences)")
    quiz: List[AIQuizQuestion] = Field(description="Exactly 3 quiz questions (2 MCQ and 1 short answer)")
    resources: List[AIResource] = Field(description="List of 2-3 study resources")

class BatchContentResponse(BaseModel):
    concepts: List[ConceptContentAI]


# --- Replanning schemas ---
class AIReplanScheduleItem(BaseModel):
    concept_id: str
    week: int
    day: int
    priority: Literal["high", "medium", "low"]

class ReplanResponse(BaseModel):
    schedule: List[AIReplanScheduleItem]
