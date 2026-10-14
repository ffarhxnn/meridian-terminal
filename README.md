# Meridian personal market terminal · v0.6

Local React/TypeScript UI, FastAPI and SQLite. All displayed market observations and history now come from public providers. Missing data stays unavailable; there is no synthetic fallback. The original project `sources/` directory is untouched.

## Start

Requires Node 22+, pnpm and Python 3.11+. From this `terminal` directory:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r backend/requirements.txt
Copy-Item .env.example .env
.venv\Scripts\python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

In a second terminal, same directory:

```powershell
pnpm install
pnpm dev
```

If pnpm requires build approval, run `pnpm approve-builds` and select esbuild. Open http://127.0.0.1:5173. API docs: http://127.0.0.1:8000/docs. Keep both services bound locally: authentication is not implemented.

## Expanded workflows (v0.5)

- **Command search:** Ctrl+K, then `SPY GP` (chart), `AAPL DES` (snapshot), `BTC NEWS` (research), `PORT`, `COMP`, `CURVE`, `ALERT`, `NOTES`, `CALC`, `EQS`, `WS`, or `HELP`. Global lookup searches supported U.S. equity/ETF listings. A real USD quote is validated before adding an instrument to SQLite; 30 additional instruments maximum keeps public traffic bounded. The original seed universe remains intact.
- **Charts:** line/candlestick rendering from actual close/OHLC fields, 1-week through 1-year lookbacks, optional 20-observation simple moving average, hover/keyboard inspection. Sources without OHLC remain line-only. Stock and crypto charts exclude the current session/day. Corporate-action adjustment conventions can differ across providers.
- **Compare:** 2–5 instruments, shared published dates, normalized performance, price return, max drawdown, per-observation log-return volatility and pairwise correlations. No forward fill or annualization; market sessions differ. Macro levels are rejected as investable price returns. Unavailable histories are explicitly excluded and labeled.
- **Rates:** official Treasury par yield curve across up to 12 tenors, source date, 10Y–2Y spread in basis points. This is not an executable bond market or a bootstrapped spot curve.
- **Screener:** current covered universe, asset/name/price/direction filters, sortable results and CSV export. Reported changes retain their source-specific periods; use Compare for aligned returns.
- **Portfolio:** weighted-average cost, realized/unrealized P/L, cash/equity and source-labeled marks, including preserved legacy fills. Export ledger CSV. No commissions, tax lots or corporate actions.
- **Alerts:** persistent at/above or at/below rules, pause/resume and deduplicated condition triggers. Evaluated during active two-minute refresh or manually. Missing/stale quotes do not trigger. Rules do not run after the app closes and do not send external messages.
- **Research/notebook:** instrument/company/question keywords rank retrieved news; optional keyword-only wire filter. Save answers with their exact question and evidence snapshot to SQLite. No full-document retrieval or automatic causal attribution.
- **Workspaces:** create named desks; per-desk panel visibility, selected instrument, filter and chart range persist in the browser. Watchlist is shared across desks. These are browser-local preferences, not cloud sync.
- **Calculators:** European Black–Scholes–Merton option scenarios with per-unit Greeks and expiry payoff, and regular fixed-coupon bond price/duration/convexity under parallel yield shocks. Inputs are explicit user scenarios; no live option chains, contract sizes, American exercise, accrued interest or credit optionality is implied. References are linked in each calculator.

Live checks returned a 12-tenor Treasury curve, a three-asset comparison with 63 common dates, and valid calculator results. Global lookup/add was tested in the browser with TSLA, now part of the local catalog. Tests use isolated temporary databases and do not write paper trades or alerts into the user's ledger.

## Data coverage

