import argparse
import csv
from pathlib import Path
from types import SimpleNamespace

from quant_system.backtest import (
    DEFAULT_BENCHMARK_CACHE,
    DEFAULT_PRICE_CACHE,
    DEFAULT_SNAPSHOTS,
    read_price_cache,
    read_snapshots,
)
from quant_system.parameter_sweep import (
    build_parameter_sets,
    run_one_config,
)


DEFAULT_OUTPUT = "quant_system/output/walk_forward_results.csv"


OUTPUT_COLUMNS = [
    "window",
    "train_start",
    "train_end",
    "test_start",
    "test_end",
    "selected_rank",
    "portfolio_size",
    "quality_growth_sleeve_size",
    "value_sleeve_size",
    "max_sector_count",
    "max_industry_count",
    "transaction_cost_bps",
    "train_periods",
    "train_cumulative_return",
    "train_annualized_return",
    "train_sharpe",
    "train_max_drawdown",
    "train_win_rate",
    "train_avg_turnover",
    "test_periods",
    "test_cumulative_return",
    "test_annualized_return",
    "test_sharpe",
    "test_max_drawdown",
    "test_win_rate",
    "test_avg_turnover",
    "test_spy_cumulative_return",
    "test_qqq_cumulative_return",
    "test_spy_excess_cumulative_return",
    "test_qqq_excess_cumulative_return",
    "test_avg_holdings_count",
    "test_min_holdings_count",
]


def main():
    parser = argparse.ArgumentParser(
        description="Run expanding-window walk-forward parameter validation."
    )
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
        "--train-periods",
        type=int,
        default=7,
        help="Number of quarterly holding periods in the first training window.",
    )
    parser.add_argument(
        "--test-periods",
        type=int,
        default=4,
        help="Number of quarterly holding periods in each test window.",
    )
    parser.add_argument(
        "--step-periods",
        type=int,
        default=4,
        help="Number of quarterly periods to move forward after each test.",
    )
    parser.add_argument(
        "--selection-metric",
        choices=["sharpe", "annualized_return", "cumulative_return"],
        default="sharpe",
    )
    args = parser.parse_args()

    snapshots = read_snapshots(Path(args.snapshots))
    prices = read_price_cache(Path(args.price_cache))
    benchmarks = read_price_cache(Path(args.benchmark_cache))
    dates = sorted(snapshots)
    if len(dates) < args.train_periods + args.test_periods + 1:
        raise RuntimeError("Not enough snapshot dates for the requested walk-forward windows.")

    parameter_sets = build_parameter_sets(
        SimpleNamespace(
            portfolio_sizes=args.portfolio_sizes,
            quality_growth_sizes=args.quality_growth_sizes,
            max_sector_counts=args.max_sector_counts,
            max_industry_counts=args.max_industry_counts,
            transaction_cost_bps_list=args.transaction_cost_bps_list,
        )
    )
    windows = build_windows(dates, args.train_periods, args.test_periods, args.step_periods)

    print(
        f"Running walk-forward: {len(windows)} windows, "
        f"{len(parameter_sets)} parameter combinations each..."
    )

    output_rows = []
    for window_number, (train_dates, test_dates) in enumerate(windows, start=1):
        train_rows = []
        for config in parameter_sets:
            train_rows.append(run_one_config(config, snapshots, prices, benchmarks, train_dates))

        train_rows.sort(
            key=lambda row: (
                row[args.selection_metric],
                row["annualized_return"],
                -abs(row["max_drawdown"]),
            ),
            reverse=True,
        )
        best_train = train_rows[0]
        test_row = run_one_config(best_train, snapshots, prices, benchmarks, test_dates)

        output_row = build_output_row(
            window_number=window_number,
            selected_rank=1,
            best_train=best_train,
            test_row=test_row,
            train_dates=train_dates,
            test_dates=test_dates,
        )
        output_rows.append(output_row)

        print(
            f"[{window_number}/{len(windows)}] "
            f"train {train_dates[0]} -> {train_dates[-1]}, "
            f"test {test_dates[0]} -> {test_dates[-1]}: "
            f"selected portfolio={best_train['portfolio_size']}, "
            f"qg={best_train['quality_growth_sleeve_size']}, "
            f"value={best_train['value_sleeve_size']}, "
            f"sector={best_train['max_sector_count']}, "
            f"cost={best_train['transaction_cost_bps']}bps, "
            f"train_sharpe={best_train['sharpe']:.2f}, "
            f"test_return={test_row['cumulative_return']:.2%}, "
            f"test_sharpe={test_row['sharpe']:.2f}"
        )

    write_rows(Path(args.output), output_rows)
    print(f"Wrote {len(output_rows)} rows to {args.output}")
    print_summary(output_rows)


