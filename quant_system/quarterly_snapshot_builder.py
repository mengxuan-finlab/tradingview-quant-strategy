import argparse
import csv
from bisect import bisect_right
from datetime import date, datetime, timedelta
from pathlib import Path

from quant_system.data_pipeline import estimate_growth_rate, estimate_roic
from quant_system.models import first_number, number
from quant_system.run_universe import OUTPUT_COLUMNS, load_symbols, write_results
from quant_system.strategy import apply_quality_value_strategy
from quant_system.valuation_engine import value_stock


DEFAULT_CACHE_DIR = "quant_system/cache/historical"
DEFAULT_OUTPUT = "quant_system/output/historical_quarterly_snapshots.csv"
DEFAULT_FAILED_OUTPUT = "quant_system/output/failed_historical_snapshots.csv"


SNAPSHOT_COLUMNS = [
    "as_of_date",
    "fiscal_date",
    "filing_date",
    "accepted_date",
    *OUTPUT_COLUMNS,
]


def main():
    parser = argparse.ArgumentParser(
        description="Build point-in-time quarterly snapshots from local historical cache."
    )
    parser.add_argument(
        "--symbols",
        help="Comma-separated symbols, for example: AAPL,MSFT,NVDA.",
    )
    parser.add_argument(
        "--universe",
        default="",
        help="CSV or text file with one symbol per row, or a CSV column named symbol.",
    )
    parser.add_argument("--cache-dir", default=DEFAULT_CACHE_DIR)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--failed-output", default=DEFAULT_FAILED_OUTPUT)
    parser.add_argument("--start-date", default="2021-09-30")
    parser.add_argument("--end-date", default="")
    parser.add_argument(
        "--rebalance-delay-days",
        type=int,
        default=45,
        help="Use quarter-end plus this delay as the rebalance date.",
    )
    parser.add_argument("--limit-symbols", type=int)
    parser.add_argument("--risk-free-rate", type=float, default=0.04)
    parser.add_argument("--market-return", type=float, default=0.10)
    parser.add_argument("--terminal-growth-rate", type=float, default=0.03)
    parser.add_argument("--tax-rate", type=float, default=0.21)
    args = parser.parse_args()

    symbols = load_symbols(args.symbols, args.universe)
    if args.limit_symbols:
        symbols = symbols[: args.limit_symbols]
    if not symbols:
        raise RuntimeError("No symbols provided. Use --symbols or --universe.")

    cache = load_cache(Path(args.cache_dir))
    as_of_dates = quarter_rebalance_dates(
        parse_date(args.start_date),
        parse_date(args.end_date) if args.end_date else infer_end_date(cache["prices"]),
        args.rebalance_delay_days,
    )

    results = []
    failures = []

    print(
        f"Building quarterly snapshots for {len(symbols)} symbols "
        f"and {len(as_of_dates)} rebalance dates..."
    )

    for symbol_index, symbol in enumerate(symbols, start=1):
        symbol_data = {
            "profile": cache["profiles"].get(symbol, {}),
            "income": cache["income"].get(symbol, []),
            "cash_flow": cache["cash_flow"].get(symbol, []),
            "balance": cache["balance"].get(symbol, []),
            "prices": cache["prices"].get(symbol, []),
        }
        if not has_required_symbol_data(symbol_data):
            continue

        built = 0
        for as_of in as_of_dates:
            try:
                snapshot = build_snapshot(
                    symbol=symbol,
                    symbol_data=symbol_data,
                    benchmark_prices=cache["benchmark_prices"],
                    as_of=as_of,
                    risk_free_rate=args.risk_free_rate,
                    market_return=args.market_return,
                    terminal_growth_rate=args.terminal_growth_rate,
                    tax_rate=args.tax_rate,
                )
                if snapshot:
                    results.append(snapshot)
                    built += 1
            except Exception as error:
                failures.append(
                    {
                        "symbol": symbol,
                        "as_of_date": as_of.isoformat(),
                        "error": str(error),
                    }
                )

        print(f"[{symbol_index}/{len(symbols)}] {symbol}: snapshots={built}")

    results.sort(key=lambda item: (item["as_of_date"], item["symbol"]))
    write_results(results, args.output, fieldnames=SNAPSHOT_COLUMNS)
    write_failures(failures, args.failed_output)
    print(f"Wrote {len(results)} rows to {args.output}")
    print(f"Wrote {len(failures)} failures to {args.failed_output}")


