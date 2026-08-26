#!/bin/bash
# Repoint Gramps media to the version selected in Paperless

BIFROST_URL=${BIFROST_URL:-http://127.0.0.1:8800}
LOG=${BIFROST_VERSIONS_LOG:-$(dirname "$0")/versions_sync.log}
exec 9>/tmp/bifrost-versions-sync.lock
flock -n 9 || exit 0

resp=$(curl -fsS -m 540 -X POST "$BIFROST_URL/sync/api/paperless/apply" \
  -H "Content-Type: application/json" -d '{"versions_only": true}' 2>&1)
summary=$(printf '%s' "$resp" | python3 -c "
import json, sys
try:
    ev = json.load(sys.stdin).get('events', [])
    s = next((e['data'] for e in ev if e.get('kind') == 'summary'), {}) or {}
    print(f\"versions_updated={s.get('versions_updated', 0)} errors={s.get('errors', 0)}\")
except Exception as e:
    print('FAILED:', (str(e) or 'no response')[:120])
" 2>/dev/null)
printf '%s %s\n' "$(date -Iseconds)" "${summary:-FAILED: no response}" >> "$LOG"
tail -n 500 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
