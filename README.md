# 量化系統

這裡放的是非 UI 的量化核心，不是 Streamlit 原型。

流程：

1. 從 FMP 抓財報與股價資料。
2. 整理成標準基本面資料。
3. 計算 WACC + DCF。
4. 計算 upside 和 score。
5. 輸出排序後的 CSV。

在 PowerShell 設定 API key：

```powershell
$env:FMP_API_KEY="your_api_key"
```

進入這個資料夾：

```powershell
cd C:\Users\user\OneDrive\Desktop\量化
```

跑一組股票：

```powershell
python -m quant_system.run_universe --symbols AAPL,MSFT,NVDA
```

輸出結果：

```text
quant_system/output/valuation_results.csv
```
