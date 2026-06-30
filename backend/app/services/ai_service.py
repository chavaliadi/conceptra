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

async def extract_concepts(topic: str, num_concepts: int = 8, syllabus_text: str | None = None) -> ExtractResponse:
    """Stage 1: Extract concepts from a topic or syllabus text with up to 5 retries."""
    system_prompt = "You are an expert curriculum builder that outputs valid JSON matching the requested structure."
    
    if syllabus_text:
        prompt = f"""
        You are parsing a course syllabus for the topic: "{topic}".
        Analyze the following extracted syllabus text and extract a list of core concepts to study.
        
        CRITICAL GRANULARITY RULE:
        Do NOT extract broad chapters, units, or modules (like "Data Link Layer", "Error Control", "Media Access Control", or "Wireless LANs"). Instead, extract specific, concrete, bullet-level sub-concepts, mechanisms, and algorithms covered within those units. 
        For example:
        - Instead of "Error Control", extract separate concepts for: "Parity Checks", "Cyclic Redundancy Check (CRC)", "Hamming Distance & Codes", and "Checksum".
        - Instead of "Data Link Layer Protocols", extract: "Stop-and-Wait ARQ", "Go-Back-N ARQ", and "Selective Repeat ARQ".
        - For media access, extract: "ALOHA", "CSMA/CD", and "CSMA/CA".
        Each concept name must be highly specific so a student can be quizzed specifically on that topic.
        
        Extract exactly {num_concepts} objects representing these granular concepts.
        
        You MUST return a JSON object with:
        1. "subject_domain": Inferred overall subject domain (e.g. "Computer Networks").
        2. "source_books": A list of primary textbooks, slide decks, or lecture note sources mentioned in the syllabus. Each source/book must be a JSON object with:
           - "source": Textbook title or name of the source (e.g. "Data Communication & Networking", "Notes I shared").
           - "chapter": Chapter number or section name if applicable (otherwise null).
           - "edition": Edition number or version details if applicable (otherwise null).
        3. "concepts": A list of exactly {num_concepts} objects representing the core study units from the syllabus. Each concept must have:
           - "id": temporary sequential ID: "c1", "c2", "c3"...
           - "name": clean, concise, highly specific study unit name.
           - "description": a short 1-2 sentence description.
           - "difficulty": "easy", "medium", or "hard".
           - "source_hint": a list of objects representing textbook/notes references from the syllabus matching this concept (e.g. [{{"source": "Forouzan", "chapter": "Chapter 10", "edition": "4th Edition"}}]).
           - "recommended_reading": recommended readings (usually a list of objects matching the source_hint textbook references).
           - "is_inferred_reading": false if book/reading references were detected, true if no book reference was found and reading is general knowledge reference.

        Deduplicate concepts: if multiple textbook references cover the same concept (like Tanenbaum and Forouzan both covering "Paging"), combine them into one concept with multiple recommended_reading entries.
        """
    else:
        prompt = f"""
        Extract a list of core concepts to study the topic: "{topic}".
        
        CRITICAL GRANULARITY RULE:
        Do NOT extract broad top-level units or fields. Extract specific, concrete, bullet-level sub-concepts, tools, or algorithms. 
        For example:
        - For "Python Programming", extract: "List Comprehensions", "Decorators", "Generator Functions", "Context Managers (with statement)" instead of "Functions" or "Control Flow".
        - For "Data Structures", extract: "Singly Linked Lists", "Binary Search Trees", "AVL Trees", "Hash Collisions & Resolution" instead of "Trees" or "Linked Lists".
        
        Extract exactly {num_concepts} objects representing these granular concepts.
        
        You MUST return a JSON object with:
        1. "subject_domain": Inferred overall subject domain (e.g. "{topic}").
        2. "source_books": null or an empty list.
        3. "concepts": A list of exactly {num_concepts} objects. Each concept must have:
           - "id": temporary sequential ID: "c1", "c2", "c3"...
           - "name": clean, concise, highly specific study unit name.
           - "description": a short 1-2 sentence description.
           - "difficulty": "easy", "medium", or "hard".
           - "source_hint": null or an empty list.
           - "recommended_reading": a list of objects representing general reference sources. Each object must contain:
             - "source": Textbook title, domain or name of the source (e.g. "Python Documentation", "Python Crash Course").
             - "chapter": null.
             - "edition": null.
           - "is_inferred_reading": true (since we do not have a syllabus).
        """
    
    for attempt in range(1, 6):
        temp = 0.1 * attempt
        try:
            result_json = await _call_groq_json(prompt, system_prompt, temperature=temp, max_tokens=1000)
            # Validate with Pydantic
            validated = ExtractResponse.model_validate(result_json)
            return validated
        except Exception as e:
            logger.warning(f"Stage 1 extraction attempt {attempt} failed: {e}")
            if attempt == 5:
                raise RuntimeError(f"Failed to extract concepts after 5 attempts: {e}")
            await _handle_retry_sleep(attempt, e)

