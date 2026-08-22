import pytest
from unittest.mock import AsyncMock, patch
from app.services.resource_classifier import (
    ResourceMetadata,
    classify_resource
)

@pytest.mark.asyncio
async def test_resource_classifier_structure_and_mock():
    """Verify that classify_resource processes input and parses structured ResourceMetadata output."""
    mock_result = ResourceMetadata(
        resource_type="video",
        estimated_depth="intro",
        format_confidence=0.95,
        reasoning="YouTube domain with intro visual tutorial"
    )

    with patch("app.services.resource_classifier.get_classifier_chain") as mock_get_chain:
        mock_chain = AsyncMock()
        mock_chain.ainvoke.return_value = mock_result
        mock_get_chain.return_value = mock_chain

        res = await classify_resource(
            title="3Blue1Brown - Neural Networks Chapter 1",
            url="https://www.youtube.com/watch?v=aircAruvnKk",
            description="What is a neural network? A visual introduction to deep learning."
        )

    assert res.resource_type == "video"
    assert res.estimated_depth == "intro"
    assert res.format_confidence == 0.95
    assert res.reasoning is not None

def test_resource_metadata_pydantic_validation():
    """Verify that ResourceMetadata enforces schema boundaries."""
    meta = ResourceMetadata(
        resource_type="practice_set",
        estimated_depth="deep_dive",
        format_confidence=0.88,
        reasoning="LeetCode algorithm problem"
    )
    assert meta.resource_type == "practice_set"
    assert meta.estimated_depth == "deep_dive"
    assert 0.0 <= meta.format_confidence <= 1.0

    # Test out-of-bounds confidence validation
    with pytest.raises(Exception):
        ResourceMetadata(
            resource_type="video",
            estimated_depth="intro",
            format_confidence=1.5  # Invalid > 1.0
        )
