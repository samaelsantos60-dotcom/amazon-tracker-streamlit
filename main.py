import os
import re
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8,pt;q=0.7",
}

def scrape_top_products(limit=10):
    url = "https://www.amazon.es/gp/bestsellers/electronics/"
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            return []

        soup = BeautifulSoup(response.content, "html.parser")
        products = []
        cards = soup.find_all("div", {"id": re.compile(r"^gridItemRoot")})

        for rank, card in enumerate(cards[:limit], start=1):
            title_elem = card.find("span", {"class": re.compile(r"_cDEbf_title_")}) or card.find("div", {"class": "p13n-sc-css-line-clamp-1"})
            title = title_elem.get_text(strip=True) if title_elem else "Produto"

            link_elem = card.find("a", {"class": "a-link-normal"})
            href = link_elem["href"] if link_elem else ""
            prod_url = f"https://www.amazon.es{href}" if href.startswith("/") else href

            price = None
            price_elem = card.find("span", {"class": "_cDEbf_price_11U0m"}) or card.find("span", {"class": "a-color-price"})
            if price_elem:
                price_text = price_elem.get_text().replace(",", ".").replace("€", "").strip()
                match = re.search(r"(\d+\.?\d*)", price_text)
                if match:
                    price = float(match.group(1))

            products.append({"rank": rank, "title": title[:40], "price": price, "url": prod_url})
        return products
    except Exception as e:
        print(f"Erro: {e}")
        return []

# Comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Olá! Envia o comando /top10 para receberes a lista dos mais vendidos da Amazon.")

# Comando /top10
async def top10(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 A procurar o Top 10 atual da Amazon...")
    products = scrape_top_products(10)
    
    if not products:
        await update.message.reply_text("❌ Erro ao obter os produtos. Tenta mais tarde.")
        return

    msg = "🔥 <b>TOP 10 MAIS VENDIDOS AMAZON</b>\n━━━━━━━━━━━━━━━━━━━\n\n"
    for item in products:
        preco = f"{item['price']}€" if item['price'] else "N/D"
        msg += f"<b>#{item['rank']} <a href='{item['url']}'>{item['title']}</a></b>\n💰 Preço: {preco}\n\n"

    await update.message.reply_text(msg, parse_mode="HTML", disable_web_page_preview=True)

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("top10", top10))
    print("🤖 Bot interativo a rodar...")
    app.run_polling()
