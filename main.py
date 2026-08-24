import os
import re
import sqlite3
import requests
from bs4 import BeautifulSoup

DB_NAME = "amazon_tracker.db"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8,pt;q=0.7",
}

def send_alert(message):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("[ERRO] TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID não definidos.")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    requests.post(url, json=payload)

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

def scrape_bestsellers_category(category_url, limit=10):
    try:
        response = requests.get(category_url, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            print(f"[ERRO] Status {response.status_code} ao aceder à categoria.")
            return []

        soup = BeautifulSoup(response.content, "html.parser")
        products = []
        cards = soup.find_all("div", {"id": re.compile(r"^gridItemRoot")})

        for rank, card in enumerate(cards[:limit], start=1):
            title_elem = card.find("span", {"class": re.compile(r"_cDEbf_title_")}) or card.find("div", {"class": "p13n-sc-css-line-clamp-1"})
            title = title_elem.get_text(strip=True) if title_elem else "Produto sem título"

            link_elem = card.find("a", {"class": "a-link-normal"})
            href = link_elem["href"] if link_elem else ""
            url = f"https://www.amazon.es{href}" if href.startswith("/") else href

            asin_match = re.search(r"/(?:dp|product-reviews)/([A-Z0-9]{10})", url)
            asin = asin_match.group(1) if asin_match else "N/D"

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
                "title": title[:45] + "..." if len(title) > 45 else title,
                "price": price,
                "url": url
            })

        return products

    except Exception as e:
        print(f"[ERRO] Exceção no scraping: {e}")
        return []

def main():
    init_db()

    CATEGORY_URL = "https://www.amazon.es/gp/bestsellers/electronics/"
    print("🔍 A recolher o Top 10...")
    top_products = scrape_bestsellers_category(CATEGORY_URL, limit=10)

    if not top_products:
        print("⚠️ Nenhum produto encontrado.")
        return

    for prod in top_products:
        save_product_data(prod["asin"], prod["title"], prod["price"], prod["rank"])

    msg = "🔥 <b>TOP 10 MAIS VENDIDOS DA AMAZON</b>\n"
    msg += "━━━━━━━━━━━━━━━━━━━\n\n"

    for item in top_products:
        preco_str = f"{item['price']}€" if item['price'] else "Indisponível"
        msg += f"<b>#{item['rank']} <a href='{item['url']}'>{item['title']}</a></b>\n"
        msg += f"💰 <b>Preço:</b> {preco_str}\n"
        msg += f"🆔 <b>ASIN:</b> <code>{item['asin']}</code>\n\n"

    msg += "━━━━━━━━━━━━━━━━━━━\n"
    msg += "⚡ <i>Relatório automático enviado via GitHub Actions.</i>"

    send_alert(msg)
    print("✅ Processo concluído com sucesso!")

if __name__ == "__main__":
    main()
