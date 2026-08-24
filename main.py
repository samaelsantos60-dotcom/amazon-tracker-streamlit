import os
import re
import sqlite3
import requests
from bs4 import BeautifulSoup
from alerts import send_alert

DB_NAME = "amazon_tracker.db"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8,pt;q=0.7",
}

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
    """Faz o scraping da página de Mais Vendidos de uma categoria."""
    try:
        response = requests.get(category_url, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            print(f"[ERRO] Status {response.status_code} ao aceder à categoria.")
            return []

        soup = BeautifulSoup(response.content, "html.parser")
        products = []
        
        # Encontra os cartões de produtos da lista de mais vendidos
        cards = soup.find_all("div", {"id": re.compile(r"^gridItemRoot")})

        for rank, card in enumerate(cards[:limit], start=1):
            # Extração do Título e Link
            title_elem = card.find("span", {"class": re.compile(r"_cDEbf_title_")}) or card.find("div", {"class": "p13n-sc-css-line-clamp-1"})
            title = title_elem.get_text(strip=True) if title_elem else "Produto sem título"

            link_elem = card.find("a", {"class": "a-link-normal"})
            href = link_elem["href"] if link_elem else ""
            url = f"https://www.amazon.es{href}" if href.startswith("/") else href

            # Extração do ASIN através do link
            asin_match = re.search(r"/(?:dp|product-reviews)/([A-Z0-9]{10})", url)
            asin = asin_match.group(1) if asin_match else "N/D"

            # Extração do Preço
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
        print(f"[ERRO] Exceção no scraping da categoria: {e}")
        return []

def main():
    init_db()

    # URL da categoria de Mais Vendidos da Amazon ES (Exemplo: Eletrónica / Tecnologia)
    # Podes alterar a URL para qualquer outra categoria da Amazon ES!
    CATEGORY_URL = "https://www.amazon.es/gp/bestsellers/electronics/"
    
    print("🔍 A recolher a lista dos mais vendidos...")
    top_products = scrape_bestsellers_category(CATEGORY_URL, limit=5)

    if not top_products:
        print("⚠️ Nenhum produto encontrado.")
        return

    # Guarda na base de dados
    for prod in top_products:
        save_product_data(prod["asin"], prod["title"], prod["price"], prod["rank"])

    # Monta o relatório para o Telegram
    msg = "🔥 <b>TOP MAIS VENDEDOS DA AMAZON</b>\n"
    msg += "━━━━━━━━━━━━━━━━━━━\n\n"

    for item in top_products:
        preco_str = f"{item['price']}€" if item['price'] else "Indisponível"
        msg += f"<b>#{item['rank']} <a href='{item['url']}'>{item['title']}</a></b>\n"
        msg += f"💰 <b>Preço:</b> {preco_str}\n"
        msg += f"🆔 <b>ASIN:</b> <code>{item['asin']}</code>\n\n"

    msg += "━━━━━━━━━━━━━━━━━━━\n"
    msg += "⚡ <i>Lista extraída diretamente da categoria de Mais Vendidos.</i>"

    send_alert(msg)

if __name__ == "__main__":
    main()
