# Quant System File Guide

這份文件用來快速分辨 `quant_system` 裡的 `.py` 和 `.csv` 各自是做什麼的。

## 日常最重要的 3 步

```powershell
python -m quant_system.run_universe --universe quant_system/universe/us_large_cap.csv
python -m quant_system.paper_trading
copy quant_system/output/paper_top15.csv quant_system/output/paper_runs/YYYY-MM-DD_top15.csv
```

這三步分別是：

```text
更新最新估值
產生最新 Top15
保存今天 Top15 快照
```

平常先記這三步就好。

## 日常會用的程式檔

```text
run_universe.py
```

更新完整 universe 的估值結果。會重新抓 FMP、重算 DCF、策略分數，輸出最新 `valuation_results.csv`。

```text
paper_trading.py
```

從最新 `valuation_results.csv` 產生 Top15 paper trading 名單，輸出 `paper_top15.csv`。

```text
portfolio.py
```

投資組合規則。包含 Top15/20、quality_growth/value sleeve、sector/industry 限制。

```text
strategy.py
```

第一層選股規則。包含 FCF、ROIC、debt、WACC、sector 排除、strategy_score 等條件。

## 研究與回測用程式檔

```text
backtest.py
backtest_audit.py
parameter_sweep.py
walk_forward.py
parameter_stability.py
audit_portfolio.py
```

用途：

```text
backtest.py               跑季度回測
backtest_audit.py         拆解回測結果
parameter_sweep.py        測不同參數組合
walk_forward.py           檢查參數是否過度擬合
parameter_stability.py    看哪些參數比較穩
audit_portfolio.py        檢查 portfolio 資料品質
```

這些是研究工具，不是每天都要跑。

## 歷史資料建立用程式檔

```text
historical_cache_builder.py
benchmark_cache_builder.py
quarterly_snapshot_builder.py
test_historical_fmp.py
```

用途：

```text
historical_cache_builder.py      建立歷史財報與價格 cache
benchmark_cache_builder.py       建立 SPY / QQQ benchmark 價格
quarterly_snapshot_builder.py    建立 point-in-time quarterly snapshots
test_historical_fmp.py           測試 FMP 歷史資料端點
```

## 底層模組

```text
fmp_client.py
data_pipeline.py
valuation_engine.py
models.py
config.py
```

用途：

```text
fmp_client.py          FMP API client
data_pipeline.py       整理 FMP 原始資料
valuation_engine.py    WACC / DCF / fair value / upside
models.py              資料模型
config.py              設定與常數
```

## 最新輸出：會被覆蓋

這些在 `quant_system/output/`，每次重跑可能會覆蓋。

```text
valuation_results.csv
```

最新完整 universe 估值結果。

```text
failed_symbols.csv
```

最新失敗股票。

```text
paper_top15.csv
```

最新 Top15 paper trading 名單。這是你準備研究或建倉時最常看的檔案。

```text
portfolio_results.csv
```

目前預設 portfolio 規則產生的組合結果。

```text
portfolio_quality_report.csv
```

目前 portfolio 的資料品質檢查結果。

## Paper Trading 快照

```text
output/paper_runs/YYYY-MM-DD_top15.csv
```

保存某一天的 Top15 名單，不會因為下一次跑 `paper_trading.py` 被覆蓋。

例子：

```text
output/paper_runs/2026-07-01_top15.csv
```

用途：

```text
回頭查當天準備買什麼
記錄實盤或 paper trading 的建倉依據
比較不同月份名單變化
```

## 完整估值備份

```text
output/runs/YYYY-MM-DD_full/
```

保存某一天完整 universe 跑完後的結果，通常包含：

```text
valuation_results.csv
portfolio_results.csv
portfolio_quality_report.csv
failed_symbols.csv
```

用途：

```text
保存完整研究快照
避免最新 valuation_results.csv 覆蓋舊資料
比較不同日期估值變化
```

## 回測輸出

```text
backtest_summary.csv
backtest_holdings.csv
backtest_metrics.csv
backtest_top15_*.csv
backtest_20s2_*.csv
```

用途：

```text
backtest_summary.csv       每季報酬摘要
backtest_holdings.csv      每季持股與單檔報酬
backtest_metrics.csv       整段回測總績效
backtest_top15_*.csv       Top15 策略回測
backtest_20s2_*.csv        20 檔 sector2 候選策略回測
```

## 回測 Audit 輸出

```text
backtest_audit_by_symbol.csv
backtest_audit_by_sector.csv
backtest_audit_by_industry.csv
backtest_audit_by_sleeve.csv
backtest_audit_by_period.csv
backtest_audit_extremes.csv
```

用途：

```text
看誰賺錢
看誰虧錢
看哪個 sector 有效
看 value / quality_growth 哪個有效
看哪些季度輸大盤
```

Top15 的 audit 在：

```text
output/top15_audit/
```

20s2 的 audit 在：

```text
output/audit_20s2/
```

## 參數研究輸出

```text
parameter_sweep_results.csv
walk_forward_results.csv
parameter_stability_report.csv
```

用途：

```text
parameter_sweep_results.csv       全部參數組合排名
walk_forward_results.csv          Walk-forward 驗證
parameter_stability_report.csv    參數穩定性報表
```

## 歷史資料 Cache

這些在 `quant_system/cache/historical/`，通常很大，不需要每天打開。

```text
income_statement_quarterly.csv
cash_flow_quarterly.csv
balance_sheet_quarterly.csv
prices_daily.csv
benchmark_prices_daily.csv
completed_historical.csv
failed_historical.csv
```

用途：

```text
支援 historical snapshots
支援 backtest
避免每次重新打 API
```

## 日常心智模型

你可以把整個系統想成：

```text
run_universe.py
    -> valuation_results.csv

paper_trading.py
    -> paper_top15.csv
    -> paper_runs/YYYY-MM-DD_top15.csv

backtest.py / parameter_sweep.py / walk_forward.py
    -> 研究用，不是每天跑
```

最重要的日常檔案：

```text
quant_system/output/paper_top15.csv
```

最重要的日常指令：

```powershell
python -m quant_system.run_universe --universe quant_system/universe/us_large_cap.csv
python -m quant_system.paper_trading
```
