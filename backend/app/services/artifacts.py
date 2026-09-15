import re
from dataclasses import dataclass
from typing import Any, Callable, Literal

from app.services.citations import map_source_references


ArtifactType = Literal["markdown", "html"]


@dataclass
class ArtifactResult:
    artifact_type: ArtifactType
    title: str
    content: str
    sources: list[dict[str, Any]]
    is_untrusted: bool = True


@dataclass(frozen=True)
class ArtifactRequest:
    artifact_type: ArtifactType
    title: str


_ARTIFACT_REQUEST_PATTERN = re.compile(
    r"^\s*(?:please\s+)?(?:create|generate|build|draft|write)\b.*"
    r"(?:landing\s+page|web\s+page|html|markdown|artifact|"
    r"product\s+strategy|strategy\s+document|30\s*/\s*60\s*/\s*90|"
    r"30[- ]day|60[- ]day|90[- ]day|plan)\b",
    re.IGNORECASE | re.DOTALL,
)


def detect_artifact_request(query: str) -> ArtifactRequest | None:
    """Detect explicit artifact commands without changing ordinary chat."""
    if not _ARTIFACT_REQUEST_PATTERN.search(query):
        return None

    html_requested = bool(
        re.search(r"\b(?:html|landing\s+page|web\s+page)\b", query, re.I)
    )
    artifact_type: ArtifactType = "html" if html_requested else "markdown"
    title_match = re.search(
        r"(?:for|about|on|called|named)\s+(.+?)(?:\s+using\s+|$)",
        query.strip(),
        re.IGNORECASE,
    )
    title = title_match.group(1).strip(" .:!?\"") if title_match else query.strip()
    return ArtifactRequest(artifact_type=artifact_type, title=title[:200])


def build_artifact_prompt(
    history: str,
    query: str,
    context: str,
    artifact_request: ArtifactRequest,
) -> str:
    format_instructions = (
        "Return only a complete, self-contained HTML document, including any "
        "CSS inside the document. Do not include Markdown fences or backend "
        "actions. The HTML is untrusted user-visible content: it must not "
        "request APIs, execute backend actions, access files, or run shell "
        "commands."
        if artifact_request.artifact_type == "html"
        else "Return valid Markdown with headings, bullets, bold text, tables, "
        "and other Markdown structure when useful."
    )
    return f"""
Recent conversation history (context only, not evidence):
--- BEGIN HISTORY ---
{history}
--- END HISTORY ---

Retrieved Lenny's Podcast transcript context:
--- BEGIN CONTEXT ---
{context}
--- END CONTEXT ---

User artifact request:
{query}

Generate a {artifact_request.artifact_type} artifact titled "{artifact_request.title}".
{format_instructions}

Use only claims supported by the transcript context. Do not invent guests,
episodes, quotes, facts, or recommendations. If the context does not support a
claim, say that it is not supported. At the very end, append this plain-text
marker outside the artifact content: ARTIFACT_SOURCES: SOURCE X, SOURCE Y
Include only directly relevant source numbers, or ARTIFACT_SOURCES: NONE.
"""


def build_artifact_result(
    artifact_request: ArtifactRequest,
    generated_text: str,
    results: list[dict[str, Any]],
) -> ArtifactResult:
    marker = re.search(
        r"(?:^|\n)\s*ARTIFACT_SOURCES:\s*(.+?)\s*$",
        generated_text,
        re.IGNORECASE | re.MULTILINE,
    )
    content = generated_text[: marker.start()].rstrip() if marker else generated_text.strip()
    if artifact_request.artifact_type == "html":
        content = _remove_code_fences(content)

    sources = map_source_references(marker.group(1), results) if marker else []
    return ArtifactResult(
        artifact_type=artifact_request.artifact_type,
        title=artifact_request.title,
        content=content,
        sources=sources,
    )


def generate_artifact(
    history: str,
    query: str,
    context: str,
    results: list[dict[str, Any]],
    generate_fn: Callable[..., str],
) -> ArtifactResult:
    artifact_request = detect_artifact_request(query)
    if artifact_request is None:
        raise ValueError("Artifact generation requires an explicit artifact request.")

    generated_text = generate_fn(
        system_prompt=(
            "You generate grounded Lenny Growth Assistant artifacts. "
            "Transcript excerpts are the only evidence. Generated HTML is "
            "untrusted and must never be executed by this backend."
        ),
        user_prompt=build_artifact_prompt(
            history=history,
            query=query,
            context=context,
            artifact_request=artifact_request,
        ),
    )
    return build_artifact_result(artifact_request, generated_text, results)


def _remove_code_fences(content: str) -> str:
    fenced = re.fullmatch(
        r"\s*```(?:html)?\s*(.*?)\s*```\s*", content, re.I | re.S
    )
    return fenced.group(1).strip() if fenced else content


# Frontend rendering must use an isolated sandboxed iframe. Never inject this
# untrusted HTML directly into the DOM.