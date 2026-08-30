import os
import re
import time
import datetime
import sqlite3
import requests
import html
from bs4 import BeautifulSoup
import google.generativeai as genai

DB_NAME = "amazon_tracker.db"
AFFILIATE_TAG = os.environ.get("AMAZON_ASSOCIATE_TAG", "ofertaspromop-21")

CATEGORY_MAP = {
    0: "https://www.amazon.es/gp/bestsellers/baby/",
    1: "https://www.amazon.es/gp/bestsellers/beauty/",
    2: "https://www.amazon.es/gp/bestsellers/hpc/",
    3: "https://www.amazon.es/gp/bestsellers/grocery/",
    4: "https://www.amazon.es/gp/bestsellers/beauty/2877074031",
    5: "https://www.amazon.es/gp/bestsellers/beauty/",
    6: "https://www.amazon.es/gp/bestsellers/baby/"
}

def get_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9,pt-PT;q=0.8,pt;q=0.7,en-US;q=0.6,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1"
    })
    return session

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

def was_sent_recently(asin, hours=336):
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

def generate_ai_caption(title, price):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        prompt = (
            f"Cria um texto persuasivo e muito curto para o Telegram em português europeu sobre o produto:\n"
            f"Produto: {title}\n\n"
            f"Regras:\n"
            f"1. Explica sucintamente o que é e porque vale a pena comprar.\n"
            f"2. Cria urgência de compra sem inventar percentagens de desconto.\n"
            f"3. NÃO incluas o preço, nome do produto nem links no texto.\n"
            f"4. Escreve no máximo 2 a 3 frases curtas."
        )
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"⚠️ [Gemini IA Warning] Erro ao gerar legenda: {e}", flush=True)
        return None

