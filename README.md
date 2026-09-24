# GroundedSearch

A Perplexity-style research engine, built backend-first: it plans web searches,
reads the pages it finds, and answers the question with citations back to the
sources it actually used.

The point of the project was to build the machinery rather than call a framework,
so there is no LangChain, no LlamaIndex and no ORM — the RAG pipeline, the SQL and
the job handling are all written out.

## What it does

`POST /api/v1/research` with a question returns a job id immediately. A worker
then runs the pipeline, and `GET /api/v1/research/{job_id}` reports progress
until the answer is ready.

```
question
  │
  ├─ 1. Gemini turns it into 3-5 search queries        → search_queries
  ├─ 2. Brave searches all of them concurrently        → sources
  ├─ 3. each page is fetched and stripped to article text (Trafilatura)
  ├─ 4. that text is split into passages and embedded  → chunks (pgvector)
  ├─ 5. the question retrieves the nearest passages, capped per source
  └─ 6. Gemini answers from those passages with [n] markers
                                                       → research_jobs.answer
```

A few decisions worth knowing, because they are where the interesting parts are:

- **Every step writes to the database before the next begins.** The job row and
  its children *are* the progress, which is what makes `GET` useful while a job
  is still running and why the pipeline function takes only a job id.
- **Failure policy differs per step, on purpose.** A failed Brave search fails the
  job, because the evidence would be incomplete. A failed page fetch does not —
  paywalls and bot blocks are normal, and roughly half of pages fail in practice.
  The job only fails if no page was readable.
- **Citations are structural, not parsed back out of the text.** The numbering is
  assigned once, before generation, from the same ordered list that builds the
  prompt and writes `sources.citation_number`. `[2]` in the answer therefore
  always refers to a real row.
- **Postgres is both the relational store and the vector store**, through pgvector
  and a hand-written `<=>` query. No separate vector service.
- **No retries.** A failed job stays failed rather than spending another job's
  worth of API credits. Jobs stranded by a dead worker are failed on age by a
  cron sweep inside the worker.
- **Page text is untrusted input.** The answer prompt says so explicitly, since
  arbitrary web pages end up inside it.

## Tech stack

| | |
|---|---|
| Language | Python 3.13, fully async |
| API | FastAPI, Uvicorn, Pydantic |
| Database | PostgreSQL 17 + pgvector, psycopg 3 with `AsyncConnectionPool`, raw SQL |
| Migrations | yoyo-migrations, plain `.sql` files |
| Jobs | arq + Redis, running in a separate worker process |
| LLM | Gemini (`gemini-3.1-flash-lite` for text, `gemini-embedding-001` at 768 dimensions) |
| Search and retrieval | Brave Search API, httpx, Trafilatura |
| Tooling | uv, pytest, Ruff, Pyright, Docker Compose |

## Running it

You need Docker, [uv](https://docs.astral.sh/uv/), a
[Google AI Studio](https://aistudio.google.com/apikey) key and a
[Brave Search API](https://brave.com/search/api/) key (both have free tiers).

```bash
cp .env.example .env          # then fill in the two API keys
uv sync                       # install dependencies
docker compose up -d          # Postgres, Redis and the job worker
make migrate                  # create the tables
make dev                      # the API on http://localhost:8000
```

Then ask it something:

```bash
curl -X POST localhost:8000/api/v1/research \
  -H 'content-type: application/json' \
  -d '{"query": "Is Rust replacing C++ for systems programming?"}'
# {"id":"409e4d74-...","status":"pending"}

curl localhost:8000/api/v1/research/409e4d74-...
```

A job takes 30-60 seconds. While it runs, `GET` fills in progressively: the
search queries appear first, then the sources, then the answer.

Interactive API docs are at `http://localhost:8000/docs`, and the worker's log is
`docker compose logs -f worker`.

**While changing pipeline code**, run the worker from source instead, so edits
take effect without rebuilding the image:

```bash
docker compose up -d db redis     # just the services
make worker                       # the worker, from your working tree
```

## Development

```bash
make test          # 64 tests; no network or database access
make test-live     # one real end-to-end job (spends API credits)
make coverage      # same as make test, with a report
make all           # lint, type check, test
```

Unit tests block outbound connections, so a test that forgets to patch an
external call fails loudly instead of quietly spending credits. Tests that need
a real database live in `tests/integration/`.

## Layout

```
app/
├── api/         HTTP only: routes, request and response models
├── agents/      run_research — the pipeline, start to finish, no HTTP
├── db/          every SQL statement in the project
├── llm/         Gemini calls, prompts, response models
├── retrieval/   chunking, embeddings, vector retrieval, per-source capping
├── search/      Brave client
├── web/         page fetching and text extraction
├── queue.py     Redis connection and enqueueing
└── worker.py    the arq worker and its cron sweep
```

`PLAN.md` holds the original design, `ROADMAP.md` what is and is not built.

## Licence

[MIT](LICENSE)
