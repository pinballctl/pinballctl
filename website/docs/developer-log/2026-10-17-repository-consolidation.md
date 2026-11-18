# Bringing the companion projects together

This historical note was reconstructed on 18 November 2026 from the repository's
maintainer import record. Its date describes the import, not the current deployment setup.

## Decision and result

Import the backglass, website and documentation projects into the controller
repository while keeping their original commits as merge parents. The controller
source layout remains intact; companion projects get dedicated directories.

| Imported directory | Original repository | Recorded imported commit |
| --- | --- | --- |
| `backglass/` | [pinballctl-backglass](https://github.com/pinballctl/pinballctl-backglass) | `c1892168d6d3ea92e2fcd24f65da05de405115f6` |
| `website/` | [pinballctl-website](https://github.com/pinballctl/pinballctl-website) | `c36821dc5360493825e70e6bb2f8f2db086faa4b` |
| `docs/` | [pinballctl-docs](https://github.com/pinballctl/pinballctl-docs) | `3bdc75c5f48bff4543d6c3499ca58ed038c64be0` |

The record states that each source repository had only `main`, no tags and a clean
working tree at import. Original commit history remains available. Paths before
the import are relative to each original repository root; inspect them with
`git log <imported-commit>` or `git show <imported-commit>:<original-path>`.

## Boundary at the time

The import initially kept the original website repositories serving their domains.
Rendered site files were retained as a transition baseline. Domain migration,
website redesign and integrating the manual were separate work.

That deployment description is historical. The current website is hosted on
GitHub Pages through this repository's workflow. Read the
[current website guide](../developer-guide/website.md) for build and deployment.
The later documentation cleanup replaces the transitional layout while retaining
the engineering workspace and existing public links.
