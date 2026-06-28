import argparse
import csv
from itertools import product
from pathlib import Path

from quant_system.backtest import (
    DEFAULT_BENCHMARK_CACHE,
    DEFAULT_PRICE_CACHE,
    DEFAULT_SNAPSHOTS,
    calculate_metrics,
    calculate_turnover,
    evaluate_holdings,
    period_return,
    portfolio_weights,
    read_price_cache,
    read_snapshots,
)
from quant_system.portfolio import DEFAULT_PORTFOLIO, build_portfolio


DEFAULT_OUTPUT = "quant_system/output/parameter_sweep_results.csv"


OUTPUT_COLUMNS = [
    "rank",
    "portfolio_size",
    "quality_growth_sleeve_size",
    "value_sleeve_size",
    "max_sector_count",
    "max_industry_count",
    "transaction_cost_bps",
    "periods",
    "avg_holdings_count",
    "min_holdings_count",
    "cumulative_return",
    "gross_cumulative_return",
    "annualized_return",
    "annualized_volatility",
    "sharpe",
    "max_drawdown",
    "win_rate",
    "average_period_return",
    "average_turnover",
    "average_transaction_cost",
    "total_transaction_cost",
    "spy_cumulative_return",
    "qqq_cumulative_return",
    "spy_excess_cumulative_return",
    "qqq_excess_cumulative_return",
]


def main():
    parser = argparse.ArgumentParser(description="Sweep portfolio/backtest parameters.")
    parser.add_argument("--snapshots", default=DEFAULT_SNAPSHOTS)
    parser.add_argument("--price-cache", default=DEFAULT_PRICE_CACHE)
    parser.add_argument("--benchmark-cache", default=DEFAULT_BENCHMARK_CACHE)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--portfolio-sizes", default="15,20,25")
    parser.add_argument("--quality-growth-sizes", default="4,6,8,10")
    parser.add_argument("--max-sector-counts", default="2,3,4")
    parser.add_argument("--max-industry-counts", default="1")
    parser.add_argument("--transaction-cost-bps-list", default="8,15,20")
    parser.add_argument(
        "--top",
        type=int,
        default=0,
        help="Only print the top N rows to console. 0 prints all rows.",
    )
    args = parser.parse_args()

    snapshots = read_snapshots(Path(args.snapshots))
    prices = read_price_cache(Path(args.price_cache))
    benchmarks = read_price_cache(Path(args.benchmark_cache))
    dates = sorted(snapshots)
    if len(dates) < 2:
        raise RuntimeError("Need at least two snapshot dates to run a sweep.")

    parameter_sets = build_parameter_sets(args)
    print(
        f"Running parameter sweep: {len(parameter_sets)} combinations, "
        f"{len(dates) - 1} holding periods each..."
    )

    rows = []
    for index, config in enumerate(parameter_sets, start=1):
        row = run_one_config(config, snapshots, prices, benchmarks, dates)
        rows.append(row)
        print(
            f"[{index}/{len(parameter_sets)}] "
            f"portfolio={config['portfolio_size']}, "
            f"qg={config['quality_growth_sleeve_size']}, "
            f"value={config['value_sleeve_size']}, "
            f"sector={config['max_sector_count']}, "
            f"cost={config['transaction_cost_bps']}bps: "
            f"return={row['cumulative_return']:.2%}, "
            f"sharpe={row['sharpe']:.2f}, "
            f"dd={row['max_drawdown']:.2%}"
        )

    rows.sort(
        key=lambda row: (
            row["sharpe"],
            row["annualized_return"],
            -abs(row["max_drawdown"]),
        ),
        reverse=True,
    )
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank

    write_rows(Path(args.output), rows)
    print(f"Wrote {len(rows)} rows to {args.output}")
    print_top_rows(rows, args.top or len(rows))


def build_parameter_sets(args):
    parameter_sets = []

    for portfolio_size, quality_growth_size, max_sector_count, max_industry_count, cost_bps in product(
        parse_int_list(args.portfolio_sizes),
        parse_int_list(args.quality_growth_sizes),
        parse_int_list(args.max_sector_counts),
        parse_int_list(args.max_industry_counts),
        parse_float_list(args.transaction_cost_bps_list),
    ):
        if quality_growth_size >= portfolio_size:
            continue

        value_size = portfolio_size - quality_growth_size
        parameter_sets.append(
            {
                "portfolio_size": portfolio_size,
                "quality_growth_sleeve_size": quality_growth_size,
                "value_sleeve_size": value_size,
                "max_sector_count": max_sector_count,
                "max_industry_count": max_industry_count,
                "transaction_cost_bps": cost_bps,
            }
        )

    return parameter_sets


