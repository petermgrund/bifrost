# Sample photos

Drop a few JPEG/PNG/HEIC files here and run `dev/bifrost-dev.sh seed`, it uploads 
them to the Immich dev owner account, tagged `Sync/Gramps`. A leading `YYYY-` in the file
name (for example `1923-farm.jpg`) sets the photo's date and adds `Sync/Date`
plus `Date/Year`, so the synced Gramps media gets a year-only date.

The seed also generates its own vintage-style test images but those contain no
faces. `dev/bifrost-dev.sh fetch-photos` downloads seven public-domain family
portraits from Wikimedia Commons so Immich's face detection, and
Bifrost's face linking, have something real to work with.
