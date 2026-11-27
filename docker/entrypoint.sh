#!/bin/sh
set -eu

PORT="${PORT:-8000}"
DATA_DIR="$(dirname "${DB_PATH:-/app/data/books.db}")"

# Railway (and other hosts) mount volumes owned by root. When started as root,
# make the data directory writable for appuser, then drop privileges.
if [ "$(id -u)" = "0" ]; then
    mkdir -p "$DATA_DIR"
    chown -R appuser:appuser "$DATA_DIR"
    exec setpriv --reuid=appuser --regid=appuser --init-groups "$0" "$@"
fi

# Listen on IPv6 + IPv4 (dual stack) when the container has IPv6, so both
# Railway's IPv4 public proxy and IPv6 private network can reach the app.
if [ -f /proc/net/if_inet6 ]; then
    BIND="[::]:${PORT}"
else
    BIND="0.0.0.0:${PORT}"
fi

echo "Starting Hypercorn on ${BIND} (uid $(id -u), data dir ${DATA_DIR})"
exec hypercorn --config docker/hypercorn.toml --bind "$BIND" app.asgi:app
