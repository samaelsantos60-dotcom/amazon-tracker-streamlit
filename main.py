# 1. CATEGORIAS DE ALTA PROCURA (Feminino, Bebé, Cuidado Pessoal e Lar)
CATEGORY_MAP = {
    0: "https://www.amazon.es/gp/bestsellers/baby",          # Segunda: Fraldas, lenços, bebé
    1: "https://www.amazon.es/gp/bestsellers/beauty",        # Terça: Maquilhagem, cosmética, beleza
    2: "https://www.amazon.es/gp/bestsellers/hpc",           # Quarta: Papel higiénico, sabão, higiene
    3: "https://www.amazon.es/gp/bestsellers/grocery",       # Quinta: Detergentes, limpeza do lar
    4: "https://www.amazon.es/gp/bestsellers/personal-care", # Sexta: Gel de banho, champôs
    5: "https://www.amazon.es/gp/bestsellers/beauty",        # Sábado: Cosmética e maquilhagem
    6: "https://www.amazon.es/gp/bestsellers/baby"           # Domingo: Produtos de bebé e cuidados
}

def main():
    init_db()
    
    weekday = datetime.datetime.now().weekday()
    category_url = CATEGORY_MAP.get(weekday, CATEGORY_MAP[0])
    
    print(f"🔍 A procurar produtos na categoria do dia ({category_url})...", flush=True)
    products = scrape_bestsellers_category(category_url, limit=60)

    novos_enviados = 0
    # Limite máximo fixado em 20 anúncios por execução
    MAX_ANUNCIOS = 20

    for prod in products:
        if novos_enviados >= MAX_ANUNCIOS:
            print(f"🛑 Meta de {MAX_ANUNCIOS} anúncios atingida por hoje!")
            break

        asin = prod["asin"]
        price = prod["price"]
        old_price = prod["old_price"]

        # 2. BLOQUEIA REPETIDOS POR 14 DIAS (336 horas)
        # Altera este valor de 24 para 336 para evitar qualquer repetição nas últimas 2 semanas
        if was_sent_recently(asin, hours=336):
            print(f"⏭️ Ignorado (já enviado nos últimos 14 dias): {asin}")
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

    print(f"✅ Processo concluído! {novos_enviados} produtos enviados hoje.", flush=True)
