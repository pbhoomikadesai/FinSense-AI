import pytest
from unittest.mock import patch, AsyncMock
from app.agents.finsense_agent import router_node, route_decision, run_agent, FinSenseState

def test_router_node_search_only():
    initial_state = FinSenseState(
        query="What is the current RBI repo rate today?",
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
    res = router_node(initial_state)
    assert res["needs_search"] is True
    assert res["needs_calculator"] is False
    assert res["calculator_type"] == "none"
    assert res["query_type"] == "rates"
    assert route_decision(res) == "search"

def test_router_node_calculator_only_emi_forces_search():
    initial_state = FinSenseState(
        query="Calculate my monthly home loan EMI for 50 lakhs",
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
    res = router_node(initial_state)
    assert res["needs_search"] is True  # Forced search for loan rates
    assert res["needs_calculator"] is True
    assert res["calculator_type"] == "emi"
    assert res["query_type"] == "mixed"
    assert route_decision(res) == "both"

def test_router_node_calculator_only_sip():
    initial_state = FinSenseState(
        query="Calculate expected returns for SIP 10000",
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
    res = router_node(initial_state)
    assert res["needs_search"] is False  # SIP doesn't force search
    assert res["needs_calculator"] is True
    assert res["calculator_type"] == "sip"
    assert res["query_type"] == "calculator"
    assert route_decision(res) == "calculator"

def test_router_node_both():
    initial_state = FinSenseState(
        query="What is the current SBI FD rate and calculate FD for 1 lakh",
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
    res = router_node(initial_state)
    assert res["needs_search"] is True
    assert res["needs_calculator"] is True
    assert res["calculator_type"] == "fd"
    assert res["query_type"] == "mixed"
    assert route_decision(res) == "both"

@pytest.mark.asyncio
@patch("app.agents.finsense_agent.search_finance_web")
@patch("app.agents.finsense_agent.groq_service.synthesize", new_callable=AsyncMock)
async def test_full_agent_flow(mock_groq_synthesize, mock_search):
    # Setup mocks
    mock_search.return_value = [
        {"title": "SBI FD Interest Rates", "content": "SBI FD rates for 1 year are 6.80% in 2025.", "url": "https://sbi.co.in", "score": 0.99}
    ]
    mock_groq_synthesize.return_value = '{"answer": "SBI FD rate for 1 year is 6.80%. Your maturity is ₹1,06,975.", "recommendation": "Go ahead with SBI.", "key_points": ["FD rate is 6.80%", "Interest is quarterly compounded"]}'
    
    query = "What is the current SBI FD rate and calculate FD for 1 lakh for 1 year at 6.8%"
    
    final_res = await run_agent(query)
    
    # Assertions
    assert final_res["answer"] == "SBI FD rate for 1 year is 6.80%. Your maturity is ₹1,06,975."
    assert final_res["recommendation"] == "Go ahead with SBI."
    assert final_res["key_points"] == ["FD rate is 6.80%", "Interest is quarterly compounded"]
    assert len(final_res["sources"]) == 1
    assert final_res["sources"][0]["title"] == "SBI FD Interest Rates"
    assert "web_search" in final_res["tools_used"]
    assert "finance_calculator" in final_res["tools_used"]
    assert final_res["calculations"]["maturity_amount"] > 100000
    assert final_res["calculations"]["rate"] == 6.8
