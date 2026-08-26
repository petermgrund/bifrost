<p align="center">
  <picture>
    <img src="bifrost/web/static/favicon.svg" width="15%">
  </picture>
</p>

# Bifrost

Bifrost is a curation console for connecting Gramps Web to other services. Think of it as a companion web app for a Gramps Web family tree. Gramps holds people, families, events, places, sources, and media, but what if your files live elsewhere? Bifrost connects other services, like Paperless-ngx, to Gramps and lets you bring their content in. Now, you don't need to have several copies of the same file scattered across several different services.

Bifrost is also a citation-generating assistant. The citation and transcription features are powered by AI models which provide you with an initial rough draft. 

Your family-tree data itself always lives in Gramps and the source systems. Bifrost never becomes the home of any of your files. Bifrost's own database holds the sync registers which record which photos and documents are already in Gramps.

# Features

* Sync Immich photos into Gramps as media objects. Tags in Immich drive it all: one tag marks a photo for sync, others carry its title and a fuzzy genealogical date (like about 1920 or before June 1955).
* Sync documents in Paperless-ngx to Gramps Web as media objects; their versions, titles, dates, and transcription text are kept up to date
    * Paperless now lets a document have multiple versions and serve whichever you select. Bifrost notices when the selected version changes and repoints the Gramps media to it so Gramps always shows the version you picked.
* Link Immich's face recognition to Gramps people: pair each recognized face with its Gramps person once, and every synced photo gets the right person links and face boxes including photos synced before the pairing was made
* Draft properly formatted genealogical source citations
* Old handwriting and faded print often defeat regular OCR. Bifrost sends the page to an AI model and writes the transcription back into Paperless, so the document becomes searchable everywhere.
* Rebuild a Paperless PDF so every page shares the same width
* Give places boundaries on the minimap


# Running Bifrost

Copy `config.example.yaml` to `config.yaml` and fill it in. Make sure you create the necessary custom fields in Paperless and Immich first. Then, depending on your installation preference:

* Dev: `python -m venv venv && venv/bin/pip install -r requirements.txt`, then `venv/bin/uvicorn bifrost.web.app:app --reload --port 8800`. The `BIFROST_CONFIG` env var overrides the config path.
* Docker: edit the host-side bind mounts in `docker-compose.yml` to match your machine. Then `docker compose up -d --build`. Create `config.yaml` before the first `compose up`.

`python -m bifrost.cli doctor` checks the database and the Gramps/Paperless connections. 

At the moment Bifrost has no authentication. Keep it on a trusted network, bind it to localhost, or put an authenticating reverse proxy in front.

# Feature Requests

Feature requests can be submitted by creating a new issue and tagging it as a new feature request.
