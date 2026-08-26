import os
import re
import datetime
import sqlite3
import requests
import html
from bs4 import BeautifulSoup
from openai import OpenAI

DB_NAME = "amazon_tracker.db"
AFFILIATE_TAG = os.environ.get("AMAZON_ASSOCIATE_TAG", "SEU_TAG_AQUI-21")

# Headers completos para simular um navegador real e reduzir bloqueios 503/403
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Ch-Ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
}

CATEGORY_MAP = {
    0: "https://www.amazon.es/gp/bestsellers/electronics/",
    1: "https://www.amazon.es/gp/bestsellers/kitchen/",
    2: "https://www.amazon.es/gp/bestsellers/computers/",
    3: "https://www.amazon.es/gp/bestsellers/home-goods/",
    4: "https://www.amazon.es/gp/bestsellers/sports/",
    5: "https://www.amazon.es/gp/bestsellers/toys/",
    6: "https://www.amazon.es/gp/bestsellers/electronics/"
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

def generate_ai_caption(title, price, old_price, coupon):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None

    try:
        client = OpenAI(api_key=api_key)
        prompt = (
            f"Cria um post curto e persuasivo para o Telegram:\n"
            f"Produto: {title}\nPreço: {price}€\n\n"
            f"Usa emojis e atrai compradores em Portugal. Sem links no texto."
        )
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"⚠️ [Aviso IA] Erro ao gerar legenda: {e}")
        return None

def send_telegram_card_with_photo(title, price, old_price, coupon, asin, url, image_url, rank):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id:
        print("❌ [ERRO] TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID não definidos nas Secrets!")
        return

    ai_caption = generate_ai_caption(title, price, old_price, coupon)

    # Limpa caracteres especiais do título para não quebrar a sintaxe HTML do Telegram
    clean_title = html.escape(title)

    if ai_caption:
        caption = f"🔥 <b>PROMOÇÃO IMPERDÍVEL</b> 🔥\n\n{html.escape(ai_caption)}\n\n🆔 <b>ASIN:</b> <code>{asin}</code>"
    else:
        preco_str = f"{price}€" if price else "Ver no site"
        preco_bloco = f"💰 <b>Preço:</b> {preco_str}\n"
        if old_price and price and old_price > price:
            desconto = int(((old_price - price) / old_price) * 100)
            preco_bloco = f"💰 <b>Preço Promoção:</b> {preco_str} <s>({old_price}€)</s> 🔥 <b>-{desconto}%</b>\n"

        cupao_bloco = f"🎟️ <b>CUPÃO:</b> <i>{html.escape(coupon)}</i>\n" if coupon else ""
        caption = (
            f"🔥 <b>OFERTA DA AMAZON</b> 🔥\n\n"
            f"📦 <b>{clean_title}</b>\n\n"
            f"{preco_bloco}"
            f"{cupao_bloco}\n"
            f"🆔 <b>ASIN:</b> <code>{asin}</code>\n"
        )

    channel_username = chat_id.replace("@", "")
    share_url = f"https://t.me/share/url?url=https://t.me/{channel_username}&text=Olha+esta+oferta!"

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
        payload = {"chat_id": chat_id, "photo": image_url, "caption": caption, "parse_mode": "HTML", "reply_markup": reply_markup}
    else:
        api_url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": caption, "parse_mode": "HTML", "reply_markup": reply_markup}

    res = requests.post(api_url, json=payload)
    if res.status_code != 200:
        print(f"❌ ERRO TELEGRAM [{res.status_code}]: {res.text}")
    else:
        print(f"✅ Enviado com sucesso para o Telegram! ASIN: {asin}")

def scrape_bestsellers_category(category_url, limit=50):
    try:
        response = requests.get(category_url, headers=HEADERS, timeout=15)
        print(f"📡 Status Code Amazon: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ A Amazon bloqueou o pedido com o código HTTP {response.status_code}")
            return []

        soup = BeautifulSoup(response.content, "html.parser")
        products = []
        cards = soup.find_all("div", {"id": re.compile(r"^gridItemRoot")})
        
        print(f"📦 Total de cartões de produtos encontrados na página: {len(cards)}")

        for rank, card in enumerate(cards[:limit], start=1):
            title_elem = card.find("span", {"class": re.compile(r"_cDEbf_title_")}) or card.find("div", {"class": "p13n-sc-css-line-clamp-1"}) or card.find("a", {"class": "a-link-normal"})
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
            price_elem = card.find("span", {"class": "_cDEbf_price_11U0m"}) or card.find("span", {"class": "a-color-price"}) or card.find("span", {"class": "p13n-sc-price"})
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
                "old_price": old_price,
                "coupon": None,
                "url": affiliate_url,
                "image_url": image_url
            })

        return products

    except Exception as e:
        print(f"❌ Exceção no Scraper: {e}")
        return []

def main():
    init_db()
    
    weekday = datetime.datetime.now().weekday()
    category_url = CATEGORY_MAP.get(weekday, CATEGORY_MAP[0])
    
    print(f"🔍 A procurar produtos na categoria do dia ({category_url})...", flush=True)
    products = scrape_bestsellers_category(category_url, limit=50)

    novos_enviados = 0
    for prod in products:
        asin = prod["asin"]
        price = prod["price"]
        old_price = prod["old_price"]

        if was_sent_recently(asin, hours=24):
            print(f"⏭️ Ignorado (já enviado nas últimas 24h): {asin}")
            continue

        print(f"🚀 PROCESSANDO PRODUTO: {asin} - Preço: {price}€", flush=True)
        send_telegram_card_with_photo(
            title=prod["title"],
            price=price,
            old_price=old_price,
            coupon=prod["coupon"],
            asin=asin,
            url=prod["url"],
            image_url=prod["image_url"],
            rank=prod["rank"]
        )
        save_product_data(asin, prod["title"], price, prod["rank"])
        novos_enviados += 1

    print(f"✅ Processo concluído! {novos_enviados} produtos processados.", flush=True)

if __name__ == "__main__":
    main()
