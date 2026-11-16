# Using Bifrost

## Photos

| To | Do this |
| --- | --- |
| Add a photo to Gramps | Add → pick the photo → fill in at least one field → Save |
| See only one Immich account's photos in Add | With two accounts → Add → pick the account at the top |
| Add many photos without opening each one | Tag them `Sync/Gramps` in Immich → Sync everything |
| Change a photo's details | Click row → edit → Save |
| Keep several scans of one photo | Open it → Versions → Add version → Pick another Immich photo or upload a file |
| Associate Immich Faces with Gramps people | Faces → choose an Immich person and a Gramps person → Link → then Sync everything |

### The editor

| Field | Where it goes |
| --- | --- |
| Title | The media title in Gramps and the photo's description in Immich |
| Code | The Gramps ID you want to use for this media object. Or leave it empty for a new random code |
| Date | The media date to display in Gramps. About, Before, After, Decade or Span, and Estimated or Calculated |
| Place | Link a photo to a Gramps place |
| Link | A `Source URL` attribute on the media if this image was downloaded from somewhere |
| Notes | A `Media Note` on the media for any additional information |

### Versions

Photo versions are saved as an Immich stack. However, Gramps will only display the main image.

| Action | Result |
| --- | --- |
| Add version | The other photo joins the stack and takes this photo's tags, location and faces |
| Make main | Gramps switches to that file |
| Match to main | Copies the main image's tags, location and faces again |
| Remove from versions | Takes it out of the stack and removes its sync and ID tags |

## Documents

Documents are edited in Paperless.

| To | Do this in Paperless |
| --- | --- |
| Add a document to Gramps | Give it a sync tag |
| Change its title, date or mirrored fields | Edit the document |
| Choose its code yourself | Type the code into the Gramps ID field before the first sync |
| Transcribe it | Give it the OCR tag |
| Add a translation | Put it in the content after a line reading `======== ENGLISH TRANSLATION ========` or whatever `paperless.translation_marker` is set to |

A document with the transcribed tag gets its content as a `Transcription` note in Gramps, and what follows the translation line as a `Translation` note.

## Codes

By default, every media object Bifrost adds gets a six-character code as its Gramps ID, for example `KHKWZY`. The purpose for this is six characters from an alphabet without look-alikes (no I, L, O, 0 or 1) keep it quick to write and type by hand without misreading, and unlike Gramps’ own O0001 numbers it does not depend on any one system’s counter. If you prefer to not use this system, set `codes: false` in config.yaml so new media gets Gramps' own next ID instead.

| Action | Result |
| --- | --- |
| Delete | Removes the media object and its transcription, translation and media notes from Gramps, and stops syncing its photo or document. The file remains in Immich or Paperless |
| Merge | Pick the other item, then the one to keep. Everything in Gramps that shows the other moves to the kept one, the other is deleted, and its ID is recorded on the kept one as a `Merged Gramps ID` attribute |
| Deleting in Gramps | The next sync stops syncing that photo or document instead of adding it again |

To sync a deleted item again, tag it again in Paperless or add it again from Immich. It will get a new code.

## What Bifrost writes

| In | What |
| --- | --- |
| Gramps | Media objects with the attributes `Immich ID`, `Immich URL`, `Paperless ID`, `Paperless URL`, `Source URL`, `Merged Gramps ID` and the mirrored Paperless fields. `Transcription`, `Translation` and `Media Note` notes. Face boxes on people, and an `Immich Person ID` attribute on linked people. Photos in place galleries |
| Immich | The `ID/<code>` tag, the description, stacks, uploaded versions, a small link record on the photo, and tags, location and faces copied between versions. On Delete, the `Sync/Gramps` and `ID/` tags are removed |
| Paperless | The Gramps ID and Gramps URL fields, and the content and tags of transcribed documents. On Delete, the two fields are emptied and the sync tags removed |