| Instruments | Provider | Key required | Meaning |
|---|---|---|---|
| BTC, ETH | Coinbase Exchange public REST | No | Last trade, rolling 24h change; completed UTC daily candles |
| EUR/USD, GBP/USD | Frankfurter v1 / ECB | No | Published daily reference rates, change from previous published day; not intraday FX |
| SPY, QQQ, AAPL, MSFT, NVDA, GLD | Yahoo Finance public website endpoint | No | Delayed/indicative quote and completed daily closes; unsupported/best-effort endpoint |
| DGS10 (legacy display ID) | U.S. Treasury XML | No | 10-year daily par yield: explicitly labeled alternative, not a fetched FRED DGS10 series |
| CPIAUCSL (display ID) | BLS API v1 CUSR0000SA0 | No | Seasonally adjusted CPI-U all-items index, 1982–84=100; date denotes reference month |
| Company financial metrics | Alpha Vantage OVERVIEW | Yes | Provider fiscal metrics; ETFs may have no company overview |
| Market reference snapshot | Yahoo chart metadata | No | Exchange, volume, 52-week range; explicitly not financial statements |
| Market, business, policy / regulatory news | CNBC Top News, BBC News Business, Federal Reserve, SEC RSS | No | Publisher headlines/descriptions, publication dates and direct article links |

Government macro feeds are official documented public interfaces. Equity prices use Yahoo's public website endpoint, which is not an officially supported developer API or a licensed real-time feed. It worked in live checks but has no stability guarantee and can be blocked or changed; 401/403/429 responses are not bypassed. Public accessibility does not establish redistribution rights. Use authorized accounts and follow provider terms. This independent project has no Bloomberg affiliation or proprietary Bloomberg data.

Provider references:

