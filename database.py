"""Persistência SQLite das métricas diárias dos produtos."""

import sqlite3
from pathlib import Path
from typing import Any, Iterable, Mapping


DEFAULT_DATABASE = Path(__file__).with_name("amazon_tracker.db")


def init_db(db_path: str | Path = DEFAULT_DATABASE) -> None:
    """Cria a tabela de métricas caso ainda não exista."""
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS product_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asin TEXT NOT NULL,
                title TEXT NOT NULL,
                metric_date TEXT NOT NULL,
                bsr INTEGER,
                price REAL,
                sellers INTEGER,
                rating REAL,
                review_count INTEGER,
                UNIQUE (asin, metric_date)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS monitored_products (
                asin TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.commit()


def save_metrics(
    metrics: Iterable[Mapping[str, object]],
    db_path: str | Path = DEFAULT_DATABASE,
) -> int:
    """Guarda uma recolha; repetir o mesmo ASIN no mesmo dia atualiza o registo."""
    rows = [
        (
            metric["asin"],
            metric.get("title", "Sem título"),
            metric["date"],
            metric.get("bsr"),
            metric.get("price"),
            metric.get("sellers"),
            metric.get("rating"),
            metric.get("review_count"),
        )
        for metric in metrics
    ]

    with sqlite3.connect(db_path) as connection:
        connection.executemany(
            """
            INSERT INTO product_metrics
                (asin, title, metric_date, bsr, price, sellers, rating, review_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(asin, metric_date) DO UPDATE SET
                title = excluded.title,
                bsr = excluded.bsr,
                price = excluded.price,
                sellers = excluded.sellers,
                rating = excluded.rating,
                review_count = excluded.review_count
            """,
            rows,
        )
        connection.commit()
    return len(rows)


def get_metrics_for_date(
    metric_date: str,
    db_path: str | Path = DEFAULT_DATABASE,
) -> dict[str, dict[str, Any]]:
    """Obtém a última métrica de cada ASIN para uma data ISO (AAAA-MM-DD)."""
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT asin, title, metric_date AS date, bsr, price, sellers,
                   rating, review_count
            FROM product_metrics
            WHERE metric_date = ?
            """,
            (metric_date,),
        ).fetchall()
    return {row["asin"]: dict(row) for row in rows}


def get_previous_metric(
    asin: str,
    before_date: str,
    db_path: str | Path = DEFAULT_DATABASE,
) -> dict[str, Any] | None:
    """Obtém o registo mais recente desse ASIN antes da data indicada."""
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """
            SELECT asin, title, metric_date AS date, bsr, price, sellers,
                   rating, review_count
            FROM product_metrics
            WHERE asin = ? AND metric_date < ?
            ORDER BY metric_date DESC
            LIMIT 1
            """,
            (asin, before_date),
        ).fetchone()
    return dict(row) if row else None


def add_monitored_products(
    products: Iterable[Mapping[str, object]],
    db_path: str | Path = DEFAULT_DATABASE,
) -> int:
    """Adiciona ASINs descobertos sem duplicar os já monitorizados."""
    rows = [
        (product["asin"], product.get("title", "Sem título"))
        for product in products
        if product.get("asin")
    ]
    with sqlite3.connect(db_path) as connection:
        cursor = connection.executemany(
            """
            INSERT OR IGNORE INTO monitored_products (asin, title)
            VALUES (?, ?)
            """,
            rows,
        )
        connection.commit()
        return cursor.rowcount


def get_monitored_asins(
    db_path: str | Path = DEFAULT_DATABASE,
) -> list[str]:
    """Devolve a lista persistente de ASINs, ordenada de forma estável."""
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            "SELECT asin FROM monitored_products ORDER BY asin"
        ).fetchall()
    return [row[0] for row in rows]