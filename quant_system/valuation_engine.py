from quant_system.models import calculate_dcf_per_share, calculate_wacc, score_stock


def value_stock(
    snapshot,
    risk_free_rate=0.04,
    market_return=0.10,
    terminal_growth_rate=0.03,
    tax_rate=0.21,
):
    wacc = calculate_wacc(
        risk_free_rate=risk_free_rate,
        beta=snapshot["beta"],
        market_return=market_return,
        equity_value=snapshot["market_cap"],
        short_term_debt=snapshot["short_term_debt"],
        long_term_debt=snapshot["long_term_debt"],
        interest_expense=snapshot["interest_expense"],
        tax_rate=tax_rate,
    )
    growth_rate = snapshot.get("growth_estimate", snapshot["fcf_growth"])
    fair_value = calculate_dcf_per_share(
        free_cash_flow=snapshot["free_cash_flow"],
        discount_rate=wacc,
        growth_rate=growth_rate,
        terminal_growth_rate=terminal_growth_rate,
        cash=snapshot["cash"],
        debt=snapshot["total_debt"],
        shares_outstanding=snapshot["shares_outstanding"],
    )
    price = snapshot["price"]
    upside = fair_value / price - 1 if price > 0 else 0.0
    score = score_stock(
        upside=upside,
        roic=snapshot.get("roic", 0.0),
        debt_to_equity=snapshot.get("debt_to_equity", 0.0),
        fcf_growth=growth_rate,
    )

    return {
        **snapshot,
        "wacc": wacc,
        "dcf_growth_rate": growth_rate,
        "fair_value": fair_value,
        "upside": upside,
        "score": score,
    }
