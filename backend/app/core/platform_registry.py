import urllib.parse
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

# Dictionary mapping platform name to search/direct URL template
PLATFORM_TEMPLATES: Dict[str, str] = {
    "neso academy": "https://www.youtube.com/results?search_query=Neso+Academy+{query}",
    "gate smashers": "https://www.youtube.com/results?search_query=Gate+Smashers+{query}",
    "freecodecamp": "https://www.youtube.com/results?search_query=freeCodeCamp+{query}",
    "computerphile": "https://www.youtube.com/results?search_query=Computerphile+{query}",
    "wikipedia": "https://en.wikipedia.org/wiki/{wiki_query}",
    "geeksforgeeks": "https://www.google.com/search?q=site:geeksforgeeks.org+{query}",
    "cisco networking academy": "https://www.google.com/search?q=site:cisco.com+{query}",
    "mdn web docs": "https://developer.mozilla.org/en-US/search?q={query}",
    "microsoft learn": "https://learn.microsoft.com/en-us/search/?terms={query}",
}

def resolve_resource_url(resource_type: str, platform: str, query: str) -> str:
    """
    Two-tier resolution server-side:
    - Tier 1: Match against known platforms in registry.
    - Tier 2: Safe fallback based on type (video -> YouTube, article/docs -> Google search).
    """
    platform_clean = platform.strip().lower()
    query_encoded = urllib.parse.quote_plus(query.strip())
    
    # Tier 1 Lookup
    if platform_clean in PLATFORM_TEMPLATES:
        template = PLATFORM_TEMPLATES[platform_clean]
        if platform_clean == "wikipedia":
            # For Wikipedia, format queries as a clean wiki link by replacing space with underscore
            wiki_query = query.strip().replace(" ", "_")
            wiki_query_encoded = urllib.parse.quote(wiki_query)
            return template.format(wiki_query=wiki_query_encoded)
        return template.format(query=query_encoded)
        
    # Tier 2 Fallback
    logger.warning(f"[platform_registry] Tier-2 fallback: platform='{platform}', type='{resource_type}', query='{query}'")
    if resource_type == "video":
        # YouTube fallback search query
        return f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(platform + ' ' + query)}"
    
    # Generic Google search fallback for docs/articles
    return f"https://www.google.com/search?q={urllib.parse.quote_plus(platform + ' ' + query)}"


SUBJECT_PLATFORM_MAP: Dict[str, List[str]] = {
    "computer networks": ["neso academy", "gate smashers", "computerphile", "cisco networking academy"],
    "data structures": ["gate smashers", "freecodecamp", "geeksforgeeks"],
    "algorithms": ["gate smashers", "freecodecamp", "geeksforgeeks"],
    "operating systems": ["neso academy", "gate smashers", "geeksforgeeks"],
    "database": ["geeksforgeeks", "mdn web docs", "freecodecamp"],
    "web": ["mdn web docs", "freecodecamp", "geeksforgeeks"],
    "_default": ["geeksforgeeks", "wikipedia", "freecodecamp"],
}

def get_preferred_platforms(subject_domain: str | None) -> List[str]:
    """Return preferred platform names for a given subject domain."""
    if not subject_domain:
        return SUBJECT_PLATFORM_MAP["_default"]
    domain_lower = subject_domain.strip().lower()
    for key in SUBJECT_PLATFORM_MAP:
        if key != "_default" and key in domain_lower:
            return SUBJECT_PLATFORM_MAP[key]
    return SUBJECT_PLATFORM_MAP["_default"]
