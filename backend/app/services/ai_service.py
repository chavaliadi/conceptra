import os
import json
import logging
import asyncio
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

from app.services.llm_provider import get_llm_provider

async def _call_groq_json(prompt: str, system_prompt: str = "You are a helpful assistant.", temperature: float = 0.1, max_tokens: int | None = None) -> Dict[str, Any]:
    """Helper to call LLM provider and guarantee JSON output."""
    provider = get_llm_provider()
    res = await provider.generate(prompt, system_prompt, temperature, response_format="json", max_tokens=max_tokens)
    if isinstance(res, dict):
        return res
    raise ValueError("Expected JSON response from LLMProvider")

async def _handle_retry_sleep(attempt: int, error: Exception):
    """Parse retry-after time from Groq error message and sleep, adding jitter to avoid collision."""
    import random
    sleep_time = 3 * attempt + random.uniform(0.5, 2.0)
    try:
        import re
        match = re.search(r"try again in ([\d\.]+)s", str(error))
        if match:
            sleep_time = float(match.group(1)) + random.uniform(0.5, 1.5)
    except Exception:
        pass
    logger.info(f"Rate limit hit. Sleeping for {sleep_time:.2f} seconds before retry attempt {attempt + 1}")
    await asyncio.sleep(sleep_time)

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
    
    for attempt in range(1, 6):
        temp = 0.1 * attempt
        try:
            result_json = await _call_groq_json(prompt, system_prompt, temperature=temp, max_tokens=600)
            # Validate with Pydantic
            validated = ExtractResponse.model_validate(result_json)
            return validated.concepts
        except Exception as e:
            logger.warning(f"Stage 1 extraction attempt {attempt} failed: {e}")
            if attempt == 5:
                raise RuntimeError(f"Failed to extract concepts after 5 attempts: {e}")
            await _handle_retry_sleep(attempt, e)

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
    
    for attempt in range(1, 6):
        temp = 0.1 * attempt
        try:
            result_json = await _call_groq_json(prompt, system_prompt, temperature=temp, max_tokens=400)
            # Validate with Pydantic (which runs DAG cycle checking)
            validated = GraphResponse.model_validate(result_json)
            return validated.edges
        except Exception as e:
            logger.warning(f"Stage 2 graph generation attempt {attempt} failed: {e}")
            if attempt == 5:
                raise RuntimeError(f"Failed to generate dependency graph after 5 attempts: {e}")
            await _handle_retry_sleep(attempt, e)

async def generate_single_concept_content(concept: AIConceptItem) -> ConceptContentAI:
    """Generate detailed explanation, quiz, and resources for a single concept with up to 3 retries."""
    system_prompt = "You are an elite technical educator who creates high-quality learning content and outputs JSON."
    prompt = f"""
    Generate a detailed explanation, quiz, and resources for the following concept:
    ID: {concept.id}
    Name: {concept.name}
    Description: {concept.description}

    You MUST generate:
    1. "explanation": A detailed, clear explanation (2-3 sentences) explaining the core concept.
    2. "quiz": A list of exactly 3 quiz questions. The first 2 must be multiple-choice ("type": "mcq") with an "options" list of 4 options and the correct "answer" matching one of the options. The 3rd question must be a short-answer question ("type": "short_answer") with no options and a sample correct "answer".
    3. "resources": A list of 2-3 study resources. Each must have "type" ("video", "docs", or "article"), a "title", and a "url" (use realistic educational domains like youtube.com, wikipedia.org, or docs.python.org).

    You MUST return a JSON object with the following fields:
    - "concept_id": Must be "{concept.id}"
    - "explanation": the explanation string
    - "quiz": the list of 3 questions
    - "resources": the list of resources
    """
    
    for attempt in range(1, 6):
        temp = 0.1 * attempt
        try:
            result_json = await _call_groq_json(prompt, system_prompt, temperature=temp, max_tokens=800)
            # Validate with Pydantic
            validated = ConceptContentAI.model_validate(result_json)
            return validated
        except Exception as e:
            logger.warning(f"Stage 4 single concept content generation attempt {attempt} for {concept.name} failed: {e}")
            if attempt == 5:
                raise RuntimeError(f"Failed to generate content for concept {concept.name} after 5 attempts: {e}")
            await _handle_retry_sleep(attempt, e)

async def generate_content(concepts: List[AIConceptItem]) -> List[ConceptContentAI]:
    """Stage 4: Generate explanations, quizzes, and resources for all concepts concurrently."""
    # We use a semaphore to avoid overloading the Groq API rate limits (TPM/RPM limits)
    semaphore = asyncio.Semaphore(2)
    
    async def sem_task(index: int, concept: AIConceptItem) -> ConceptContentAI:
        # Stagger start by 1.2s to prevent initial rate-limit collisions
        await asyncio.sleep(index * 1.2)
        async with semaphore:
            return await generate_single_concept_content(concept)
            
    tasks = [sem_task(i, c) for i, c in enumerate(concepts)]
    results = await asyncio.gather(*tasks)
    return list(results)

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
    
    for attempt in range(1, 6):
        temp = 0.1 * attempt
        try:
            result_json = await _call_groq_json(prompt, system_prompt, temperature=temp, max_tokens=500)
            validated = ReplanResponse.model_validate(result_json)
            return validated.schedule
        except Exception as e:
            logger.warning(f"AI replanning attempt {attempt} failed: {e}")
            if attempt == 5:
                raise RuntimeError(f"Failed to generate replanned schedule after 5 attempts: {e}")
            await _handle_retry_sleep(attempt, e)
