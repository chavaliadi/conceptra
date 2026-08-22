import pytest
from unittest.mock import patch, AsyncMock
from app.services.ai_service import build_graph, extract_concepts
from app.schemas.ai_schemas import AIConceptItem

@pytest.mark.asyncio
async def test_build_graph_retry_with_correction_prompt():
    """Verify that build_graph feeds the cycle error back into the LLM on attempt 2."""
    concepts = [
        AIConceptItem(id="c1", name="Concept 1", description="Desc 1", difficulty="easy"),
        AIConceptItem(id="c2", name="Concept 2", description="Desc 2", difficulty="medium"),
    ]

    # Attempt 1: Cyclic edges (c1 -> c2 and c2 -> c1)
    bad_cyclic_response = {
        "edges": [
            {"from_id": "c1", "to_id": "c2", "confidence": 1.0, "source": "llm_inferred"},
            {"from_id": "c2", "to_id": "c1", "confidence": 1.0, "source": "llm_inferred"},
        ]
    }

    # Attempt 2: Corrected acyclic DAG (c1 -> c2)
    good_acyclic_response = {
        "edges": [
            {"from_id": "c1", "to_id": "c2", "confidence": 1.0, "source": "llm_inferred"}
        ]
    }

    prompts_received = []

    async def mock_call_groq_json(prompt: str, system_prompt: str, temperature: float, max_tokens: int):
        prompts_received.append(prompt)
        if len(prompts_received) == 1:
            return bad_cyclic_response
        return good_acyclic_response

    with patch("app.services.ai_service._call_groq_json", side_effect=mock_call_groq_json):
        result_edges = await build_graph(concepts)

    # 1. Verify two calls were made
    assert len(prompts_received) == 2

    # 2. Verify attempt 1 prompt did not have correction note
    assert "CORRECTION REQUIRED" not in prompts_received[0]

    # 3. Verify attempt 2 prompt explicitly contained the previous cycle error
    attempt_2_prompt = prompts_received[1]
    assert "CORRECTION REQUIRED (Previous Attempt Failed):" in attempt_2_prompt
    assert "The dependency graph contains cycles!" in attempt_2_prompt
    assert "remove or reverse one of the conflicting edges" in attempt_2_prompt

    # 4. Verify result returned valid corrected DAG
    assert len(result_edges) == 1
    assert result_edges[0].from_id == "c1"
    assert result_edges[0].to_id == "c2"

@pytest.mark.asyncio
async def test_extract_concepts_retry_with_correction_prompt():
    """Verify that extract_concepts feeds schema validation errors back to the LLM on retry."""
    # Attempt 1: Too few concepts (< 4) violates Pydantic validator
    bad_count_response = {
        "subject_domain": "Python",
        "source_books": [],
        "concepts": [
            {"id": "c1", "name": "Variables", "description": "Variables desc", "difficulty": "easy"}
        ]
    }

    # Attempt 2: Valid count (4 concepts)
    good_count_response = {
        "subject_domain": "Python",
        "source_books": [],
        "concepts": [
            {"id": f"c{i}", "name": f"Concept {i}", "description": f"Desc {i}", "difficulty": "easy"}
            for i in range(1, 5)
        ]
    }

    prompts_received = []

    async def mock_call_groq_json(prompt: str, system_prompt: str, temperature: float, max_tokens: int):
        prompts_received.append(prompt)
        if len(prompts_received) == 1:
            return bad_count_response
        return good_count_response

    with patch("app.services.ai_service._call_groq_json", side_effect=mock_call_groq_json):
        result = await extract_concepts(topic="Python", num_concepts=4)

    assert len(prompts_received) == 2
    assert "CORRECTION REQUIRED (Previous Attempt Failed):" in prompts_received[1]
    assert "Expected 4 to 40 concepts" in prompts_received[1]
    assert len(result.concepts) == 4
