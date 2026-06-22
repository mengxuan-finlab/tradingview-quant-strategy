from quant_system.models import calculate_cagr, first_number, number


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
    income_statement = client.first(
        "income-statement",
        {"symbol": clean_symbol, "period": "annual", "limit": 1},
    )
    ratios = client.first(
        "ratios",
        {"symbol": clean_symbol, "period": "annual", "limit": 1},
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

    return {
        "symbol": clean_symbol,
        "price": first_number(quote, ["price"], fallback=number(profile.get("price"))),
        "market_cap": first_number(
            quote,
            ["marketCap"],
            fallback=number(profile.get("marketCap")) or number(profile.get("mktCap")),
        ),
        "beta": number(profile.get("beta")),
        "free_cash_flow": number(latest_cash_flow.get("freeCashFlow")),
        "cash": first_number(
            balance_sheet,
            ["cashAndShortTermInvestments", "cashAndCashEquivalents"],
        ),
        "total_debt": total_debt,
        "short_term_debt": short_term_debt,
        "long_term_debt": long_term_debt,
        "interest_expense": abs(number(income_statement.get("interestExpense"))),
        "shares_outstanding": first_number(
            income_statement,
            ["weightedAverageShsOutDil", "weightedAverageShsOut"],
            fallback=number(profile.get("sharesOutstanding")),
        ),
        "fcf_growth": calculate_cagr(
            [number(item.get("freeCashFlow")) for item in cash_flows]
        ),
        "roic": number(ratios.get("returnOnCapitalEmployed")),
        "debt_to_equity": number(ratios.get("debtEquityRatio")),
    }
