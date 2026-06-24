import argparse
import csv
from pathlib import Path

from quant_system.build_portfolio_from_results import coerce_row


AUDIT_COLUMNS = [
    "portfolio_rank",
    "portfolio_sleeve",
    "symbol",
    "company_name",
    "sector",
    "industry",
    "price",
    "fair_value",
    "upside",
    "strategy_score",
    "wacc",
    "dcf_growth_rate",
    "free_cash_flow",
    "market_cap",
    "beta",
    "roic",
    "debt_to_equity",
    "momentum_12m",
    "warning_count",
    "warning_flags",
]


CYCLICAL_SECTORS = {
    "Basic Materials",
    "Energy",
    "Consumer Cyclical",
}


CYCLICAL_INDUSTRY_KEYWORDS = [
    "oil",
    "gas",
    "gold",
    "silver",
    "mining",
    "metals",
    "coal",
    "steel",
    "aluminum",
    "airlines",
    "auto",
    "semiconductors",
]


def main():
    parser = argparse.ArgumentParser(
        description="Audit final portfolio for valuation and data-quality warning flags."
    )
    parser.add_argument(
        "--input",
        default="quant_system/output/portfolio_results.csv",
        help="Portfolio CSV path.",
    )
    parser.add_argument(
        "--output",
        default="quant_system/output/portfolio_quality_report.csv",
        help="Quality report CSV path.",
    )
    args = parser.parse_args()

    portfolio = read_portfolio(args.input)
    report = [audit_row(row) for row in portfolio]
    write_report(report, args.output)

    flagged = sum(1 for row in report if row["warning_count"] > 0)
    print(f"Wrote {len(report)} audit rows to {args.output}; {flagged} rows have warnings")


def read_portfolio(input_path):
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"Portfolio file not found: {input_path}")

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return [coerce_row(row) for row in csv.DictReader(file)]


def audit_row(row):
    flags = warning_flags(row)
    return {
        "portfolio_rank": row.get("portfolio_rank", ""),
        "portfolio_sleeve": row.get("portfolio_sleeve", ""),
        "symbol": row.get("symbol", ""),
        "company_name": row.get("company_name", ""),
        "sector": row.get("sector", ""),
        "industry": row.get("industry", ""),
        "price": row.get("price", ""),
        "fair_value": row.get("fair_value", ""),
        "upside": row.get("upside", ""),
        "strategy_score": row.get("strategy_score", ""),
        "wacc": row.get("wacc", ""),
        "dcf_growth_rate": row.get("dcf_growth_rate", ""),
        "free_cash_flow": row.get("free_cash_flow", ""),
        "market_cap": row.get("market_cap", ""),
        "beta": row.get("beta", ""),
        "roic": row.get("roic", ""),
        "debt_to_equity": row.get("debt_to_equity", ""),
        "momentum_12m": row.get("momentum_12m", ""),
        "warning_count": len(flags),
        "warning_flags": ";".join(flags),
    }


def warning_flags(row):
    flags = []
    upside = row.get("upside", 0.0)
    wacc = row.get("wacc", 0.0)
    growth = row.get("dcf_growth_rate", 0.0)
    beta = row.get("beta", 0.0)
    roic = row.get("roic", 0.0)
    debt_to_equity = row.get("debt_to_equity", 0.0)
    momentum_12m = row.get("momentum_12m", 0.0)
    market_cap = row.get("market_cap", 0.0)

    if upside > 3.0:
        flags.append("extreme_upside_over_300pct")
    elif upside > 1.5:
        flags.append("high_upside_over_150pct")
    if upside < 0.10:
        flags.append("thin_margin_of_safety")
    if growth >= 0.295:
        flags.append("growth_assumption_near_cap")
    if wacc < 0.06:
        flags.append("low_wacc_under_6pct")
    if beta <= 0:
        flags.append("non_positive_beta")
    elif beta < 0.5:
        flags.append("low_beta_under_0_5")
    if roic > 1.0:
        flags.append("very_high_roic_over_100pct")
    if debt_to_equity > 1.5:
        flags.append("high_debt_to_equity")
    if momentum_12m < -0.30:
        flags.append("negative_12m_momentum_under_minus_30pct")
    if market_cap < 15_000_000_000:
        flags.append("near_minimum_market_cap")
    if is_cyclical(row):
        flags.append("cyclical_business_check_normalized_fcf")

    return flags


def is_cyclical(row):
    sector = row.get("sector", "")
    industry = row.get("industry", "").lower()
    return sector in CYCLICAL_SECTORS or any(
        keyword in industry for keyword in CYCLICAL_INDUSTRY_KEYWORDS
    )


def write_report(report, output_path):
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=AUDIT_COLUMNS)
        writer.writeheader()
        writer.writerows(report)


if __name__ == "__main__":
    main()
