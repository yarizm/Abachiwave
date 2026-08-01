#!/bin/sh
set -eu

marker="/app/node_modules/.abachiwave-package-lock.sha256"
current_hash="$(sha256sum /app/package-lock.json | awk '{print $1}')"
stored_hash=""

if [ -f "$marker" ]; then
  stored_hash="$(cat "$marker")"
fi

if [ "$stored_hash" != "$current_hash" ]; then
  echo "package-lock.json changed; synchronizing web dependencies"
  npm ci
  printf '%s' "$current_hash" > "$marker"
fi

exec "$@"
