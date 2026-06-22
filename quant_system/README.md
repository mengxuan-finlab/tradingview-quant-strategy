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

Run a small universe:

```powershell
python -m quant_system.run_universe --symbols AAPL,MSFT,NVDA
```

Output:

```text
quant_system/output/valuation_results.csv
```
