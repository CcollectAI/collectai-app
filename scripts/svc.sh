#!/usr/bin/env bash
set -euo pipefail
APP="app.main:app"
HOST="0.0.0.0"
PORT="${PORT:-8080}"
LOG="/tmp/collectors-merge.out"
PID="/tmp/collectors-merge.pid"

start() {
  if [ -f "$PID" ] && kill -0 "$(cat "$PID")" 2>/dev/null; then
    echo "[svc] already running (pid $(cat "$PID"))"; exit 0
  fi
  echo "[svc] starting uvicorn on :$PORT"
  nohup bash -lc "source .env >/dev/null 2>&1 || true; exec uvicorn ${APP} --host ${HOST} --port ${PORT}" >>"$LOG" 2>&1 &
  echo $! > "$PID"
  sleep 1
  status
}
stop() {
  if [ -f "$PID" ] && kill -0 "$(cat "$PID")" 2>/dev/null; then
    kill "$(cat "$PID")" || true
    rm -f "$PID"
    echo "[svc] stopped"
  else
    echo "[svc] not running"
  fi
}
status() {
  if [ -f "$PID" ] && kill -0 "$(cat "$PID")" 2>/dev/null; then
    echo "[svc] running (pid $(cat "$PID"))"
  else
    echo "[svc] stopped"
    tail -n 50 "$LOG" 2>/dev/null || true
  fi
}
logs() { tail -n 200 -f "$LOG"; }
case "${1:-}" in
  start) start ;;
  stop) stop ;;
  restart) stop; start ;;
  status) status ;;
  logs) logs ;;
  *) echo "usage: $0 {start|stop|restart|status|logs}"; exit 1 ;;
esac
