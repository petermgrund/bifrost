#!/bin/bash
# Repoint Gramps media to the displayed version of an Immich stack.
#
# Runs ONLY the version phase of the Immich sync (versions_only) — it never
# creates media or touches dates/places/descriptions, so it's safe unattended.
# When the stack primary changes (you promote a different version), this repoints
# the Gramps media to it (path/mime + Immich ID/URL), clears now-invalid face
# rects and best-effort re-derives them, and propagates the sync tag to members.
# Only stacks Bifrost manages (a member tagged Gramps/Base/*, or a tracked row)
# are touched — pre-existing burst/RAW stacks are ignored.
# Cron: offset from the Paperless versions cron. flock prevents overlap.
LOG=/opt/stacks/bifrost/immich_versions_sync.log
exec 9>/tmp/bifrost-immich-versions-sync.lock
flock -n 9 || exit 0

resp=$(curl -fsS -m 540 -X POST http://127.0.0.1:8800/sync/api/immich/apply \
  -H "Content-Type: application/json" -d '{"versions_only": true}' 2>&1)
summary=$(printf '%s' "$resp" | python3 -c "
import json, sys
try:
    ev = json.load(sys.stdin).get('events', [])
    s = next((e['data'] for e in ev if e.get('kind') == 'summary'), {}) or {}
    print(f\"versions_updated={s.get('versions_updated', 0)} \"
          f\"faces_cleared={s.get('faces_cleared', 0)} \"
          f\"faces_rederived={s.get('faces_rederived', 0)} \"
          f\"errors={s.get('errors', 0)}\")
except Exception as e:
    print('FAILED:', (str(e) or 'no response')[:120])
" 2>/dev/null)
printf '%s %s\n' "$(date -Iseconds)" "${summary:-FAILED: no response}" >> "$LOG"
# keep the log small
tail -n 500 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
