import re
import logging
from typing import TypedDict, Optional, List, Dict, Any

from langgraph.graph import StateGraph, END

# Import tools
from app.tools.search_tool import search_finance_web
from app.tools.calculator_tool import calculate_emi, calculate_sip, calculate_tax, calculate_fd
from app.tools.formatter_tool import format_response

# Import services
from app.services import groq_service

logger = logging.getLogger(__name__)

# State definition
class FinSenseState(TypedDict):
    query: str
    query_type: str          # "rates" | "calculator" | "comparison" | "recommendation" | "mixed"
    needs_search: bool
    needs_calculator: bool
    calculator_type: str     # "emi" | "sip" | "tax" | "fd" | "none"
    search_results: list
    calc_results: dict
    groq_synthesis: str
    final_response: dict
    error: str | None


def extract_numbers(query: str) -> dict:
    """
    Extracts financial numbers, rates, and tenures from the query string using regex.
    """
    q = query.lower()
    amount = None
    
    # Match lakhs: e.g. "50 lakh", "50lakhs", "50 l", "50 lpa"
    lakh_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:lakh|l|lpa)s?\b", q)
    if lakh_match:
        amount = float(lakh_match.group(1)) * 100000
        
    if not amount:
        # Match crores: e.g. "1 crore", "1cr"
        crore_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:crore|cr)s?\b", q)
        if crore_match:
            amount = float(crore_match.group(1)) * 10000000
            
    if not amount:
        # Match standard large numbers (thousands, millions) but ignore common budget years
        nums = re.findall(r"\b(\d{4,10})\b", q)
        for num in nums:
            val = float(num)
            if val not in [2024, 2025, 2026, 2027]:
                amount = val
                break
                
    # Match rate / percentage: e.g. "8.5%", "8.5 percent", "rate of 8.5"
    rate = None
    pct_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:%|percent)", q)
    if pct_match:
        rate = float(pct_match.group(1))
    if not rate:
        # Look for numbers following at / rate / interest
        at_match = re.search(r"(?:at|rate|interest of|interest)\s+(\d+(?:\.\d+)?)", q)
        if at_match:
            rate = float(at_match.group(1))
            
    # Match years/tenure: e.g. "20 years", "20 y", "1 year"
    years = None
    years_match = re.search(r"(\d+)\s*(?:year|yr)s?\b", q)
    if years_match:
        years = int(years_match.group(1))
        
    return {
        "amount": amount,
        "rate": rate,
        "years": years
    }


def extract_rate_from_search(search_results: list) -> float | None:
    """
    Scans search result snippets to extract a logical interest rate percentage (e.g. 8.70%).
    Useful for running comparative loan EMI calculations.
    """
    if not search_results:
        return None
    for res in search_results:
        content = res.get("content", "").lower()
        # Find percentages like "8.75%" or "9%"
        matches = re.findall(r"\b(\d+(?:\.\d+)?)\s*%", content)
        for m in matches:
            try:
                val = float(m)
                # Logical interest rate range for Indian car/home/personal loans (6% to 15%)
                if 6.0 <= val <= 15.0:
                    return val
            except ValueError:
                continue
    return None


# NODES