def send_telegram_card_with_photo(title, price, old_price, coupon, asin, url, image_url, rank):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id:
        print("❌ [ERRO] Configuração ausente: TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID", flush=True)
        return False

    ai_caption = generate_ai_caption(title, price)
    clean_title = html.escape(title)

    preco_str = f"{price}€" if price else "Ver no site"
    preco_bloco = f"💰 <b>Preço:</b> {preco_str}\n"
    if old_price and price and old_price > price:
        desconto = int(((old_price - price) / old_price) * 100)
        preco_bloco = f"💰 <b>Preço Promoção:</b> {preco_str} <s>({old_price}€)</s> 🔥 <b>-{desconto}%</b>\n"

    cupao_bloco = f"🎟️ <b>CUPÃO:</b> <i>{html.escape(coupon)}</i>\n" if coupon else ""
    
    if ai_caption:
        descricao_bloco = f"{html.escape(ai_caption)}\n\n"
    else:
        descricao_bloco = "⚡ Aproveita esta grande oportunidade em destaque na Amazon!\n\n"

    caption = (
        f"🔥 <b>OFERTA DA AMAZON</b> 🔥\n\n"
        f"📦 <b>{clean_title}</b>\n\n"
        f"{descricao_bloco}"
        f"{preco_bloco}"
        f"{cupao_bloco}"
        f"🆔 <b>ASIN:</b> <code>{asin}</code>"
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

    try:
        if image_url and image_url.startswith("http"):
            api_url = f"https://api.telegram.org/bot{token}/sendPhoto"
            payload = {"chat_id": chat_id, "photo": image_url, "caption": caption, "parse_mode": "HTML", "reply_markup": reply_markup}
        else:
            api_url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {"chat_id": chat_id, "text": caption, "parse_mode": "HTML", "reply_markup": reply_markup}

        res = requests.post(api_url, json=payload, timeout=10)
        if res.status_code != 200:
            print(f"❌ ERRO TELEGRAM [{res.status_code}]: {res.text}", flush=True)
            return False
        else:
            print(f"✅ Mensagem enviada para o Telegram! ASIN: {asin}", flush=True)
            return True
    except Exception as e:
        print(f"❌ Exceção ao enviar para o Telegram: {e}", flush=True)
        return False

def scrape_bestsellers_category(category_url, limit=60):
    session = get_session()
    try:
        print(f"📡 Efetuando requisição à URL: {category_url}", flush=True)
        response = session.get(category_url, timeout=15)
        print(f"📡 Status HTTP Amazon: {response.status_code}", flush=True)
        
        if response.status_code != 200:
            print(f"❌ Acesso negado pela Amazon (Código {response.status_code}).", flush=True)
            return []

        soup = BeautifulSoup(response.content, "html.parser")
        products = []
        
        # Procura os cards por vários seletores possíveis
        cards = soup.find_all("div", {"id": re.compile(r"^gridItemRoot")})
        if not cards:
            cards = soup.find_all("div", {"class": re.compile(r"zg-grid-general-faceout")})
        if not cards:
            cards = soup.find_all("div", {"class": re.compile(r"p13n-sc-unstructured-line-item")})
        if not cards:
            cards = soup.find_all("li", {"class": re.compile(r"zg-item-immersion")})

        print(f"📦 Produtos extraídos da página: {len(cards)}", flush=True)

        for rank, card in enumerate(cards[:limit], start=1):
            title = ""

            img_elem = card.find("img")
            if img_elem and img_elem.get("alt"):
                title = img_elem["alt"].strip()

            if not title:
                title_elem = (
                    card.find("div", {"class": re.compile(r"_cDEbf_title_")})
                    or card.find("span", {"class": re.compile(r"_cDEbf_title_")})
                    or card.find("div", {"class": "p13n-sc-css-line-clamp-1"})
                    or card.find("div", {"class": "p13n-sc-truncate-desktop-type2"})
                    or card.find("a", {"class": "a-link-normal"})
                )
                if title_elem:
                    title = title_elem.get_text(strip=True)

            if not title:
                title = "Produto Amazon em Promoção"

            image_url = ""
            if img_elem:
                image_url = img_elem.get("src") or img_elem.get("data-a-dynamic-image", "")
                if "{" in image_url:
                    match_img = re.search(r'"(https://[^"]+)"', image_url)
                    if match_img:
                        image_url = match_img.group(1)

            link_elem = card.find("a", {"class": "a-link-normal"})
            href = link_elem["href"] if link_elem and "href" in link_elem.attrs else ""
            clean_url = f"https://www.amazon.es{href}" if href.startswith("/") else href

            asin_match = re.search(r"/(?:dp|product-reviews|gp/product)/([A-Z0-9]{10})", clean_url)
            asin = asin_match.group(1) if asin_match else "N/D"

            if asin == "N/D":
                continue

            affiliate_url = f"https://www.amazon.es/dp/{asin}?tag={AFFILIATE_TAG}"

            price = None
            price_elem = (
                card.find("span", {"class": re.compile(r"_cDEbf_price_")}) 
                or card.find("span", {"class": "a-color-price"}) 
                or card.find("span", {"class": "p13n-sc-price"})
                or card.find("span", {"class": "a-size-base a-color-price"})
                or card.find("span", {"class": "_cDEbf_price_11U0m"})
            )
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
                "old_price": None,
                "coupon": None,
                "url": affiliate_url,
                "image_url": image_url
            })

        return products

    except Exception as e:
        print(f"❌ Erro ao raspar dados: {e}", flush=True)
        return []

def main():
    print("🚀 SCRIPT INICIADO", flush=True)
    init_db()
    
    weekday = datetime.datetime.now().weekday()
    category_url = CATEGORY_MAP.get(weekday, CATEGORY_MAP[0])
    
    print(f"🔍 A procurar produtos na categoria do dia ({category_url})...", flush=True)
    products = scrape_bestsellers_category(category_url, limit=60)

    novos_enviados = 0
    MAX_ANUNCIOS = 20

    for prod in products:
        if novos_enviados >= MAX_ANUNCIOS:
            print(f"🛑 Meta de {MAX_ANUNCIOS} anúncios atingida!", flush=True)
            break

        asin = prod["asin"]
        price = prod["price"]
        old_price = prod["old_price"]

        if was_sent_recently(asin, hours=336):
            print(f"⏭️ Ignorado (já enviado nos últimos 14 dias): {asin}", flush=True)
            continue

        print(f"🚀 PROCESSANDO PRODUTO: {asin} - Preço: {price}€", flush=True)
        
        sucesso = send_telegram_card_with_photo(
            title=prod["title"],
            price=price,
            old_price=old_price,
            coupon=prod["coupon"],
            asin=asin,
            url=prod["url"],
            image_url=prod["image_url"],
            rank=prod["rank"]
        )
        
        if sucesso:
            save_product_data(asin, prod["title"], price, prod["rank"])
            novos_enviados += 1
            time.sleep(2)

    print(f"✅ Processo concluído! {novos_enviados} produtos enviados hoje.", flush=True)

if __name__ == "__main__":
    main()
