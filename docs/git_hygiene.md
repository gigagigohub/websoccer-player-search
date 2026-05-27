# Git Hygiene

Use Git for reproducible project state, not for every local artifact.

## Commit

- Site JSON and other files that are intentionally published.
- Scripts that are reused by updates, automation, or analysis.
- Runbooks and README updates that future runs depend on.
- Focused bug fixes and data-processing logic changes.
- Analysis outputs only when they are curated project artifacts.

## Keep Local

- Tokens, cookies, gate keys, User-Agent values, and other secrets.
- Charles sessions, logs, virtual environments, and machine-specific state.
- One-off HTML, CSV, notebook, or image outputs made during exploration.
- Intermediate reports that are useful during a chat but not part of the site.

Put local analysis outputs under:

```text
app/prepared/local/
```

Use this for broader scratch work:

```text
local/
tmp/
artifacts/
```

Before committing, prefer:

```bash
git status --short
git add path/to/intentional-file
```

Avoid `git add .` unless the status has been reviewed and every file is intentional.
