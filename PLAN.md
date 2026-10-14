# Implementation plan

1. Preserve project references; create an isolated local `terminal/` application. No synced source files modified.
2. Build a React + TypeScript terminal: searchable multi-asset universe, chart, watchlist, news, fundamentals, research, cross-asset signals, workspace settings, paper trading.
3. Add FastAPI with SQLite cache and persistent paper ledger. Ship deterministic demo mode and explicit opt-in provider adapters with provenance.
4. Validate backend accounting, adapter failure behavior, research citations, frontend production build, and local preview.
5. Document setup, provider contracts, limitations and follow-on milestones.

Research availability: project sources directory is empty; prior conversation returns content references rather than the completed research. The original X post could not be fetched (403). This implementation uses the user's feature brief, not a claimed reconstruction of unavailable research.

## v0.2 public-data upgrade — completed 2026-10-14

- Removed runtime synthetic quote/history/fundamental data and fabricated ticker sparklines.
- Connected public Coinbase Exchange crypto and Frankfurter/ECB FX data; completed-candle history.
- Connected key-dependent Alpha Vantage equity/company data and FRED macro data; explicit unavailable states until configured.
- Added Fed/SEC live RSS, source publication timestamps, direct article citations and per-feed failure labels.
- Research citations now refer to the exact retrieved evidence returned with each response; optional model receives those records and falls back when citation IDs are invalid.
- Preserved prior ledger records; new paper fills retain provider provenance and reject missing/stale quotes.
- Verified eight deterministic tests, production build, real network smoke checks and browser citation workflow.

Remaining external setup: authorized Alpha Vantage/FRED credentials and optional AI key. No credentials were invented or embedded. Broader market/company news and full-article retrieval remain future work.

## v0.3 keyless coverage — completed 2026-10-14

- Yahoo public website chart endpoint supplies all six equity/ETF quotes and history without a key, explicitly best-effort and delayed/indicative. It is not described as a supported licensed API. Optional Alpha Vantage override remains.
- Official Treasury XML and BLS v1 supply keyless macro observations/history. Treasury par yield is labeled as an alternative to the legacy DGS10 display ID; CPI uses BLS CUSR0000SA0, skipping missing months and annual averages.
- CNBC and BBC publisher RSS broaden market/business news. Ten entries per source preserve coverage balance; UI publisher filter added.
- Live smoke test returned provider observations for all 12 instruments and 40 cited headlines across four publishers. Twelve tests and frontend production build pass; equity chart and news filter verified in browser.
- Company fundamentals remain key-dependent. Gemini is unnecessary for data retrieval and was not called.
