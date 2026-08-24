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

def scrape_amazon_product(asin):
    url = f"https://www.amazon.es/dp/{asin}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.content, "html.parser")

        # Título
        title_element = soup.find("span", {"id": "productTitle"})
        title = title_element.get_text(strip=True) if title_element else "Sem Título"

        # Preço
        price = None
        price_element = soup.find("span", {"class": "a-offscreen"})
        if price_element:
            price_text = price_element.get_text().replace(",", ".").replace("€", "").strip()
            match = re.search(r"(\d+\.?\d*)", price_text)
            if match:
                price = float(match.group(1))

        # Best Sellers Rank (BSR)
        bsr = 999999
        text_content = soup.get_text()
        bsr_match = re.search(r"Nº\s*([\d\.]+)\s*en", text_content, re.IGNORECASE)
        if bsr_match:
            bsr = int(bsr_match.group(1).replace(".", ""))

        return {
            "asin": asin,
            "title": title[:40] + "..." if len(title) > 40 else title,
            "price": price,
            "bsr": bsr,
            "url": url
        }
    except Exception as e:
        print(f"Erro no ASIN {asin}: {e}")
        return None

def main():
    init_db()

    # Adiciona os ASINs que queres monitorizar
    asins = [
        "B08N5WRWNW", 
        "B09B234C3S", 
        "B07PFFMP9P"  
    ]

    results = []
    print("🔍 A extrair dados dos produtos...")

    for asin in asins:
        data = scrape_amazon_product(asin)
        if data:
            save_product_data(data["asin"], data["title"], data["price"], data["bsr"])
            results.append(data)

    if not results:
        print("Nenhum dado recolhido.")
        return

    # Ordena os produtos do MAIS VENDIDO (menor BSR) para o menos vendido
    results.sort(key=lambda x: x["bsr"])

    # MONTAGEM DO RELATÓRIO
    msg = "📊 <b>RELATÓRIO DE MONITORIZAÇÃO AMAZON</b>\n"
    msg += "━━━━━━━━━━━━━━━━━━━\n\n"
    msg += "🔥 <b>PRODUTOS MAIS VENDIDOS / PROCURADOS:</b>\n\n"

    for idx, item in enumerate(results, start=1):
        preco_str = f"{item['price']}€" if item['price'] else "Indisponível"
        bsr_str = f"#{item['bsr']:,}".replace(",", ".") if item['bsr'] != 999999 else "N/D"

        msg += f"<b>{idx}. <a href='{item['url']}'>{item['title']}</a></b>\n"
        msg += f"🏆 <b>Ranking (BSR):</b> {bsr_str}\n"
        msg += f"💰 <b>Preço Atual:</b> {preco_str}\n"
        msg += f"🆔 <b>ASIN:</b> <code>{item['asin']}</code>\n\n"

    msg += "━━━━━━━━━━━━━━━━━━━\n"
    msg += "💡 <i>Quanto menor o número do BSR, mais unidades o produto está a vender!</i>"

    send_alert(msg)

if __name__ == "__main__":
    main()
