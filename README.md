# DAViCal export

Export all DAViCal collections to the export folder. Each collection of each
user is stored as its own .ics/.vcf file. Those collections can then be imported
into other DAV stores likee .g. Nextcloud. Make sure the target directory is
writable by the user running the script (usually postgres).,

One file per user and collection is exported, by default into the folder
"/tmp/dav-export". This can be changed using the `--target-dir` parameter.
Calendars (`VCALENDAR`) and events (`VTODO`, `VEVENT`, `VJOURNAL`) are stored as `.ics`
files. Contacts are stored as `.vcf` files. Each files is named
`<user>-<collection>.<extension>`.

Since DAViCal wraps each event entry with an extra `VACALENDAR` entry, the event
entry is unwrapped and exported directly. The extra `VCALENDAR` data is
discarded.

Run this script as a user that can connect to the database (e.g. postgres).

This software is provided as-is and is licensed under the GPLv3 license.
