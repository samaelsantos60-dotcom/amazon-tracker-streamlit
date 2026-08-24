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

def was_sent_recently(asin, hours=24):
    """Verifica se o produto (ASIN) foi enviado para o Telegram nas últimas X horas."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id FROM products 
        WHERE asin = ? AND timestamp >= datetime('now', '-' || ? || ' hours')
    ''', (asin, hours))
    row = cursor.fetchone()
    conn.close()
    return row is not None

def save_product_data(asin, title, price, bsr):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO products (asin, title, price, bsr)
        VALUES (?, ?, ?, ?)
    ''', (asin, title, price, bsr))
    conn.commit()
    conn.close()

def send_telegram_card_with_photo(title, price, old_price, coupon, asin, url, image_url, rank):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("[ERRO] Variáveis do Telegram não configuradas.")
        return

    preco_str = f"{price}€" if price else "Ver no site"
    
    preco_bloco = f"💰 <b>Preço:</b> {preco_str}\n"
    if old_price and price and old_price > price:
        desconto = int(((old_price - price) / old_price) * 100)
        preco_bloco = (
            f"💰 <b>Preço Promoção:</b> {preco_str} "
            f"<s>({old_price}€)</s> 🔥 <b>-{desconto}%</b>\n"
        )

    cupao_bloco = ""
    if coupon:
        cupao_bloco = f"🎟️ <b>CUPÃO DISPONÍVEL:</b> <i>{coupon}</i>\n⚠️ <i>Marca a caixa do cupão na página do produto!</i>\n"

    caption = (
        f"🔥 <b>OFERTA DA AMAZON</b> 🔥\n\n"
        f"📦 <b>{title}</b>\n\n"
        f"{preco_bloco}"
        f"{cupao_bloco}\n"
        f"🆔 <b>ASIN:</b> <code>{asin}</code>\n"
    )

    channel_username = chat_id.replace("@", "")
    share_text = "Olha esta promoção incrível com desconto na Amazon! 😱🔥"
    share_url = f"https://t.me/share/url?url=https://t.me/{channel_username}&text={requests.utils.quote(share_text)}"

    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "🛒 VER PROMOÇÃO", "url": url},
                {"text": "📲 PARTILHAR", "url": share_url}
            ]
        ]
    }

    if image_url and image_url.startswith("http"):
        api_url = f"https://api.telegram.org/bot{token}/sendPhoto"
        payload = {
            "chat_id": chat_id,
            "photo": image_url,
            "caption": caption,
            "parse_mode": "HTML",
            "reply_markup": reply_markup
        }
    else:
        api_url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": caption,
            "parse_mode": "HTML",
            "reply_markup": reply_markup
        }

    requests.post(api_url, json=payload)

def scrape_bestsellers_category(category_url, limit=10):
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

            img_elem = card.find("img")
            image_url = img_elem["src"] if img_elem and "src" in img_elem.attrs else ""

            link_elem = card.find("a", {"class": "a-link-normal"})
            href = link_elem["href"] if link_elem else ""
            clean_url = f"https://www.amazon.es{href}" if href.startswith("/") else href

            asin_match = re.search(r"/(?:dp|product-reviews)/([A-Z0-9]{10})", clean_url)
            asin = asin_match.group(1) if asin_match else "N/D"

            if asin == "N/D":
                continue

            affiliate_url = f"https://www.amazon.es/dp/{asin}?tag={AFFILIATE_TAG}"

            price = None
            old_price = None
            price_elem = card.find("span", {"class": "_cDEbf_price_11U0m"}) or card.find("span", {"class": "a-color-price"})
            if price_elem:
                price_text = price_elem.get_text().replace(",", ".").replace("€", "").strip()
                match = re.search(r"(\d+\.?\d*)", price_text)
                if match:
                    price = float(match.group(1))

            old_price_elem = card.find("span", {"class": "a-text-price"})
            if old_price_elem:
                old_price_text = old_price_elem.get_text().replace(",", ".").replace("€", "").strip()
                match = re.search(r"(\d+\.?\d*)", old_price_text)
                if match:
                    old_price = float(match.group(1))

            coupon = None
            coupon_elem = card.find("span", text=re.compile(r"Cupón|Cupom|desconto", re.I)) or card.find("span", {"class": "a-badge-text"})
            if coupon_elem:
                coupon = coupon_elem.get_text(strip=True)

            products.append({
                "rank": rank,
                "asin": asin,
                "title": title,
                "price": price,
                "old_price": old_price,
                "coupon": coupon,
                "url": affiliate_url,
                "image_url": image_url
            })

        return products

    except Exception as e:
        print(f"[ERRO] Exceção: {e}")
        return []

def main():
    init_db()
    CATEGORY_URL = "https://www.amazon.es/gp/bestsellers/electronics/"
    
    print("🔍 A verificar produtos e histórico de envio...")
    products = scrape_bestsellers_category(CATEGORY_URL, limit=10)

    novos_enviados = 0
    for prod in products:
        # Pula se o produto já foi enviado nas últimas 24 horas
        if was_sent_recently(prod["asin"], hours=24):
            print(f"⏭️ Ignorado (já enviado recentemente): {prod['asin']}")
            continue

        send_telegram_card_with_photo(
            title=prod["title"],
            price=prod["price"],
            old_price=prod["old_price"],
            coupon=prod["coupon"],
            asin=prod["asin"],
            url=prod["url"],
            image_url=prod["image_url"],
            rank=prod["rank"]
        )
        save_product_data(prod["asin"], prod["title"], prod["price"], prod["rank"])
        novos_enviados += 1

    print(f"✅ Processo concluído! {novos_enviados} novos produtos enviados.")

if __name__ == "__main__":
    main()
from alerts import send_alert
send_alert("🧪 Teste de Notificação: Se leres isto, o bot está a funcionar!")
