import pytest
from app.tools.calculator_tool import calculate_emi, calculate_sip, calculate_tax, calculate_fd
from app.tools.formatter_tool import format_response

def test_calculate_emi():
    res = calculate_emi(5000000, 8.5, 20)
    assert "error" not in res
    # EMI calculation: ~43391.14
    assert abs(res["monthly_emi"] - 43391) < 1.0
    assert res["total_payment"] > 5000000
    assert res["total_interest"] > 0
    assert res["principal"] == 5000000

def test_calculate_sip():
    res = calculate_sip(10000, 12, 10)
    assert "error" not in res
    assert res["maturity_amount"] > res["total_invested"]
    assert res["total_invested"] == 10000 * 12 * 10
    assert res["total_returns"] > 0

def test_calculate_tax():
    # Salaried individual with 10 LPA gross income
    # New regime: Standard deduction of 75000 -> Taxable income = 9,25,000
    # Slabs:
    # 0 - 3L: 0%
    # 3L - 7L (4L): 5% -> 20000
    # 7L - 9.25L (2.25L): 10% -> 22500
    # Base tax = 42500. Taxable income is 9.25L > 7L, so no rebate.
    # Tax payable = 42500.
    res = calculate_tax(1000000, "new")
    assert "error" not in res
    assert res["tax_payable"] == 42500.0
    assert res["taxable_income"] == 925000.0
    assert res["take_home"] == 1000000.0 - 42500.0

def test_calculate_fd():
    res = calculate_fd(100000, 7.0, 1, "quarterly")
    assert "error" not in res
    # compounding quarterly: 100000 * (1 + 0.07/4)^4 = 100000 * (1.0175)^4 = 107185.90
    assert abs(res["maturity_amount"] - 107186) < 10.0
    assert res["maturity_amount"] > 100000
    assert res["interest_earned"] > 0
    assert res["compounding"] == "quarterly"

def test_format_response():
    query = "Test query"
    query_type = "rates"
    search_results = [{"title": "Test Title", "content": "Test content", "url": "https://test.com"}]
    calc_results = {"monthly_emi": 43391}
    groq_synthesis = '{"answer": "Synthesis answer", "recommendation": "Consult advisor", "key_points": ["Point A", "Point B"]}'
    
    formatted = format_response(query, query_type, search_results, calc_results, groq_synthesis)
    
    # Required keys in formatted JSON
    assert "answer" in formatted
    assert "recommendation" in formatted
    assert "key_points" in formatted
    assert "sources" in formatted
    assert "tools_used" in formatted
    assert "calculations" in formatted
    assert "disclaimer" in formatted
    assert "last_updated" in formatted
    
    assert formatted["answer"] == "Synthesis answer"
    assert formatted["recommendation"] == "Consult advisor"
    assert formatted["key_points"] == ["Point A", "Point B"]
    assert formatted["sources"] == [{"title": "Test Title", "url": "https://test.com"}]
    assert "web_search" in formatted["tools_used"]
    assert "finance_calculator" in formatted["tools_used"]
    assert formatted["calculations"] == calc_results
