import argparse
import csv
from collections import defaultdict
from pathlib import Path


DEFAULT_HOLDINGS = "quant_system/output/backtest_holdings.csv"
DEFAULT_SUMMARY = "quant_system/output/backtest_summary.csv"
DEFAULT_OUTPUT_DIR = "quant_system/output"


GROUP_COLUMNS = [
    "group",
    "count",
    "win_count",
    "loss_count",
    "win_rate",
    "avg_holding_return",
    "avg_winner_return",
    "avg_loser_return",
    "payoff_ratio",
    "total_contribution",
    "avg_contribution",
    "best_period",
    "best_symbol",
    "best_return",
    "best_contribution",
    "worst_period",
    "worst_symbol",
    "worst_return",
    "worst_contribution",
]


PERIOD_COLUMNS = [
    "period_start",
    "period_end",
    "holdings_count",
    "win_count",
    "loss_count",
    "win_rate",
    "avg_holding_return",
    "total_contribution",
    "gross_return",
    "net_return",
    "spy_return",
    "qqq_return",
    "excess_spy_return",
    "excess_qqq_return",
    "turnover",
    "transaction_cost",
    "top_symbol",
    "top_contribution",
    "bottom_symbol",
    "bottom_contribution",
]


EXTREME_COLUMNS = [
    "rank_type",
    "period_start",
    "period_end",
    "symbol",
    "company_name",
    "portfolio_sleeve",
    "sector",
    "industry",
    "holding_return",
    "return_contribution",
    "strategy_score",
    "upside",
    "roic",
    "debt_to_equity",
]


def main():
    parser = argparse.ArgumentParser(description="Audit backtest holdings and periods.")
    parser.add_argument("--holdings", default=DEFAULT_HOLDINGS)
    parser.add_argument("--summary", default=DEFAULT_SUMMARY)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--top-n", type=int, default=25)
    args = parser.parse_args()

    holdings = read_rows(Path(args.holdings))
    summary = read_rows(Path(args.summary))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    normalize_holdings(holdings)
    normalize_summary(summary)

    write_group_audit(
        output_dir / "backtest_audit_by_symbol.csv",
        holdings,
        key=lambda row: row["symbol"],
        display=lambda row: row["symbol"],
    )
    write_group_audit(
        output_dir / "backtest_audit_by_sector.csv",
        holdings,
        key=lambda row: row.get("sector", ""),
        display=lambda row: row.get("sector", ""),
    )
    write_group_audit(
        output_dir / "backtest_audit_by_industry.csv",
        holdings,
        key=lambda row: row.get("industry", ""),
        display=lambda row: row.get("industry", ""),
    )
    write_group_audit(
        output_dir / "backtest_audit_by_sleeve.csv",
        holdings,
        key=lambda row: row.get("portfolio_sleeve", ""),
        display=lambda row: row.get("portfolio_sleeve", ""),
    )
    write_period_audit(
        output_dir / "backtest_audit_by_period.csv",
        holdings,
        summary,
    )
    write_extremes(
        output_dir / "backtest_audit_extremes.csv",
        holdings,
        top_n=args.top_n,
    )

    print(f"Wrote audit files to {output_dir}")


def read_rows(path):
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def normalize_holdings(rows):
    numeric_columns = [
        "target_weight",
        "entry_price",
        "exit_price",
        "holding_return",
        "return_contribution",
        "strategy_score",
        "upside",
        "roic",
        "debt_to_equity",
    ]
    for row in rows:
        for column in numeric_columns:
            row[column] = parse_float(row.get(column))


def normalize_summary(rows):
    numeric_columns = [
        "gross_return",
        "net_return",
        "portfolio_return",
        "spy_return",
        "qqq_return",
        "excess_spy_return",
        "excess_qqq_return",
        "turnover",
        "transaction_cost",
    ]
    for row in rows:
        for column in numeric_columns:
            row[column] = parse_float(row.get(column))


def write_group_audit(path, holdings, key, display):
    groups = defaultdict(list)
    for row in holdings:
        groups[key(row)].append(row)

    rows = []
    for _, group_rows in groups.items():
        rows.append(build_group_row(display(group_rows[0]), group_rows))

    rows.sort(key=lambda row: row["total_contribution"], reverse=True)
    write_rows(path, GROUP_COLUMNS, rows)


