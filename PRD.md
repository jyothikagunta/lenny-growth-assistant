# Product
Lenny Growth Assistant

## Problem
Product and growth practitioners often know that useful advice exists somewhere in Lenny's Podcast, but finding the right episode and connecting advice across hundreds of transcripts is slow. Lenny Growth Assistant provides a conversational interface for asking product, growth, startup, and leadership questions against a transcript knowledge base instead of requiring manual episode-by-episode search.

The product is intentionally transcript-grounded. It should be useful when the retrieved material supports an answer and explicit when the available evidence is incomplete.

## Target users
- **Product managers** looking for practical approaches to product discovery, prioritization, activation, retention, and team collaboration.
- **Growth practitioners** researching acquisition, onboarding, experimentation, funnels, metrics, and growth teams.
- **Startup and product leaders** looking for grounded perspectives on strategy, leadership, hiring, culture, and company building.

These are product assumptions for the take-home, not claims based on completed user research or market validation.

## User stories
- As a product manager, I can ask a product or growth question and receive an answer grounded in relevant transcript excerpts.
- As a practitioner, I can ask a follow-up question in the same session so recent conversation context is available.
- As a product leader, I can request a grounded product strategy document in Markdown.
- As a founder or marketer, I can request an HTML landing page artifact and preview it safely beside the conversation.
- As a writer, I can request a Ship 30 for 30-style essay using the dedicated writing guidance and transcript evidence.
- As a researcher, I can inspect the episode and guest sources attached to an answer or artifact.

## Success metric
**Primary metric: Grounded answer success rate.**

Percentage of evaluated answers where factual claims about Lenny's Podcast are supported by retrieved transcript material and the returned source metadata maps to the actual retrieved records.

This metric requires a future evaluation set or human review process. It has not been measured in production by this take-home.

Secondary metrics:
- **Response success rate:** successful chat responses divided by chat requests.
- **Artifact generation success rate:** artifact requests that return a structured Markdown or HTML artifact divided by explicit artifact requests.
- **Citation validity rate:** returned source references that are valid, in-range, deduplicated mappings to retrieved sources.
- **Latency:** time from chat request to response, including retrieval and model generation.

## Assumptions
- A local checkout of the transcript repository is available for ingestion, or its path is supplied through `TRANSCRIPT_SOURCE_DIR` or `--source-dir`.
- Users accept transcript-grounded answers and understand that the assistant will not fill unsupported gaps with general knowledge.
- Ollama and the configured local model are available for the local demo. Ollama is not bundled with the application.
- Cloud providers are optional. OpenAI is supported through the LLM abstraction when credentials are configured; the Claude Agent SDK path is selected separately through `AGENT_BACKEND`.
- PostgreSQL is available for sessions, messages, transcript records, chunks, and full-text retrieval.

## Scope
### In scope
- Session-based conversational chat through FastAPI and the React frontend.
- PostgreSQL-backed transcript retrieval using English full-text search.
- Deterministic mapping of model `SOURCE N` references to retrieved source metadata.
- Follow-up conversation history within a session.
- Markdown artifacts and complete HTML artifacts.
- Sandboxed HTML preview in the frontend Artifact Viewer.
- Local Ollama as the default demo path, plus the existing provider abstractions.
- Ship 30 for 30 writing guidance as a dedicated capability.
- Reproducible local transcript ingestion with portable paths, idempotent reruns, and update-in-place refresh.
- Structured logs and safe error responses for model, retrieval, artifact, and database failures.

### Out of scope
- User accounts, authentication, authorization, and multi-tenant data isolation beyond session separation.
- Semantic/vector retrieval, reranking, hybrid search, or automatic web search.
- Automatic transcript downloading or internet synchronization.
- File downloads, artifact persistence, artifact versioning, or collaborative editing.
- Production deployment, Docker, cloud infrastructure, billing, and operational dashboards.
- Claims of validated product-market fit or completed user research.

## Risks and tradeoffs
| Risk | Mitigation or tradeoff in the current implementation |
| --- | --- |
| Hallucinated facts or recommendations | Prompts require transcript-only factual support; empty retrieval receives an explicit insufficient-support statement. |
| Citation mismatch | The backend treats retrieved results as authoritative, bounds source numbers, deduplicates references, and copies only metadata from retrieval results. |
| Latency with local models | Ollama is supported for a self-contained demo, but local inference can be slow. LLM requests use a configurable timeout with a 180-second default and 30-second minimum. |
| Cloud cost | Cloud providers are optional and selected through configuration rather than silently used as a fallback. |
| Local model quality | The default `llama3.2:3b` path is convenient for local execution but may produce weaker synthesis or citation prose than larger models. Deterministic source mapping limits metadata errors but cannot make unsupported prose factual. |
| Data leakage | Logs omit prompts, answers, transcript contents, API keys, raw provider details, and sensitive request data. |
| Unsafe HTML rendering | HTML is not executed by the backend and is rendered by the frontend in a sandboxed iframe without same-origin access or parent DOM access. |
| Transcript freshness | Ingestion accepts a supplied local checkout, stores portable source paths, skips unchanged records, and refreshes changed records and chunks. It does not download new transcripts automatically. |
| Full-text retrieval limitations | PostgreSQL English full-text search is simple and explainable, with an expression GIN index, but it does not provide semantic matching or guaranteed recall for every phrasing. |

## Product decisions
- **Transcript grounding over general knowledge:** the product's value is traceable, episode-based advice. Unsupported claims are less useful than an explicit limitation.
- **PostgreSQL full-text retrieval:** the existing database already stores transcript chunks and supports `to_tsvector`/`websearch_to_tsquery`; an expression GIN index improves the current query without changing ranking semantics or adding another search system.
- **Ollama for the local demo:** it allows the application to run against a local OpenAI-compatible endpoint without requiring a cloud API key. Availability and model quality remain local setup concerns.
- **Provider abstraction:** the LLM service keeps provider selection separate from prompt and retrieval orchestration, allowing Ollama and OpenAI configuration plus the existing Claude Agent SDK facade without silent provider fallback.
- **Sandboxed HTML artifacts:** HTML is untrusted user-visible content. A sandboxed iframe gives the viewer a separate execution context instead of injecting generated markup into the main application DOM.
