# Agent-Assisted Development Record

This project was built and verified with AI coding-agent assistance in the shared workspace. The repository does not contain committed agent transcript files, and `git log` reports no commits, so this document does not reproduce exact prompt/response conversations. The table below summarizes tasks that are evidenced by the current source tree, tests, configuration, and recorded implementation work.

| Task | Agent direction | Implementation/result | Verification |
| --- | --- | --- | --- |
| Backend/session API | Implement the FastAPI session and message foundation without breaking the existing API shape. | Session and message routes use SQLAlchemy models and PostgreSQL persistence; chat uses session-scoped history. | Existing session isolation and chat facade tests; application import check. |
| Transcript ingestion | Make local transcript ingestion reproducible, portable, idempotent, and refreshable. | `backend/scripts/ingest_transcripts.py` supports `--source-dir` and `TRANSCRIPT_SOURCE_DIR`, stores portable paths, refreshes changed records, and skips malformed files without stopping. | Four focused ingestion tests plus the full unittest suite. |
| Retrieval | Preserve PostgreSQL English full-text behavior and improve its indexing. | Retrieval keeps `websearch_to_tsquery`, `ts_rank`, descending rank, and limits; an Alembic migration adds the expression GIN index. | Retrieval contract tests, live PostgreSQL retrieval verification, and migration application. |
| Agent facade | Integrate local and Claude execution behind the existing facade with explicit provider selection. | `AGENT_BACKEND=local` uses direct retrieval plus the LLM service; `AGENT_BACKEND=claude` uses the Claude Agent SDK path and restricted MCP tools. | Agent selection/configuration tests and Claude option restriction tests. Real Claude execution was not claimed. |
| Ship 30 for 30 skill | Add a dedicated writing capability without treating its guidance as Lenny evidence. | Matching requests route through the Ship 30 for 30 instructions/tool path while transcript excerpts remain the factual source. | Skill principles, grounding, prompt-routing, and restricted-tool tests. |
| Artifact generation | Add explicit Markdown/HTML artifact generation through the agent facade. | Artifact detection is conservative; results include type, title, content, and retrieved sources. HTML is untrusted and handled as text by the backend. | Artifact detection, structure, retrieval-context, and HTML non-execution tests. |
| Frontend MVP | Build the actual conversational UI and Artifact Viewer around the existing API contracts. | React/Vite app provides sessions, chat, follow-ups, sources, Markdown rendering, sandboxed HTML preview, Copy, Show source, loading/errors, and responsive layout. | Frontend lint/build; browser checks for startup, session creation, provider visibility, new conversation, and responsive empty state. |
| CORS/API origin fix | Resolve local browser calls between Vite and FastAPI. | FastAPI explicitly allows localhost/127.0.0.1 on ports 5173 and 5174; frontend API configuration remains centralized. | Live CORS preflight checks for both 5174 origins and frontend build. |
| Citation integrity | Prevent model-created source metadata from becoming authoritative. | Valid `SOURCE N` references are bounded, deduplicated, and mapped only to retrieved source objects; invalid numbers are ignored. | Elena Verna/Casey Winters regression tests, artifact source tests, and full suite. |
| PostgreSQL GIN index | Add a matching full-text expression index without changing retrieval semantics. | Migration `3f6e9c2a1b7d...` creates `ix_transcript_chunks_content_fts` on `to_tsvector('english', content)`. | `alembic upgrade head`, PostgreSQL metadata inspection, retrieval contract test, and full suite. |
| Reproducible ingestion | Remove machine-specific source paths and support refresh from a clean checkout. | Portable `episode-folder/transcript.md` paths, source-directory configuration, legacy-path normalization, and update-in-place chunks. | Focused ingestion tests and full suite. |
| Structured logging/failure handling | Add simple production-oriented observability without logging secrets or prompts. | Standard-library structured logging covers LLM, retrieval, agent, artifact, and database events; safe 503 handling and rollback were added. | Focused failure/log-safety tests and full suite. |
| Product/design documentation | Document the actual product, UX, architecture, and limitations. | `PRD.md`, `design.md`, and `architecture.md` describe current behavior without production or research claims. | Documentation review, full backend suite, and diff checks. |
| Docker/Compose | Add a one-command container definition without requiring local Docker execution. | Compose defines PostgreSQL, Ollama, backend, and frontend/Nginx; migrations run before Uvicorn; named volumes and health checks are included. | YAML parsing, referenced-file checks, backend tests, frontend lint/build, and diff check. Docker build/up was not executed because Docker CLI was unavailable. |

## Verification philosophy

AI-assisted changes were reviewed against the implementation surface and validated with the cheapest relevant checks:

- **Automated backend tests:** Python `unittest discover` covers sessions, isolation, agents, retrieval, citations, artifacts, ingestion, the search index contract, Ship 30 for 30, and failure handling.
- **Application import checks:** `from app.main import app` verifies the FastAPI application can load with the configured environment.
- **Frontend checks:** `npm run lint` and `npm run build` validate the Vite/TypeScript frontend.
- **Database checks:** Alembic migration execution, PostgreSQL index metadata inspection, and a live retrieval query were performed for the local database.
- **Diff checks:** `git diff --check` was run after implementation/documentation changes.
- **Manual browser verification:** the frontend was opened during implementation. The app loading, session creation, provider/model visibility, New Conversation behavior, and responsive empty state were observed. Model-dependent response/artifact scenarios should still be rerun by an evaluator with PostgreSQL and Ollama running.

Automated tests establish repeatable behavior; they do not replace live-provider, browser, or Docker verification. No real Claude Agent SDK execution was claimed, and Docker execution was not available locally.

## Important agentic architecture

The implemented agent facade is in `backend/app/services/agent.py`:

- **Local path:** retrieves transcript chunks directly, builds grounded context, and calls the configured OpenAI-compatible LLM service. The current demo configuration uses Ollama.
- **Claude path:** uses the Claude Agent SDK with a restricted MCP transcript-search tool. Unrestricted tools such as filesystem and shell capabilities are disabled in the Claude options.
- **Retrieval/tool restrictions:** transcript excerpts are the factual evidence boundary. Conversation history is context only, and Ship 30 for 30 writing guidance is not evidence about Lenny's Podcast.
- **Ship 30 for 30 routing:** matching requests enable the dedicated writing capability while Lenny-related factual claims remain grounded in retrieved excerpts.
- **Provider selection:** `AGENT_BACKEND` selects the local or Claude path explicitly. There is no silent provider fallback.

The Claude path and its configuration are implemented and tested at the facade/options level, but no claim is made that a real Claude request was executed during this work.