def load_cache(cache_dir):
    return {
        "profiles": load_profiles(cache_dir / "profiles.csv"),
        "income": group_statement_rows(cache_dir / "income_statement_quarterly.csv"),
        "cash_flow": group_statement_rows(cache_dir / "cash_flow_quarterly.csv"),
        "balance": group_statement_rows(cache_dir / "balance_sheet_quarterly.csv"),
        "prices": group_price_rows(cache_dir / "prices_daily.csv"),
        "benchmark_prices": group_price_rows(cache_dir / "benchmark_prices_daily.csv"),
    }


def load_profiles(path):
    profiles = {}
    for row in read_csv(path):
        symbol = clean_symbol(row.get("symbol"))
        if symbol and symbol not in profiles:
            profiles[symbol] = row
    return profiles


def group_statement_rows(path):
    grouped = {}
    for row in read_csv(path):
        symbol = clean_symbol(row.get("symbol"))
        if not symbol:
            continue
        row["_date"] = parse_date(row.get("date"))
        row["_available_date"] = available_date(row)
        grouped.setdefault(symbol, []).append(row)

    for rows in grouped.values():
        rows.sort(key=lambda item: item["_available_date"], reverse=True)

    return grouped


def group_price_rows(path):
    grouped = {}
    for row in read_csv(path):
        symbol = clean_symbol(row.get("symbol"))
        price_date = parse_date(row.get("date"))
        close = number(row.get("close"))
        if not symbol or not price_date or close <= 0:
            continue
        grouped.setdefault(symbol, []).append({"date": price_date, "close": close})

    for rows in grouped.values():
        rows.sort(key=lambda item: item["date"])

    return grouped


