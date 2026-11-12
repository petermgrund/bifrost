<p align="center">
  <picture>
    <img src="bifrost/web/static/favicon.svg" width="15%">
  </picture>
</p>

# Bifrost

Bifrost is a curation console for connecting Gramps Web to other services. Think of it as a companion web app for a Gramps Web family tree. Gramps holds people, families, events, places, sources, and media, but what if your files live elsewhere? Bifrost connects other services, like Paperless-ngx, Immich and copyparty, to Gramps and lets you bring their content in. Now, you don't need to have several copies of the same file scattered across several different services.

Your family-tree data itself always lives in Gramps, and documents/photos/videos remain within their respective source system. Bifrost will never become the home of any of your files, and it keeps no database of its own.

# Features

* Add Immich photos in the Photos editor to add them to Gramps as media objects. You can edit the title, date, place, notes and web links. Changes you make to your Immich photos will then stay synced in Gramps.
* Link Immich's face recognition to Gramps people by pairing each recognized face with its Gramps person once. Then, every synced photo going forward gets face boxes in Gramps.
* Sync documents in Paperless-ngx to Gramps Web and keep their versions, titles, dates, and transcription text up to date. Chosen custom fields are mirrored as attributes on the media object in Gramps.
* Old handwriting and faded print often defeat regular OCR. Tag a document in Paperless and Bifrost sends the page to an AI model and writes the transcription back into Paperless and Gramps.
* Sync the files in a copyparty folder (audio and anything else Paperless and Immich don't take) to Gramps Web as media objects. A file named with a code takes that code, or is linked from the media object that already has it.

Developer's comment: I am developing Bifrost to assist me in my genealogical documentation workflow. Therefore, you may not be interested in using all of the features. Feel free to pick and choose which tools you'd like to use. At a minimum, you need to configure Gramps Web and Paperless-ngx.

# Running Bifrost

Copy `config.example.yaml` to `config.yaml` and fill it in. Make sure you create the necessary custom fields in Paperless and Immich first. Then, depending on your installation preference:

* Docker: edit the host-side bind mounts in `docker-compose.yml` to match your machine. Then `docker compose up -d --build`. Create `config.yaml` before the first `compose up`.
* Paperless pushes changes to Bifrost through a custom workflow.
* copyparty pushes changes to Bifrost through its `xau`, `xar` and `xad` hooks running `dev/copyparty/bifrost-hook.py` (see `dev/copyparty/copyparty.conf`). Mount the copyparty folder read-only into Gramps' media folder at `sync.copyparty.path_mappings[].gramps_prefix`.
* `python -m bifrost.cli doctor` checks the Gramps, Paperless, Immich and copyparty connections.

At the moment Bifrost has no authentication. Keep it on a trusted network, bind it to localhost, or put an authenticating reverse proxy in front.

# Feature Requests

Feature requests can be submitted by creating a new issue and tagging it as a new feature request.