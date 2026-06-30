import networkx as nx
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator

# --- Shared structures ---
class BookReference(BaseModel):
    source: str = Field(description="Textbook name, slides, lecture notes, or other source cited")
    chapter: Optional[str] = Field(None, description="Chapter or section number/name, e.g. Chapter 3")
    edition: Optional[str] = Field(None, description="Book edition or version details, e.g. 5th Edition")

# --- Stage 1 schemas ---
class AIConceptItem(BaseModel):
    id: str = Field(description="Temporary ID like c1, c2, ...")
    name: str = Field(description="Name of the study concept")
    description: str = Field(description="Short 1-2 sentence description of the concept")
    difficulty: Literal["easy", "medium", "hard"] = Field("medium", description="Assigned difficulty level")
    source_hint: Optional[List[BookReference]] = Field(None, description="Direct syllabus book/slides references mapping to this concept")
    recommended_reading: Optional[List[BookReference]] = Field(None, description="Recommended readings (textbook chapter references)")
    is_inferred_reading: bool = Field(False, description="True if no direct source was found and reading is general knowledge reference")

class ExtractResponse(BaseModel):
    subject_domain: Optional[str] = Field(None, description="Inferred overall subject domain, e.g. Computer Networks")
    source_books: Optional[List[BookReference]] = Field(None, description="List of primary books/sources detected in the syllabus")
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
    confidence: float = Field(1.0, description="LLM-assigned confidence score between 0 and 1")
    source: Literal["llm_inferred", "seeded_from_prior_graph", "user_edited"] = Field("llm_inferred")

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
    platform: str = Field(description="Recommended platform, e.g. Neso Academy, Wikipedia, Cisco, MDN Web Docs, etc.")
    query: str = Field(description="Dynamic search keyword phrase, e.g. Physical Layer Data Communication")

class ConceptContentAI(BaseModel):
    concept_id: str = Field(description="Must match one of the concept IDs from Stage 1")
    explanation: str = Field(description="Detailed explanation with Analogy, Examples, and Reading references in Markdown")
    quiz: List[AIQuizQuestion] = Field(description="Exactly 3 quiz questions (2 MCQ and 1 short answer)")
    resources: List[AIResource] = Field(description="List of 2-3 study resources with platforms & queries")

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