def read_csv(path):
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def build_snapshot(
    symbol,
    symbol_data,
    benchmark_prices,
    as_of,
    risk_free_rate,
    market_return,
    terminal_growth_rate,
    tax_rate,
):
    profile = symbol_data["profile"]
    income_rows = available_rows(symbol_data["income"], as_of)
    cash_flow_rows = available_rows(symbol_data["cash_flow"], as_of)
    balance_rows = available_rows(symbol_data["balance"], as_of)
    if not income_rows or not cash_flow_rows or not balance_rows:
        return None

    price = price_on_or_before(symbol_data["prices"], as_of)
    if price <= 0:
        return None

    latest_income = income_rows[0]
    latest_balance = balance_rows[0]
    recent_income = income_rows[:8]
    recent_cash_flow = cash_flow_rows[:8]
    ttm_income = sum_statement_rows(recent_income[:4])
    ttm_cash_flow = sum_statement_rows(recent_cash_flow[:4])

    shares_outstanding = first_number(
        latest_income,
        ["weightedAverageShsOutDil", "weightedAverageShsOut"],
        fallback=number(profile.get("sharesOutstanding")),
    )
    if shares_outstanding <= 0:
        return None

    short_term_debt = number(latest_balance.get("shortTermDebt"))
    long_term_debt = first_number(
        latest_balance,
        ["longTermDebt", "longTermDebtAndCapitalLeaseObligation"],
    )
    total_debt = first_number(
        latest_balance,
        ["totalDebt"],
        fallback=short_term_debt + long_term_debt,
    )
    cash = first_number(
        latest_balance,
        ["cashAndShortTermInvestments", "cashAndCashEquivalents"],
    )
    shareholders_equity = first_number(
        latest_balance,
        ["totalStockholdersEquity", "totalEquity", "totalShareholderEquity"],
    )
    free_cash_flow = number(ttm_cash_flow.get("freeCashFlow"))
    revenue_growth = ttm_growth(recent_income, "revenue")
    fcf_growth = ttm_growth(recent_cash_flow, "freeCashFlow")
    eps_growth = ttm_growth(recent_income, "epsDiluted", fallback_key="eps")
    growth_estimate = estimate_growth_rate(
        revenue_growth=revenue_growth,
        fcf_growth=fcf_growth,
        eps_growth=eps_growth,
    )
    market_cap = price * shares_outstanding
    roic = estimate_roic(ttm_income, total_debt, shareholders_equity, cash)
    debt_to_equity = total_debt / shareholders_equity if shareholders_equity > 0 else 0.0
    beta = calculate_beta(symbol_data["prices"], benchmark_prices.get("SPY", []), as_of)
    momentum = calculate_momentum(symbol_data["prices"], as_of)

    raw_snapshot = {
        "symbol": symbol,
        "company_name": str(profile.get("companyName") or ""),
        "sector": str(profile.get("sector") or ""),
        "industry": str(profile.get("industry") or ""),
        "exchange": str(profile.get("exchange") or ""),
        "is_etf": parse_bool(profile.get("isEtf")),
        "is_fund": parse_bool(profile.get("isFund")),
        "is_adr": parse_bool(profile.get("isAdr")),
        "is_actively_trading": parse_bool(profile.get("isActivelyTrading"), default=True),
        "price": price,
        "market_cap": market_cap,
        "beta": beta,
        "free_cash_flow": free_cash_flow,
        "cash": cash,
        "total_debt": total_debt,
        "short_term_debt": short_term_debt,
        "long_term_debt": long_term_debt,
        "interest_expense": abs(number(ttm_income.get("interestExpense"))),
        "shares_outstanding": shares_outstanding,
        "revenue_growth": revenue_growth,
        "fcf_growth": fcf_growth,
        "eps_growth": eps_growth,
        "growth_estimate": growth_estimate,
        "momentum_3m": momentum["momentum_3m"],
        "momentum_6m": momentum["momentum_6m"],
        "momentum_12m": momentum["momentum_12m"],
        "roic": roic,
        "debt_to_equity": debt_to_equity,
    }
    valuation = value_stock(
        raw_snapshot,
        risk_free_rate=risk_free_rate,
        market_return=market_return,
        terminal_growth_rate=terminal_growth_rate,
        tax_rate=tax_rate,
    )
    result = apply_quality_value_strategy(valuation)

    return {
        **result,
        "as_of_date": as_of.isoformat(),
        "fiscal_date": latest_income.get("date", ""),
        "filing_date": latest_income.get("filingDate", ""),
        "accepted_date": latest_income.get("acceptedDate", ""),
    }


def has_required_symbol_data(symbol_data):
    return (
        bool(symbol_data["income"])
        and bool(symbol_data["cash_flow"])
        and bool(symbol_data["balance"])
        and bool(symbol_data["prices"])
    )


def available_rows(rows, as_of):
    return [row for row in rows if row["_available_date"] <= as_of]


def available_date(row):
    return (
        parse_date(row.get("acceptedDate"))
        or parse_date(row.get("filingDate"))
        or parse_date(row.get("date"))
        or date.min
    )


def sum_statement_rows(rows):
    total = {}
    for row in rows:
        for key, value in row.items():
            if key.startswith("_") or key in {"symbol", "date", "period"}:
                continue
            try:
                total[key] = total.get(key, 0.0) + number(value)
            except (TypeError, ValueError):
                continue
    return total


def ttm_growth(rows, key, fallback_key=None):
    if len(rows) < 8:
        return 0.05

    latest = sum(number(row.get(key)) for row in rows[:4])
    previous = sum(number(row.get(key)) for row in rows[4:8])

    if latest == 0 and fallback_key:
        latest = sum(number(row.get(fallback_key)) for row in rows[:4])
        previous = sum(number(row.get(fallback_key)) for row in rows[4:8])

    if previous <= 0 or latest <= 0:
        return 0.05

    return latest / previous - 1


