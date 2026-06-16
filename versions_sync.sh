#!/bin/bash
# Repoint Gramps media to the currently-selected Paperless version.
#
# Runs ONLY phase 2 of the Paperless sync (versions_only) — it never creates
# media or touches titles/dates/transcriptions, so it's safe unattended. When a
# Paperless document's selected version changes, its served file's checksum
# changes; this repoints the Gramps media path (and clears face rects on img
# docs). Cron: every 10 min. flock prevents overlapping runs.
LOG=/opt/stacks/bifrost/versions_sync.log
exec 9>/tmp/bifrost-versions-sync.lock
flock -n 9 || exit 0

resp=$(curl -fsS -m 540 -X POST http://127.0.0.1:8800/sync/api/paperless/apply \
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
# keep the log small
tail -n 500 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
