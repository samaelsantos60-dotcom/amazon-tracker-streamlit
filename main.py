import os
import re
import sqlite3
import requests
from bs4 import BeautifulSoup

DB_NAME = "amazon_tracker.db"
AFFILIATE_TAG = os.environ.get("AMAZON_ASSOCIATE_TAG", "SEU_TAG_AQUI-21")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8,pt;q=0.7",
}

def send_telegram_card(title, price, asin, url, rank):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("[ERRO] Variáveis do Telegram não configuradas.")
        return

    preco_str = f"{price}€" if price else "Ver no site"

    # Mensagem formatada individual
    text = (
        f"🔥 <b>OFERTA #{rank} DA AMAZON</b> 🔥\n\n"
        f"📦 <b>{title}</b>\n\n"
        f"💰 <b>Preço:</b> {preco_str}\n"
        f"🆔 <b>ASIN:</b> <code>{asin}</code>\n"
    )

    # Botão Inline de Link Direto
    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "🛒 VER OFERTA NA AMAZON", "url": url}
            ]
        ]
    }

    api_url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "reply_markup": reply_markup,
        "disable_web_page_preview": False
    }
    
    requests.post(api_url, json=payload)

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asin TEXT NOT NULL,
            title TEXT,
            price REAL,
            bsr INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def save_product_data(asin, title, price, bsr):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO products (asin, title, price, bsr)
        VALUES (?, ?, ?, ?)
    ''', (asin, title, price, bsr))
    conn.commit()
    conn.close()

def scrape_bestsellers_category(category_url, limit=5):
    try:
        response = requests.get(category_url, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            return []

        soup = BeautifulSoup(response.content, "html.parser")
        products = []
        cards = soup.find_all("div", {"id": re.compile(r"^gridItemRoot")})

        for rank, card in enumerate(cards[:limit], start=1):
            title_elem = card.find("span", {"class": re.compile(r"_cDEbf_title_")}) or card.find("div", {"class": "p13n-sc-css-line-clamp-1"})
            title = title_elem.get_text(strip=True) if title_elem else "Produto Amazon"

            link_elem = card.find("a", {"class": "a-link-normal"})
            href = link_elem["href"] if link_elem else ""
            clean_url = f"https://www.amazon.es{href}" if href.startswith("/") else href

            asin_match = re.search(r"/(?:dp|product-reviews)/([A-Z0-9]{10})", clean_url)
            asin = asin_match.group(1) if asin_match else "N/D"

            affiliate_url = f"https://www.amazon.es/dp/{asin}?tag={AFFILIATE_TAG}" if asin != "N/D" else clean_url

            price = None
            price_elem = card.find("span", {"class": "_cDEbf_price_11U0m"}) or card.find("span", {"class": "a-color-price"})
            if price_elem:
                price_text = price_elem.get_text().replace(",", ".").replace("€", "").strip()
                match = re.search(r"(\d+\.?\d*)", price_text)
                if match:
                    price = float(match.group(1))

            products.append({
                "rank": rank,
                "asin": asin,
                "title": title,
                "price": price,
                "url": affiliate_url
            })

        return products

    except Exception as e:
        print(f"[ERRO] Exceção: {e}")
        return []

def main():
    init_db()
    CATEGORY_URL = "https://www.amazon.es/gp/bestsellers/electronics/"
    
    print("🔍 A recolher produtos para enviar cartões com botão...")
    products = scrape_bestsellers_category(CATEGORY_URL, limit=5)

    for prod in products:
        save_product_data(prod["asin"], prod["title"], prod["price"], prod["rank"])
        send_telegram_card(
            title=prod["title"],
            price=prod["price"],
            asin=prod["asin"],
            url=prod["url"],
            rank=prod["rank"]
        )

    print("✅ Cartões com botões enviados para o Telegram!")

if __name__ == "__main__":
    main()
