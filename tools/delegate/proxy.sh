#!/usr/bin/env bash
# tools/delegate/proxy.sh
#
# LiteLLM proxy lifecycle control (standalone). The start action is
# auto-invoked from run.sh / launch.sh / activate.sh as well — use this
# script only when you want manual control.
#
# Usage:
#   proxy.sh start | stop | restart | status | logs

set -euo pipefail
DELEGATE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$DELEGATE_DIR/lib.sh"

cmd="${1:-status}"

case "$cmd" in
    start)
        load_env
        ensure_proxy
        ;;
    stop)
        stop_proxy
        ;;
    restart)
        stop_proxy
        sleep 1
        load_env
        ensure_proxy
        ;;
    status)
        if proxy_alive; then
            pid_msg=""
            [[ -f "$PROXY_PID_FILE" ]] && pid_msg=" (pid $(cat "$PROXY_PID_FILE"))"
            printf 'up   %s%s\n' "$PROXY_URL" "$pid_msg"
            exit 0
        else
            printf 'down %s\n' "$PROXY_URL"
            exit 1
        fi
        ;;
    logs)
        [[ -f "$PROXY_LOG_FILE" ]] || die "no log file at $PROXY_LOG_FILE"
        exec tail -f "$PROXY_LOG_FILE"
        ;;
    -h|--help)
        sed -n '1,10p' "$0"
        ;;
    *)
        die "unknown subcommand: $cmd (try: start|stop|restart|status|logs)"
        ;;
esac
