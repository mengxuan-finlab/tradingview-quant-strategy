import argparse
import csv
from collections import defaultdict
from pathlib import Path


DEFAULT_SWEEP = "quant_system/output/parameter_sweep_results.csv"
DEFAULT_WALK_FORWARD = "quant_system/output/walk_forward_results.csv"
DEFAULT_OUTPUT = "quant_system/output/parameter_stability_report.csv"


PARAMETERS = [
    ("portfolio_size", "portfolio_size"),
    ("quality_growth_sleeve_size", "quality_growth_sleeve_size"),
    ("value_sleeve_size", "value_sleeve_size"),
    ("max_sector_count", "max_sector_count"),
    ("max_industry_count", "max_industry_count"),
    ("transaction_cost_bps", "transaction_cost_bps"),
]


OUTPUT_COLUMNS = [
    "parameter",
    "value",
    "top10_count",
    "top20_count",
    "top50_count",
    "walk_forward_count",
    "avg_sweep_rank",
    "avg_sweep_cumulative_return",
    "avg_sweep_sharpe",
    "avg_walk_forward_test_return",
    "avg_walk_forward_test_sharpe",
]


def main():
    parser = argparse.ArgumentParser(
        description="Summarize parameter stability from sweep and walk-forward results."
    )
    parser.add_argument("--sweep", default=DEFAULT_SWEEP)
    parser.add_argument("--walk-forward", default=DEFAULT_WALK_FORWARD)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    sweep_rows = read_rows(Path(args.sweep))
    walk_rows = read_rows(Path(args.walk_forward))
    report_rows = build_report(sweep_rows, walk_rows)
    write_rows(Path(args.output), report_rows)

    print(f"Wrote {len(report_rows)} rows to {args.output}")
    print_top_takeaways(report_rows)


def read_rows(path):
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def build_report(sweep_rows, walk_rows):
    keys = set()
    sweep_groups = defaultdict(list)
    walk_groups = defaultdict(list)

    for row in sweep_rows:
        for label, column in PARAMETERS:
            key = (label, normalize_value(row.get(column)))
            keys.add(key)
            sweep_groups[key].append(row)

    for row in walk_rows:
        for label, column in PARAMETERS:
            key = (label, normalize_value(row.get(column)))
            keys.add(key)
            walk_groups[key].append(row)

    report = []
    for parameter, value in sorted(keys, key=sort_key):
        sweep_items = sweep_groups[(parameter, value)]
        walk_items = walk_groups[(parameter, value)]
        report.append(
            {
                "parameter": parameter,
                "value": value,
                "top10_count": count_top_rank(sweep_items, 10),
                "top20_count": count_top_rank(sweep_items, 20),
                "top50_count": count_top_rank(sweep_items, 50),
                "walk_forward_count": len(walk_items),
                "avg_sweep_rank": average_float(sweep_items, "rank"),
                "avg_sweep_cumulative_return": average_float(
                    sweep_items, "cumulative_return"
                ),
                "avg_sweep_sharpe": average_float(sweep_items, "sharpe"),
                "avg_walk_forward_test_return": average_float(
                    walk_items, "test_cumulative_return"
                ),
                "avg_walk_forward_test_sharpe": average_float(
                    walk_items, "test_sharpe"
                ),
            }
        )

    report.sort(
        key=lambda row: (
            row["parameter"],
            -int(row["walk_forward_count"]),
            -int(row["top20_count"]),
            parse_float(row["avg_sweep_rank"]) if row["avg_sweep_rank"] != "" else 999999,
        )
    )
    return report


def count_top_rank(rows, limit):
    return sum(1 for row in rows if parse_float(row.get("rank")) <= limit)


def average_float(rows, column):
    values = [parse_float(row.get(column)) for row in rows if row.get(column) not in (None, "")]
    if not values:
        return ""
    return sum(values) / len(values)


def normalize_value(value):
    number = parse_float(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:g}"


def parse_float(value):
    if value in (None, ""):
        return 0.0
    return float(value)


def sort_key(item):
    parameter, value = item
    try:
        numeric_value = float(value)
    except ValueError:
        numeric_value = 0.0
    return parameter, numeric_value


def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(format_row(row))


def format_row(row):
    formatted = dict(row)
    for column in [
        "avg_sweep_rank",
        "avg_sweep_cumulative_return",
        "avg_sweep_sharpe",
        "avg_walk_forward_test_return",
        "avg_walk_forward_test_sharpe",
    ]:
        value = formatted.get(column)
        formatted[column] = "" if value == "" else value
    return formatted


def print_top_takeaways(rows):
    print("Most stable values by parameter:")
    for parameter in [label for label, _ in PARAMETERS]:
        items = [row for row in rows if row["parameter"] == parameter]
        if not items:
            continue
        best = max(
            items,
            key=lambda row: (
                int(row["walk_forward_count"]),
                int(row["top20_count"]),
                int(row["top10_count"]),
                parse_float(row["avg_sweep_sharpe"]),
            ),
        )
        print(
            f"{parameter}={best['value']}: "
            f"walk_forward={best['walk_forward_count']}, "
            f"top20={best['top20_count']}, "
            f"avg_sweep_sharpe={format_number(best['avg_sweep_sharpe'])}"
        )


def format_number(value):
    if value == "":
        return ""
    return f"{value:.2f}"


if __name__ == "__main__":
    main()
