import logging
from app.services.tavily_service import search

logger = logging.getLogger(__name__)

def search_finance_web(query: str) -> list[dict]:
    """
    Uses the Tavily service to perform a search with added India and 2025 context.
    Returns a list of dictionaries with keys: title, content, url, score.
    """
    # Append India and 2025/2026 for local context relevance
    enhanced_query = f"{query} India 2025"
    try:
        results = search(enhanced_query, max_results=3)
        return results
    except Exception as e:
        logger.error(f"Error in search_finance_web tool: {str(e)}")
        return []
