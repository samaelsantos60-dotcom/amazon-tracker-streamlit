"""Dashboard Streamlit para o histórico do Amazon Tracker."""

import sqlite3
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


DATABASE_PATH = Path(__file__).with_name("amazon_tracker.db")
ALERT_WINDOW_DAYS = 7


@st.cache_data(ttl=60)
def load_metrics() -> pd.DataFrame:
    """Lê todas as métricas guardadas na base SQLite."""
    if not DATABASE_PATH.exists():
        return pd.DataFrame()

    with sqlite3.connect(DATABASE_PATH) as connection:
        data = pd.read_sql_query(
            """
            SELECT asin, title, metric_date AS data, bsr, price, sellers,
                   rating, review_count
            FROM product_metrics
            ORDER BY metric_date ASC, asin ASC
            """,
            connection,
        )
    if not data.empty:
        data["data"] = pd.to_datetime(data["data"])
    return data


def count_recent_alerts(data: pd.DataFrame) -> int:
    """Conta oportunidades/descidas de preço nos últimos sete dias."""
    if data.empty:
        return 0

    ordered = data.sort_values(["asin", "data"])
    latest_date = ordered["data"].max()
    start_date = latest_date - pd.Timedelta(days=ALERT_WINDOW_DAYS - 1)
    alerts = 0

    for _, product_data in ordered.groupby("asin"):
        previous = None
        for _, current in product_data.iterrows():
            if previous is not None and current["data"] >= start_date:
                bsr_alert = (
                    pd.notna(previous["bsr"])
                    and pd.notna(current["bsr"])
                    and previous["bsr"] > 0
                    and (previous["bsr"] - current["bsr"]) / previous["bsr"] > 0.20
                )
                price_alert = (
                    pd.notna(previous["price"])
                    and pd.notna(current["price"])
                    and previous["price"] > 0
                    and (previous["price"] - current["price"]) / previous["price"]
                    > 0.10
                )
                if bsr_alert or price_alert:
                    alerts += 1
            previous = current
    return alerts


def line_chart(
    data: pd.DataFrame,
    column: str,
    title: str,
    y_axis_title: str,
    reverse_y: bool = False,
) -> go.Figure:
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=data["data"],
            y=data[column],
            mode="lines+markers",
            name=column,
            connectgaps=False,
        )
    )
    figure.update_layout(
        title=title,
        xaxis_title="Data",
        yaxis_title=y_axis_title,
        hovermode="x unified",
        margin={"l": 20, "r": 20, "t": 55, "b": 20},
    )
    if reverse_y:
        figure.update_yaxes(autorange="reversed")
    return figure


st.set_page_config(
    page_title="Amazon Tracker",
    page_icon="📦",
    layout="wide",
)
st.title("📦 Amazon Tracker — Amazon.es")
st.caption("Acompanhamento diário de preços, BSR e oportunidades")

metrics = load_metrics()
if metrics.empty:
    st.warning(
        f"A base de dados `{DATABASE_PATH.name}` ainda não tem métricas. "
        "Execute `python main.py` para fazer a primeira recolha."
    )
    st.stop()

total_asins = metrics["asin"].nunique()
recent_alerts = count_recent_alerts(metrics)
col1, col2 = st.columns(2)
col1.metric("Total de ASINs monitorizados", total_asins)
col2.metric(f"Alertas disparados recentemente ({ALERT_WINDOW_DAYS} dias)", recent_alerts)

latest = (
    metrics.sort_values("data")
    .groupby("asin", as_index=False)
    .tail(1)
    .sort_values("asin")
    .rename(
        columns={
            "asin": "ASIN",
            "title": "Título",
            "bsr": "Último BSR",
            "price": "Último Preço (€)",
            "sellers": "Número de Vendedores",
        }
    )
)
st.subheader("Dados mais recentes por produto")
st.dataframe(
    latest[["ASIN", "Título", "Último BSR", "Último Preço (€)", "Número de Vendedores"]],
    use_container_width=True,
    hide_index=True,
)

st.subheader("Evolução por produto")
selected_asin = st.selectbox(
    "Selecione um produto (ASIN)",
    options=sorted(metrics["asin"].unique()),
)
selected_data = metrics[metrics["asin"] == selected_asin].sort_values("data")
product_title = selected_data["title"].iloc[-1]
st.caption(f"Produto: {product_title}")
st.plotly_chart(
    line_chart(
        selected_data,
        "bsr",
        "Evolução do BSR (ranking #1 no topo)",
        "BSR — quanto menor, melhor",
        reverse_y=True,
    ),
    use_container_width=True,
)
st.plotly_chart(
    line_chart(
        selected_data,
        "price",
        "Evolução do Preço",
        "Preço (€)",
    ),
    use_container_width=True,
)

csv_data = metrics.to_csv(index=False).encode("utf-8-sig")
st.download_button(
    label="⬇️ Exportar todos os dados em CSV",
    data=csv_data,
    file_name="amazon_tracker_metrics.csv",
    mime="text/csv",
)