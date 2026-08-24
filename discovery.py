"""Descoberta automática de produtos Keepa para Amazon.es."""

import json
import os
from typing import Any

import requests

from database import DEFAULT_DATABASE, add_monitored_products
from keepa_api import fetch_products


PRODUCT_FINDER_ENDPOINT = "https://api.keepa.com/productfinder"
DOMAIN = 9
DEFAULT_CATEGORY_ID = 1055398
MIN_PRICE_EUR = 15
MAX_PRICE_EUR = 50
MAX_BSR = 20_000


def discover_products() -> list[dict[str, Any]]:
    """Procura produtos de uma categoria e aplica os filtros comerciais."""
    api_key = os.getenv("KEEPA_API_KEY")
    if not api_key:
        print("[DISCOVERY] Sem KEEPA_API_KEY; descoberta automática ignorada.")
        return []

    category_id = int(os.getenv("KEEPA_CATEGORY_ID", DEFAULT_CATEGORY_ID))
    selection = {
        "rootCategory": category_id,
        "current_SALES": {"min": 1, "max": MAX_BSR},
        "current_PRICE": {
            "min": MIN_PRICE_EUR * 100,
            "max": MAX_PRICE_EUR * 100,
        },
    }
    print(
        f"[DISCOVERY] A procurar produtos na categoria {category_id} "
        f"(Amazon.es, domain={DOMAIN})..."
    )
    response = requests.get(
        PRODUCT_FINDER_ENDPOINT,
        params={
            "key": api_key,
            "domain": DOMAIN,
            "selection": json.dumps(selection),
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    asins = payload.get("asinList", [])
    if not asins:
        print("[DISCOVERY] Nenhum ASIN devolvido pelo Product Finder.")
        return []

    print(f"[DISCOVERY] Product Finder devolveu {len(asins)} ASIN(s).")
    products = fetch_products(asins)
    filtered = [
        product
        for product in products
        if isinstance(product.get("bsr"), (int, float))
        and product["bsr"] < MAX_BSR
        and isinstance(product.get("price"), (int, float))
        and MIN_PRICE_EUR <= product["price"] <= MAX_PRICE_EUR
    ]
    print(
        f"[DISCOVERY] {len(filtered)} produto(s) passaram os filtros "
        f"(BSR < {MAX_BSR}, preço {MIN_PRICE_EUR}€–{MAX_PRICE_EUR}€)."
    )
    return filtered


def run_discovery(db_path: str = str(DEFAULT_DATABASE)) -> int:
    """Executa a descoberta e guarda novos ASINs na tabela de monitorização."""
    products = discover_products()
    added = add_monitored_products(products, db_path)
    print(f"[DISCOVERY] {added} novo(s) ASIN(s) adicionado(s) à monitorização.")
    return added