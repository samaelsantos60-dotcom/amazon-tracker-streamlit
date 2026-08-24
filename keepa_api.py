"""Cliente Keepa para Amazon.es, com dados simulados sem uma API key."""

from datetime import date
import os
import random
from typing import Any

import requests


KEEPA_ENDPOINT = "https://api.keepa.com/product"
AMAZON_ES_DOMAIN = 9


def _simulated_product(asin: str) -> dict[str, Any]:
    """Gera métricas determinísticas o suficiente para testes locais."""
    seed = sum(ord(character) for character in asin)
    generator = random.Random(seed + date.today().toordinal())
    return {
        "asin": asin,
        "title": f"Produto Amazon de teste ({asin})",
        "date": date.today().isoformat(),
        "bsr": generator.randint(100, 150_000),
        "price": round(generator.uniform(9.99, 249.99), 2),
        "sellers": generator.randint(1, 12),
        "rating": round(generator.uniform(3.5, 5.0), 1),
        "review_count": generator.randint(10, 25_000),
    }


def _value(product: dict[str, Any], stats: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if product.get(key) is not None:
            return product[key]
        if stats.get(key) is not None:
            return stats[key]
    return None


def _parse_product(product: dict[str, Any]) -> dict[str, Any]:
    """Normaliza os campos mais comuns devolvidos pelo Keepa.

    O Keepa pode devolver valores atuais diretamente ou dentro de ``stats``.
    """
    stats = product.get("stats") or {}
    current = stats.get("current") or {}

    # Algumas respostas usam um dicionário amigável; preserva também esse formato.
    if isinstance(current, dict):
        current_stats = current
    elif isinstance(current, list):
        # Na resposta compacta da Keepa: NEW=1, SALES RANK=3 e
        # quantidade de ofertas NEW=11. Valores negativos significam n/d.
        current_stats = {
            "newPrice": current[1] if len(current) > 1 else None,
            "bsr": current[3] if len(current) > 3 else None,
            "sellers": current[11] if len(current) > 11 else None,
        }
    else:
        current_stats = {}

    price = _value(product, current_stats, "price", "buyBoxPrice", "newPrice")
    if isinstance(price, (int, float)) and price > 1000:
        price = price / 100

    rating = _value(product, stats, "rating")
    if isinstance(rating, (int, float)) and rating > 5:
        rating = rating / 10

    return {
        "asin": product.get("asin"),
        "title": product.get("title") or "Sem título",
        "date": date.today().isoformat(),
        "bsr": _value(product, stats, "bsr", "salesRank", "bestSellerRank"),
        "price": price,
        "sellers": _value(product, stats, "sellers", "offerCount", "numberOfOffers"),
        "rating": rating,
        "review_count": _value(
            product, stats, "reviewCount", "reviews", "totalReviews"
        ),
    }


def fetch_products(asins: list[str]) -> list[dict[str, Any]]:
    """Consulta produtos na API ou usa fallback simulado quando não há key."""
    api_key = os.getenv("KEEPA_API_KEY")
    if not api_key:
        print("[KEEPA] KEEPA_API_KEY não encontrada; a usar dados simulados.")
        return [_simulated_product(asin) for asin in asins]

    print(f"[KEEPA] A consultar {len(asins)} produto(s) na Amazon.es (domain=9)...")
    response = requests.get(
        KEEPA_ENDPOINT,
        params={
            "key": api_key,
            "domain": AMAZON_ES_DOMAIN,
            "asin": ",".join(asins),
            "stats": 1,
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    products = payload.get("products", [])
    if not products:
        raise RuntimeError(f"Keepa não devolveu produtos: {payload}")
    return [_parse_product(product) for product in products]