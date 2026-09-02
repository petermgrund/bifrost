set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$here"

usage() {
  cat <<USAGE
Usage: $(basename "$0") <command> [args]

  up              build + start everything (first run also writes dev/.env and a
                  placeholder dev/config.yaml), then wait for the services
  seed [opts]     create the dev users, tags, custom fields and sample data in
                  Gramps Web, Paperless-ngx and Immich; writes dev/config.yaml
                  and restarts Bifrost. Re-runnable. Options:
                    --example-tree   also import Gramps' example.gramps (2000+ people)
                    --no-immich / --no-paperless   skip a service
  status          service health, URLs and logins
  doctor          python -m bifrost.cli doctor inside the Bifrost container
  test            pytest inside the Bifrost container
  logs [service]  follow logs
  shell           bash inside the Bifrost container
  down            stop everything (data is kept)
  reset           stop everything and DELETE all dev data (asks first)
  fetch-photos    download public-domain sample photos with real faces into
                  dev/samples/photos (see fetch-sample-photos.sh), for Immich's
                  face recognition; run seed afterwards
  compose ...     raw docker compose passthrough for this stack
USAGE
}

env_get() { # env_get KEY DEFAULT  (reads dev/.env)
  local v
  v="$(grep -E "^$1=" .env 2>/dev/null | tail -1 | cut -d= -f2- || true)"
  printf '%s' "${v:-$2}"
}

host_tz() {
  local link
  link="$(readlink /etc/localtime 2>/dev/null || true)"
  case "$link" in
    *zoneinfo/*) printf '%s' "${link#*zoneinfo/}" ;;
    *) printf 'Etc/UTC' ;;
  esac
}

ensure_env() {
  if [ ! -f .env ]; then
    cp .env.example .env
    echo "wrote dev/.env from .env.example"
  fi
  if [ -z "$(env_get TZ '')" ]; then
    local tz; tz="$(host_tz)"
    sed -i.bak "s#^TZ=.*#TZ=$tz#" .env && rm -f .env.bak
    echo "dev/.env: TZ=$tz (from this Mac)"
  fi
}

ensure_dirs() {
  mkdir -p data/gramps/media \
           data/paperless/media/documents/originals data/paperless/export data/paperless/consume \
           data/immich/library/upload \
           data/boundaries data/bifrost samples/photos
}

ensure_config() {
  # Bifrost refuses to start without a config; the seed step replaces this
  [ -f config.yaml ] && return
  cat > config.yaml <<'YAML'
# placeholder written by bifrost-dev.sh; `bifrost-dev.sh seed` replaces it
gramps:
  base_url: "http://grampsweb:5000/api"
  username: "owner"
  password: "not-seeded-yet"
paperless:
  base_url: "http://paperless:8000"
  api_token: "not-seeded-yet"
database: data/bifrost/bifrost.db
places:
  boundaries_dir: "/boundaries"
YAML
  echo "wrote placeholder dev/config.yaml"
}

health() { # health SERVICE -> healthy|starting|unhealthy|none|missing
  local id
  id="$(docker compose ps -q "$1" 2>/dev/null || true)"
  [ -z "$id" ] && { echo missing; return; }
  docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$id" 2>/dev/null || echo missing
}

wait_healthy() {
  local deadline=$(( $(date +%s) + ${1:-900} )) svc all_ok
  echo "waiting for grampsweb, paperless, immich-server to report healthy (first start pulls images and initialises databases; this can take a few minutes)"
  while :; do
    all_ok=1
    for svc in grampsweb paperless immich-server; do
      case "$(health "$svc")" in healthy|running) ;; *) all_ok=0 ;; esac
    done
    [ "$all_ok" = 1 ] && return 0
    if [ "$(date +%s)" -ge "$deadline" ]; then
      echo "gave up waiting; current state:"; docker compose ps; return 1
    fi
    printf '  grampsweb=%s paperless=%s immich=%s\n' "$(health grampsweb)" "$(health paperless)" "$(health immich-server)"
    sleep 10
  done
}

probe() { # probe URL -> http status or 000
  curl -s -o /dev/null -m 5 -w '%{http_code}' "$1" || true
}

status() {
  docker compose ps --format 'table {{.Service}}\t{{.Status}}\t{{.Ports}}'
  local bind gp pp ip bp pw
  bind="$(env_get BIND_ADDRESS 127.0.0.1)"; [ "$bind" = 0.0.0.0 ] && bind=localhost
  gp="$(env_get GRAMPS_PORT 5555)"; pp="$(env_get PAPERLESS_PORT 8000)"
  ip="$(env_get IMMICH_PORT 2283)"; bp="$(env_get BIFROST_PORT 8800)"; pw="$(env_get DEV_PASSWORD bifrost-dev)"
  echo
  printf '  %-14s %-28s http %s   login %s\n' "Bifrost"   "http://$bind:$bp"  "$(probe "http://$bind:$bp/healthz")" "(none)"
  printf '  %-14s %-28s http %s   login %s\n' "Gramps Web" "http://$bind:$gp" "$(probe "http://$bind:$gp/api/metadata/")" "owner / $pw"
  printf '  %-14s %-28s http %s   login %s\n' "Paperless"  "http://$bind:$pp" "$(probe "http://$bind:$pp/api/")" "admin / $pw"
  printf '  %-14s %-28s http %s   login %s\n' "Immich"     "http://$bind:$ip" "$(probe "http://$bind:$ip/api/server/ping")" "owner@bifrost.dev / $pw  (also partner@bifrost.dev)"
  echo
  if grep -q not-seeded-yet config.yaml 2>/dev/null; then
    echo "dev/config.yaml is the placeholder: run '$(basename "$0") seed' to create users, tags, fields and sample data"
  fi
}

cmd="${1:-}"; shift || true
case "$cmd" in
  up)
    ensure_env; ensure_dirs; ensure_config
    docker compose up -d --build "$@"
    wait_healthy || true
    status
    ;;
  seed)
    ensure_env; ensure_dirs; ensure_config
    if printf '%s\n' "$@" | grep -qx -- '--example-tree' && [ ! -f samples/example.gramps ]; then
      echo "copying example.gramps out of the grampsweb image"
      docker compose cp grampsweb:/venv/share/doc/gramps/example/gramps/example.gramps samples/example.gramps
    fi
    docker compose run --rm --build seed python dev/seed/seed.py "$@"
    echo "restarting bifrost with the new dev/config.yaml"
    docker compose up -d --force-recreate --no-deps bifrost
    ;;
  status)   status ;;
  doctor)   docker compose exec bifrost python -m bifrost.cli doctor ;;
  test)     docker compose exec bifrost python -m pytest -q "$@" ;;
  logs)     docker compose logs -f --tail=100 "$@" ;;
  shell)    docker compose exec bifrost bash ;;
  down)     docker compose down "$@" ;;
  reset)
    echo "This deletes the dev containers, named volumes and everything under dev/data (trees, documents, photos) plus dev/config.yaml."
    printf 'Type yes to continue: '; read -r ans
    [ "$ans" = yes ] || { echo "aborted"; exit 1; }
    docker compose down -v --remove-orphans
    rm -rf data config.yaml
    echo "reset done; '$(basename "$0") up' starts fresh"
    ;;
  fetch-photos) ./fetch-sample-photos.sh ;;
  compose)  docker compose "$@" ;;
  ""|-h|--help|help) usage ;;
  *) echo "unknown command: $cmd" >&2; usage >&2; exit 2 ;;
esac
