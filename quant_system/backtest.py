import argparse
import csv
import math
from bisect import bisect_right
from datetime import datetime
from pathlib import Path

from quant_system.portfolio import DEFAULT_PORTFOLIO, build_portfolio
from quant_system.run_universe import OUTPUT_COLUMNS


DEFAULT_SNAPSHOTS = "quant_system/output/historical_quarterly_snapshots.csv"
DEFAULT_PRICE_CACHE = "quant_system/cache/historical/prices_daily.csv"
DEFAULT_BENCHMARK_CACHE = "quant_system/cache/historical/benchmark_prices_daily.csv"
DEFAULT_SUMMARY_OUTPUT = "quant_system/output/backtest_summary.csv"
DEFAULT_HOLDINGS_OUTPUT = "quant_system/output/backtest_holdings.csv"
DEFAULT_METRICS_OUTPUT = "quant_system/output/backtest_metrics.csv"


SUMMARY_COLUMNS = [
    "period_start",
    "period_end",
    "candidate_count",
    "pass_count",
    "holdings_count",
    "missing_exit_count",
    "buy_turnover",
    "sell_turnover",
    "turnover",
    "transaction_cost",
    "gross_return",
    "net_return",
    "portfolio_return",
    "spy_return",
    "qqq_return",
    "excess_spy_return",
    "excess_qqq_return",
    "gross_equity",
    "net_equity",
    "equity",
    "spy_equity",
    "qqq_equity",
]


HOLDING_COLUMNS = [
    "period_start",
    "period_end",
    "portfolio_rank",
    "target_weight",
    "portfolio_sleeve",
    "entry_price",
    "exit_price",
    "holding_return",
    "return_contribution",
    *OUTPUT_COLUMNS,
]


