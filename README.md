# Django 6.1 with Python 3.14: the code

Companion code for the book *Django 6.1 with Python 3.14*, by Franky Bonanno.
Each chapter has its own folder, and each project has its own `pyproject.toml` and `uv.lock`.
There is a git tag for each chapter (`ch01` … `ch11`, plus `appendix-a`): check out a tag to see the
repository exactly as it is at the end of that chapter.

Every result in the book was obtained with Python 3.14.6, Django 6.1.2 and PostgreSQL 18.6
(pgvector 0.8.x). If something does not work, check the versions first.

| Folder | Chapter | What it is |
|---|---|---|
| `ch01/` | 1. Python 3.14 and uv | The small programs of the chapter (t-strings, zstd, uuid7, annotations, subinterpreters, except without parentheses) |
| `ch02/taskmanager/` | 2. The first project | Task manager (SQLite) |
| `ch03/blog/` | 3. PostgreSQL and full-text search | Blog (PostgreSQL) |
| `ch04/address-book/` | 4. HTMX | Address book (SQLite) |
| `ch05/shop-project/` | 5. A shop with an interactive cart | Shop (SQLite) |
| `ch06/semantics/` | 6. Embeddings and search by meaning | Sentences with pgvector |
| `ch07/kb/` | 7. A knowledge base that answers | Knowledge base (PostgreSQL + pgvector) |
| `ch08/postbox/` | 8. Background jobs | Mail campaigns with tasks |
| `ch09/saas/` | 9. A multi-tenant helpdesk | Helpdesk (PostgreSQL) |
| `ch10/vault/` | 10. DjangoVault | Document management system |
| `ch11/vault/` | 11. From laptop to server | DjangoVault with tests, CI, Docker and deployment |
| `appendix-a/` | Appendix A | The probe project used to check the Django 5.2 → 6.0 → 6.1 upgrade |

## Quick start

You need [uv](https://docs.astral.sh/uv/) (it installs Python 3.14 for you). For one project:

```bash
cd ch02/taskmanager
uv sync --locked
uv run pytest
```

Chapters 3 and 6 to 10 need PostgreSQL 15 or later (the book uses 18) with the `vector` extension
available (chapters 6, 7 and 10). Install PostgreSQL as shown in Chapter 3, then create all the roles
and databases at once:

```bash
./scripts/create-databases.sh
```

The script is safe to run more than once. If your PostgreSQL listens on a different port, set `DB_PORT`
(and `DB_PASSWORD` where the chapter's settings read it), as the chapter explains.

Chapter 11 runs in Docker: see `ch11/vault/README.md`. Copy `.env.example` to `.env` and fill it in first.
The file `.github/workflows/ch11.yml` is the Chapter 11 CI workflow adapted to this repository, where each
chapter lives in its own folder.

## Notes

- Never commit a real `.env` file. The repository holds only `.env.example`.
- The embedding model of chapters 6 and 7 (about one gigabyte) is downloaded the first time it is needed
  into a `.models/` folder, which `.gitignore` excludes.
- The code is released under the MIT licence (see `LICENSE`). It covers the code in this repository only: the text of the book remains under the author's copyright.
