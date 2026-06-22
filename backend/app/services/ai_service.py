import os
import json
import logging
import httpx
import networkx as nx
from typing import List, Dict, Any
from app.schemas.ai_schemas import (
    AIConceptItem,
    ExtractResponse,
    AIEdge,
    GraphResponse,
    ConceptContentAI,
    BatchContentResponse,
    ReplanResponse,
    AIReplanScheduleItem
)

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

async def _call_groq_json(prompt: str, system_prompt: str = "You are a helpful assistant.", temperature: float = 0.1) -> Dict[str, Any]:
    """Helper to call Groq API and guarantee JSON output."""
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY environment variable is not set!")
        
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": temperature,
        "response_format": {"type": "json_object"},
        "stream": False
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(GROQ_API_URL, headers=headers, json=payload)
        if response.status_code != 200:
            logger.error(f"Groq API error (status {response.status_code}): {response.text}")
            raise RuntimeError(f"Groq API failed: {response.text}")
            
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)

async def extract_concepts(topic: str, num_concepts: int = 8) -> List[AIConceptItem]:
    """Stage 1: Extract concepts from a topic with up to 3 retries."""
    system_prompt = "You are an expert curriculum builder that output valid JSON matching the requested structure."
    prompt = f"""
    Extract a list of core concepts to study the topic: "{topic}".
    You MUST return a JSON object with a single key "concepts" which is a list of objects.
    Each object must have the following fields:
    - "id": a temporary ID like "c1", "c2", "c3" (keep them sequential)
    - "name": the name of the concept
    - "description": a short 1-2 sentence description of the concept

    Generate exactly {num_concepts} concepts.
    """
    
    for attempt in range(1, 4):
        temp = 0.1 * attempt
        try:
            result_json = await _call_groq_json(prompt, system_prompt, temperature=temp)
            # Validate with Pydantic
            validated = ExtractResponse.model_validate(result_json)
            return validated.concepts
        except Exception as e:
            logger.warning(f"Stage 1 extraction attempt {attempt} failed: {e}")
            if attempt == 3:
                raise RuntimeError(f"Failed to extract concepts after 3 attempts: {e}")

async def build_graph(concepts: List[AIConceptItem]) -> List[AIEdge]:
    """Stage 2: Build dependency edges between concepts with up to 3 retries (including DAG validation)."""
    concepts_data = [{"id": c.id, "name": c.name, "description": c.description} for c in concepts]
    concepts_json = json.dumps(concepts_data, indent=2)
    
    system_prompt = "You are a graph theory and curriculum routing expert. You output valid JSON."
    prompt = f"""
    Establish dependency edges between the following study concepts:
    {concepts_json}

    A dependency edge from "A" to "B" means "A" must be studied before "B" can be understood.
    You MUST return a JSON object with a single key "edges" which is a list of objects.
    Each object must have:
    - "from_id": the ID of the prerequisite concept (e.g. "c1")
    - "to_id": the ID of the dependent concept (e.g. "c2")

    CRITICAL RULES:
    1. Do NOT create cycles. The graph must be a Directed Acyclic Graph (DAG).
    2. Avoid self-loops (from_id cannot equal to_id).
    3. Ensure there is a path through all concepts where possible, but keep edges reasonable (typically N-1 to N*1.5 edges).
    """
    
    for attempt in range(1, 4):
        temp = 0.1 * attempt
        try:
            result_json = await _call_groq_json(prompt, system_prompt, temperature=temp)
            # Validate with Pydantic (which runs DAG cycle checking)
            validated = GraphResponse.model_validate(result_json)
            return validated.edges
        except Exception as e:
            logger.warning(f"Stage 2 graph generation attempt {attempt} failed: {e}")
            if attempt == 3:
                raise RuntimeError(f"Failed to generate dependency graph after 3 attempts: {e}")

