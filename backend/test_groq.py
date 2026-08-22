import httpx
import os
import pytest
from dotenv import load_dotenv
load_dotenv()

@pytest.mark.asyncio
async def test_groq():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        pytest.skip("GROQ_API_KEY is not set in environment")

    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        res = await client.get("https://api.groq.com/openai/v1/models", headers=headers)
        assert res.status_code == 200
        models = res.json().get("data", [])
        assert len(models) > 0

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_groq())
