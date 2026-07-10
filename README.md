<p align="center">
  <picture>
    <img src="bifrost/web/static/favicon.svg" width="15%">
  </picture>
</p>

# Bifrost

Bifrost is a curation console for connecting Gramps Web to other services. Think of it as a companion web app for a Gramps Web family tree. Gramps holds people, families, events, places, sources, and media, but what if your files live elsewhere? Bifrost connects other services, like Paperless-ngx (a document management system for scans), to Gramps and lets you bring their content in. Now, you don't need to have several copies of the same file scattered across several different services.

Bifrost is also a citation-generating assistant. The citation and transcription features are powered by AI models which provide you with an initial rough draft. 

Bifrost's memory lives in Gramps and the source systems, so nothing important depends on Bifrost's own database. It can be deleted without any consequences on your data.

# Features

* Sync documents in Paperless-ngx to Gramps Web as media objects; their versions, titles, dates, and transcription text are kept up to date
    * Paperless now lets a document have multiple versions and serve whichever you select. Bifrost notices when the selected version changes and repoints the Gramps media to it so Gramps always shows the version you picked.
* Draft properly formatted genealogical source citations
* Old handwriting and faded print often defeat regular OCR. Bifrost sends the page to an AI model and writes the transcription back into Paperless, so the document becomes searchable everywhere.
* Rebuild a Paperless PDF so every page shares the same width
* Give places boundaries on the minimap


# Feature Requests

Feature requests can be submitted by creating a new issue and tagging it as a new feature request.