async def generate_content(concepts: List[AIConceptItem]) -> List[ConceptContentAI]:
    """Stage 4: Generate explanations, quizzes, and resources for all concepts in one batched call."""
    concepts_data = [{"id": c.id, "name": c.name, "description": c.description} for c in concepts]
    concepts_json = json.dumps(concepts_data, indent=2)
    
    system_prompt = "You are an elite technical educator who creates high-quality learning content and outputs JSON."
    prompt = f"""
    Generate detailed explanations, quizzes, and resources for the following concepts:
    {concepts_json}

    For EACH concept in the list, you MUST generate:
    1. "explanation": A detailed, clear explanation (2-3 sentences) explaining the core concept.
    2. "quiz": A list of exactly 3 quiz questions. The first 2 must be multiple-choice ("type": "mcq") with an "options" list of 4 options and the correct "answer" matching one of the options. The 3rd question must be a short-answer question ("type": "short_answer") with no options and a sample correct "answer".
    3. "resources": A list of 2-3 study resources. Each must have "type" ("video", "docs", or "article"), a "title", and a "url" (use realistic educational domains like youtube.com, wikipedia.org, or docs.python.org).

    You MUST return a JSON object with a single key "concepts" which is a list of objects, each having:
    - "concept_id": the ID of the concept matching the input list (e.g. "c1")
    - "explanation": the explanation string
    - "quiz": the list of 3 questions
    - "resources": the list of resources
    """
    
    for attempt in range(1, 4):
        temp = 0.1 * attempt
        try:
            result_json = await _call_groq_json(prompt, system_prompt, temperature=temp)
            # Validate with Pydantic
            validated = BatchContentResponse.model_validate(result_json)
            return validated.concepts
        except Exception as e:
            logger.warning(f"Stage 4 content generation attempt {attempt} failed: {e}")
            if attempt == 3:
                raise RuntimeError(f"Failed to generate content batch after 3 attempts: {e}")

async def replan_schedule(
    topic: str,
    concepts: List[Dict[str, Any]],      # List of {"id": str, "name": str}
    edges: List[Dict[str, Any]],         # List of {"from_id": str, "to_id": str}
    current_schedule: List[Dict[str, Any]], # List of {"concept_id": str, "week": int, "day": int, "priority": str}
    struggling_ids: List[str],            # List of concept string IDs
    remaining_days: int
) -> List[AIReplanScheduleItem]:
    """Call Groq to redistribute study schedule based on struggling concepts."""
    # Build the descendants using networkx
    G = nx.DiGraph()
    for c in concepts:
        G.add_node(c["id"])
    for e in edges:
        G.add_edge(e["from_id"], e["to_id"])
        
    descendants = set()
    for sid in struggling_ids:
        if G.has_node(sid):
            descendants.update(nx.descendants(G, sid))
            
    # Prepare prompt inputs
    concepts_info = []
    for c in concepts:
        cid = c["id"]
        status = "struggling" if cid in struggling_ids else ("dependent" if cid in descendants else "normal")
        concepts_info.append(f"- ID: {cid}, Name: {c['name']}, Description: {c.get('description', '')}, Status: {status}")
        
    current_sched_info = []
    for s in current_schedule:
        current_sched_info.append(f"- Concept ID: {s['concept_id']}, Week: {s['week']}, Day: {s['day']}, Priority: {s['priority']}")
        
    system_prompt = "You are a graph theory and study scheduling routing expert. You output valid JSON."
    prompt = f"""
    We need to adaptively replan a study schedule for the topic "{topic}".
    The student is struggling with some concepts. We need to redistribute the study schedule over the remaining {remaining_days} days.
    
    CRITICAL INSTRUCTIONS:
    1. Struggling concepts (marked as "struggling") and their downstream dependents (marked as "dependent") should be delayed or prioritized higher.
    2. Concepts that are normal or already learned should be compressed/accelerated.
    3. The schedule MUST respect prerequisite order (edges): a concept cannot be studied before its prerequisites are complete.
    4. Provide week and day assignments assuming 5 study days per week (Days 1 to 5).
    5. Output the entire schedule (all concept IDs) in a single valid JSON list.
    
    Concepts metadata:
    {"\n".join(concepts_info)}
    
    Dependencies (Prerequisite -> Dependent):
    {json.dumps(edges)}
    
    Current Schedule:
    {"\n".join(current_sched_info)}
    
    You MUST return a JSON object with a single key "schedule" containing a list of objects, each with:
    - "concept_id": the ID of the concept (matching input list)
    - "week": the week number (integer starting from 1)
    - "day": the day number (integer from 1 to 5)
    - "priority": the priority string ("high", "medium", "low")
    
    Output the JSON now:
    """
    
    for attempt in range(1, 4):
        temp = 0.1 * attempt
        try:
            result_json = await _call_groq_json(prompt, system_prompt, temperature=temp)
            validated = ReplanResponse.model_validate(result_json)
            return validated.schedule
        except Exception as e:
            logger.warning(f"AI replanning attempt {attempt} failed: {e}")
            if attempt == 3:
                raise RuntimeError(f"Failed to generate replanned schedule after 3 attempts: {e}")
