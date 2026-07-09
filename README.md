<p align="center">
  <picture>
    <img src="bifrost/web/static/favicon.svg" width="20%">
  </picture>
</p>

# Bifrost

Bifrost is a curation console for connecting Gramps Web to other services. Think of it as a companion web app for a Gramps Web family tree. Gramps holds people, families, events, places, sources, and media, but what if your files live elsewhere? Bifrost connects other services, like Paperless-ngx and Immich, to Gramps and lets you bring their content in. Now, you don't need to have several copies of the same file scattered across several different services.

Bifrost is also a citation-generating assistant. Crafting consistant citations can be one of the most tedious and time-consuming aspects of genealogy.

Bifrost's memory lives in Gramps and the source systems, so nothing important depends on Bifrost's own database. It can be deleted without any consequences on your data.

# Features

* Sync documents in Paperless-ngx to Gramps Web as media objects; their versions, titles, dates, and transcription text are kept up to date
    * Paperless now lets a document have multiple versions and serve whichever you select. Bifrost notices when the selected version changes and repoints the Gramps media to it so Gramps always shows the version you picked.
* Draft properly formatted genealogical source citations
* Transcribe handwriting, old print, and photographed records that Paperless-ngx's OCR can't make sense of
* Rebuild a Paperless PDF so every page shares the same width
* Give places boundaries on the minimap


# Feature Requests

Feature requests can be submitted by creating a new issue and tagging it as a new feature request.

# Development

Bifrost consolidates several independent scripts intended to sync Gramps Web to Paperless-ngx, Immich, and OSM; as well as to be a genealogical citation generator. 