def price_on_or_before(prices, as_of):
    index = price_index_on_or_before(prices, as_of)
    if index < 0:
        return 0.0
    return prices[index]["close"]


def price_index_on_or_before(prices, as_of):
    dates = [row["date"] for row in prices]
    return bisect_right(dates, as_of) - 1


def calculate_momentum(prices, as_of):
    index = price_index_on_or_before(prices, as_of)
    latest = prices[index]["close"] if index >= 0 else 0.0

    return {
        "momentum_3m": trailing_return(prices, index, latest, 63),
        "momentum_6m": trailing_return(prices, index, latest, 126),
        "momentum_12m": trailing_return(prices, index, latest, 252),
    }


def trailing_return(prices, index, latest, lookback):
    previous_index = index - lookback
    if latest <= 0 or previous_index < 0:
        return 0.0
    previous = prices[previous_index]["close"]
    if previous <= 0:
        return 0.0
    return latest / previous - 1


def calculate_beta(stock_prices, benchmark_prices, as_of, lookback=252):
    stock_returns = daily_returns(stock_prices, as_of, lookback)
    benchmark_returns = daily_returns(benchmark_prices, as_of, lookback)
    common_dates = sorted(set(stock_returns) & set(benchmark_returns))
    if len(common_dates) < 60:
        return 1.0

    stock_values = [stock_returns[item] for item in common_dates]
    benchmark_values = [benchmark_returns[item] for item in common_dates]
    benchmark_mean = sum(benchmark_values) / len(benchmark_values)
    stock_mean = sum(stock_values) / len(stock_values)
    variance = sum((item - benchmark_mean) ** 2 for item in benchmark_values)
    if variance == 0:
        return 1.0

    covariance = sum(
        (stock - stock_mean) * (benchmark - benchmark_mean)
        for stock, benchmark in zip(stock_values, benchmark_values)
    )
    return covariance / variance


def daily_returns(prices, as_of, lookback):
    index = price_index_on_or_before(prices, as_of)
    if index <= 0:
        return {}

    start = max(1, index - lookback + 1)
    returns = {}
    for item_index in range(start, index + 1):
        previous = prices[item_index - 1]["close"]
        current = prices[item_index]["close"]
        if previous > 0 and current > 0:
            returns[prices[item_index]["date"]] = current / previous - 1
    return returns


def quarter_rebalance_dates(start_date, end_date, delay_days):
    quarter_ends = []
    current = add_months(date(start_date.year, start_date.month, 1), -3)
    current = date(current.year, ((current.month - 1) // 3 + 1) * 3, 1)
    current = end_of_month(current)

    while current <= end_date:
        as_of = current + timedelta(days=delay_days)
        if as_of >= start_date and as_of <= end_date:
            quarter_ends.append(as_of)
        current = add_months(current, 3)
        current = end_of_month(current)

    return quarter_ends


def infer_end_date(price_cache):
    latest_dates = [
        rows[-1]["date"]
        for rows in price_cache.values()
        if rows
    ]
    return max(latest_dates) if latest_dates else date.today()


def add_months(value, months):
    month = value.month - 1 + months
    year = value.year + month // 12
    month = month % 12 + 1
    return date(year, month, 1)


def end_of_month(value):
    next_month = add_months(date(value.year, value.month, 1), 1)
    return next_month - timedelta(days=1)


def parse_date(value):
    if not value:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    raw = raw.split(" ")[0]
    return datetime.strptime(raw, "%Y-%m-%d").date()


def parse_bool(value, default=False):
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def clean_symbol(value):
    return str(value or "").strip().upper()


def write_failures(failures, output_path):
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["symbol", "as_of_date", "error"])
        writer.writeheader()
        writer.writerows(failures)


if __name__ == "__main__":
    main()
