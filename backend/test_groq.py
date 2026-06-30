import httpx
import os
import asyncio
from dotenv import load_dotenv
load_dotenv()

async def test_groq():
    api_key = os.getenv("GROQ_API_KEY")
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        res = await client.get("https://api.groq.com/openai/v1/models", headers=headers)
        print(f"Status: {res.status_code}")
        models = res.json().get("data", [])
        for m in models:
            print(f"Model ID: {m['id']}")

asyncio.run(test_groq())