METRIC_COLUMNS = [
    "periods",
    "start_date",
    "end_date",
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
    parser = argparse.ArgumentParser(description="Backtest quarterly portfolio snapshots.")
    parser.add_argument("--snapshots", default=DEFAULT_SNAPSHOTS)
    parser.add_argument("--price-cache", default=DEFAULT_PRICE_CACHE)
    parser.add_argument("--benchmark-cache", default=DEFAULT_BENCHMARK_CACHE)
    parser.add_argument("--summary-output", default=DEFAULT_SUMMARY_OUTPUT)
    parser.add_argument("--holdings-output", default=DEFAULT_HOLDINGS_OUTPUT)
    parser.add_argument("--metrics-output", default=DEFAULT_METRICS_OUTPUT)
    parser.add_argument(
        "--portfolio-size",
        type=int,
        default=DEFAULT_PORTFOLIO["portfolio_size"],
    )
    parser.add_argument(
        "--value-sleeve-size",
        type=int,
        default=DEFAULT_PORTFOLIO["value_sleeve_size"],
    )
    parser.add_argument(
        "--quality-growth-sleeve-size",
        type=int,
        default=DEFAULT_PORTFOLIO["quality_growth_sleeve_size"],
    )
    parser.add_argument(
        "--max-sector-count",
        type=int,
        default=DEFAULT_PORTFOLIO["max_sector_count"],
    )
    parser.add_argument(
        "--max-industry-count",
        type=int,
        default=DEFAULT_PORTFOLIO["max_industry_count"],
    )
    parser.add_argument(
        "--transaction-cost-bps",
        type=float,
        default=8.0,
        help="One-way transaction cost in basis points. 8 bps = 0.08%.",
    )
    args = parser.parse_args()

    snapshots = read_snapshots(Path(args.snapshots))
    prices = read_price_cache(Path(args.price_cache))
    benchmarks = read_price_cache(Path(args.benchmark_cache))
    dates = sorted(snapshots)
    if len(dates) < 2:
        raise RuntimeError("Need at least two snapshot dates to run a backtest.")

    portfolio_config = {
        "portfolio_size": args.portfolio_size,
        "value_sleeve_size": args.value_sleeve_size,
        "quality_growth_sleeve_size": args.quality_growth_sleeve_size,
        "max_sector_count": args.max_sector_count,
        "max_industry_count": args.max_industry_count,
    }
    summary_rows = []
    holding_rows = []
    previous_weights = {}
    gross_equity = 1.0
    net_equity = 1.0
    spy_equity = 1.0
    qqq_equity = 1.0
    transaction_cost_rate = args.transaction_cost_bps / 10_000

    print(f"Running backtest across {len(dates) - 1} holding periods...")

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
        holdings, gross_return, missing_exit_count = evaluate_holdings(
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
        holding_rows.extend(holdings)
        previous_weights = current_weights
        print(
            f"[{index}/{len(dates) - 1}] {period_start} -> {period_end}: "
            f"holdings={len(portfolio)}, gross={gross_return:.2%}, "
            f"net={net_return:.2%}, turnover={turnover:.2%}, "
            f"SPY={spy_return:.2%}, QQQ={qqq_return:.2%}"
        )

    metrics = calculate_metrics(summary_rows)
    write_rows(Path(args.summary_output), SUMMARY_COLUMNS, summary_rows)
    write_rows(Path(args.holdings_output), HOLDING_COLUMNS, holding_rows)
    write_rows(Path(args.metrics_output), METRIC_COLUMNS, [metrics])
    print(f"Wrote {len(summary_rows)} rows to {args.summary_output}")
    print(f"Wrote {len(holding_rows)} rows to {args.holdings_output}")
    print(f"Wrote metrics to {args.metrics_output}")


def read_snapshots(path):
    grouped = {}
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            clean = normalize_snapshot_row(row)
            as_of = parse_date(clean["as_of_date"])
            grouped.setdefault(as_of, []).append(clean)
    return grouped


def normalize_snapshot_row(row):
    clean = dict(row)
    for key in [
        "pass_strategy",
        "is_etf",
        "is_fund",
        "is_adr",
        "is_actively_trading",
    ]:
        clean[key] = parse_bool(clean.get(key))

    for key in [
        "strategy_score",
        "price",
        "fair_value",
        "upside",
        "score",
        "wacc",
        "dcf_growth_rate",
        "growth_estimate",
        "revenue_growth",
        "fcf_growth",
        "eps_growth",
        "momentum_3m",
        "momentum_6m",
        "momentum_12m",
        "free_cash_flow",
        "market_cap",
        "beta",
        "roic",
        "debt_to_equity",
    ]:
        clean[key] = parse_float(clean.get(key))

    return clean


def read_price_cache(path):
    grouped = {}
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            symbol = str(row.get("symbol", "")).strip().upper()
            price_date = parse_date(row.get("date"))
            close = parse_float(row.get("close"))
            if not symbol or not price_date or close <= 0:
                continue
            grouped.setdefault(symbol, []).append({"date": price_date, "close": close})

    for rows in grouped.values():
        rows.sort(key=lambda item: item["date"])

    return grouped


def evaluate_holdings(portfolio, prices, period_start, period_end):
    holdings = []
    portfolio_return = 0.0
    missing_exit_count = 0

    for stock in portfolio:
        symbol = stock["symbol"]
        entry_price = parse_float(stock.get("price"))
        exit_price = price_on_or_before(prices.get(symbol, []), period_end)
        if entry_price <= 0:
            holding_return = 0.0
            missing_exit_count += 1
        elif exit_price <= 0:
            holding_return = 0.0
            missing_exit_count += 1
        else:
            holding_return = exit_price / entry_price - 1

        contribution = parse_float(stock.get("target_weight")) * holding_return
        portfolio_return += contribution
        holdings.append(
            {
                **stock,
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "entry_price": entry_price,
                "exit_price": exit_price,
                "holding_return": holding_return,
                "return_contribution": contribution,
            }
        )

    return holdings, portfolio_return, missing_exit_count


def portfolio_weights(portfolio):
    return {
        stock["symbol"]: parse_float(stock.get("target_weight"))
        for stock in portfolio
    }


def calculate_turnover(previous_weights, current_weights):
    symbols = set(previous_weights) | set(current_weights)
    buy_turnover = 0.0
    sell_turnover = 0.0

    for symbol in symbols:
        previous_weight = previous_weights.get(symbol, 0.0)
        current_weight = current_weights.get(symbol, 0.0)
        change = current_weight - previous_weight
        if change > 0:
            buy_turnover += change
        elif change < 0:
            sell_turnover += abs(change)

    return buy_turnover, sell_turnover, buy_turnover + sell_turnover


def period_return(prices, start_date, end_date):
    start_price = price_on_or_before(prices, start_date)
    end_price = price_on_or_before(prices, end_date)
    if start_price <= 0 or end_price <= 0:
        return 0.0
    return end_price / start_price - 1


def price_on_or_before(prices, as_of):
    if not prices:
        return 0.0
    dates = [row["date"] for row in prices]
    index = bisect_right(dates, as_of) - 1
    if index < 0:
        return 0.0
    return prices[index]["close"]


def calculate_metrics(summary_rows):
    returns = [parse_float(row["net_return"]) for row in summary_rows]
    gross_returns = [parse_float(row["gross_return"]) for row in summary_rows]
    spy_returns = [parse_float(row["spy_return"]) for row in summary_rows]
    qqq_returns = [parse_float(row["qqq_return"]) for row in summary_rows]
    equity_curve = [parse_float(row["net_equity"]) for row in summary_rows]
    gross_equity_curve = [parse_float(row["gross_equity"]) for row in summary_rows]
    cumulative_return = equity_curve[-1] - 1 if equity_curve else 0.0
    gross_cumulative_return = gross_equity_curve[-1] - 1 if gross_equity_curve else 0.0
    periods = len(returns)
    annualized_return = (1 + cumulative_return) ** (4 / periods) - 1 if periods else 0.0
    annualized_volatility = stddev(returns) * math.sqrt(4)
    sharpe = annualized_return / annualized_volatility if annualized_volatility > 0 else 0.0
    max_drawdown = calculate_max_drawdown(equity_curve)
    win_rate = sum(1 for item in returns if item > 0) / periods if periods else 0.0
    average_period_return = sum(returns) / periods if periods else 0.0
    average_turnover = average([parse_float(row["turnover"]) for row in summary_rows])
    average_transaction_cost = average(
        [parse_float(row["transaction_cost"]) for row in summary_rows]
    )
    total_transaction_cost = sum(
        parse_float(row["transaction_cost"]) for row in summary_rows
    )
    spy_cumulative_return = compound_return(spy_returns)
    qqq_cumulative_return = compound_return(qqq_returns)

    return {
        "periods": periods,
        "start_date": summary_rows[0]["period_start"] if summary_rows else "",
        "end_date": summary_rows[-1]["period_end"] if summary_rows else "",
        "cumulative_return": cumulative_return,
        "gross_cumulative_return": gross_cumulative_return,
        "annualized_return": annualized_return,
        "annualized_volatility": annualized_volatility,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown,
        "win_rate": win_rate,
        "average_period_return": average_period_return,
        "average_turnover": average_turnover,
        "average_transaction_cost": average_transaction_cost,
        "total_transaction_cost": total_transaction_cost,
        "spy_cumulative_return": spy_cumulative_return,
        "qqq_cumulative_return": qqq_cumulative_return,
        "spy_excess_cumulative_return": cumulative_return - spy_cumulative_return,
        "qqq_excess_cumulative_return": cumulative_return - qqq_cumulative_return,
    }


def calculate_max_drawdown(equity_curve):
    peak = 1.0
    max_drawdown = 0.0
    for value in equity_curve:
        peak = max(peak, value)
        if peak > 0:
            max_drawdown = min(max_drawdown, value / peak - 1)
    return max_drawdown


def compound_return(returns):
    value = 1.0
    for item in returns:
        value *= 1 + item
    return value - 1


def stddev(values):
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((item - mean) ** 2 for item in values) / (len(values) - 1)
    return math.sqrt(variance)


def average(values):
    return sum(values) / len(values) if values else 0.0


def write_rows(path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


def parse_date(value):
    if not value:
        return None
    raw = str(value).strip().split(" ")[0]
    if not raw:
        return None
    return datetime.strptime(raw, "%Y-%m-%d").date()


def parse_bool(value):
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def parse_float(value):
    if value in (None, ""):
        return 0.0
    return float(value)


if __name__ == "__main__":
    main()
