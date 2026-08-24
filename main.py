"""Monitor de métricas de produtos Amazon Espanha para GitHub Actions."""

import argparse
from datetime import date, datetime

from alerts import build_alert_message, send_alert
from database import (
    add_monitored_products,
    get_monitored_asins,
    get_previous_metric,
    init_db,
    save_metrics,
)
from keepa_api import fetch_products


ASINS = [
    "B08N5WRWNW",
]


def test_keepa_connection() -> int:
    """Testa a API (ou confirma explicitamente o modo de dados simulados)."""
    print("[TESTE] A verificar a ligação ao Keepa para a Amazon.es...")
    try:
        metrics = fetch_products([ASINS[0]])
        if metrics and metrics[0]["title"].startswith("Produto Amazon de teste"):
            print("[TESTE] OK: KEEPA_API_KEY não definida; dados de teste ativos.")
        else:
            print(
                f"[TESTE] OK: API Keepa respondeu com {len(metrics)} produto(s) "
                "(domain=9, Amazon.es)."
            )
        return 0
    except Exception as error:
        print(f"[TESTE] ERRO: não foi possível obter resposta do Keepa: {error}")
        return 1


def collect_metrics() -> None:
    started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[INÍCIO] Recolha iniciada em {started_at}")
    print(f"[INFO] ASINs configurados: {len(ASINS)}")

    try:
        monitored_asins = get_monitored_asins() or ASINS
        print(f"[INFO] ASINs em monitorização: {len(monitored_asins)}")
        metrics = fetch_products(monitored_asins)
        print(f"[INFO] Métricas recebidas: {len(metrics)}")
        saved = save_metrics(metrics)
        today = date.today().isoformat()
        for metric in metrics:
            print(
                f"[PRODUTO] {metric['asin']} | {metric['title']} | "
                f"BSR={metric.get('bsr')} | preço={metric.get('price')}€ | "
                f"vendedores={metric.get('sellers')} | rating={metric.get('rating')} | "
                f"avaliações={metric.get('review_count')}"
            )
            previous = get_previous_metric(metric["asin"], today)
            reasons = []
            if previous:
                old_bsr, new_bsr = previous.get("bsr"), metric.get("bsr")
                if (
                    isinstance(old_bsr, (int, float))
                    and old_bsr > 0
                    and isinstance(new_bsr, (int, float))
                    and (old_bsr - new_bsr) / old_bsr > 0.20
                ):
                    reasons.append(
                        f"Oportunidade de Vendas — BSR melhorou "
                        f"{((old_bsr - new_bsr) / old_bsr) * 100:.1f}% "
                        f"({old_bsr} → {new_bsr})"
                    )

                old_price, new_price = previous.get("price"), metric.get("price")
                if (
                    isinstance(old_price, (int, float))
                    and old_price > 0
                    and isinstance(new_price, (int, float))
                    and (old_price - new_price) / old_price > 0.10
                ):
                    reasons.append(
                        f"Queda de Preço/Guerra de Buy Box — preço caiu "
                        f"{((old_price - new_price) / old_price) * 100:.1f}% "
                        f"({old_price:.2f}€ → {new_price:.2f}€)"
                    )

            if reasons:
                print(f"[ALERTA] Condição atingida para {metric['asin']}.")
                send_alert(build_alert_message(metric, reasons))
            elif previous:
                print(f"[ALERTAS] Sem alterações relevantes para {metric['asin']}.")
            else:
                print(f"[ALERTAS] Sem histórico de ontem para {metric['asin']}.")
        print(f"[SUCESSO] {saved} registo(s) guardado(s) na base de dados SQLite.")
    except Exception as error:
        print(f"[ERRO] A recolha falhou: {error}")
    finally:
        print(f"[FIM] Recolha terminada em {datetime.now():%Y-%m-%d %H:%M:%S}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Monitor de métricas Amazon.es")
    parser.add_argument(
        "--test-keepa",
        action="store_true",
        help="testa a ligação ao Keepa e termina",
    )
    args = parser.parse_args()

    if args.test_keepa:
        raise SystemExit(test_keepa_connection())

    print("[ARRANQUE] Monitor de métricas Amazon.es")
    init_db()
    print("[BASE DE DADOS] SQLite inicializada.")
    add_monitored_products(
        [{"asin": asin, "title": "Produto inicial"} for asin in ASINS]
    )

    print("[ARRANQUE] A executar recolha de dados...")
    collect_metrics()
    print("[CONCLUÍDO] Execução finalizada com sucesso.")


if __name__ == "__main__":
    main()
