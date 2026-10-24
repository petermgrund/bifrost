<p align="center">
  <picture>
    <img src="bifrost/web/static/favicon.svg" width="15%">
  </picture>
</p>

# Bifrost

Bifrost is a curation console for connecting Gramps Web to other services. Think of it as a companion web app for a Gramps Web family tree. Gramps holds people, families, events, places, sources, and media, but what if your files live elsewhere? Bifrost connects other services, like Paperless-ngx and Immich, to Gramps and lets you bring their content in. Now, you don't need to have several copies of the same file scattered across several different services.

Your family-tree data itself always lives in Gramps, and documents/photos/videos remain within their respective source system. Bifrost will never become the home of any of your files. Bifrost's own database simply holds the sync registers which record which photos and documents are already in Gramps, and can be used to keep everything up to date and consistent across your genealogy ecosystem. 

# Features

* Describe Immich photos in the Photos editor to add them to Gramps as media objects. Title, date (fuzzy dates like about 1920 or before June 1955), place, notes and web links.
* Sync documents in Paperless-ngx to Gramps Web as media objects, and keep their versions, titles, dates, and transcription text up to date.
* Link Immich's face recognition to Gramps people by pairing each recognized face with its Gramps person once. Then, every synced photo gets face boxes in Gramps.
* Old handwriting and faded print often defeat regular OCR. Bifrost sends the page to an AI model and writes the transcription back into Paperless and Gramps.

Developer's comment: I am developing Bifrost to assist me in my genealogical documentation workflow. Therefore, you may not be interested in using all of the features. Feel free to pick and choose which tools you'd like to use. At a minimum, you need to configure Gramps Web and Paperless-ngx.

# Running Bifrost

Copy `config.example.yaml` to `config.yaml` and fill it in. Make sure you create the necessary custom fields in Paperless and Immich first. Then, depending on your installation preference:

* Dev: `python -m venv venv && venv/bin/pip install -r requirements.txt`, then `venv/bin/uvicorn bifrost.web.app:app --reload --port 8800`. The `BIFROST_CONFIG` env var overrides the config path.
* Docker: edit the host-side bind mounts in `docker-compose.yml` to match your machine. Then `docker compose up -d --build`. Create `config.yaml` before the first `compose up`.
* Paperless pushes changes to Bifrost through a workflow. Triggers Document added and Document updated, each filtered to documents with any of the sync tags or the transcription tag, action Webhook, URL `http://<bifrost>:8800/sync/api/paperless/webhook`, a parameter `doc_id` with value `{{doc_id}}`, and a header `X-Bifrost-Token` set to `sync.paperless.webhook_token`.
* `python -m bifrost.cli doctor` checks the database, the Gramps/Paperless connections and whether the register agrees with Gramps. `python -m bifrost.cli reconcile` lists the differences and `reconcile --apply` repairs the register.

At the moment Bifrost has no authentication. Keep it on a trusted network, bind it to localhost, or put an authenticating reverse proxy in front.

# API

`/api/v1/code/{code}` for a code's ledger entry and `/api/v1/export` for the ledger, collections and photo links.

# Feature Requests

Feature requests can be submitted by creating a new issue and tagging it as a new feature request.