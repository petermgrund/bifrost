# Bifrost dev stack

## Quick start

```bash
dev/bifrost-dev.sh up
dev/bifrost-dev.sh seed
```

Then open `http://<PUBLIC_HOST>:8800` from any machine on the LAN.

| Service | URL | Login |
| --- | --- | --- |
| Bifrost | `http://<PUBLIC_HOST>:8800` | none |
| Gramps Web | `http://<PUBLIC_HOST>:5555` | `owner` / `bifrost-dev` |
| Paperless-ngx | `http://<PUBLIC_HOST>:8000` | `admin` / `bifrost-dev` |
| Immich | `http://<PUBLIC_HOST>:2283` | `owner@bifrost.dev` or `partner@bifrost.dev` / `bifrost-dev` |

| `dev/.env` | |
| --- | --- |
| `BIND_ADDRESS` | `0.0.0.0` listens on the LAN, `127.0.0.1` on this Mac only |
| `PUBLIC_HOST` | the name the services link each other by; `up` fills in this Mac's Bonjour name (`localhost` when bound to `127.0.0.1`); run `seed` after changing it |

## Commands

`dev/bifrost-dev.sh` with no arguments lists all options:

| Command | What it does |
| --- | --- |
| `up` | `docker compose up -d --build`, then waits for health and prints the URLs |
| `seed [--example-tree] [--no-immich] [--no-paperless]` | Seeds the services (re-runnable) and rewrites `dev/config.yaml`, then restarts Bifrost |
| `status` | Container health plus an HTTP probe of every service |
| `doctor` | `python -m bifrost.cli doctor` inside the Bifrost container |
| `test` | `pytest` inside the Bifrost container |
| `logs [service]` | Follow logs (`bifrost`, `grampsweb`, `paperless`, `immich-server`, ...) |
| `shell` | Bash in the Bifrost container |
| `down` | Stop; all data is kept |
| `reset` | Stop and delete every volume and `dev/data` (asks first) |
| `fetch-photos` | Download seven public-domain family portraits for face detection, then run `seed` again |
| `compose ...` | Anything else, e.g. `compose ps`, `compose pull` |

## Layout

```
dev/
  bifrost-dev.sh        driver script
  docker-compose.yml    the stack (project name bifrost-dev)
  Dockerfile            Bifrost dev image: prod deps + pytest, Pillow, piexif
  requirements-dev.txt
  .env.example          -> .env
  config.yaml           
  seed/seed.py          the seeding script
  seed/samples.py       generates the sample documents and photos
  samples/photos/       your real photos for Immich
  data/                 all persistent bind mounts:
    gramps/media/                     Gramps media base dir
    paperless/media/documents/originals -> Gramps /app/media/paperless (ro)
    immich/library/upload/            -> Gramps /app/media/immich (ro)
    bifrost/bifrost.db                Bifrost's database
    samples/                          the generated documents and photos
```