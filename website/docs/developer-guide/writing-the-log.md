# Writing the Developer Log

Use the log for a meaningful decision, investigation result or implementation
milestone. Write a concise public account with the problem, decision, evidence,
limitations and next steps. Keep current operating instructions in the Developer
Guide and released changes in the Changelog.

## Add an entry

1. Create `website/docs/developer-log/YYYY-MM-DD-short-id.md` with one descriptive H1.
2. Add a record to `website/content/developer-log.json` using the same date and ID.
3. Choose a few existing tags where possible. Use lowercase words joined with hyphens for new tags.
4. Add `related` entry IDs for direct follow-ups or decisions that explain the context.
5. Build and check the site, then review the entry, log index and topic pages on desktop and mobile.

Example metadata:

```json
{
  "id": "example-decision",
  "slug": "developer-log/2026-11-18-example-decision",
  "date": "2026-11-18",
  "tags": ["documentation", "website"],
  "summary": "A short description of the decision and its effect.",
  "related": ["documentation-home"]
}
```

The builder generates the chronological index, clickable tags, topic pages and
related links from this metadata. The same entries remain searchable through site
search. Topic pages work without JavaScript and have stable, shareable URLs.

## Dates and follow-ups

Use the decision or milestone date. If reconstructing an older event, state when
the note was written and cite the repository record. Do not invent historical
conclusions. Correct small factual errors in place; use a new dated entry for a
changed decision and link both entries so the progression is clear.

## Public discussion summaries

Tags connect published notes; they do not import private chats or Todoist discussions.
Only include a discussion summary when authorised for publication. Link to a public
issue or pull request if one exists, omit personal names and private machine details,
and distinguish proposals from implemented or validated behaviour.
