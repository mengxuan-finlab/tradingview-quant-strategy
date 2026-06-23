from collections import defaultdict


DEFAULT_PORTFOLIO = {
    "portfolio_size": 20,
    "max_sector_count": 3,
    "max_industry_count": 1,
    "require_positive_upside": True,
}


def build_portfolio(results, config=None):
    config = config or DEFAULT_PORTFOLIO
    candidates = sorted(
        results,
        key=lambda item: item.get("strategy_score", 0.0),
        reverse=True,
    )
    selected = []
    sector_counts = defaultdict(int)
    industry_counts = defaultdict(int)

    for stock in candidates:
        if len(selected) >= config["portfolio_size"]:
            break
        if not stock.get("pass_strategy"):
            continue
        if config.get("require_positive_upside", True) and stock.get("upside", 0.0) <= 0:
            continue

        sector = stock.get("sector", "")
        industry = stock.get("industry", "")
        if sector_counts[sector] >= config["max_sector_count"]:
            continue
        if industry_counts[industry] >= config["max_industry_count"]:
            continue

        selected.append(stock)
        sector_counts[sector] += 1
        industry_counts[industry] += 1

    weight = 1 / len(selected) if selected else 0.0
    return [
        {
            **stock,
            "portfolio_rank": rank,
            "target_weight": weight,
        }
        for rank, stock in enumerate(selected, start=1)
    ]
