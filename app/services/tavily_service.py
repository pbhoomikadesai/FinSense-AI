import os
import logging
from tavily import TavilyClient

logger = logging.getLogger(__name__)

def search(query: str, max_results: int = 3) -> list[dict]:
    """
    Search Tavily with query and return up to max_results formatted dictionaries.
    Prioritizes specific domains, falling back to a general search on failure/no results.
    Does not raise exceptions.
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        logger.warning("TAVILY_API_KEY not set. Returning empty list.")
        return []
    
    try:
        client = TavilyClient(api_key=api_key)
        # Prioritize high-quality Indian financial domains
        domains = ["rbi.org.in", "moneycontrol.com", "economictimes.com", "bankbazaar.com", "cleartax.in"]
        results = []
        
        try:
            response = client.search(
                query=query,
                max_results=max_results,
                include_domains=domains
            )
            results = response.get("results", [])
        except Exception as e:
            logger.warning(f"Tavily search with domain filter failed ({e}). Falling back to general search.")
            results = []
            
        # Fall back to general search if no results or if domain search failed
        if not results:
            try:
                response = client.search(
                    query=query,
                    max_results=max_results
                )
                results = response.get("results", [])
            except Exception as e:
                logger.error(f"General Tavily search failed: {e}")
                return []
                
        formatted_results = []
        for r in results:
            formatted_results.append({
                "title": r.get("title", ""),
                "content": r.get("content", ""),
                "url": r.get("url", ""),
                "score": r.get("score", 0.0)
            })
            
        return formatted_results[:max_results]
    except Exception as e:
        logger.error(f"Unexpected error in Tavily service: {e}")
        return []
