import os
import re
import time
import datetime
import sqlite3
import requests
import html
from bs4 import BeautifulSoup
from openai import OpenAI

DB_NAME = "amazon_tracker.db"
AFFILIATE_TAG = os.environ.get("AMAZON_ASSOCIATE_TAG", "SEU_TAG_AQUI-21")

# Headers reforçados para simular um navegador de desktop real
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1"
}

# URLs diretas das subcategorias desejadas
CATEGORY_MAP = {
    0: "https://www.amazon.es/gp/bestsellers/baby/ref=zg_bs_nav_baby_0",            # Segunda: Bebé
    1: "https://www.amazon.es/gp/bestsellers/beauty/ref=zg_bs_nav_beauty_0",        # Terça: Beleza
    2: "https://www.amazon.es/gp/bestsellers/hpc/ref=zg_bs_nav_hpc_0",              # Quarta: Higiene / Saúde
    3: "https://www.amazon.es/gp/bestsellers/grocery/ref=zg_bs_nav_grocery_0",      # Quinta: Supermercado
    4: "https://www.amazon.es/gp/bestsellers/beauty/2877074031",                    # Sexta: Champôs / Banho
    5: "https://www.amazon.es/gp/bestsellers/beauty/ref=zg_bs_nav_beauty_0",        # Sábado: Cosmética
    6: "https://www.amazon.es/gp/bestsellers/baby/ref=zg_bs_nav_baby_0"             # Domingo: Bebé
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

def generate_ai_caption(title, price, old_price, coupon):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None

    try:
        client = OpenAI(api_key=api_key)
        prompt = (
            f"Cria um texto persuasivo e muito curto para o Telegram em português europeu sobre o produto:\n"
            f"Produto: {title}\n\n"
            f"Regras:\n"
            f"1. Explica sucintamente o que é e porque vale a pena comprar.\n"
            f"2. Cria urgência de compra sem inventar percentagens de desconto.\n"
            f"3. NÃO incluas o preço, nome do produto nem links no texto.\n"
            f"4. Escreve no máximo 2 a 3 frases curtas."
        )
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=120
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"⚠️ [IA Warning] Não foi possível gerar legenda: {e}", flush=True)
        return None

def send_telegram_card_with_photo(title, price, old_price, coupon, asin, url, image_url, rank):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id:
        print("❌ [ERRO] Configuração ausente: TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID", flush=True)
        return False

    ai_caption = generate_ai_caption(title, price, old_price, coupon)
    clean_title = html.escape(title)

    preco_str = f"{price}€" if price else "Ver no site"
    preco_bloco = f"💰 <b>Preço:</b> {preco_str}\n"
    if old_price and price and old_price > price:
        desconto = int(((old_price - price) / old_price) * 100)
        preco_bloco = f"💰 <b>Preço Promoção:</b> {preco_str} <s>({old_price}€)</s> 🔥 <b>-{desconto}%</b>\n"

    cupao_bloco = f"🎟️ <b>CUPÃO:</b> <i>{html.escape(coupon)}</i>\n" if coupon else ""
    
    # Bloco descritivo: Usa a IA ou uma frase genérica se a IA falhar
    if ai_caption:
        descricao_bloco = f"{html.escape(ai_caption)}\n\n"
    else:
        descricao_bloco = "⚡ Aproveita esta grande oportunidade em destaque na Amazon!\n\n"

    # Montagem final da legenda sem linhas em branco excessivas
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
    try:
        print(f"📡 Efetuando requisição à URL: {category_url}", flush=True)
        response = requests.get(category_url, headers=HEADERS, timeout=15)
        print(f"📡 Status HTTP Amazon: {response.status_code}", flush=True)
        
        if response.status_code != 200:
            print(f"❌ Acesso negado pela Amazon (Código {response.status_code}).", flush=True)
            return []

        soup = BeautifulSoup(response.content, "html.parser")
        products = []
        
        cards = soup.find_all("div", {"id": re.compile(r"^gridItemRoot")})
        if not cards:
            cards = soup.find_all("div", {"class": re.compile(r"zg-grid-general-faceout")})

        print(f"📦 Produtos extraídos da página: {len(cards)}", flush=True)

        for rank, card in enumerate(cards[:limit], start=1):
            title = ""

            # 1. Tenta encontrar a tag de imagem e usar o atributo 'alt' (mais fiável)
            img_elem = card.find("img")
            if img_elem and img_elem.get("alt"):
                title = img_elem["alt"].strip()

            # 2. Se falhar, procura por seletores textuais de título da Amazon
            if not title:
                title_elem = (
                    card.find("div", {"class": re.compile(r"_cDEbf_title_")})
                    or card.find("span", {"class": re.compile(r"_cDEbf_title_")})
                    or card.find("div", {"class": "p13n-sc-css-line-clamp-1"})
                    or card.find("div", {"class": "p13n-sc-truncate-desktop-type2"})
                    or card.find("span", {"class": "zg-text-js-queue-clamp"})
                )
                if title_elem:
                    title = title_elem.get_text(strip=True)

            # 3. Se ainda assim estiver vazio, tenta capturar o texto dentro dos links <a>
            if not title:
                link_title = card.find("a", {"class": "a-link-normal"})
                if link_title:
                    title = link_title.get_text(strip=True)

            # 4. Fallback final se nada for encontrado
            if not title:
                title = "Produto Amazon em Promoção"

            image_url = img_elem["src"] if img_elem and "src" in img_elem.attrs else ""

            link_elem = card.find("a", {"class": "a-link-normal"})
            href = link_elem["href"] if link_elem and "href" in link_elem.attrs else ""
            clean_url = f"https://www.amazon.es{href}" if href.startswith("/") else href

            asin_match = re.search(r"/(?:dp|product-reviews)/([A-Z0-9]{10})", clean_url)
            asin = asin_match.group(1) if asin_match else "N/D"

            if asin == "N/D":
                continue

            affiliate_url = f"https://www.amazon.es/dp/{asin}?tag={AFFILIATE_TAG}"

            price = None
            price_elem = (
                card.find("span", {"class": "_cDEbf_price_11U0m"}) 
                or card.find("span", {"class": "a-color-price"}) 
                or card.find("span", {"class": "p13n-sc-price"})
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
