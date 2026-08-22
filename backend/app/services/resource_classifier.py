import os
from typing import Literal
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

class ResourceMetadata(BaseModel):
    """Structured metadata extracted for learning resources to track effectiveness."""
    resource_type: Literal["video", "article", "practice_set", "other"] = Field(
        description="Type of the learning material: video (e.g., YouTube, lectures), article (docs, tutorials, blogs), practice_set (quizzes, problem sets, exercises), or other (repos, tools, ambiguous/broken links)."
    )
    estimated_depth: Literal["intro", "deep_dive"] = Field(
        description="Depth level: 'intro' for high-level overviews, quick tutorials, surface summaries; 'deep_dive' for comprehensive guides, advanced technical specs, rigorous exercises."
    )
    format_confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 and 1.0 reflecting how certain the classification is given the provided URL, title, and description."
    )
    reasoning: str | None = Field(
        default=None,
        description="Short 1-sentence rationale for the classification decision."
    )

CLASSIFIER_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are an educational resource classification engine.
Analyze the provided resource title, URL, and description to extract structured metadata.

Classification Rules:
1. resource_type:
   - 'video': Video hosting platforms (YouTube, Vimeo, Coursera lectures, etc.)
   - 'article': Documentation, blog posts, textbook chapters, technical guides (MDN, Wikipedia, Medium, Dev.to, official docs).
   - 'practice_set': Interactive problem sets, LeetCode, HackerRank, interactive quizzes, flashcards, exercises.
   - 'other': Repositories, software download links, forums, podcasts, ambiguous links, or broken/gibberish metadata.
2. estimated_depth:
   - 'intro': Basic overviews, crash courses, quick starts, glossary definitions, short summaries, or low-information content.
   - 'deep_dive': In-depth documentation, multi-part tutorials, advanced engineering architectures, rigorous problem sets.
3. format_confidence:
   - High (0.8 - 1.0): Clear domain, explicit title and description matching the format.
   - Moderate (0.5 - 0.79): Moderate clarity or slightly ambiguous format.
   - Low (0.0 - 0.49): Highly ambiguous, insufficient info, broken URLs, or nonsense text.

Be objective, robust against incomplete or corrupt descriptions, and strictly output structured data conforming to the schema."""
    ),
    (
        "human",
        """Resource to classify:
- Title: {title}
- URL: {url}
- Description: {description}"""
    )
])

def get_classifier_chain(api_key: str | None = None, model_name: str | None = None):
    """Builds a LangChain structured extraction chain with Groq."""
    key = api_key or os.getenv("GROQ_API_KEY")
    if not key:
        raise ValueError("GROQ_API_KEY must be provided or set in environment variables.")
        
    chosen_model = model_name or os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    llm = ChatGroq(
        api_key=key,
        model=chosen_model,
        temperature=0.0
    )
    structured_llm = llm.with_structured_output(ResourceMetadata)
    return CLASSIFIER_PROMPT | structured_llm

async def classify_resource(
    title: str,
    url: str | None = None,
    description: str | None = None,
    api_key: str | None = None,
    model_name: str | None = None
) -> ResourceMetadata:
    """Classify a learning resource into structured metadata using LangChain + Groq."""
    chain = get_classifier_chain(api_key=api_key, model_name=model_name)
    result = await chain.ainvoke({
        "title": title or "Unknown",
        "url": url or "N/A",
        "description": description or "N/A"
    })
    return result
