import os
import logging
from groq import AsyncGroq

logger = logging.getLogger(__name__)

async def synthesize(query: str, context: str, query_type: str) -> str:
    """
    Synthesizes the query, search results, and calculator outputs using Groq LLM.
    Uses llama-3.3-70b-versatile and falls back to llama-3.1-8b-instant on rate limits.
    Enforces India-specific context, Rupee formatting, source citing, and SEBI advice disclaimer.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        logger.error("GROQ_API_KEY not set.")
        return '{"answer": "Error: GROQ_API_KEY is not configured.", "recommendation": "Set GROQ_API_KEY in the environment.", "key_points": []}'
        
    client = AsyncGroq(api_key=api_key)
    
    system_prompt = (
        "You are FinSense AI, an expert personal finance AI assistant for India.\n"
        "Your task is to synthesize the query, search results, and calculator outputs to answer the query.\n\n"
        "Rules:\n"
        "1. Focus strictly on Indian financial regulations, terms, tax laws, and context.\n"
        "2. All amounts MUST be stated in Indian Rupees (₹). Use Lakhs/Crores for larger numbers (e.g., ₹50 Lakhs instead of 5,000,000).\n"
        "3. Cite relevant sources (by title/URL domain) or calculations from the context to back up your answer.\n"
        "4. Do NOT give definitive investment advice; advise consulting a SEBI-registered advisor.\n"
        "5. When the user provides an interest rate or parameter in their query, always compare it against current market rates from search results. If the user's rate differs significantly from current market rates, flag this explicitly in your answer and display/compare calculations (like EMI or interest payments) at both the user's rate and the current market rates.\n"
        "6. Respond ONLY with a valid JSON object matching the following structure:\n"
        "{\n"
        '  "answer": "A detailed, clear answer based on the context and calculations. Cite sources here. Discuss comparisons of interest rates/calculations if applicable.",\n'
        '  "recommendation": "Your recommendations or suggestion (e.g., PPF vs ELSS comparison details or loan structure), noting to consult a financial advisor.",\n'
        '  "key_points": ["Key takeaway 1", "Key takeaway 2", "Key takeaway 3"]\n'
        "}\n"
    )
    
    user_prompt = (
        f"Query: {query}\n"
        f"Query Type: {query_type}\n"
        f"Context (Web Search & Calculations):\n{context}\n"
    )
    
    primary_model = "llama-3.3-70b-versatile"
    fallback_model = "llama-3.1-8b-instant"
    
    try:
        response = await client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model=primary_model,
            response_format={"type": "json_object"},
            temperature=0.2
        )
        return response.choices[0].message.content
    except Exception as e:
        # Check if rate limit (status code 429) or error message indicates rate limits
        err_msg = str(e).lower()
        if "429" in err_msg or "rate limit" in err_msg:
            logger.warning(f"Groq rate limit hit with model {primary_model}. Falling back to {fallback_model}. Error: {e}")
            try:
                response = await client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    model=fallback_model,
                    response_format={"type": "json_object"},
                    temperature=0.2
                )
                return response.choices[0].message.content
            except Exception as fallback_err:
                logger.error(f"Fallback model failed: {fallback_err}")
                return f'{{"answer": "Error generating synthesis: rate limit exceeded and fallback failed.", "recommendation": "Please retry in a moment.", "key_points": ["Rate limit hit", "Fallback failed"]}}'
        else:
            logger.error(f"Groq service error: {e}")
            return f'{{"answer": "Error generating synthesis: {str(e)}", "recommendation": "Please try again later or check Groq service.", "key_points": ["API error occurred"]}}'
