# Reference audit — 2026-10-14

Existing application preserved in the local Git history. Synced sources are untouched. Reference checkouts are ignored, separate from application source.

| Reference | Inspected revision | License and decision |
|---|---|---|
| ErTasselli/OpenTerminal | aed097c680cd8ec1c391ae06966babe7d6d91fc6 | MIT; notice preserved. Inspected actual Workspace, TopBar, Sidebar, global CSS, store, provider registry/cache and dashboard/chart screenshots. Independently integrated the layout pattern and black/amber dense visual language. |
| openbq-org/OpenBB | 7c9d4221bdf66965e3f6c7f4dc6ee848073e5ae2 | Apache-2.0; license preserved. Inspected platform package and provider abstraction. Keep existing FastAPI adapters, incrementally introduce provider contracts; do not install the full SDK just for keyless feeds. Windows checkout has long-path failures; relevant files were read from Git objects. |
| feremabraz/bloomberg-terminal | d53714efca546ed90bf4396383d1459cc962de69 | README says MIT but no LICENSE/COPYING/NOTICE file found at this revision. Workflow/design reference only; source not copied. Its simulated data is not reused. |

## Integration choices

React 19/Vite and FastAPI/SQLite remain intact. OpenTerminal uses Next/Express, but replacing working infrastructure would add risk without improving these features. react-grid-layout 1.5.4 supplies actual drag/resize; Lightweight Charts 5.2.1 supplies genuine OHLC/line/volume and indicator panes. The chart retains TradingView attribution. No Bloomberg assets or brand identity copied.

## Current stage verification

- New chart indicators, date normalization, corrupt layout bounds and qualified command parser: 6 Node tests passed.
- Application backend: 32 pytest tests passed. pytest.ini excludes reference repository tests.
- TypeScript check and production build passed. Separate chart/workspace chunks remove the oversized-bundle warning.
- Biome recommended lint passes for new components/features/services/types/tests. Existing main.tsx and Tools.tsx are not yet migrated to this lint baseline. Validated non-null assertions are permitted in new chart math/integration code.
- Browser inspected at 1440x900 and 1920x1080; no horizontal overflow at 1920. Confirmed real AAPL and BTC charts, RSI/MACD panes, maximize/restore retaining state, close/add widget, qualified AAPL command, actual chart resize, persistence after reload, reset positions. Header drag attempted vertically; automatic compaction returned it to the original row, so arbitrary reordering is not claimed as verified.
- Screenshots saved locally under ignored qa/workstation-1440.jpg and workstation-1920.jpg.

## Remaining work

Keyboard chart navigation; richer autocomplete than native suggestions; verify arbitrary drag reordering; broader global index/commodity/FX coverage; keyless company statements; stronger provider backoff/health contracts. Current WEI opens covered instruments, not a complete world-index dataset. FA opens available metadata with an explicit statement-coverage notice. Calculators use user assumptions, not a live options chain. Full Bloomberg data, chat, broker connectivity and entitlements are outside public-data parity.


## Follow-on data stage

Added backend/transport.py with tests and sanitized status integration; backend/statements.py with annual period/unit/accession validation, six-hour SQLite caching, checked issuer mapping and per-fact filing citations; src/features/statements/Statements.tsx; command FA routing and research evidence integration. Live SEC companyfacts/submissions succeeded for AAPL/MSFT/NVDA/TSLA. Added Statements navigation, keyboard-accessible chart observation inspection and provider-health UI. Updated main.py, feeds.py, status.py, Tools.tsx, commands/tests and README.

Latest checks: 39 backend tests, 6 frontend tests, new-module Biome lint, TypeScript and production build pass. Selected annual US-GAAP facts are supported; complete statements, additional issuers and quarterly/TTM normalization remain future tasks. Provider backoff is now implemented; a typed pluggable provider registry and stale-while-revalidate background scheduler remain future architecture work. Old stage limitations above describe that earlier checkpoint.

Final checkpoint: 40 backend tests including Retry-After/cooldown recovery, and 6 frontend tests. Horizontal widget drag was subsequently verified (market panel moved from right to left and displaced the chart); reset restored the original layout. Browser verified SEC facts in the copilot. Live sanitized health returned Yahoo HTTP 200 with latency and no parameters.