- [Coinbase candles](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles), [ticker](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-ticker), [24h stats](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-stats)
- [Frankfurter v1 documentation](https://frankfurter.dev/v1/)
- [Alpha Vantage documentation](https://www.alphavantage.co/documentation/)
- [Treasury XML documentation](https://home.treasury.gov/treasury-daily-interest-rate-xml-feed), [BLS API v1 documentation](https://www.bls.gov/developers/api_signature.htm)
- [Yahoo Finance equity history](https://finance.yahoo.com/quote/SPY/history/): public website, not an official developer API; the adapter uses `/v8/finance/chart/{symbol}?range=1y&interval=1d`, validates symbol/currency and uses exchange-local calendar dates.
- [CNBC market RSS](https://www.cnbc.com/id/100003114/device/rss/rss.html), [BBC Business RSS](https://feeds.bbci.co.uk/news/business/rss.xml)
- [Federal Reserve RSS directory](https://www.federalreserve.gov/feeds/feeds.htm), [SEC RSS feed](https://www.sec.gov/news/pressreleases.rss)

## Configuration

Copy `.env.example` to `.env` in this directory. Enter credentials locally, never into frontend variables or source files. Restart the backend after changes. Failed requests back off for 60 seconds, so a newly configured feed may take that long to retry.

| Variable | Purpose |
|---|---|
| `ALPHA_VANTAGE_API_KEY` | Optional authorized equity quote/history override, and required for company fundamentals. Without it, quotes/history use keyless Yahoo website data |
| `AI_PROVIDER` | `auto` prefers configured OpenAI then Gemini; `openai`, `gemini`, `off` select explicitly |
| `OPENAI_API_KEY` | Optional synthesis; sends question and retrieved public evidence to OpenAI |
| `GEMINI_API_KEY` | Optional synthesis through Gemini; key sent in a header, never a URL |
| `GEMINI_MODEL` | Defaults to `gemini-2.5-flash-lite`; model availability/free quota depends on your account |
| `OPENAI_MODEL` | Configurable model available to your API account; default `gpt-4.1-mini` |
| `DB_PATH` | SQLite path; default `terminal.sqlite3` relative to working directory |
| `VITE_API_URL` | Frontend origin of backend; default `http://127.0.0.1:8000` |

`FRED_API_KEY`, `DATA_MODE` and `COINGECKO_API_KEY` from v0.1 are no longer used. Existing SQLite records and browser watchlists remain preserved. New cache entries use a separate namespace, so old synthetic observations cannot leak into the public data view.

## Refresh, provenance and failure handling

The UI polls every two minutes. Backend cache TTLs: crypto quotes two minutes, equity/FX quotes 15 minutes, macro quote/history six hours, other history one hour, company financial fundamentals one day, keyless reference metadata 15 minutes, RSS five minutes. Polling is not streaming. Observation timestamps stay separate from retrieval timestamps. Historical candles omit the current open UTC day; FX gaps reflect unpublished days rather than interpolated prices. Ranges cover calendar days ending at the latest available observation.

On upstream failure, previously retrieved observations retain their timestamp and source with a `stale` label. If no real observation exists, prices are null and charts are empty. Failures back off for 60 seconds; concurrent requests for the same resource share one fetch. API quotas can prevent full equity coverage, especially on small plans. A valid key does not guarantee entitlement to every endpoint.

## Live news and research citations

The wire fetches CNBC Top News, BBC News Business, and official Fed/SEC RSS feeds, normalizes publication timestamps, deduplicates article URLs and sorts newest first. Every item links directly to its publisher article and labels provider/stale status. The list keeps the newest ten entries per publisher (up to 40) so one busy feed cannot eliminate all other sources. Filter by publisher in the UI. This includes broader markets and business coverage, not comprehensive real-time commercial news. Publisher headline text is preserved with prominent attribution and original links; third-party articles may be paywalled. Only headlines and publisher RSS descriptions are retrieved; full articles are not fetched or implied.

Research returns a retrieved-evidence digest without an AI key. With a key, the model receives the selected quote and five news entries, is instructed to cite supplied evidence IDs, and must return only known citation IDs. An empty response, missing citations or unknown IDs falls back to the deterministic digest. The UI stores the response's own source list, so later wire refreshes cannot change what a citation refers to. Citation-ID validation does not independently prove every AI claim is entailed; verify the source. News is ranked by instrument aliases, company-name and question keywords. This is keyword relevance, not semantic verification or comprehensive company coverage.

## Paper portfolio

The $100,000 paper ledger supports buys/sells with transactional cash and holding validation, no shorting. New fills use a currently available provider observation, and persist its source/time alongside the fill. Stale/unavailable quotes are rejected. Prices can still be daily/delayed and are not executable bid/ask prices. Older v0.1 trades are preserved and explicitly labeled legacy synthetic fills. No real brokerage orders exist.

Equity totals show incomplete marks if any holding lacks a price. No fees, dividends, realized P/L reporting or cross-currency accounting. FX quantities are base-currency units valued in USD. Macro series are not tradable.

## Verification

```powershell
python -m pytest backend -q
pnpm build
```

The deterministic test suite cover missing observations, trading validation/source persistence, citation mapping, feed URL safety/HTML stripping, deduplication, stale cache, completed crypto candles, unavailable history, Treasury namespaces, BLS missing months/annual averages, equity exchange dates and BBC domain validation. Live smoke checks on 2026-10-14 retrieved BTC/ETH quotes, both FX rates, 100 BTC daily closes, 73 FX observations, 16 actual RSS entries and a cited research digest. The v0.3 live checks additionally returned equity quotes/history, Treasury and CPI observations and CNBC/BBC entries without keys. Authorized Alpha Vantage fundamentals and AI synthesis remain unverified without keys.

## Next milestones

1. Add a supported, entitled equity provider if stronger uptime guarantees are needed; the keyless website adapter remains best-effort. Company financial statements still need an authorized provider; keyless market-reference metadata is available.
2. Add a licensed company-specific market-news provider and full-document retrieval with passage-level citations.
3. Add aligned cross-asset returns/correlations with explicit mixed-frequency handling; current pulse is a directional comparison only.
4. Add draggable workspace layouts, export/import, richer accounting and authentication before hosting.
5. Import the original Deep Research report when accessible; it was absent from the mirrored project and readable prior chat.

## Source investigation notes (2026-10-14)

Stooq keyless CSV returned 404 and its page required browser verification; no bypass was attempted. Nasdaq public quote requests responded once but subsequent quote/history requests timed out, so it was not added as a dependency. Treasury XML and BLS v1 worked with no keys. BLS v1 has restrictive daily quotas: macro results cache for six hours and missing/unpublished values are skipped. Avoid frequent backend restarts with an empty database. CPI uses the published reference month and can be revised. Treasury par yield is explicitly not presented as identical to FRED DGS10.

No Gemini key is necessary for quotes or RSS. An optional Gemini synthesis adapter is now available; no live Gemini requests were made without credentials. The deterministic cited digest works without any AI account. Google documents free-tier availability and that free-tier prompts may be used to improve its products; account terms/quotas apply. No billing settings are changed. See [Gemini generation API](https://ai.google.dev/api/generate-content) and [pricing/data-use terms](https://ai.google.dev/gemini-api/docs/pricing).

The current source tree has 30 automated tests covering data parsing/provenance, portfolio cost basis, date alignment, calculator identities/finite differences, alerts, notebooks, global catalog validation and model citation contracts. Gemini is tested with a mock transport; live credentialed AI remains unverified. See `ROADMAP.md` for the capability expansion map and external dependencies.


## Dense workstation stage

The main workspace now uses a black/amber terminal theme, seven resizable widgets, per-workspace saved positions, close/restore, lock/reset and maximize controls. Chart choices: genuine Candles/OHLC when supplied, Line/Area otherwise; volume, SMA20/50, EMA20, Bollinger, Wilder RSI and MACD. No artificial candles or volumes. Mouse crosshair, pan/zoom and FIT are supported. Preferences persist locally.

Use `AAPL US EQUITY GP`, `BTC NEWS`, `DES`, `FA` after a covered symbol; `TOP`, `ECO`, `WEI`, `FX`, `CRYPTO`, `PORT`, `SCR`, `MOV`, `HELP`. Native suggestions and the last 30 commands are stored in this browser; Up/Down recalls history, Ctrl+K focuses input, Escape clears it. WEI covers the current universe only; FA exposes available metadata and explicitly identifies missing statements. Unknown instruments use the existing global lookup.

Checks: `pnpm test` (Node 22.18+ or 24 for built-in TypeScript stripping), `pnpm lint` (new module baseline), `pnpm build`, `python -m pytest -q` (application tests only). Latest stage: 6 frontend and 32 backend tests passed. See REFERENCE_AUDIT.md for inspected revisions, browser checks and known gaps; THIRD_PARTY_NOTICES.md for attribution.


## SEC annual financial facts and provider health

`AAPL FA` or `AAPL US EQUITY FA` opens selected annual SEC US-GAAP facts. Also supported: MSFT, NVDA, TSLA (TSLA must be added through lookup when absent). The Statements sidebar opens the selected instrument. Every figure includes its unit, start/end dates, filing date, tag and direct filing index link. Financial research questions can retrieve up to six of these facts as separately cited evidence. SEC data requires no API key: https://www.sec.gov/search-filings/edgar-application-programming-interfaces . Issuer identity is checked against SEC submissions. Standard tags only; missing values are not estimated. Later filings can restate prior annual values. This is not a complete income/balance/cash-flow statement or TTM dataset.

Requests to SEC hosts are spaced to at most five starts per second per process. Facts are cached for six hours. Public-feed requests have at most four concurrent requests per host, exponential cooldown after failure, 15-minute cooldown after 401/403 and bounded Retry-After handling for 429/503. No immediate retry or access bypass. Coverage shows host, HTTP status, latency, failures and cooldown; it never returns URLs, parameters or keys. Health is process-local and resets at server restart; SQLite observations persist. Chart observation arrows are focusable buttons: Enter inspects the previous/next reported bar in the legend.

Latest validation: 39 backend tests and 6 frontend tests pass; new-module lint, TypeScript and production build pass. Live SEC checks succeeded for all four mapped issuers (Nvidia has 9/10 supported standard metrics). One test-client dependency deprecation warning remains. Backend tests use isolated SQLite and mocked upstreams; live probes are separate from automated assertions.

Provider cooldown recovery test added: latest backend count is 40. Browser also confirmed horizontal widget reordering and reset, plus financial evidence citations in the copilot.
