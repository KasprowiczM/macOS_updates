# Public source maintenance

The public Git history was sanitized to remove local development captures, machine-generated inventories, and local agent settings. Branch and release-tag names are retained, while commit identifiers differ from older clones. Public authorship and the project license remain.

Use a fresh clone in a separate directory after a history migration. Do not merge older unsanitized branches into the public history. Existing clones may have release tags that point to older commits; preserve local work and use a fresh clone instead of replacing tags in place.

Generated inventories, session logs, local settings, and development captures stay outside tracked source. Ignore rules do not prevent forced additions. Review staged files and audit all refs before publication. History rewriting alone cannot establish that a hosting provider has removed cached objects.
