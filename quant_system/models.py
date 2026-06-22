def number(value):
    if value in (None, ""):
        return 0.0

    return float(value)


def first_number(data, keys, fallback=0.0):
    for key in keys:
        value = number(data.get(key))
        if value != 0:
            return value

    return fallback


def calculate_cagr(values, default=0.05):
    positive_values = [value for value in values if value > 0]
    if len(positive_values) < 2:
        return default

    latest = positive_values[0]
    oldest = positive_values[-1]
    years = len(positive_values) - 1

    if oldest <= 0:
        return default

    return (latest / oldest) ** (1 / years) - 1


def calculate_wacc(
    risk_free_rate,
    beta,
    market_return,
    equity_value,
    short_term_debt,
    long_term_debt,
    interest_expense,
    tax_rate=0.21,
):
    debt = short_term_debt + long_term_debt
    total_capital = equity_value + debt

    if total_capital <= 0:
        raise ValueError("total capital must be greater than 0")

    cost_of_equity = risk_free_rate + beta * (market_return - risk_free_rate)
    cost_of_debt = interest_expense / debt if debt > 0 else 0

    return (
        (equity_value / total_capital) * cost_of_equity
        + (debt / total_capital) * cost_of_debt * (1 - tax_rate)
    )


def calculate_dcf_per_share(
    free_cash_flow,
    discount_rate,
    growth_rate,
    terminal_growth_rate,
    cash,
    debt,
    shares_outstanding,
):
    if discount_rate <= terminal_growth_rate:
        raise ValueError("discount rate must be greater than terminal growth rate")
    if shares_outstanding <= 0:
        raise ValueError("shares outstanding must be greater than 0")

    projected_fcfs = []
    current_fcf = free_cash_flow

    for _ in range(5):
        current_fcf *= 1 + growth_rate
        projected_fcfs.append(current_fcf)

    terminal_value = (
        projected_fcfs[-1] * (1 + terminal_growth_rate)
    ) / (discount_rate - terminal_growth_rate)

    enterprise_value = sum(
        projected_fcf / ((1 + discount_rate) ** year)
        for year, projected_fcf in enumerate(projected_fcfs, start=1)
    )
    enterprise_value += terminal_value / ((1 + discount_rate) ** 5)

    equity_value = enterprise_value + cash - debt
    return equity_value / shares_outstanding


def score_stock(upside, roic=0.0, debt_to_equity=0.0, fcf_growth=0.0):
    valuation_score = clamp((upside + 0.5) / 1.0)
    quality_score = clamp(roic / 0.25)
    growth_score = clamp(fcf_growth / 0.20)
    safety_score = clamp(1 - debt_to_equity / 2.0)

    return (
        valuation_score * 0.40
        + quality_score * 0.25
        + growth_score * 0.20
        + safety_score * 0.15
    )


def clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))
