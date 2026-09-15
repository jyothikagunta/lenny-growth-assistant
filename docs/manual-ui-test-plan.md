# Manual UI Test Plan

## Environment

This plan targets the current local stack:

- PostgreSQL with the `lenny_growth` database and current migrations.
- Ollama running locally with `llama3.2:3b` available.
- FastAPI backend on port 8000.
- Vite frontend on port 5173, or the alternate Vite port if 5173 is occupied.

Host startup commands are documented in [README.md](../README.md). The core commands are:

```powershell
# Backend terminal
cd backend
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH="."
python -m uvicorn app.main:app --reload --port 8000

# Frontend terminal
cd frontend
npm run dev
```

Before chat tests, confirm Ollama is running and the model is available:

```powershell
ollama serve
ollama list
```

The Docker/Compose workflow is documented separately, but Docker execution was not available on the development machine.

## Test matrix

| ID | Area | Steps | Expected result | Status |
| --- | --- | --- | --- | --- |
| UI-01 | UI startup | Start the backend/frontend and open the Vite URL. | The Lenny Growth Assistant shell loads with conversation and Artifact Viewer panels. | Verified |
| UI-02 | UI startup | Wait for initial bootstrap. | Provider/model status becomes visible, for example `ollama · llama3.2:3b`; no expected startup API error remains. | Verified |
| UI-03 | UI startup | Inspect the browser console and network tab during startup. | No unexpected frontend errors; session/runtime requests reach the backend when PostgreSQL is available. | Not yet manually verified as a clean-console assertion |
| SES-01 | Session | Open the app for the first time. | The frontend creates a backend session; the composer becomes usable after initialization. | Verified |
| SES-02 | New conversation | Send a message, then select **New conversation**. | A fresh session is created; messages, draft, and current artifact are cleared. | Verified |
| SES-03 | Session isolation | Use two separate conversations and ask a follow-up in only one. | The conversations do not share persisted history. | Automated; manual follow-up isolation not separately performed |
| SES-04 | Conversation persistence | Send multiple messages in one conversation. | The same session ID is used for follow-ups and the conversation remains visible during interaction. | Automated contract coverage; live persistence depends on PostgreSQL |
| CHAT-01 | Normal chat | Ask a product-market-fit or activation question. | A user message appears, the loading indicator runs, then an assistant response appears. | Not yet manually verified in this test plan; requires Ollama/PostgreSQL |
| CHAT-02 | Normal chat | Repeat CHAT-01 while watching the composer. | Send is disabled during the request and the loading state is visible. | Implemented; not separately manually verified |
| CHAT-03 | Sources | Complete a grounded question with retrieved evidence. | Compact episode/guest source metadata appears below the assistant response; valid URLs are clickable. | Automated source mapping; live UI rendering not separately verified |
| FUP-01 | Follow-up | Ask an initial question, then ask a related follow-up in the same session. | The follow-up uses session context and remains transcript-grounded. | Not yet manually verified with a live model |
| GRD-01 | Grounding | Ask a question with weak or no transcript support. | The assistant clearly acknowledges insufficient support. | Automated empty-retrieval coverage; live model behavior not separately verified |
| GRD-02 | Grounding | Inspect the response sources for GRD-01. | No fabricated source metadata is shown. | Automated; live UI rendering not separately verified |
| CIT-01 | Citation integrity | Use a response that references valid `SOURCE N` values. | Displayed source metadata corresponds to the ordered retrieved sources. | Automated |
| CIT-02 | Citation integrity | Use an invalid source number or model text naming an unrelated guest. | Out-of-range references are ignored and model text cannot create source metadata. | Automated |
| MD-01 | Markdown artifact | Request a Markdown product strategy document. | A structured artifact appears in the right panel with a title and Markdown content. | Automated artifact coverage; live UI not separately verified |
| MD-02 | Markdown artifact | Inspect headings, bullets, emphasis, numbered lists, and tables. | Markdown renders as formatted content rather than raw markup. | Implemented with React Markdown/GFM; not separately manually verified |
| MD-03 | Markdown artifact | Select **Copy**, then paste into a text editor. | The artifact content is copied and the control shows confirmation. | Implemented; not separately manually verified |
| MD-04 | Markdown artifact | Select **Show source**, then return to preview. | Raw Markdown is shown and preview can be restored. | Implemented; not separately manually verified |
| HTML-01 | HTML artifact | Request a self-contained HTML landing page. | The Artifact Viewer displays the generated page in the HTML preview state. | Implemented; live model-dependent flow not separately verified |
| HTML-02 | HTML artifact | Inspect the viewer label. | `HTML Preview · Sandboxed` is visible. | Implemented; browser state not separately manually verified |
| HTML-03 | HTML artifact | Select **Show source**, then restore preview. | Raw HTML is visible without injecting it into the main app DOM. | Implemented; not separately manually verified |
| HTML-04 | HTML artifact | Select **Copy**, then paste the HTML elsewhere. | The artifact content is copied. | Implemented; not separately manually verified |
| HTML-05 | HTML security | Use generated HTML containing scripts or parent-window access attempts. | The preview cannot access the parent application; the iframe has an empty restrictive `sandbox` attribute and no same-origin grant. | Automated implementation inspection; hostile-content browser test not separately performed |
| SHIP-01 | Ship 30 for 30 | Explicitly request a Ship 30 for 30 essay. | The response follows the dedicated writing structure and remains grounded in transcript evidence. | Automated routing/instruction coverage; live model flow not separately verified |
| SHIP-02 | Ship 30 for 30 | Inspect the essay sources. | Only retrieved Lenny transcript sources appear as factual sources. | Automated citation/source coverage |
| ERR-01 | Error handling | Stop Ollama or make the configured Ollama endpoint unavailable, then send a question. | The API returns a safe 503 state; the UI shows a clear error without provider internals or secrets. | Automated failure handling; live outage not manually performed |
| ERR-02 | Error handling | Configure a nonexistent/unavailable model and send a question. | The request fails safely without a stack trace in the user-facing response. | Automated provider failure coverage; live model outage not manually performed |
| ERR-03 | Error handling | Select OpenAI without setting `OPENAI_API_KEY`. | The API returns a safe configuration 503; no key or raw exception is exposed. | Automated |
| ERR-04 | Error handling | Stop PostgreSQL, then create/send a session request. | Database failure is logged and surfaced as a safe service error. | Automated mocked database coverage; live outage not manually performed |
| ERR-05 | Error handling | Ask a query that returns no transcript chunks. | The request does not crash; the assistant states that transcript support is insufficient and does not invent sources. | Automated |
| RWD-01 | Responsive UI | Open the app at a desktop viewport. | Conversation and Artifact Viewer are side by side; controls do not overlap. | Empty-state layout verified; full artifact layout not separately verified |
| RWD-02 | Responsive UI | Resize to a narrow/mobile viewport. | Panels stack vertically, the composer remains usable, and empty states remain visible. | Responsive empty state verified; full response layout not separately verified |
| SEC-01 | Security | Inspect the frontend source for generated-content rendering. | Generated HTML is not rendered with `dangerouslySetInnerHTML`; it uses a sandboxed iframe. | Automated code inspection |
| SEC-02 | Security | Inspect backend artifact handling. | Backend treats HTML as content and does not execute it server-side. | Automated tests/code inspection |
| REG-01 | Regression | Generate an artifact, then ask a normal chat question. | Normal chat still works and the existing artifact state behaves as expected. | Not yet manually verified with a live model |
| REG-02 | Regression | Ask follow-ups after an artifact response. | Session history and source mapping remain correct. | Automated backend coverage; live UI flow not separately verified |
| REG-03 | Regression | Trigger a backend error, recover the backend, and reload/retry. | The frontend remains usable and can create a new session after recovery. | Not yet manually verified |

