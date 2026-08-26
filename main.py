def send_telegram_card_with_photo(title, price, old_price, coupon, asin, url, image_url, rank):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("[ERRO] Variáveis do Telegram não configuradas.")
        return

    ai_caption = generate_ai_caption(title, price, old_price, coupon)

    if ai_caption:
        caption = f"🔥 <b>PROMOÇÃO IMPERDÍVEL</b> 🔥\n\n{ai_caption}\n\n🆔 <b>ASIN:</b> <code>{asin}</code>"
    else:
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

    # ENVIO E TRATAMENTO DE RESPOSTA CORRETO
    res = requests.post(api_url, json=payload)
    if res.status_code != 200:
        print(f"❌ ERRO TELEGRAM [{res.status_code}]: {res.text}")
    else:
        print(f"✅ Enviado com sucesso para o Telegram! ASIN: {asin}")


def main():
    init_db()
    
    weekday = datetime.datetime.now().weekday()
    category_url = CATEGORY_MAP.get(weekday, CATEGORY_MAP[0])
    
    print(f"🔍 A procurar produtos na categoria do dia ({category_url})...")
    products = scrape_bestsellers_category(category_url, limit=50)

    novos_enviados = 0
    for prod in products:
        asin = prod["asin"]
        price = prod["price"]
        old_price = prod["old_price"]
        coupon = prod["coupon"]

        # 1. Pula APENAS se já tiver sido enviado recentemente (evita repetições)
        if was_sent_recently(asin, hours=24):
            print(f"⏭️ Ignorado (já enviado nas últimas 24h): {asin}")
            continue

        print(f"🚀 PROCESSANDO PRODUTO: {asin} - Preço: {price}€")
        send_telegram_card_with_photo(
            title=prod["title"],
            price=price,
            old_price=old_price,
            coupon=coupon,
            asin=asin,
            url=prod["url"],
            image_url=prod["image_url"],
            rank=prod["rank"]
        )
        save_product_data(asin, prod["title"], price, prod["rank"])
        novos_enviados += 1

    print(f"✅ Processo concluído! {novos_enviados} produtos processados.")
