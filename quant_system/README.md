# Fundamental Quant System

This folder is the non-UI core for a fundamental quant workflow:

1. Pull fundamental data from FMP.
2. Convert it into a standard snapshot.
3. Run WACC + DCF.
4. Score and rank stocks.
5. Export ranked results to CSV.

Set your API key in PowerShell:

```powershell
$env:FMP_API_KEY="your_api_key"
```

Run a small symbol list:

```powershell
python -m quant_system.run_universe --symbols AAPL,MSFT,NVDA
```

Run a universe file with a safety limit:

```powershell
python -m quant_system.run_universe --universe quant_system/universe/us_large_cap.csv --limit 20
```

Output:

```text
quant_system/output/valuation_results.csv
```

Build historical quarterly snapshots for backtesting:

```powershell
python -m quant_system.quarterly_snapshot_builder --universe quant_system/universe/us_large_cap.csv --start-date 2021-06-28
```

Test with a few symbols first:

```powershell
python -m quant_system.quarterly_snapshot_builder --symbols AAPL,MSFT,ANET,XOM --start-date 2022-01-01 --end-date 2023-12-31 --output quant_system/output/test_historical_quarterly_snapshots.csv --failed-output quant_system/output/test_failed_historical_snapshots.csv
```

Historical snapshot output:

```text
quant_system/output/historical_quarterly_snapshots.csv
```

Run the quarterly backtest:

```powershell
python -m quant_system.backtest
```

Backtest output:

```text
quant_system/output/backtest_summary.csv
quant_system/output/backtest_holdings.csv
quant_system/output/backtest_metrics.csv
```
