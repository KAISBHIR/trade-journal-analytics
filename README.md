# Trade Journal Analytics

A web app that turns a raw trade-history export (CSV) into an interactive analytics dashboard — win rate, net P/L, per-strategy performance, and an editable trade table, without touching a spreadsheet.

Upload a broker trade-history CSV, tag trades with up to 4 custom strategy labels (auto-detected from trade comments or assigned manually), and get a live dashboard: win/loss breakdown, profit evolution over time, cumulative P/L per strategy, and profit distribution by strategy — all filterable and editable in place.

## Why this exists

Most traders track performance in a spreadsheet that gets stale after a few dozen trades. This automates the whole loop: upload → auto-tag → visualize → edit inline, so the dashboard stays a live source of truth instead of a one-time report.

## Architecture

- **FastAPI** backend handles the upload flow (3-step wizard: upload CSV → name strategies → view dashboard) with an in-memory, thread-safe `JournalStore`
- **Dash** (mounted as WSGI middleware inside the FastAPI app) powers the actual interactive dashboard — filters, KPI cards, Plotly charts, and an editable data table that writes back to the shared store
- Strategy auto-detection matches numbered tags in trade comments (e.g. `"[2] breakout entry"`) against user-defined strategy names

```
CSV upload ──► services/analyzer.py    parses & validates required columns
                     │                  (Ticket, Symbol, OpenTime, CloseTime, Profit, ...)
                     ▼
              core/journal_logic.py    computes duration, win/loss result,
                     │                  auto-tags strategy from comment
                     ▼
              core/state.py            thread-safe in-memory store shared
                     │                  between FastAPI routes and Dash callbacks
                     ▼
              dash_app/dash_dashboard.py   live filterable dashboard:
                                            KPIs, win/loss donut, profit-over-time,
                                            per-strategy equity curves, boxplot,
                                            editable trade table
```

## Usage

```
pip install -r requirements.txt
uvicorn trade_journal_app.main:app --reload
```

Open `http://localhost:8000`, upload a CSV with columns `Ticket, Symbol, Type, OpenPrice, ClosePrice, OpenTime, CloseTime, Profit` (standard MT4/MT5 trade-history export format), name your strategies, then open the dashboard.

## Stack

Python, FastAPI, Dash / Plotly, Dash Bootstrap Components, pandas, Flask (WSGI mount target for Dash)
