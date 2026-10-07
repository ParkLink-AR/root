#!/usr/bin/env bash
# Apunta mobile y admin-backend a la API que se le pase (EXPO_PUBLIC_API_URL en su .env).
# Lo usan `make up` (http://localhost:8080) y `make online` (el gateway por Cloudflare).
#
#   ./scripts/set-api-url.sh http://localhost:8080
#
# Expo graba EXPO_PUBLIC_* en el bundle: después de un cambio hay que reiniciar Expo con -c.
set -euo pipefail

url="${1:?uso: $0 <api-url>}"
root="$(cd "$(dirname "$0")/.." && pwd)"

for app in mobile admin-backend; do
  env_file="$root/$app/.env"

  if [ ! -f "$env_file" ]; then
    # admin-backend no trae .env, solo .env.example: se crea uno local, fuera de git.
    printf '# Generado por scripts/set-api-url.sh\nEXPO_PUBLIC_API_URL=%s\n' "$url" > "$env_file"
    exclude="$(git -C "$root/$app" rev-parse --git-path info/exclude)"
    case "$exclude" in /*) ;; *) exclude="$root/$app/$exclude" ;; esac
    grep -qxF '.env' "$exclude" 2>/dev/null || printf '.env\n' >> "$exclude"
    echo "[$app] .env creado -> $url"
    continue
  fi

  current="$(grep -E '^EXPO_PUBLIC_API_URL=' "$env_file" | head -1 | cut -d= -f2- || true)"
  if [ "$current" = "$url" ]; then
    echo "[$app] API ok: $url"
  elif [ -n "$current" ]; then
    tmp="$(mktemp)"
    awk -v url="$url" '!done && /^EXPO_PUBLIC_API_URL=/ { print "EXPO_PUBLIC_API_URL=" url; done=1; next } { print }' "$env_file" > "$tmp"
    cat "$tmp" > "$env_file" && rm -f "$tmp"
    echo "[$app] API $current -> $url (reiniciá Expo con -c)"
  else
    printf '\nEXPO_PUBLIC_API_URL=%s\n' "$url" >> "$env_file"
    echo "[$app] API agregada -> $url (reiniciá Expo con -c)"
  fi
done
