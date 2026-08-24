#!/usr/bin/env bash
# Supervisor simples: mantém ambos os serviços ativos e reinicia-os se terminarem.
set -u

run_monitor() {
  while true; do
    echo "[SUPERVISOR] A iniciar main.py..."
    python main.py >> monitor.log 2>&1
    status=$?
    echo "[SUPERVISOR] main.py terminou ($status); a reiniciar em 5s..."
    sleep 5
  done
}

run_dashboard() {
  while true; do
    echo "[SUPERVISOR] A iniciar Streamlit na porta 8501..."
    streamlit run dashboard.py \
      --server.headless true \
      --server.address 0.0.0.0 \
      --server.port 8501 >> streamlit.log 2>&1
    status=$?
    echo "[SUPERVISOR] Streamlit terminou ($status); a reiniciar em 5s..."
    sleep 5
  done
}

run_monitor &
monitor_pid=$!
run_dashboard &
dashboard_pid=$!

cleanup() {
  echo "[SUPERVISOR] A terminar os serviços..."
  kill "$monitor_pid" "$dashboard_pid" 2>/dev/null || true
  wait "$monitor_pid" "$dashboard_pid" 2>/dev/null || true
}

trap cleanup INT TERM EXIT

# O supervisor permanece em primeiro plano. Este heartbeat também deixa claro,
# nos logs do Replit, que a aplicação continua viva e a porta está publicada.
while kill -0 "$monitor_pid" 2>/dev/null && kill -0 "$dashboard_pid" 2>/dev/null; do
  echo "[SUPERVISOR] Servidor no ar — Streamlit: porta 8501 — $(date '+%Y-%m-%d %H:%M:%S')"
  sleep 30
done

echo "[SUPERVISOR] Um serviço terminou; a encerrar o supervisor."
exit 1