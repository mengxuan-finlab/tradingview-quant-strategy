from quant_system.models import clamp


DEFAULT_STRATEGY = {
    "min_market_cap": 10_000_000_000,
    "min_roic": 0.05,
    "max_debt_to_equity": 2.5,
    "max_wacc": 0.25,
    "min_strategy_score": 0.60,
}


RESEARCH_CANDIDATE = {
    "extreme_score": 0.75,
    "high_score": 0.60,
    "watch_score": 0.45,
    "min_extreme_upside": 0.50,
    "min_extreme_roic": 0.15,
    "min_extreme_growth_estimate": 0.10,
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
    if stock.get("roic", 0.0) < config["min_roic"]:
        reasons.append("roic_too_low")
    if stock.get("debt_to_equity", 0.0) > config["max_debt_to_equity"]:
        reasons.append("debt_too_high")
    if stock["wacc"] <= 0 or stock["wacc"] > config["max_wacc"]:
        reasons.append("wacc_out_of_range")

    strategy_score = medium_term_factor_score(stock)
    research_priority = classify_research_priority(stock, strategy_score)
    pass_strategy = len(reasons) == 0 and strategy_score >= config["min_strategy_score"]

    return {
        **stock,
        "strategy": "medium_factor_quality_value_momentum",
        "pass_strategy": pass_strategy,
        "strategy_score": strategy_score,
        "research_priority": research_priority,
        "reject_reasons": ";".join(reasons),
    }


def medium_term_factor_score(stock):
    valuation_score = clamp((stock["upside"] + 0.20) / 1.20)
    quality_score = clamp(stock.get("roic", 0.0) / 0.25)
    growth_score = clamp(stock.get("growth_estimate", stock.get("fcf_growth", 0.0)) / 0.20)
    safety_score = clamp(1 - stock.get("debt_to_equity", 0.0) / 2.5)
    momentum_score = momentum_factor_score(stock)
    size_score = clamp(stock["market_cap"] / 200_000_000_000)

    return (
        valuation_score * 0.20
        + quality_score * 0.25
        + growth_score * 0.20
        + safety_score * 0.15
        + momentum_score * 0.10
        + size_score * 0.10
    )


def momentum_factor_score(stock):
    momentum_3m = stock.get("momentum_3m", 0.0)
    momentum_6m = stock.get("momentum_6m", 0.0)
    momentum_12m = stock.get("momentum_12m", 0.0)
    blended_momentum = momentum_3m * 0.40 + momentum_6m * 0.35 + momentum_12m * 0.25

    return clamp((blended_momentum + 0.20) / 0.80)


def classify_research_priority(stock, strategy_score, config=None):
    config = config or RESEARCH_CANDIDATE

    is_extreme_candidate = (
        stock["upside"] >= config["min_extreme_upside"]
        and stock.get("roic", 0.0) >= config["min_extreme_roic"]
        and stock.get("growth_estimate", stock.get("fcf_growth", 0.0)) >= config["min_extreme_growth_estimate"]
        and stock.get("debt_to_equity", 0.0) <= config["max_extreme_debt_to_equity"]
        and stock["free_cash_flow"] > 0
    )

    if strategy_score >= config["extreme_score"] or is_extreme_candidate:
        return "EXTREME_RESEARCH"
    if strategy_score >= config["high_score"]:
        return "HIGH_RESEARCH"
    if strategy_score >= config["watch_score"]:
        return "WATCH"

    return "IGNORE"
