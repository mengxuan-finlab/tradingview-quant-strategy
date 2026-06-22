from quant_system.models import clamp


DEFAULT_STRATEGY = {
    "min_market_cap": 10_000_000_000,
    "min_upside": 0.00,
    "min_roic": 0.05,
    "max_debt_to_equity": 2.5,
    "max_wacc": 0.25,
}


RESEARCH_CANDIDATE = {
    "extreme_score": 0.75,
    "high_score": 0.60,
    "min_extreme_upside": 0.50,
    "min_extreme_roic": 0.15,
    "min_extreme_fcf_growth": 0.10,
    "max_extreme_debt_to_equity": 1.2,
}


def apply_quality_value_strategy(stock, config=None):
    config = config or DEFAULT_STRATEGY
    reasons = []

    if stock["price"] <= 0:
        reasons.append("no_price")
    if stock["free_cash_flow"] <= 0:
        reasons.append("negative_or_zero_fcf")
    if stock["market_cap"] < config["min_market_cap"]:
        reasons.append("market_cap_too_small")
    if stock["upside"] < config["min_upside"]:
        reasons.append("negative_dcf_upside")
    if stock.get("roic", 0.0) < config["min_roic"]:
        reasons.append("roic_too_low")
    if stock.get("debt_to_equity", 0.0) > config["max_debt_to_equity"]:
        reasons.append("debt_too_high")
    if stock["wacc"] <= 0 or stock["wacc"] > config["max_wacc"]:
        reasons.append("wacc_out_of_range")

    strategy_score = medium_term_factor_score(stock)
    research_priority = classify_research_priority(stock, strategy_score)

    return {
        **stock,
        "strategy": "medium_factor_quality_value",
        "pass_strategy": len(reasons) == 0,
        "strategy_score": strategy_score,
        "research_priority": research_priority,
        "reject_reasons": ";".join(reasons),
    }


def medium_term_factor_score(stock):
    valuation_score = clamp((stock["upside"] + 0.20) / 1.20)
    quality_score = clamp(stock.get("roic", 0.0) / 0.25)
    growth_score = clamp(stock.get("fcf_growth", 0.0) / 0.20)
    safety_score = clamp(1 - stock.get("debt_to_equity", 0.0) / 2.5)
    size_score = clamp(stock["market_cap"] / 200_000_000_000)

    return (
        valuation_score * 0.30
        + quality_score * 0.25
        + growth_score * 0.20
        + safety_score * 0.15
        + size_score * 0.10
    )


def classify_research_priority(stock, strategy_score, config=None):
    config = config or RESEARCH_CANDIDATE

    is_extreme_candidate = (
        stock["upside"] >= config["min_extreme_upside"]
        and stock.get("roic", 0.0) >= config["min_extreme_roic"]
        and stock.get("fcf_growth", 0.0) >= config["min_extreme_fcf_growth"]
        and stock.get("debt_to_equity", 0.0) <= config["max_extreme_debt_to_equity"]
        and stock["free_cash_flow"] > 0
    )

    if strategy_score >= config["extreme_score"] or is_extreme_candidate:
        return "EXTREME_RESEARCH"
    if strategy_score >= config["high_score"]:
        return "HIGH_RESEARCH"
    if stock["upside"] > 0 and stock["free_cash_flow"] > 0:
        return "WATCH"

    return "IGNORE"