def build_group_row(group_name, rows):
    winners = [row for row in rows if row["holding_return"] > 0]
    losers = [row for row in rows if row["holding_return"] < 0]
    best = max(rows, key=lambda row: row["return_contribution"])
    worst = min(rows, key=lambda row: row["return_contribution"])
    avg_winner = average([row["holding_return"] for row in winners])
    avg_loser = average([row["holding_return"] for row in losers])
    payoff_ratio = abs(avg_winner / avg_loser) if avg_loser else 0.0

    return {
        "group": group_name,
        "count": len(rows),
        "win_count": len(winners),
        "loss_count": len(losers),
        "win_rate": len(winners) / len(rows) if rows else 0.0,
        "avg_holding_return": average([row["holding_return"] for row in rows]),
        "avg_winner_return": avg_winner,
        "avg_loser_return": avg_loser,
        "payoff_ratio": payoff_ratio,
        "total_contribution": sum(row["return_contribution"] for row in rows),
        "avg_contribution": average([row["return_contribution"] for row in rows]),
        "best_period": best["period_start"],
        "best_symbol": best["symbol"],
        "best_return": best["holding_return"],
        "best_contribution": best["return_contribution"],
        "worst_period": worst["period_start"],
        "worst_symbol": worst["symbol"],
        "worst_return": worst["holding_return"],
        "worst_contribution": worst["return_contribution"],
    }


def write_period_audit(path, holdings, summary):
    holdings_by_period = defaultdict(list)
    for row in holdings:
        holdings_by_period[row["period_start"]].append(row)

    rows = []
    for summary_row in summary:
        period = summary_row["period_start"]
        period_holdings = holdings_by_period.get(period, [])
        winners = [row for row in period_holdings if row["holding_return"] > 0]
        losers = [row for row in period_holdings if row["holding_return"] < 0]
        best = max(period_holdings, key=lambda row: row["return_contribution"]) if period_holdings else {}
        worst = min(period_holdings, key=lambda row: row["return_contribution"]) if period_holdings else {}

        rows.append(
            {
                "period_start": period,
                "period_end": summary_row["period_end"],
                "holdings_count": len(period_holdings),
                "win_count": len(winners),
                "loss_count": len(losers),
                "win_rate": len(winners) / len(period_holdings) if period_holdings else 0.0,
                "avg_holding_return": average([row["holding_return"] for row in period_holdings]),
                "total_contribution": sum(row["return_contribution"] for row in period_holdings),
                "gross_return": summary_row.get("gross_return", 0.0),
                "net_return": summary_row.get("net_return", summary_row.get("portfolio_return", 0.0)),
                "spy_return": summary_row.get("spy_return", 0.0),
                "qqq_return": summary_row.get("qqq_return", 0.0),
                "excess_spy_return": summary_row.get("excess_spy_return", 0.0),
                "excess_qqq_return": summary_row.get("excess_qqq_return", 0.0),
                "turnover": summary_row.get("turnover", 0.0),
                "transaction_cost": summary_row.get("transaction_cost", 0.0),
                "top_symbol": best.get("symbol", ""),
                "top_contribution": best.get("return_contribution", 0.0),
                "bottom_symbol": worst.get("symbol", ""),
                "bottom_contribution": worst.get("return_contribution", 0.0),
            }
        )

    write_rows(path, PERIOD_COLUMNS, rows)


def write_extremes(path, holdings, top_n):
    best = sorted(holdings, key=lambda row: row["return_contribution"], reverse=True)[:top_n]
    worst = sorted(holdings, key=lambda row: row["return_contribution"])[:top_n]
    rows = []
    rows.extend(format_extreme_rows("best", best))
    rows.extend(format_extreme_rows("worst", worst))
    write_rows(path, EXTREME_COLUMNS, rows)


def format_extreme_rows(rank_type, rows):
    return [
        {
            "rank_type": rank_type,
            "period_start": row["period_start"],
            "period_end": row["period_end"],
            "symbol": row["symbol"],
            "company_name": row.get("company_name", ""),
            "portfolio_sleeve": row.get("portfolio_sleeve", ""),
            "sector": row.get("sector", ""),
            "industry": row.get("industry", ""),
            "holding_return": row["holding_return"],
            "return_contribution": row["return_contribution"],
            "strategy_score": row["strategy_score"],
            "upside": row["upside"],
            "roic": row["roic"],
            "debt_to_equity": row["debt_to_equity"],
        }
        for row in rows
    ]


def write_rows(path, fieldnames, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


def parse_float(value):
    if value in (None, ""):
        return 0.0
    return float(value)


def average(values):
    return sum(values) / len(values) if values else 0.0


if __name__ == "__main__":
    main()
