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
