from abc import ABC, abstractmethod
import os
import json
import logging
import httpx
from typing import Dict, Any

logger = logging.getLogger(__name__)

class LLMProvider(ABC):
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str = "You are a helpful assistant.",
        temperature: float = 0.1,
        response_format: str = "json",  # "json" or "text"
        max_tokens: int | None = None
    ) -> Dict[str, Any] | str:
        """Generate content from the LLM.

        Should support JSON mode and plain text mode.
        """
        pass

class GroqProvider(LLMProvider):
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        self.model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"
        if not self.api_key:
            logger.warning("GROQ_API_KEY is not set in environment variables.")

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "You are a helpful assistant.",
        temperature: float = 0.1,
        response_format: str = "json",
        max_tokens: int | None = None
    ) -> Dict[str, Any] | str:
        if not self.api_key:
            raise ValueError("GROQ_API_KEY environment variable is not set!")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature,
            "stream": False
        }
        if response_format == "json":
            payload["response_format"] = {"type": "json_object"}
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(self.api_url, headers=headers, json=payload)
            if response.status_code == 429 and payload.get("model") == "llama-3.3-70b-versatile":
                logger.warning("Groq rate limit (TPM/TPD) exceeded on llama-3.3-70b-versatile. Falling back to llama-3.1-8b-instant permanently...")
                self.model = "llama-3.1-8b-instant"
                payload["model"] = "llama-3.1-8b-instant"
                response = await client.post(self.api_url, headers=headers, json=payload)
                
            if response.status_code != 200:
                logger.error(f"Groq API error (status {response.status_code}): {response.text}")
                raise RuntimeError(f"Groq API failed: {response.text}")
            
            data = response.json()
            content = data["choices"][0]["message"]["content"]

            # Asynchronously log API usage statistics
            try:
                usage = data.get("usage", {})
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
                
                # Approximate pricing for Llama-3.3-70b-versatile: $0.59/M prompt, $0.79/M completion
                cost = (prompt_tokens * 0.59 + completion_tokens * 0.79) / 1000000.0
                latency = int(response.elapsed.total_seconds() * 1000)

                action = "chat"
                lower_prompt = prompt.lower()
                lower_system = system_prompt.lower()

                if "extract core concepts" in lower_prompt:
                    action = "concept_extraction"
                elif "dependency edges" in lower_prompt:
                    action = "edge_generation"
                elif "detailed explanations" in lower_prompt:
                    action = "content_generation"
                elif "soft-grading" in lower_system or "quiz/grade" in lower_prompt:
                    action = "soft_grading"
                elif "prerequisite" in lower_system or "edges/explanation" in lower_prompt:
                    action = "edge_explanation"

                from app.database import AsyncSessionLocal
                from app.models.database import ApiUsageLog

                async with AsyncSessionLocal() as db:
                    log_entry = ApiUsageLog(
                        action_name=action,
                        provider="groq",
                        tokens_prompt=prompt_tokens,
                        tokens_completion=completion_tokens,
                        latency_ms=latency,
                        cost_usd=cost,
                        cache_hit=False
                    )
                    db.add(log_entry)
                    await db.commit()
            except Exception as log_err:
                logger.warning(f"Failed to log API usage statistics: {log_err}")

            if response_format == "json":
                try:
                    return json.loads(content)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON content from Groq: {content}")
                    raise e
            return content

_provider_instance: LLMProvider | None = None

def get_llm_provider() -> LLMProvider:
    global _provider_instance
    if _provider_instance is None:
        _provider_instance = GroqProvider()
    return _provider_instance
