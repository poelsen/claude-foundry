#!/usr/bin/env bash
# tools/delegate/proxy.sh
#
# claude-code-router (ccr) proxy lifecycle control (standalone). The
# start action is auto-invoked from run.sh / launch.sh / activate.sh as
# well — use this script only when you want manual control.
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
            printf 'up   %s\n' "$PROXY_URL"
            exit 0
        else
            printf 'down %s\n' "$PROXY_URL"
            exit 1
        fi
        ;;
    logs)
        log_dir="$CCR_CONFIG_DIR/logs"
        [[ -d "$log_dir" ]] || die "no ccr logs dir at $log_dir"
        exec tail -f "$log_dir"/ccr-*.log "$CCR_CONFIG_DIR/claude-code-router.log" 2>/dev/null
        ;;
    -h|--help)
        sed -n '1,10p' "$0"
        ;;
    *)
        die "unknown subcommand: $cmd (try: start|stop|restart|status|logs)"
        ;;
esac
