import logging

logger = logging.getLogger(__name__)

def calculate_emi(principal: float, annual_rate: float, tenure_years: int) -> dict:
    """
    Calculates the EMI, total payment, and total interest for a loan.
    Formula: P * R * (1+R)^N / ((1+R)^N - 1)
    """
    try:
        p = float(principal)
        annual_r = float(annual_rate)
        n_years = int(tenure_years)
        
        r = (annual_r / 12) / 100
        n = n_years * 12
        
        if r == 0:
            monthly_emi = p / n
        else:
            monthly_emi = p * r * ((1 + r) ** n) / (((1 + r) ** n) - 1)
            
        total_payment = monthly_emi * n
        total_interest = total_payment - p
        
        return {
            "monthly_emi": round(monthly_emi, 2),
            "total_payment": round(total_payment, 2),
            "total_interest": round(total_interest, 2),
            "principal": round(p, 2)
        }
    except Exception as e:
        logger.error(f"Error calculating EMI: {e}")
        return {"error": str(e)}

def calculate_sip(monthly_investment: float, annual_rate: float, years: int) -> dict:
    """
    Calculates the maturity amount, total invested, and returns for a SIP.
    Formula: P * ((1+R)^N - 1) / R * (1+R)
    """
    try:
        p = float(monthly_investment)
        annual_r = float(annual_rate)
        n_years = int(years)
        
        r = (annual_r / 12) / 100
        n = n_years * 12
        
        if r == 0:
            maturity_amount = p * n
        else:
            maturity_amount = p * (((1 + r) ** n - 1) / r) * (1 + r)
            
        total_invested = p * n
        total_returns = maturity_amount - total_invested
        
        return {
            "maturity_amount": round(maturity_amount, 2),
            "total_invested": round(total_invested, 2),
            "total_returns": round(total_returns, 2),
            "years": n_years
        }
    except Exception as e:
        logger.error(f"Error calculating SIP: {e}")
        return {"error": str(e)}

def calculate_tax(annual_income: float, regime: str = "new") -> dict:
    """
    Calculates the income tax based on the New and Old regime tax slabs.
    Includes Standard Deduction:
    - New Regime: Budget 2025-26: Standard Deduction = ₹75,000, 87A Rebate for Taxable Income <= ₹7,00,000
    - Old Regime: Standard Deduction = ₹50,000, 87A Rebate for Taxable Income <= ₹5,00,000
    """
    # Comment: Slabs last_updated: "Budget 2025-26"
    try:
        income = float(annual_income)
        regime = regime.strip().lower()
        
        if regime == "new":
            # Apply Standard Deduction
            deduction = 75000.0
            taxable_income = max(0.0, income - deduction)
            
            # Slabs 2025-26:
            # 0 - 3,00,000: 0%
            # 3,00,001 - 7,00,000: 5%
            # 7,00,001 - 10,00,000: 10%
            # 10,00,001 - 12,00,000: 15%
            # 12,00,001 - 15,00,000: 20%
            # Above 15,00,000: 30%
            
            # Calculate base tax (mathematical calculation on taxable income)
            tax = 0.0
            temp_income = taxable_income
            
            if temp_income > 1500000:
                tax += (temp_income - 1500000) * 0.30
                temp_income = 1500000
            if temp_income > 1200000:
                tax += (temp_income - 1200000) * 0.20
                temp_income = 1200000
            if temp_income > 1000000:
                tax += (temp_income - 1000000) * 0.15
                temp_income = 1000000
            if temp_income > 700000:
                tax += (temp_income - 700000) * 0.10
                temp_income = 700000
            if temp_income > 300000:
                tax += (temp_income - 300000) * 0.05
            
            # Rebate 87A: If taxable income is less than or equal to 7,00,000, tax is 0.
            if taxable_income <= 700000:
                tax_payable = 0.0
            else:
                tax_payable = tax
                
        else:  # old regime
            # Apply Standard Deduction
            deduction = 50000.0
            taxable_income = max(0.0, income - deduction)
            
            # Slabs old regime:
            # 0 - 2,50,000: 0%
            # 2,50,001 - 5,00,000: 5%
            # 5,00,001 - 10,00,000: 20%
            # Above 10,00,000: 30%
            
            tax = 0.0
            temp_income = taxable_income
            
            if temp_income > 1000000:
                tax += (temp_income - 1000000) * 0.30
                temp_income = 1000000
            if temp_income > 500000:
                tax += (temp_income - 500000) * 0.20
                temp_income = 500000
            if temp_income > 250000:
                tax += (temp_income - 250000) * 0.05
                
            # Rebate 87A: If taxable income is less than or equal to 5,00,000, tax is 0.
            if taxable_income <= 500000:
                tax_payable = 0.0
            else:
                tax_payable = tax
                
        effective_rate = (tax_payable / income) * 100 if income > 0 else 0
        take_home = income - tax_payable
        
        return {
            "regime": regime,
            "gross_income": round(income, 2),
            "taxable_income": round(taxable_income, 2),
            "tax_payable": round(tax_payable, 2),
            "effective_rate": round(effective_rate, 2),
            "take_home": round(take_home, 2),
            "last_updated": "Budget 2025-26"
        }
    except Exception as e:
        logger.error(f"Error calculating Tax: {e}")
        return {"error": str(e)}

def calculate_fd(principal: float, annual_rate: float, tenure_years: float, compounding: str = "quarterly") -> dict:
    """
    Calculates the maturity amount and interest earned for a Fixed Deposit.
    Formula: A = P * (1 + r/n)^(n*t)
    """
    try:
        p = float(principal)
        rate = float(annual_rate)
        t = float(tenure_years)
        comp = compounding.strip().lower()
        
        if comp == "monthly":
            n = 12
        elif comp == "annually":
            n = 1
        else:
            n = 4  # default quarterly compounding
            
        r = rate / 100
        maturity_amount = p * ((1 + r / n) ** (n * t))
        interest_earned = maturity_amount - p
        
        return {
            "maturity_amount": round(maturity_amount, 2),
            "interest_earned": round(interest_earned, 2),
            "principal": round(p, 2),
            "tenure_years": t,
            "rate": rate,
            "compounding": comp
        }
    except Exception as e:
        logger.error(f"Error calculating FD: {e}")
        return {"error": str(e)}
