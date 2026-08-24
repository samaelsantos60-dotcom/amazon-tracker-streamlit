def send_telegram_card(title, price, asin, url, rank):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("[ERRO] Variáveis do Telegram não configuradas.")
        return

    preco_str = f"{price}€" if price else "Ver no site"

    # Texto da mensagem
    text = (
        f"🔥 <b>OFERTA #{rank} DA AMAZON</b> 🔥\n\n"
        f"📦 <b>{title}</b>\n\n"
        f"💰 <b>Preço:</b> {preco_str}\n"
        f"🆔 <b>ASIN:</b> <code>{asin}</code>\n"
    )

    # Link dinâmico para partilhar no Telegram
    # Altera 'ofertas_amazon_pt' para o username do teu canal sem o @
    channel_username = chat_id.replace("@", "")
    share_text = f"Olha esta oferta imperdível na Amazon! 😱🔥"
    share_url = f"https://t.me/share/url?url=https://t.me/{channel_username}&text={requests.utils.quote(share_text)}"

    # Teclado com 2 botões (uma linha com dois botões lado a lado)
    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "🛒 VER OFERTA", "url": url},
                {"text": "📲 PARTILHAR", "url": share_url}
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
