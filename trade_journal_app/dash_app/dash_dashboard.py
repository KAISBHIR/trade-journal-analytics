from flask import Flask
from starlette.middleware.wsgi import WSGIMiddleware
from dash import Dash, html, dcc, dash_table
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
import re
import json
from datetime import datetime, timedelta

from trade_journal_app.core.state import JournalStore


def init_dashboard(store: JournalStore):
    flask_app = Flask(__name__)

    custom_styles = {
        "dark_theme": {"backgroundColor": "#0E1117", "color": "white"},
        "card_style": {
            "backgroundColor": "#1A1D24",
            "borderRadius": "8px",
            "boxShadow": "0 4px 6px rgba(0,0,0,0.1)",
            "margin": "10px",
            "padding": "12px",
        },
        "header_style": {"color": "#00FFC6", "fontFamily": "Segoe UI, sans-serif", "fontWeight": "600"},
    }

    dash_app = Dash(
        __name__,
        server=flask_app,
        requests_pathname_prefix="/dash/",
        external_stylesheets=[dbc.themes.DARKLY, "https://fonts.googleapis.com/css2?family=Segoe+UI:wght@400;600&display=swap"],
        title="📊 Trade Journal Dashboard",
    )

    dash_app.layout = html.Div(
        [
            dcc.Store(id="table-store", storage_type="memory"),
            # inline dropdown used to fill Unlabeled Strategy values (shown when user clicks Strategy cell)
            dcc.Dropdown(
                id="inline-strategy-dropdown",
                options=[],
                placeholder="Assign strategy...",
                style={"display": "none", "marginTop": 8, "width": "260px", "color": "black", "backgroundColor": "white", "zIndex": 100000},
            ),
            # Header / Filters
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.H2("Trade Performance Analytics", style={"color": "#00FFC6", "marginBottom": "4px"}),
                            html.Div("Actionable trader dashboard — clear & focused", style={"color": "#aaa", "fontSize": 12}),
                        ],
                        md=6,
                    ),
                    dbc.Col(
                        [
                            html.Div([
                                html.Div("Filter mode", style={"color": "#00FFC6", "fontSize": 12, "marginBottom": 6}),
                                dbc.RadioItems(
                                    id="filter-mode",
                                    options=[
                                        {"label": "All (none)", "value": "none"},
                                        {"label": "By Symbol", "value": "symbol"},
                                        {"label": "By Strategy", "value": "strategy"},
                                    ],
                                    value="none",
                                    inline=True,
                                    persistence=True,
                                    style={"color": "white"},
                                ),
                                html.Div(
                                    [
                                        dcc.Dropdown(
                                            id="symbol-filter",
                                            placeholder="Select symbol(s)",
                                            multi=True,
                                            className="light-dropdown",
                                            style={
                                                "display": "none",
                                                "marginTop": 8,
                                                "color": "black",
                                                "backgroundColor": "white",
                                            },
                                            persistence=True,
                                        ),
                                        dcc.Dropdown(
                                            id="strategy-filter",
                                            placeholder="Select strategy(ies)",
                                            multi=True,
                                            className="light-dropdown",
                                            style={
                                                "display": "none",
                                                "marginTop": 8,
                                                "color": "black",
                                                "backgroundColor": "white",
                                            },
                                            persistence=True,
                                        ),
                                    ],
                                    style={"textAlign": "right"},
                                ),
                            ]),
                        ],
                        md=6,
                    ),
                ],
                align="center",
                className="mb-2",
                style={"padding": "6px 12px"},
            ),

            # Second row: grouping + KPI quick filter (date range removed)
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.Label("Group by (for time charts)", style={"color": "#00FFC6", "fontSize": 12}),
                            dcc.RadioItems(
                                id="time-period",
                                options=[
                                    {"label": " Day", "value": "D"},
                                    {"label": " Week", "value": "W"},
                                    {"label": " Month", "value": "M"},
                                ],
                                value="D",
                                inline=True,
                                style={"color": "white"},
                            ),
                        ],
                        md=6,
                    ),
                    dbc.Col(
                        [
                            html.Label("Quick KPI filter", style={"color": "#00FFC6", "fontSize": 12}),
                            dcc.RadioItems(
                                id="kpi-filter",
                                options=[
                                    {"label": "All trades", "value": "all"},
                                    {"label": "Only wins", "value": "wins"},
                                    {"label": "Only losses", "value": "losses"},
                                ],
                                value="all",
                                inline=True,
                                style={"color": "white"},
                            ),
                        ],
                        md=6,
                    ),
                ],
                className="mb-3",
                style={"padding": "0 12px"},
            ),

            # KPI cards row
            dbc.Row(id="kpi-row", className="mb-3", style={"padding": "0 12px"}),
            # Charts grid
            dbc.Row(
                [
                    dbc.Col(
                        [
                            dbc.Card(
                                [
                                    dbc.CardHeader("Win / Loss (donut)"),
                                    dbc.CardBody(dcc.Graph(id="win-loss-fig")),
                                ],
                                style=custom_styles["card_style"],
                            ),
                            dbc.Card(
                                [
                                    dbc.CardHeader(html.Div(id="hourly-card-header", children="Profit evolution (Wins vs Losses)")),
                                    dbc.CardBody(dcc.Graph(id="hourly-fig")),
                                ],
                                style={**custom_styles["card_style"], "marginTop": "8px"},
                            ),
                        ],
                        md=6,
                    ),
                    dbc.Col(
                        [
                            dbc.Card(
                                [
                                    dbc.CardHeader("Strategy P/L Evolution"),
                                    dbc.CardBody(dcc.Graph(id="stacked-equity-fig")),
                                ],
                                style=custom_styles["card_style"],
                            ),
                            dbc.Card(
                                [
                                    dbc.CardHeader("Strategy performance (box / median + spread)"),
                                    dbc.CardBody(dcc.Graph(id="strategy-box-fig")),
                                ],
                                style={**custom_styles["card_style"], "marginTop": "8px"},
                            ),
                        ],
                        md=6,
                    ),
                ],
                className="mb-3",
                style={"padding": "0 12px"},
            ),

            # Bottom: trade table
            dbc.Row(
                [
                    dbc.Col(
                        [
                            dbc.Card(
                                [
                                    dbc.CardHeader("Detailed Trades"),
                                    dbc.CardBody(html.Div(id="trade-table")),
                                ],
                                style=custom_styles["card_style"],
                            )
                        ],
                    )
                ],
                style={"padding": "0 12px"},
            ),

            # hidden div for debug if needed
            html.Div(id="debug", style={"display": "none"}),
        ],
        style={"backgroundColor": "#0E1117", "minHeight": "100vh", "paddingBottom": "40px"},
    )

    # populate filter options & toggle
    def _get_dataframe() -> pd.DataFrame:
        df = store.get_dataframe()
        if df is None:
            return pd.DataFrame()
        return df

    def _persist_dataframe(df: pd.DataFrame) -> None:
        store.set_dataframe(df)

    @dash_app.callback(
        Output("symbol-filter", "style"),
        Output("strategy-filter", "style"),
        Output("symbol-filter", "options"),
        Output("strategy-filter", "options"),
        Input("filter-mode", "value"),
    )
    def update_filters(mode):
        df = _get_dataframe()
        sym_opts = []
        strat_opts = []
        if not df.empty:
            if "Symbol" in df.columns:
                unique_syms = df["Symbol"].dropna().astype(str).unique().tolist()
                sym_opts = [{"label": s, "value": s} for s in sorted(unique_syms)]
            if "Strategy" in df.columns:
                unique_strats = df["Strategy"].dropna().astype(str).unique().tolist()
                strat_opts = [{"label": (f"Strategy {s}" if re.fullmatch(r"\d+", s) else s), "value": s} for s in sorted(unique_strats)]
        if mode == "symbol":
            return {"display": "block", "marginTop": 8}, {"display": "none"}, sym_opts, []
        if mode == "strategy":
            return {"display": "none"}, {"display": "block", "marginTop": 8}, [], strat_opts
        return {"display": "none"}, {"display": "none"}, [], []

    # main update callback: KPIs, figures and table
    @dash_app.callback(
        Output("kpi-row", "children"),
        Output("win-loss-fig", "figure"),
        Output("hourly-fig", "figure"),
        Output("stacked-equity-fig", "figure"),
        Output("strategy-box-fig", "figure"),
        Output("trade-table", "children"),
        Output("hourly-card-header", "children"),
        Output("debug", "children"),                 # <-- added debug output
        Input("filter-mode", "value"),
        Input("symbol-filter", "value"),
        Input("strategy-filter", "value"),
        Input("time-period", "value"),
        Input("kpi-filter", "value"),
        Input("table-store", "data"),
    )
    def update_dashboard(filter_mode, symbol_sel, strategy_sel, period, kpi_filter, store_data):
        # prefer table-store (edits) if present, otherwise fall back to uploaded_df
        base_df = _get_dataframe()
        if store_data and isinstance(store_data, list):
            try:
                df = pd.DataFrame(store_data).copy()
            except Exception:
                df = base_df.copy()
        else:
            df = base_df.copy()

        if df is None or df.empty:
            empty_fig = go.Figure()
            empty_fig.update_layout(paper_bgcolor="#1D1D24", plot_bgcolor="#1D1D24", font={"color": "white"})
            return (
                [],
                empty_fig,
                empty_fig,
                empty_fig,
                empty_fig,
                html.Div("No data uploaded yet.", style={"color": "white"}),
                "Profit evolution (Wins vs Losses)",
                "no-data"
            )

        # ensure time columns exist and typed
        if "CloseTime" in df.columns:
            df["CloseTime"] = pd.to_datetime(df["CloseTime"], errors="coerce")
        if "OpenTime" in df.columns:
            df["OpenTime"] = pd.to_datetime(df["OpenTime"], errors="coerce")

        # ensure Result/Profit/Strategy exist
        if "Profit" not in df.columns:
            df["Profit"] = 0.0
        if "Result" not in df.columns:
            df["Result"] = df["Profit"].apply(lambda p: "Win" if p > 0 else ("Loss" if p < 0 else "Neutral"))
        if "Strategy" not in df.columns:
            df["Strategy"] = "Unlabeled"
        if "Symbol" not in df.columns:
            df["Symbol"] = "Unknown"

        # apply quick KPI filter
        if kpi_filter == "wins":
            df = df[df["Result"] == "Win"]
        elif kpi_filter == "losses":
            df = df[df["Result"] == "Loss"]

        # apply selection filter depending on mode
        if filter_mode == "symbol" and symbol_sel:
            if isinstance(symbol_sel, list):
                df = df[df["Symbol"].isin(symbol_sel)]
            else:
                df = df[df["Symbol"] == symbol_sel]
        if filter_mode == "strategy" and strategy_sel:
            if isinstance(strategy_sel, list):
                df = df[df["Strategy"].isin(strategy_sel)]
            else:
                df = df[df["Strategy"] == strategy_sel]

        # Basic KPIs
        total_trades = len(df)
        wins = int((df["Result"] == "Win").sum()) if total_trades else 0
        losses = int((df["Result"] == "Loss").sum()) if total_trades else 0
        win_rate = (wins / total_trades * 100) if total_trades else 0.0
        net_pl = float(df["Profit"].sum()) if total_trades else 0.0
        avg_trade = float(df["Profit"].mean()) if total_trades else 0.0
        avg_win = float(df.loc[df["Profit"] > 0, "Profit"].mean()) if any(df["Profit"] > 0) else 0.0
        avg_loss = float(df.loc[df["Profit"] < 0, "Profit"].mean()) if any(df["Profit"] < 0) else 0.0

        # KPI cards
        kpis = [
            dbc.Col(dbc.Card(dbc.CardBody([html.Div("Total trades", style={"color": "#888", "fontSize": 12}), html.Div(f"{total_trades}", style={"color": "white", "fontSize": 20, "fontWeight": "700"})])), md=2),
            dbc.Col(dbc.Card(dbc.CardBody([html.Div("Win rate", style={"color": "#888", "fontSize": 12}), html.Div(f"{win_rate:.1f}%", style={"color": "#00FFC6", "fontSize": 20, "fontWeight": "700"})])), md=2),
            dbc.Col(dbc.Card(dbc.CardBody([html.Div("Net P/L", style={"color": "#888", "fontSize": 12}), html.Div(f"${net_pl:,.2f}", style={"color": "#00FFC6" if net_pl >= 0 else "#FF4B4B", "fontSize": 20, "fontWeight": "700"})])), md=2),
            dbc.Col(dbc.Card(dbc.CardBody([html.Div("Avg trade", style={"color": "#888", "fontSize": 12}), html.Div(f"${avg_trade:,.2f}", style={"color": "white", "fontSize": 16, "fontWeight": "600"})])), md=2),
            dbc.Col(dbc.Card(dbc.CardBody([html.Div("Avg win / loss", style={"color": "#888", "fontSize": 12}), html.Div(f"${avg_win:,.0f} / ${avg_loss:,.0f}", style={"color": "white", "fontSize": 14})])), md=4),
        ]

        # Win/Loss donut
        total = wins + losses
        win_pct = (wins / total * 100) if total > 0 else 0
        donut = go.Figure()
        donut.add_trace(go.Pie(labels=["Wins", "Losses"], values=[wins, losses], hole=0.55,
                              marker={"colors": ["#00FF9F", "#FF4B4B"], "line": {"color": "#0E1117", "width": 3}},
                              textinfo="none", hoverinfo="label+value+percent"))
        donut.update_layout(annotations=[{"text": f"<b>{win_pct:.0f}%</b><br><span style='font-size:12px'>Win rate</span>", "x": 0.5, "y": 0.5, "showarrow": False, "font": {"size": 20, "color": "#00FFC6"}}], showlegend=True, paper_bgcolor="#1A1D24", plot_bgcolor="#1D1D24", margin={"t": 10, "b": 10, "l": 10, "r": 10}, height=340)

        # ---------- Context-aware "hourly-fig" (renamed: profit evolution) ----------
        bar_fig = go.Figure()
        hourly_header = "Profit evolution (Wins vs Losses)"
        # choose time column
        time_col = "CloseTime" if "CloseTime" in df.columns else ("OpenTime" if "OpenTime" in df.columns else None)
        if time_col is None:
            bar_fig.update_layout(paper_bgcolor="#1D1D24", plot_bgcolor="#1D1D24", height=300)
        else:
            # grouping params
            if period == "D":
                freq = "D"
                dr_freq = "D"
                period_label = "Day"
            elif period == "W":
                freq = "W-MON"
                dr_freq = "W-MON"
                period_label = "Week"
            else:
                freq = "MS"
                dr_freq = "MS"
                period_label = "Month"

            df["_ts"] = pd.to_datetime(df[time_col], errors="coerce")
            df = df.dropna(subset=["_ts"])
            if df.empty:
                bar_fig.update_layout(paper_bgcolor="#1D1D24", plot_bgcolor="#1D1D24", height=300)
            else:
                start = df["_ts"].min().floor("D")
                end = df["_ts"].max().ceil("D")
                full_idx = pd.date_range(start=start, end=end, freq=dr_freq)

                grouped_ts = df.set_index("_ts").groupby([pd.Grouper(freq=freq), "Result"])["Profit"].sum().unstack(fill_value=0)
                grouped_ts = grouped_ts.reindex(full_idx, fill_value=0)
                for col in ["Win", "Loss"]:
                    if col not in grouped_ts.columns:
                        grouped_ts[col] = 0.0
                grouped_ts["Loss"] = -grouped_ts["Loss"].abs()
                x_vals = grouped_ts.index

                span_days = (end - start).days
                if span_days > 365 * 2:
                    tickfmt = "%Y"
                    nticks = 8
                elif span_days > 120:
                    tickfmt = "%b %Y"
                    nticks = 10
                elif span_days > 60:
                    tickfmt = "%b %d"
                    nticks = 12
                else:
                    tickfmt = "%Y-%m-%d"
                    nticks = 15

                tickangle = -45 if len(x_vals) > 20 else -30

                bar_fig.add_trace(go.Bar(x=x_vals, y=grouped_ts["Win"].values, name="Wins", marker_color="#00FF9F", hovertemplate="%{x|%Y-%m-%d}: <b>%{y:$,.2f}</b><extra></extra>"))
                bar_fig.add_trace(go.Bar(x=x_vals, y=grouped_ts["Loss"].values, name="Losses", marker_color="#FF4B4B", hovertemplate="%{x|%Y-%m-%d}: <b>%{y:$,.2f}</b><extra></extra>"))

                bar_fig.update_layout(
                    barmode="group",
                    xaxis=dict(title=period_label, type="date", tickformat=tickfmt, tickangle=tickangle, tickmode="auto", nticks=nticks, showgrid=False, showspikes=True, spikemode="across", spikesnap="cursor"),
                    yaxis=dict(title="Total Profit ($)", showgrid=True, gridcolor="rgba(255,255,255,0.06)"),
                    plot_bgcolor="#0E1117",
                    paper_bgcolor="#0E1117",
                    font=dict(color="white", family="Segoe UI, Roboto, Sans-Serif"),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
                    hovermode="x unified",
                    height=420,
                    margin={"t": 20, "b": 80, "l": 40, "r": 20},
                    xaxis_rangeslider_visible=True,
                    xaxis_rangeslider=dict(bgcolor="rgba(255,255,255,0.02)"),
                    xaxis_rangeselector=dict(
                        visible=True,
                        bgcolor="#111318",
                        buttons=list([
                            dict(count=1, label="1M", step="month", stepmode="backward"),
                            dict(count=3, label="3M", step="month", stepmode="backward"),
                            dict(count=6, label="6M", step="month", stepmode="backward"),
                            dict(count=1, label="YTD", step="year", stepmode="todate"),
                            dict(count=1, label="1Y", step="year", stepmode="backward"),
                            dict(step="all")
                        ])
                    )
                )

        # ---------- Strategy P/L Evolution (multi-line clearer view) ----------
        stacked_fig = go.Figure()
        if "CloseTime" in df.columns:
            df["Date"] = pd.to_datetime(df["CloseTime"], errors="coerce").dt.floor("D")
            agg = df.groupby(["Date", "Strategy"])["Profit"].sum().unstack(fill_value=0).sort_index()
            if not agg.empty:
                cum = agg.cumsum()
                full_idx = pd.date_range(start=cum.index.min(), end=cum.index.max(), freq="D")
                cum = cum.reindex(full_idx, method="ffill").fillna(0)
                palette = px.colors.qualitative.Set2
                final_pls = cum.iloc[-1].sort_values(ascending=False)
                total_pl = final_pls.sum()
                for i, (strategy, final_pl) in enumerate(final_pls.items()):
                    color = palette[i % len(palette)]
                    stacked_fig.add_trace(go.Scatter(x=cum.index, y=cum[strategy], name=f"{strategy} (${final_pl:,.0f})", mode="lines", line={"width": 2, "color": color}, hovertemplate=(f"<b>{strategy}</b><br>" + "%{x|%Y-%m-%d}<br>" + "P/L: <b>$%{y:,.2f}</b><extra></extra>")))
                total_line = cum.sum(axis=1)
                stacked_fig.add_trace(go.Scatter(x=cum.index, y=total_line, name=f"Total P/L (${total_pl:,.0f})", mode="lines", line={"width": 3, "color": "#00FFC6", "dash": "dot"}, hovertemplate="Total P/L: <b>$%{y:,.2f}</b><extra></extra>"))
                stacked_fig.update_layout(xaxis=dict(title="Date", showgrid=False, showspikes=True, spikemode="across", spikesnap="cursor"), yaxis=dict(title="Cumulative P/L ($)", showgrid=True, gridcolor="rgba(255,255,255,0.06)", zeroline=True, zerolinecolor="rgba(255,255,255,0.2)"), paper_bgcolor="#1A1D24", plot_bgcolor="#1A1D24", font=dict(color="white"), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=10)), hovermode="x unified", height=340, margin={"t": 20, "b": 10, "l": 40, "r": 20})
            else:
                stacked_fig.update_layout(paper_bgcolor="#1D1D24", plot_bgcolor="#1D1D24", height=340)
        else:
            stacked_fig.update_layout(paper_bgcolor="#1D1D24", plot_bgcolor="#1D1E24", height=340)

        # Strategy boxplot
        if "Strategy" in df.columns and not df.empty:
            box_fig = px.box(df, x="Strategy", y="Profit", points="outliers", color="Strategy", color_discrete_sequence=px.colors.qualitative.Dark24)
            box_fig.update_layout(title="Profit distribution by Strategy", paper_bgcolor="#1D1D24", plot_bgcolor="#1D1D24", height=340, showlegend=False)
        else:
            box_fig = go.Figure()
            box_fig.update_layout(paper_bgcolor="#1D1D24", plot_bgcolor="#1D1D24", height=340)

        # Trade table: build display columns but keep numeric Profit for conditional styling (hidden)
        display_cols = ["Ticket", "Symbol", "Type", "Lots", "OpenPrice", "ClosePrice", "Profit", "Commission", "Swap", "Result", "Strategy", "Comment", "OpenTime", "CloseTime", "Duration_Hours"]
        present_cols = [c for c in display_cols if c in df.columns]
        df_table = df[present_cols].copy()

        # create display strings
        if "Profit" in df_table.columns:
            df_table["ProfitStr"] = df_table["Profit"].map(lambda x: f"${x:,.2f}")
        if "Duration_Hours" in df_table.columns:
            df_table["Duration_HoursStr"] = df_table["Duration_Hours"].map(lambda x: (f"{x:.1f}h" if pd.notna(x) else ""))

        # ensure Comment column exists so user can edit/create it
        if "Comment" not in df_table.columns:
            df_table["Comment"] = ""

        # --- build strategy dropdown options from master uploaded_df (keep raw values as strings) ---
        master = _get_dataframe()
        strat_options = []
        if not master.empty and "Strategy" in master.columns:
            raw_vals = master["Strategy"].dropna().astype(str).tolist()
            seen_vals = set()
            for v in raw_vals:
                val = v.strip()
                if val == "" or val in seen_vals:
                    continue
                seen_vals.add(val)
                label = (f"Strategy {val}" if re.fullmatch(r"\d+", val) else val)
                strat_options.append({"label": label, "value": val})
        if not strat_options:
            stored = store.get_strategies()
            named = [name for name in stored.values() if name]
            if named:
                strat_options = [{"label": name, "value": name} for name in named]
            else:
                strat_options = [{"label": f"Strategy {i}", "value": str(i)} for i in range(1, 5)]

        # build DataTable columns mapping (use dropdown presentation for Strategy)
        columns = []
        for c in present_cols:
            if c == "Profit":
                columns.append({"name": "Profit (raw)", "id": "Profit", "hidden": True})
                columns.append({"name": "Profit", "id": "ProfitStr", "editable": False})
            elif c == "Duration_Hours":
                columns.append({"name": "Duration (h)", "id": "Duration_HoursStr", "editable": False})
            elif c == "Strategy":
                columns.append({"name": "Strategy", "id": "Strategy", "editable": True, "presentation": "dropdown"})
            elif c == "Comment":
                columns.append({"name": "Comment", "id": "Comment", "editable": True})
            else:
                columns.append({"name": c, "id": c, "editable": False})

        # coerce Strategy values to string so dropdown values match cell values
        if "Strategy" in df_table.columns:
            df_table["Strategy"] = df_table["Strategy"].fillna("").astype(str)

        table = dash_table.DataTable(
            id="trade-datatable",
            data=df_table.to_dict("records"),
            columns=columns,
            editable=True,
            row_deletable=False,
            page_size=10,
            style_table={"overflowX": "auto"},
            style_header={"backgroundColor": "#1A1D24", "color": "#00FFC6", "fontWeight": "bold"},
            style_cell={"backgroundColor": "#0E1117", "color": "white", "textAlign": "center", "padding": "6px"},
            style_data_conditional=[
                {"if": {"filter_query": "{Profit} > 0"}, "color": "#00FF9F"},
                {"if": {"filter_query": "{Profit} < 0"}, "color": "#FF4B4B"},
            ],
            dropdown={"Strategy": {"options": strat_options}},
        )

        # before returning everything, prepare debug text visible in the hidden debug div
        debug_text = f"strategies_count={len(strat_options)} labels={ [o['label'] for o in strat_options[:20]] }"

        return kpis, donut, bar_fig, stacked_fig, box_fig, table, hourly_header, debug_text

    # persist edits from DataTable -> global_data and table-store
    @dash_app.callback(
        Output("table-store", "data"),
        Input("trade-datatable", "data"),
        prevent_initial_call=True,
    )
    def persist_table_edits(table_rows):
        if table_rows is None:
            raise PreventUpdate
        try:
            edited = pd.DataFrame(table_rows)
        except Exception:
            raise PreventUpdate

        # restore numeric Profit if ProfitStr exists but Profit column missing
        if "ProfitStr" in edited.columns and "Profit" not in edited.columns:
            try:
                edited["Profit"] = edited["ProfitStr"].replace("[\\$,]", "", regex=True).astype(float)
            except Exception:
                edited["Profit"] = np.nan

        # merge edits into the authoritative uploaded_df when possible (match by Ticket)
        current = _get_dataframe()
        if not current.empty and "Ticket" in edited.columns and "Ticket" in current.columns:
            current = current.set_index("Ticket")
            edited = edited.set_index("Ticket")
            # update only columns present in edited
            for col in edited.columns:
                current.loc[edited.index, col] = edited[col]
            try:
                current = current.reset_index()
            except Exception:
                current = current.copy()
            _persist_dataframe(current)
            return current.to_dict("records")
        else:
            # fallback: replace the global dataframe with edited (best-effort)
            try:
                _persist_dataframe(edited.copy())
            except Exception:
                pass
            return edited.to_dict("records")

    return WSGIMiddleware(dash_app.server)

