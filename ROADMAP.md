# Terminal expansion map

This is a personal research terminal, not Bloomberg software or a feature-equivalent replacement. The plan expands useful workflows without fabricating coverage or proprietary data.

| Workflow | Current / next implementation | External dependency |
|---|---|---|
| Security lookup, charts, watchlists | Working; command navigation and indicators next | Keyless best-effort equity website data; authorized feed optional |
| Multi-asset relative value | Aligned price returns, drawdown, descriptive volatility and correlations | Provider history and clear session semantics |
| Macro / rates | Treasury curve and CPI with public sources | Government feed availability |
| Company analysis | Provider overview; add SEC filings and statement metrics | SEC rate/contact requirements; authorized fundamentals provider |
| News and research | Four RSS publishers, evidence citations, keyword relevance, saved research notes | Full-document retrieval/licensed broad news later |
| Portfolio / risk | Paper execution, weighted average cost, realized/unrealized P/L and CSV export | No brokerage connection; no tax-lot or corporate-action engine yet |
| Alerts | Persistent threshold rules evaluated during active refresh | Background scheduling must be explicitly configured later |
| Workspaces | Per-workspace panel visibility and defaults, browser persistence | Local browser storage |
| Fixed income | Treasury curve, bond price/yield scenarios next | Corporate/municipal bond reference data often licensed |
| Derivatives | Transparent local option calculator next | Executable chains, Greeks, surfaces need entitled data |
| Screening | Sort/filter covered universe; widen symbol catalog with validation | Provider rate limits and symbol coverage |
| Calendars | Official macro release links; structured events later | Reliable calendar feeds/licensed earnings coverage |
| Trading / messaging | Paper execution only | Broker integration, compliance and licensed/private networks are separate projects |

Changes are tested incrementally. Missing, stale, indicative and unsupported feeds remain labeled. Forecasting and causal claims must not be inferred from descriptive analytics.
