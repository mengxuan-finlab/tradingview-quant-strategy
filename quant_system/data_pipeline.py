from quant_system.models import calculate_cagr, first_number, number


MIN_GROWTH_ESTIMATE = -0.10
MAX_GROWTH_ESTIMATE = 0.30


def fetch_fundamental_snapshot(client, symbol):
    clean_symbol = symbol.strip().upper()

    quote = client.first("quote", {"symbol": clean_symbol})
    profile = client.first("profile", {"symbol": clean_symbol})
    cash_flows = client.get(
        "cash-flow-statement",
        {"symbol": clean_symbol, "period": "annual", "limit": 5},
    )
    balance_sheet = client.first(
        "balance-sheet-statement",
        {"symbol": clean_symbol, "period": "annual", "limit": 1},
    )
    income_statements = client.get(
        "income-statement",
        {"symbol": clean_symbol, "period": "annual", "limit": 5},
    )
    income_statement = income_statements[0] if income_statements else {}
    ratios = client.first(
        "ratios",
        {"symbol": clean_symbol, "period": "annual", "limit": 1},
    )
    price_history = client.get(
        "historical-price-eod/full",
        {"symbol": clean_symbol},
    )

    latest_cash_flow = cash_flows[0] if cash_flows else {}
    short_term_debt = number(balance_sheet.get("shortTermDebt"))
    long_term_debt = first_number(
        balance_sheet,
        ["longTermDebt", "longTermDebtAndCapitalLeaseObligation"],
    )
    total_debt = first_number(
        balance_sheet,
        ["totalDebt"],
        fallback=short_term_debt + long_term_debt,
    )
    cash = first_number(
        balance_sheet,
        ["cashAndShortTermInvestments", "cashAndCashEquivalents"],
    )
    shareholders_equity = first_number(
        balance_sheet,
        ["totalStockholdersEquity", "totalEquity", "totalShareholderEquity"],
    )
    roic = first_number(
        ratios,
        ["returnOnCapitalEmployed", "returnOnInvestedCapital", "roic"],
        fallback=estimate_roic(income_statement, total_debt, shareholders_equity, cash),
    )
    debt_to_equity = first_number(
        ratios,
        ["debtToEquityRatio", "debtEquityRatio", "debtToEquity"],
        fallback=(total_debt / shareholders_equity if shareholders_equity > 0 else 0.0),
    )
    fcf_growth = calculate_cagr(
        [number(item.get("freeCashFlow")) for item in cash_flows]
    )
    revenue_growth = calculate_cagr(
        [number(item.get("revenue")) for item in income_statements]
    )
    eps_growth = calculate_cagr(
        [first_number(item, ["epsdiluted", "epsDiluted", "eps"]) for item in income_statements]
    )
    growth_estimate = estimate_growth_rate(
        revenue_growth=revenue_growth,
        fcf_growth=fcf_growth,
        eps_growth=eps_growth,
    )
    momentum = calculate_momentum(price_history)

    return {
        "symbol": clean_symbol,
        "company_name": str(profile.get("companyName") or ""),
        "sector": str(profile.get("sector") or ""),
        "industry": str(profile.get("industry") or ""),
        "exchange": str(profile.get("exchange") or ""),
        "is_etf": bool(profile.get("isEtf")),
        "is_fund": bool(profile.get("isFund")),
        "is_adr": bool(profile.get("isAdr")),
        "is_actively_trading": bool(profile.get("isActivelyTrading", True)),
        "price": first_number(quote, ["price"], fallback=number(profile.get("price"))),
        "market_cap": first_number(
            quote,
            ["marketCap"],
            fallback=number(profile.get("marketCap")) or number(profile.get("mktCap")),
        ),
        "beta": number(profile.get("beta")),
        "free_cash_flow": number(latest_cash_flow.get("freeCashFlow")),
        "cash": cash,
        "total_debt": total_debt,
        "short_term_debt": short_term_debt,
        "long_term_debt": long_term_debt,
        "interest_expense": abs(number(income_statement.get("interestExpense"))),
        "shares_outstanding": first_number(
            income_statement,
            ["weightedAverageShsOutDil", "weightedAverageShsOut"],
            fallback=number(profile.get("sharesOutstanding")),
        ),
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


def estimate_growth_rate(revenue_growth, fcf_growth, eps_growth, analyst_growth=None):
    factors = [
        (revenue_growth, 0.40),
        (fcf_growth, 0.30),
        (eps_growth, 0.20),
        (analyst_growth, 0.10),
    ]
    weighted_sum = 0.0
    used_weight = 0.0

    for value, weight in factors:
        if value is None:
            continue
        weighted_sum += value * weight
        used_weight += weight

    if used_weight == 0:
        return 0.05

    return clamp(weighted_sum / used_weight, MIN_GROWTH_ESTIMATE, MAX_GROWTH_ESTIMATE)


def calculate_momentum(price_history):
    closes = [number(row.get("close")) for row in price_history if number(row.get("close")) > 0]
    latest_close = closes[0] if closes else 0.0

    return {
        "momentum_3m": price_return(latest_close, closes, 63),
        "momentum_6m": price_return(latest_close, closes, 126),
        "momentum_12m": price_return(latest_close, closes, 252),
    }


def price_return(latest_close, closes, index):
    if latest_close <= 0 or len(closes) <= index or closes[index] <= 0:
        return 0.0

    return latest_close / closes[index] - 1


def estimate_roic(income_statement, total_debt, shareholders_equity, cash):
    operating_income = number(income_statement.get("operatingIncome"))
    income_before_tax = number(income_statement.get("incomeBeforeTax"))
    income_tax_expense = abs(number(income_statement.get("incomeTaxExpense")))
    invested_capital = total_debt + shareholders_equity - cash

    if operating_income <= 0 or invested_capital <= 0:
        return 0.0

    tax_rate = 0.21
    if income_before_tax > 0 and income_tax_expense > 0:
        tax_rate = min(max(income_tax_expense / income_before_tax, 0.0), 0.35)

    nopat = operating_income * (1 - tax_rate)
    return nopat / invested_capital


def clamp(value, low, high):
    return max(low, min(high, value))
