"""Envio de alertas formatados para Telegram, com fallback no terminal."""

import os
from typing import Any

import requests


def _format_number(value: Any, suffix: str = "") -> str:
    if value is None:
        return "n/d"
    return f"{value}{suffix}"


def build_alert_message(
    metric: dict[str, Any],
    reasons: list[str],
) -> str:
    """Cria uma mensagem legível com as métricas que dispararam o alerta."""
    return (
        "🚨 Alerta Amazon.es\n"
        f"Produto: {metric.get('title', 'Sem título')}\n"
        f"ASIN: {metric.get('asin')}\n"
        f"Motivo: {'; '.join(reasons)}\n"
        f"BSR: {_format_number(metric.get('bsr'))}\n"
        f"Preço: {_format_number(metric.get('price'), ' €')}\n"
        f"Vendedores: {_format_number(metric.get('sellers'))}\n"
        f"Rating: {_format_number(metric.get('rating'))}\n"
        f"Avaliações: {_format_number(metric.get('review_count'))}"
    )


def print_alert(message: str) -> None:
    """Imprime um alerta destacado quando o Telegram não está configurado."""
    border = "=" * 72
    print(f"\n{border}\n🔔 ALERTA (modo terminal)\n{message}\n{border}\n")


def send_telegram_message(message: str) -> bool:
    """Envia uma mensagem através do Telegram Bot API."""
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not telegram_token or not telegram_chat_id:
        return False

    response = requests.post(
        f"https://api.telegram.org/bot{telegram_token}/sendMessage",
        json={"chat_id": telegram_chat_id, "text": message},
        timeout=15,
    )
    response.raise_for_status()
    print("[ALERTA] Notificação enviada para o Telegram.")
    return True


def send_alert(message: str) -> bool:
    """Envia para Telegram ou imprime no terminal como fallback.

    As credenciais são lidas dos Secrets/env vars e nunca são impressas.
    Retorna True quando o Telegram aceitou a notificação.
    """
    if send_telegram_message(message):
        return True

    print("[ALERTA] Telegram não configurado; a mostrar alerta no terminal.")
    print_alert(message)
    return False