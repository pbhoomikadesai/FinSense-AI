import json
import logging

logger = logging.getLogger(__name__)

def format_response(
    query: str,
    query_type: str,
    search_results: list,
    calc_results: dict,
    groq_synthesis: str
) -> dict:
    """
    Formats the final response into the required JSON structure.
    Tries to parse the groq_synthesis as JSON to extract structured fields.
    If parsing fails, places the raw text in the answer field.
    """
    answer = groq_synthesis
    recommendation = ""
    key_points = []
    
    if groq_synthesis:
        cleaned_synthesis = groq_synthesis.strip()
        # Handle markdown code block wrapper if the LLM output JSON inside ```json ... ```
        if cleaned_synthesis.startswith("```"):
            # strip markdown lines
            lines = cleaned_synthesis.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            cleaned_synthesis = "\n".join(lines).strip()
            
        try:
            parsed = json.loads(cleaned_synthesis)
            if isinstance(parsed, dict):
                answer = parsed.get("answer", answer)
                recommendation = parsed.get("recommendation", "")
                key_points = parsed.get("key_points", [])
        except json.JSONDecodeError:
            logger.info("groq_synthesis is not valid JSON, returning raw string in answer")
            
    # Format sources
    sources = []
    for res in search_results:
        if isinstance(res, dict):
            sources.append({
                "title": res.get("title", "Finance Source"),
                "url": res.get("url", "")
            })
            
    # Determine tools used
    tools_used = []
    if search_results:
        tools_used.append("web_search")
    if calc_results:
        tools_used.append("finance_calculator")
        
    # Generate backup key points if empty
    if not key_points and answer:
        # split by sentences or just construct one
        key_points = [line.strip() for line in answer.split(".") if line.strip()][:3]
        if not key_points:
            key_points = ["Refer to the synthesized answer for key details."]

    return {
        "answer": answer,
        "recommendation": recommendation if recommendation else "Review parameters and consult a SEBI-registered professional.",
        "key_points": key_points,
        "sources": sources,
        "tools_used": tools_used,
        "calculations": calc_results if calc_results else None,
        "disclaimer": "This is for informational purposes only and does not constitute financial advice. Please consult a SEBI-registered financial advisor before making investment decisions.",
        "last_updated": "2025-26"
    }