def router_node(state: FinSenseState) -> FinSenseState:
    """
    Classifies query, sets tool flags, and detects calculator types.
    """
    logger.info("Running router_node")
    q = state["query"].lower()
    
    # Classify tools needed
    search_keywords = ["rate", "current", "today", "compare", "best", "which bank", "vs", "rbi", "repo", "slab", "regime"]
    calc_keywords = ["calculate", "emi", "sip", "tax", "fd", "lakh", "crore", "per month", "slab", "interest rate", "regime"]
    
    needs_search = any(k in q for k in search_keywords)
    needs_calculator = any(k in q for k in calc_keywords)
    
    # Determine calculator type
    calculator_type = "none"
    if "emi" in q or "loan" in q:
        calculator_type = "emi"
        needs_search = True  # Always search for current rates on loan/EMI queries
    elif "sip" in q:
        calculator_type = "sip"
    elif "tax" in q or "slab" in q or "lpa" in q or "regime" in q:
        calculator_type = "tax"
        needs_search = True  # Always search for tax slabs/budget regulations
    elif "fd" in q or "fixed deposit" in q:
        calculator_type = "fd"
        needs_search = True  # Always search for current FD rates
        
    if calculator_type != "none":
        needs_calculator = True
        
    # Classify query type
    if needs_search and needs_calculator:
        query_type = "mixed"
    elif needs_search:
        if "compare" in q or "vs" in q:
            query_type = "comparison"
        elif "best" in q or "recommend" in q or "should i" in q:
            query_type = "recommendation"
        else:
            query_type = "rates"
    elif needs_calculator:
        query_type = "calculator"
    else:
        query_type = "recommendation"  # default
        
    # Modify state copy
    new_state = state.copy()
    new_state["needs_search"] = needs_search
    new_state["needs_calculator"] = needs_calculator
    new_state["calculator_type"] = calculator_type
    new_state["query_type"] = query_type
    
    logger.info(f"Route: search={needs_search}, calc={needs_calculator} ({calculator_type}), type={query_type}")
    return new_state


def search_node(state: FinSenseState) -> FinSenseState:
    """
    Runs web search if query needs fresh rate or comparative data.
    """
    logger.info("Running search_node")
    new_state = state.copy()
    if state["needs_search"]:
        try:
            results = search_finance_web(state["query"])
            new_state["search_results"] = results
        except Exception as e:
            logger.error(f"Search node failed: {e}")
            new_state["error"] = f"Search error: {str(e)}"
    return new_state


def calculator_node(state: FinSenseState) -> FinSenseState:
    """
    Executes appropriate calculator tool based on the state's calculator_type.
    """
    logger.info(f"Running calculator_node for type {state['calculator_type']}")
    new_state = state.copy()
    if not state["needs_calculator"] or state["calculator_type"] == "none":
        return new_state
        
    try:
        vals = extract_numbers(state["query"])
        calc_type = state["calculator_type"]
        res = {}
        
        if calc_type == "emi":
            principal = vals["amount"] if vals["amount"] is not None else 5000000.0  # 50 Lakhs default
            rate = vals["rate"] if vals["rate"] is not None else 8.5  # 8.5% default
            years = vals["years"] if vals["years"] is not None else 20  # 20 years default
            res = calculate_emi(principal, rate, years)
            
            # Run comparative EMI if search results yielded a live rate
            search_res = state.get("search_results", [])
            if search_res:
                market_rate = extract_rate_from_search(search_res)
                if market_rate and abs(market_rate - rate) > 0.05:
                    market_res = calculate_emi(principal, market_rate, years)
                    res["market_rate"] = market_rate
                    res["market_emi"] = market_res["monthly_emi"]
                    res["market_total_interest"] = market_res["total_interest"]
                    res["market_total_payment"] = market_res["total_payment"]
            
        elif calc_type == "sip":
            # If amount is very large, assume it is target and set default monthly SIP to 10k
            amt = vals["amount"]
            monthly_investment = amt if amt is not None and amt < 1000000 else 10000.0
            rate = vals["rate"] if vals["rate"] is not None else 12.0  # 12% default
            years = vals["years"] if vals["years"] is not None else 10  # 10 years default
            res = calculate_sip(monthly_investment, rate, years)
            if amt is not None and amt >= 1000000:
                res["target_amount"] = amt  # Include for LLM context
                
        elif calc_type == "tax":
            income = vals["amount"] if vals["amount"] is not None else 1000000.0  # 10 LPA default
            regime = "old" if "old" in state["query"].lower() else "new"
            res = calculate_tax(income, regime)
            
        elif calc_type == "fd":
            principal = vals["amount"] if vals["amount"] is not None else 100000.0  # 1 Lakh default
            rate = vals["rate"] if vals["rate"] is not None else 7.0  # 7% default
            years = vals["years"] if vals["years"] is not None else 1.0  # 1 year default
            compounding = "monthly" if "monthly" in state["query"].lower() else "annually" if ("annual" in state["query"].lower() or "yearly" in state["query"].lower()) else "quarterly"
            res = calculate_fd(principal, rate, years, compounding)
            
        new_state["calc_results"] = res
    except Exception as e:
        logger.error(f"Calculator node failed: {e}")
        new_state["error"] = f"Calculator error: {str(e)}"
        
    return new_state


