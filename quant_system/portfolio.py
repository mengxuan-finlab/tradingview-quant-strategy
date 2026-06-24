from collections import defaultdict


DEFAULT_PORTFOLIO = {
    "portfolio_size": 20,
    "value_sleeve_size": 14,
    "quality_growth_sleeve_size": 6,
    "max_sector_count": 3,
    "max_industry_count": 1,
    "min_quality_growth_score": 0.60,
    "min_quality_growth_roic": 0.10,
    "max_quality_growth_debt_to_equity": 1.8,
    "min_quality_growth_upside": -0.50,
    "max_quality_growth_upside": 0.25,
    "min_quality_growth_momentum_12m": 0.0,
}


def build_portfolio(results, config=None):
    config = {**DEFAULT_PORTFOLIO, **(config or {})}
    candidates = sorted(
        results,
        key=lambda item: item.get("strategy_score", 0.0),
        reverse=True,
    )
    selected = []
    selected_symbols = set()
    sector_counts = defaultdict(int)
    industry_counts = defaultdict(int)

    add_candidates(
        selected=selected,
        selected_symbols=selected_symbols,
        sector_counts=sector_counts,
        industry_counts=industry_counts,
        candidates=candidates,
        config=config,
        sleeve="quality_growth",
        target_count=config["quality_growth_sleeve_size"],
        predicate=is_quality_growth_candidate,
    )
    add_candidates(
        selected=selected,
        selected_symbols=selected_symbols,
        sector_counts=sector_counts,
        industry_counts=industry_counts,
        candidates=candidates,
        config=config,
        sleeve="value",
        target_count=config["value_sleeve_size"],
        predicate=is_value_candidate,
    )

    if len(selected) < config["portfolio_size"]:
        add_candidates(
            selected=selected,
            selected_symbols=selected_symbols,
            sector_counts=sector_counts,
            industry_counts=industry_counts,
            candidates=candidates,
            config=config,
            sleeve="value",
            target_count=config["portfolio_size"] - len(selected),
            predicate=is_value_candidate,
        )

    selected = selected[: config["portfolio_size"]]

    weight = 1 / len(selected) if selected else 0.0
    return [
        {
            **stock,
            "portfolio_rank": rank,
            "target_weight": weight,
        }
        for rank, stock in enumerate(selected, start=1)
    ]


def add_candidates(
    selected,
    selected_symbols,
    sector_counts,
    industry_counts,
    candidates,
    config,
    sleeve,
    target_count,
    predicate,
):
    added = 0

    for stock in candidates:
        if added >= target_count or len(selected) >= config["portfolio_size"]:
            break
        if not predicate(stock, config):
            continue

        symbol = stock.get("symbol")
        sector = stock.get("sector", "")
        industry = stock.get("industry", "")
        if symbol in selected_symbols:
            continue
        if sector_counts[sector] >= config["max_sector_count"]:
            continue
        if industry_counts[industry] >= config["max_industry_count"]:
            continue

        selected.append({**stock, "portfolio_sleeve": sleeve})
        selected_symbols.add(symbol)
        sector_counts[sector] += 1
        industry_counts[industry] += 1
        added += 1


def is_value_candidate(stock, config):
    return stock.get("pass_strategy") and stock.get("upside", 0.0) > 0


def is_quality_growth_candidate(stock, config):
    return (
        stock.get("pass_strategy")
        and stock.get("upside", 0.0) >= config["min_quality_growth_upside"]
        and stock.get("upside", 0.0) <= config["max_quality_growth_upside"]
        and stock.get("strategy_score", 0.0) >= config["min_quality_growth_score"]
        and stock.get("free_cash_flow", 0.0) > 0
        and stock.get("roic", 0.0) >= config["min_quality_growth_roic"]
        and stock.get("debt_to_equity", 0.0) <= config["max_quality_growth_debt_to_equity"]
        and stock.get("momentum_12m", 0.0) >= config["min_quality_growth_momentum_12m"]
    )