## Evaluator smoke test

A minimal five-minute evaluation sequence:

1. Start PostgreSQL, Ollama with `llama3.2:3b`, FastAPI, and Vite using [README.md](../README.md).
2. Open `http://localhost:5173/` and confirm the provider/model badge.
3. Ask a grounded product or growth question and inspect the answer sources.
4. Ask a related follow-up in the same conversation.
5. Request a Markdown strategy document and inspect the rendered artifact, Copy, and Show source controls.
6. Request an HTML landing page and inspect the `HTML Preview · Sandboxed` viewer.
7. Check that artifact and answer sources correspond to transcript retrieval and that generated HTML is isolated from the parent page.

## Known limitations

- Docker execution was not locally verified because the Docker CLI is unavailable on the development machine.
- The Claude path requires separate SDK installation and authentication configuration; real Claude execution was not claimed in the implementation verification.
- The OpenAI path requires an API key.
- Retrieval is PostgreSQL full-text search rather than vector/semantic search.
- Transcript freshness depends on running the explicit ingestion/refresh command against an updated local checkout.
- There is no dedicated frontend automated unit-test framework; frontend lint/build and manual browser checks are used.
- Live model-dependent UI tests require PostgreSQL and Ollama to be running and therefore are not marked as completed solely from mocked backend tests.