async def synthesis_node(state: FinSenseState) -> FinSenseState:
    """
    Combines search results and calculator outputs and calls Groq service.
    """
    logger.info("Running synthesis_node")
    new_state = state.copy()
    
    # Formulate context block
    context_parts = []
    
    if state["search_results"]:
        context_parts.append("=== Web Search Results ===")
        for i, res in enumerate(state["search_results"]):
            context_parts.append(
                f"Source [{i+1}]: {res.get('title')}\n"
                f"URL: {res.get('url')}\n"
                f"Content: {res.get('content')}\n"
            )
            
    if state["calc_results"]:
        context_parts.append("=== Financial Calculation Output ===")
        for k, v in state["calc_results"].items():
            context_parts.append(f"{k}: {v}")
            
    context = "\n".join(context_parts) if context_parts else "No additional context available."
    
    try:
        synthesis = await groq_service.synthesize(
            query=state["query"],
            context=context,
            query_type=state["query_type"]
        )
        new_state["groq_synthesis"] = synthesis
    except Exception as e:
        logger.error(f"Synthesis node failed: {e}")
        new_state["error"] = f"Synthesis error: {str(e)}"
        new_state["groq_synthesis"] = f'{{"answer": "Error generating synthesis: {str(e)}", "recommendation": "Consult a professional", "key_points": []}}'
        
    return new_state


def output_node(state: FinSenseState) -> FinSenseState:
    """
    Generates structured, validated response dictionary.
    """
    logger.info("Running output_node")
    new_state = state.copy()
    try:
        final_res = format_response(
            query=state["query"],
            query_type=state["query_type"],
            search_results=state["search_results"],
            calc_results=state["calc_results"],
            groq_synthesis=state["groq_synthesis"]
        )
        new_state["final_response"] = final_res
    except Exception as e:
        logger.error(f"Output node formatting failed: {e}")
        new_state["error"] = f"Output formatting error: {str(e)}"
        new_state["final_response"] = {
            "answer": "An error occurred formatting the final response.",
            "recommendation": "Please try again later.",
            "key_points": ["Error encountered"],
            "sources": [],
            "tools_used": [],
            "calculations": None,
            "disclaimer": "This is for informational purposes only. Consult a financial advisor.",
            "last_updated": "2025-26"
        }
    return new_state


# ROUTING LOGIC

def route_decision(state: FinSenseState) -> str:
    """
    Decides the path from router node based on state flags.
    """
    if state["needs_search"] and state["needs_calculator"]:
        return "both"
    elif state["needs_search"]:
        return "search"
    elif state["needs_calculator"]:
        return "calculator"
    else:
        return "synthesis"


# BUILD GRAPH

graph = StateGraph(FinSenseState)

# Add Nodes
graph.add_node("router", router_node)
graph.add_node("search", search_node)
graph.add_node("calculator", calculator_node)
graph.add_node("synthesis", synthesis_node)
graph.add_node("output", output_node)

# Entry Point
graph.set_entry_point("router")

# Router conditional edge
graph.add_conditional_edges(
    "router",
    route_decision,
    {
        "search": "search",
        "calculator": "calculator",
        "both": "search",
        "synthesis": "synthesis"
    }
)

# Search conditional edge
graph.add_conditional_edges(
    "search",
    lambda s: "calculator" if s["needs_calculator"] else "synthesis",
    {
        "calculator": "calculator",
        "synthesis": "synthesis"
    }
)

# Static Edges
graph.add_edge("calculator", "synthesis")
graph.add_edge("synthesis", "output")
graph.add_edge("output", END)

# Compile Agent
agent = graph.compile()


async def run_agent(query: str) -> dict:
    """
    Executes the FinSense agent on the query and returns the final structured dictionary.
    """
    initial_state = FinSenseState(
        query=query,
        query_type="",
        needs_search=False,
        needs_calculator=False,
        calculator_type="none",
        search_results=[],
        calc_results={},
        groq_synthesis="",
        final_response={},
        error=None
    )
    result = await agent.ainvoke(initial_state)
    return result["final_response"]