def run_one_config(config, snapshots, prices, benchmarks, dates):
    summary_rows = []
    previous_weights = {}
    gross_equity = 1.0
    net_equity = 1.0
    spy_equity = 1.0
    qqq_equity = 1.0
    transaction_cost_rate = config["transaction_cost_bps"] / 10_000

    portfolio_config = {
        **DEFAULT_PORTFOLIO,
        "portfolio_size": config["portfolio_size"],
        "quality_growth_sleeve_size": config["quality_growth_sleeve_size"],
        "value_sleeve_size": config["value_sleeve_size"],
        "max_sector_count": config["max_sector_count"],
        "max_industry_count": config["max_industry_count"],
    }

    for index, period_start in enumerate(dates[:-1], start=1):
        period_end = dates[index]
        candidates = snapshots[period_start]
        portfolio = build_portfolio(candidates, portfolio_config)
        current_weights = portfolio_weights(portfolio)
        buy_turnover, sell_turnover, turnover = calculate_turnover(
            previous_weights,
            current_weights,
        )
        transaction_cost = turnover * transaction_cost_rate
        _, gross_return, missing_exit_count = evaluate_holdings(
            portfolio,
            prices,
            period_start,
            period_end,
        )
        net_return = gross_return - transaction_cost
        spy_return = period_return(benchmarks.get("SPY", []), period_start, period_end)
        qqq_return = period_return(benchmarks.get("QQQ", []), period_start, period_end)
        gross_equity *= 1 + gross_return
        net_equity *= 1 + net_return
        spy_equity *= 1 + spy_return
        qqq_equity *= 1 + qqq_return

        summary_rows.append(
            {
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "candidate_count": len(candidates),
                "pass_count": sum(1 for item in candidates if item.get("pass_strategy")),
                "holdings_count": len(portfolio),
                "missing_exit_count": missing_exit_count,
                "buy_turnover": buy_turnover,
                "sell_turnover": sell_turnover,
                "turnover": turnover,
                "transaction_cost": transaction_cost,
                "gross_return": gross_return,
                "net_return": net_return,
                "portfolio_return": net_return,
                "spy_return": spy_return,
                "qqq_return": qqq_return,
                "excess_spy_return": net_return - spy_return,
                "excess_qqq_return": net_return - qqq_return,
                "gross_equity": gross_equity,
                "net_equity": net_equity,
                "equity": net_equity,
                "spy_equity": spy_equity,
                "qqq_equity": qqq_equity,
            }
        )
        previous_weights = current_weights

    metrics = calculate_metrics(summary_rows)
    holdings_counts = [row["holdings_count"] for row in summary_rows]

    return {
        **config,
        **metrics,
        "avg_holdings_count": average(holdings_counts),
        "min_holdings_count": min(holdings_counts) if holdings_counts else 0,
    }


def parse_int_list(value):
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def parse_float_list(value):
    return [float(item.strip()) for item in value.split(",") if item.strip()]


def average(values):
    return sum(values) / len(values) if values else 0.0


def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in OUTPUT_COLUMNS})


def print_top_rows(rows, limit):
    print("Top parameter rows:")
    for row in rows[:limit]:
        print(
            f"rank={row['rank']}, "
            f"portfolio={row['portfolio_size']}, "
            f"qg={row['quality_growth_sleeve_size']}, "
            f"value={row['value_sleeve_size']}, "
            f"sector={row['max_sector_count']}, "
            f"cost={row['transaction_cost_bps']}bps, "
            f"return={row['cumulative_return']:.2%}, "
            f"annual={row['annualized_return']:.2%}, "
            f"sharpe={row['sharpe']:.2f}, "
            f"dd={row['max_drawdown']:.2%}, "
            f"turnover={row['average_turnover']:.2%}"
        )


if __name__ == "__main__":
    main()