async def build_graph(concepts: List[AIConceptItem]) -> List[AIEdge]:
    """Stage 2: Build dependency edges between concepts with up to 5 retries (including DAG validation)."""
    concepts_data = [
        {
            "id": c.id, 
            "name": c.name, 
            "description": c.description,
            "difficulty": c.difficulty
        } 
        for c in concepts
    ]
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
    - "confidence": confidence score (float between 0.0 and 1.0)
    - "source": "llm_inferred"

    CRITICAL RULES:
    1. Do NOT create cycles. The graph must be a Directed Acyclic Graph (DAG).
    2. Avoid self-loops (from_id cannot equal to_id).
    3. Ensure there is a path through all concepts where possible, but keep edges reasonable (typically N-1 to N*1.5 edges).
    """
    
    for attempt in range(1, 6):
        temp = 0.1 * attempt
        try:
            result_json = await _call_groq_json(prompt, system_prompt, temperature=temp, max_tokens=600)
            # Validate with Pydantic (which runs DAG cycle checking)
            validated = GraphResponse.model_validate(result_json)
            return validated.edges
        except Exception as e:
            logger.warning(f"Stage 2 graph generation attempt {attempt} failed: {e}")
            if attempt == 5:
                raise RuntimeError(f"Failed to generate dependency graph after 5 attempts: {e}")
            await _handle_retry_sleep(attempt, e)

async def generate_single_concept_content(concept: AIConceptItem) -> ConceptContentAI:
    """Generate detailed explanation, quiz, and resources for a single concept with up to 5 retries."""
    system_prompt = "You are an elite technical educator who creates high-quality learning content and outputs JSON."
    
    # Format readings if available
    readings_str = ""
    if concept.recommended_reading:
        readings_str = "\n".join([f"* {r.source}: Chapter {r.chapter or ''}" for r in concept.recommended_reading])
    else:
        readings_str = "* General reference resources."

    prompt = f"""
    Generate detailed explanation, quiz, and resources for the following concept:
    ID: {concept.id}
    Name: {concept.name}
    Description: {concept.description}
    Difficulty: {concept.difficulty}
    Recommended Readings:
    {readings_str}

    You MUST return a JSON object with the following fields:
    1. "concept_id": Must be "{concept.id}"
    2. "explanation": A detailed, markdown-formatted study guide. It MUST contain the following sections:
       ### Concept Explanation
       [detailed 2-3 sentence explanation of the concept]
       
       💡 **Analogy:**
       [a relatable, memorable real-world analogy to help the student understand the concept]
       
       🌐 **Real-World Example:**
       [an actual engineering, programming, or network design implementation where this is used]
       
       🎯 **Exam Tip:**
       [direct exam advice, common exam questions, or mathematical formulas they must memorize]
       
       ⚠️ **Frequently Confused With:**
       [what this concept is commonly mistaken for, and the key difference, e.g. CSMA/CD vs CSMA/CA]
       
       📚 **Recommended Reading:**
       {readings_str}
       
    3. "quiz": A list of exactly 3 multiple-choice quiz questions. Each question must have:
       - "type": "mcq"
       - "question": a clear, challenging quiz question text targeting this concept
       - "options": exactly 4 distinct options/choices as a list of strings
       - "correct_option_index": 0-based integer index of the correct option in the options list (0, 1, 2, or 3)
       - Do NOT generate short-answer questions or write-in responses. Only multiple-choice.
    4. "resources": A list of exactly 2-3 study resources. Each resource MUST have:
       - "type": "video", "docs", or "article"
       - "title": human-readable title of the resource (e.g. "Physical Layer Explained")
       - "platform": the target platform name. Choose from: "Neso Academy", "Gate Smashers", "freeCodeCamp", "Wikipedia", "GeeksforGeeks", "Cisco Networking Academy", "MDN Web Docs", "Microsoft Learn", "Official Documentation".
       - "query": search keywords for this platform (e.g. "Physical Layer Data Communication", "OSI reference model", "checksum calculation tutorial").
       - Do NOT include any "url" key.
    """
    
    for attempt in range(1, 6):
        temp = 0.1 * attempt
        try:
            result_json = await _call_groq_json(prompt, system_prompt, temperature=temp, max_tokens=1000)
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
    # Semaphore(4): allow up to 4 concurrent Groq calls.
    # llama-3.3-70b-versatile TPM limit is 12k; each content call uses ~600 tokens max,
    # so 4 concurrent calls reserve ~2400 tokens/s - well within safe burst limits.
    # The stagger is intentionally removed: the semaphore itself controls throughput,
    # and pre-semaphore staggering was causing up to 9.6s of artificial idle waiting.
    semaphore = asyncio.Semaphore(4)
    
    async def sem_task(concept: AIConceptItem) -> ConceptContentAI:
        async with semaphore:
            return await generate_single_concept_content(concept)
            
    tasks = [sem_task(c) for c in concepts]
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