def build_windows(dates, train_periods, test_periods, step_periods):
    windows = []
    train_end_index = train_periods
    while train_end_index + test_periods < len(dates):
        train_dates = dates[: train_end_index + 1]
        test_dates = dates[train_end_index : train_end_index + test_periods + 1]
        windows.append((train_dates, test_dates))
        train_end_index += step_periods
    return windows


def build_output_row(window_number, selected_rank, best_train, test_row, train_dates, test_dates):
    return {
        "window": window_number,
        "train_start": train_dates[0].isoformat(),
        "train_end": train_dates[-1].isoformat(),
        "test_start": test_dates[0].isoformat(),
        "test_end": test_dates[-1].isoformat(),
        "selected_rank": selected_rank,
        "portfolio_size": best_train["portfolio_size"],
        "quality_growth_sleeve_size": best_train["quality_growth_sleeve_size"],
        "value_sleeve_size": best_train["value_sleeve_size"],
        "max_sector_count": best_train["max_sector_count"],
        "max_industry_count": best_train["max_industry_count"],
        "transaction_cost_bps": best_train["transaction_cost_bps"],
        "train_periods": best_train["periods"],
        "train_cumulative_return": best_train["cumulative_return"],
        "train_annualized_return": best_train["annualized_return"],
        "train_sharpe": best_train["sharpe"],
        "train_max_drawdown": best_train["max_drawdown"],
        "train_win_rate": best_train["win_rate"],
        "train_avg_turnover": best_train["average_turnover"],
        "test_periods": test_row["periods"],
        "test_cumulative_return": test_row["cumulative_return"],
        "test_annualized_return": test_row["annualized_return"],
        "test_sharpe": test_row["sharpe"],
        "test_max_drawdown": test_row["max_drawdown"],
        "test_win_rate": test_row["win_rate"],
        "test_avg_turnover": test_row["average_turnover"],
        "test_spy_cumulative_return": test_row["spy_cumulative_return"],
        "test_qqq_cumulative_return": test_row["qqq_cumulative_return"],
        "test_spy_excess_cumulative_return": test_row["spy_excess_cumulative_return"],
        "test_qqq_excess_cumulative_return": test_row["qqq_excess_cumulative_return"],
        "test_avg_holdings_count": test_row["avg_holdings_count"],
        "test_min_holdings_count": test_row["min_holdings_count"],
    }


def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in OUTPUT_COLUMNS})


def print_summary(rows):
    if not rows:
        return
    total_return = compound_return([row["test_cumulative_return"] for row in rows])
    spy_return = compound_return([row["test_spy_cumulative_return"] for row in rows])
    qqq_return = compound_return([row["test_qqq_cumulative_return"] for row in rows])
    beat_spy = sum(1 for row in rows if row["test_spy_excess_cumulative_return"] > 0)
    beat_qqq = sum(1 for row in rows if row["test_qqq_excess_cumulative_return"] > 0)

    print("Walk-forward summary:")
    print(f"test compound return={total_return:.2%}")
    print(f"test SPY compound return={spy_return:.2%}")
    print(f"test QQQ compound return={qqq_return:.2%}")
    print(f"beat SPY windows={beat_spy}/{len(rows)}")
    print(f"beat QQQ windows={beat_qqq}/{len(rows)}")


def compound_return(returns):
    value = 1.0
    for item in returns:
        value *= 1 + item
    return value - 1


if __name__ == "__main__":
    main()
