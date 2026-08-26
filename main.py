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

        # ------------------------------------------------------------------
        # FILTRO DE VALIDAÇÃO REMOVIDO:
        # Agora o código envia TODOS os produtos novos sem ignorar por preço/desconto.
        # ------------------------------------------------------------------

        print(f"🚀 ENVIANDO PRODUTO: {asin} - Preço: {price}€")
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

    print(f"✅ Processo concluído! {novos_enviados} produtos enviados para o Telegram.")
