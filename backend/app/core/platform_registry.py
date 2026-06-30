import urllib.parse
from typing import Dict

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
    if resource_type == "video":
        # YouTube fallback search query
        return f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(platform + ' ' + query)}"
    
    # Generic Google search fallback for docs/articles
    return f"https://www.google.com/search?q={urllib.parse.quote_plus(platform + ' ' + query)}"
