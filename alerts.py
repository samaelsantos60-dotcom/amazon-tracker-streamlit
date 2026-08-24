import os
import requests

def send_alert(message):
    """Envia uma mensagem formatada via HTML para o Telegram."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("[ERRO TELEGRAM] Secrets não configurados.")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print("✅ Relatório enviado para o Telegram com sucesso!")
        else:
            print(f"[ERRO TELEGRAM] Código {response.status_code}: {response.text}")
    except Exception as e:
        print(f"[ERRO TELEGRAM] Exceção: {e}")
