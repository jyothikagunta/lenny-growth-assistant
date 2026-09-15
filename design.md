# Design

## Design principles
- **Grounded over confident:** make the evidence boundary visible and prefer an insufficient-support statement to an invented answer.
- **Fast path to useful answers:** a focused composer, recent session history, and prompt suggestions keep the first interaction direct.
- **Clear source traceability:** assistant responses show the returned episode and guest metadata, with valid source URLs linked when available.
- **Artifacts are first-class outputs:** generated Markdown and HTML appear beside the conversation instead of being buried in chat text.
- **Safe rendering by default:** generated HTML is treated as untrusted content and previewed only inside a sandboxed iframe.

## Main layout
The current frontend is a responsive React + Vite application with two primary panels:

### Conversation panel
The left/main panel contains:
- Application identity and current provider/model status.
- A conversation heading and session status.
- User and assistant message rows.
- Rendered assistant Markdown, including headings, lists, emphasis, and tables where supported.
- Compact source links beneath assistant responses.
- A multiline composer with Send, loading, disabled, and error states.

### Artifact Viewer panel
The right panel contains:
- An empty state before an artifact exists.
- Artifact title and type when a structured artifact is returned.
- Rendered Markdown or sandboxed HTML preview.
- Copy and Show source controls.
- Artifact-specific source links.

The layout uses a calm, work-oriented visual language with restrained color, generous spacing, serif display headings, and compact metadata. It is a product workspace rather than a marketing landing page.

## Conversation states
- **Empty state:** prompts the user to ask a product/growth question or choose a suggested prompt such as improving activation or creating a strategy document.
- **Loading:** the composer is disabled and an assistant typing indicator appears while the chat request is running. Initial session creation shows a session-starting state.
- **Successful response:** the user message and assistant response are appended to the conversation. Sources are shown when returned by the backend.
- **Error:** a visible alert banner reports a safe request error. The composer remains available when the session is usable.
- **Follow-up conversation:** the same session ID is sent for subsequent chat requests, and the backend supplies recent session history as context.
- **New conversation:** New conversation creates a fresh backend session, clears messages, clears the current artifact, and resets the composer.

## Source presentation
Assistant source metadata is rendered below the corresponding assistant message. The UI displays the episode title and guest name when present. A source URL becomes a new-tab link only when it parses as `http` or `https`; the frontend does not invent or transform missing URLs.

Artifact sources are rendered separately below the artifact viewer. Their metadata comes from the artifact response, which the backend maps from retrieved transcript results rather than trusting model-created metadata.

## Artifact experience
### Markdown rendering
Markdown artifacts are rendered with `react-markdown` and `remark-gfm`. This supports headings, bold text, bullets, numbered lists, and GitHub-flavored tables without injecting arbitrary HTML into the main application DOM.

### HTML preview
HTML artifacts are shown in an iframe using `srcDoc`. The iframe uses an empty restrictive `sandbox` attribute and does not grant same-origin access. Generated HTML is not inserted through `dangerouslySetInnerHTML` and is never executed by the backend.

The viewer labels this state as **HTML Preview · Sandboxed**.

### Show source
Show source toggles from the rendered view to a preformatted raw Markdown or HTML view. This makes the generated artifact inspectable without executing it in the application DOM.

### Copy
Copy writes the artifact content to the browser clipboard and gives temporary visual confirmation. File downloads are not implemented.

## Responsive behavior
On wider screens, the conversation and artifact viewer appear side by side. Below the responsive breakpoint, the panels stack vertically, with the conversation above the artifact viewer. Header controls wrap into a compact mobile arrangement, and the artifact iframe uses a shorter height on small screens.

## Accessibility/usability considerations
- The chat and artifact viewer have accessible region labels.
- The composer and Send control have labels and disabled states.
- Errors use an alert role.
- Buttons expose text or title attributes for actions such as Copy and New conversation.
- Assistant updates are placed in a live conversation region.
- Source links open in a new tab with `rel="noreferrer"`.
- The implementation has not been audited for WCAG conformance, screen-reader completeness, or keyboard navigation beyond the implemented composer behavior.
- Enter sends a message; Shift+Enter creates a new line.

## Example user flows
### 1. Ask a grounded product question
1. Open the frontend.
2. The app creates a backend session.
3. Enter a question such as how to improve activation.
4. Send it and wait for the assistant response.
5. Review the answer and its returned transcript sources.

### 2. Ask a follow-up
1. Ask an initial question.
2. Enter a follow-up in the same composer.
3. The same session ID is sent, so recent session history is available to the agent as context.

### 3. Generate a Markdown artifact
1. Request a product strategy document or Markdown artifact.
2. The backend retrieves transcript context first.
3. The response includes structured artifact metadata.
4. The viewer renders the Markdown and lists artifact sources.

### 4. Generate an HTML artifact
1. Request an HTML landing page.
2. The backend returns complete HTML as untrusted content when generation succeeds.
3. The viewer displays it in the sandboxed iframe and labels it accordingly.
4. Show source exposes the raw HTML; Copy copies it to the clipboard.

### 5. Start a new conversation
1. Select New conversation.
2. The frontend creates a new backend session.
3. Existing messages and the current artifact are cleared.
4. The empty conversation state is shown again.
