# ChatGPT data export

The extension only archives conversations that are opened in the browser.
Missing ones can be fetched from the official export: ChatGPT → Settings →
Data controls → Export data, download the ZIP from the mail, then:

```bash
polaris import-export ~/Downloads/<export>.zip --since 2026-09-14 --dry-run   # show
polaris import-export ~/Downloads/<export>.zip --since 2026-09-14             # import
```

Only project conversations (`gizmo_id` = `g-p-...`), only the current branch;
existing messages are skipped. Projects without a mapping are reported
(`polaris map <id> <folder>`). The curator then processes the new material
day by day as usual.

**Old chats as readable Markdown, without curation.** For large amounts of
old chats, curation is expensive and skews the weighting. `archive-export`
files them as Markdown instead; nothing goes to `raw/`, the curator ignores
them:

```bash
polaris archive-export ~/Downloads/<unpacked-export>/ --since 2025-10-02 --min-turns 6 \
    --project Customer-A --project Customer-B --dry-run
```

Result: `<project>/ChatGPT-Archiv/<YYYY-MM-DD> <title>.md` (front matter with
chat ID, period, `kuratiert: nein`) and
`ChatGPT-Archiv/Dateien/<chat>/<original name>`. Branched chats refer to the
original chat for the shared history. `.pst/.mbox/.zip` are only noted;
uploaded files missing from the export are linked to a file of the same name
in the project folder if there is one. Repeatable (already filed chat IDs are
skipped). Single chats can be curated later by moving them into `inbox/`.

---

[Back to the README](../README.md)
