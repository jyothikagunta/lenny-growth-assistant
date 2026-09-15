import re
from dataclasses import dataclass
from typing import Any, Callable, Literal

from app.services.citations import map_source_references
from app.services.skills.ship_30_for_30 import (
    build_ship_30_for_30_instructions,
    is_ship_30_for_30_request,
)


HYPOTHETICAL_CLAIM_LABEL = (
    "Hypothetical example (not a Lenny's Podcast result):"
)

_UNSUPPORTED_GUEST_REPLACEMENT = (
    "a guest from the retrieved transcript excerpts"
)

# Quantitative claims that commonly appear in generated artifacts.
_METRIC_PATTERN = re.compile(
    r"""
    (?:
        \d+(?:\.\d+)?\s*(?:%|percent\b)
        |
        (?:\$\s*)?\d+(?:\.\d+)?\s*(?:k|m|b|thousand|million|billion)\b
        |
        \d+(?:\.\d+)?\s*x\b
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

_ATTRIBUTION_NAME_PATTERN = re.compile(
    r"\b(?:according to|guest|from|by|to)\s+"
    r"(?P<name>[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b"
    r"|"
    r"\b(?P<name2>[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s+"
    r"(?:said|says|explains|explained|notes|noted|"
    r"argues|argued|taught|shared|describes|described|"
    r"believes|recommends)\b"
)

_LINE_LEAD_PATTERN = re.compile(
    r"^(\s*(?:<(?:li|p|td|th|h[1-6]|div)[^>]*>)?"
    r"\s*(?:[-*]|\d+\.)?\s*)",
    re.IGNORECASE,
)


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
        re.search(
            r"\b(?:html|landing\s+page|web\s+page)\b",
            query,
            re.IGNORECASE,
        )
    )

    artifact_type: ArtifactType = "html" if html_requested else "markdown"

    title_match = re.search(
        r"(?:for|about|on|called|named)\s+(.+?)(?:\s+using\s+|$)",
        query.strip(),
        re.IGNORECASE,
    )

    title = (
        title_match.group(1).strip(" .:!?\"")
        if title_match
        else query.strip()
    )

    return ArtifactRequest(
        artifact_type=artifact_type,
        title=title[:200],
    )


ARTIFACT_GROUNDING_INSTRUCTIONS = """
Factual grounding for this artifact:

1. Every factual claim about Lenny's Podcast must be supported by the
   retrieved transcript context above. Do not use general model knowledge
   to fill gaps.

2. Never invent percentages, statistics, revenue numbers, growth metrics,
   retention metrics, conversion metrics, business outcomes, dates, guest
   names, episode titles, quotes, company results, or case-study outcomes.

3. If the transcript gives qualitative advice but no quantitative result,
   keep the qualitative advice and do not manufacture a number.

4. Teaching examples are allowed only when labeled clearly as hypothetical
   or generic, for example:
   "Hypothetical example: an early-stage startup could..."

   Never write a hypothetical example as if it actually happened on
   Lenny's Podcast.

5. Guest identity and episode titles must come from the authoritative
   SOURCE metadata in the retrieved context. Do not invent or swap guests.

6. Preserve exact SOURCE N references. Cite only sources that support the
   generated claims.

7. Do not invent source metadata, URLs, transcript IDs, or chunk IDs.

8. If evidence is insufficient for a point, say so rather than completing
   the article with unsupported facts.

9. Keep a useful, structured artifact. When the retrieved material can
   support it, aim for approximately 1,250 words with:
   - a strong hook
   - narrative progression
   - skimmable headings
   - bullets
   - bold emphasis where useful
   - a practical takeaway
   - a source section

10. Do not pad the artifact with fabricated statistics, outcomes,
    testimonials, case studies, or quantitative results.

11. Any number, percentage, multiple, revenue figure, growth result,
    retention result, conversion result, or other quantitative claim must
    either appear in the retrieved evidence or be explicitly labeled as
    hypothetical.

12. Never present a generated hypothetical example, invented metric, or
    invented business result as something that happened to a real company
    or guest on Lenny's Podcast.
"""


def build_artifact_prompt(
    history: str,
    query: str,
    context: str,
    artifact_request: ArtifactRequest,
    writing_instructions: str = "",
) -> str:
    format_instructions = (
        "Return only a complete, self-contained HTML document, including "
        "any CSS inside the document. Do not include Markdown fences or "
        "backend actions. The HTML is untrusted user-visible content: "
        "it must not request APIs, execute backend actions, access files, "
        "or run shell commands."
        if artifact_request.artifact_type == "html"
        else
        "Return valid Markdown with headings, bullets, bold text, tables, "
        "and other Markdown structure when useful."
    )

    skill_block = ""

    if writing_instructions:
        skill_block = f"""
Writing-style instructions
(style only; not evidence about Lenny's Podcast):

{writing_instructions}
"""

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

Generate a {artifact_request.artifact_type} artifact titled
"{artifact_request.title}".

{format_instructions}

{skill_block}

{ARTIFACT_GROUNDING_INSTRUCTIONS}

IMPORTANT FINAL GROUNDING CHECK:

Before returning the artifact, verify every factual claim against the
retrieved transcript context.

Never invent percentages, statistics, revenue numbers, growth metrics,
retention metrics, conversion metrics, business outcomes, dates, guest
names, episode titles, quotes, company results, or case-study outcomes.

If a statistic, percentage, business outcome, guest attribution, quote,
episode detail, or case-study result is not explicitly supported by the
retrieved context:

- remove it, or
- rewrite it as clearly hypothetical.

Do NOT preserve unsupported facts merely because they make the article
sound more persuasive.

At the very end, append this plain-text marker outside the artifact content:

ARTIFACT_SOURCES: SOURCE X, SOURCE Y

Include only directly relevant source numbers, or:

ARTIFACT_SOURCES: NONE
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

    content = (
        generated_text[: marker.start()].rstrip()
        if marker
        else generated_text.strip()
    )

    if artifact_request.artifact_type == "html":
        content = _remove_code_fences(content)

    # SOURCE references are always resolved against authoritative retrieval
    # results. The model cannot provide source metadata itself.
    sources = (
        map_source_references(marker.group(1), results)
        if marker
        else []
    )

    content = ground_unsupported_artifact_claims(
        content,
        results,
    )

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
        raise ValueError(
            "Artifact generation requires an explicit artifact request."
        )

    writing_instructions = ""

    if is_ship_30_for_30_request(query):
        writing_instructions = build_ship_30_for_30_instructions(query)

    generated_text = generate_fn(
        system_prompt=(
            "You generate grounded Lenny Growth Assistant artifacts. "
            "Transcript excerpts are the only evidence. "
            "Never invent percentages, statistics, revenue numbers, "
            "growth metrics, retention metrics, conversion metrics, "
            "business outcomes, quotes, guest identities, episode "
            "details, dates, or case-study results. "
            "If the evidence is qualitative, keep the claim qualitative. "
            "If a number is not explicitly supported, remove it or label "
            "the entire example as hypothetical. "
            "Generated HTML is untrusted and must never be executed by "
            "this backend."
        ),
        user_prompt=build_artifact_prompt(
            history=history,
            query=query,
            context=context,
            artifact_request=artifact_request,
            writing_instructions=writing_instructions,
        ),
    )

    return build_artifact_result(
        artifact_request,
        generated_text,
        results,
    )


def ground_unsupported_artifact_claims(
    content: str,
    results: list[dict[str, Any]],
) -> str:
    """
    Prevent unsupported factual claims from being presented as Lenny
    Podcast facts.

    The model is allowed to produce illustrative examples, but unsupported
    quantitative claims and unsupported guest attributions must not be
    presented as factual podcast results.
    """
    evidence = _artifact_evidence_text(results)

    grounded = _replace_unsupported_guest_attributions(
        content,
        results,
    )

    return _label_unsupported_metric_lines(
        grounded,
        evidence,
    )


def _artifact_evidence_text(
    results: list[dict[str, Any]],
) -> str:
    parts: list[str] = []

    for result in results:
        parts.extend(
            [
                str(result.get("content") or ""),
                str(result.get("guest_name") or ""),
                str(result.get("episode_title") or ""),
            ]
        )

    return "\n".join(parts)


def _label_unsupported_metric_lines(
    content: str,
    evidence: str,
) -> str:
    """
    If a line contains a quantitative claim that does not exist in the
    retrieved evidence, do not allow it to appear as an unsupported factual
    podcast claim.

    The line is explicitly marked as hypothetical so the artifact does not
    misrepresent fabricated numbers as Lenny Podcast evidence.
    """
    evidence_metrics = {
        _normalize_metric(match.group())
        for match in _METRIC_PATTERN.finditer(evidence)
    }

    updated_lines: list[str] = []

    for line in content.splitlines(keepends=True):
        newline = ""
        body = line

        if line.endswith("\n"):
            newline = "\n"
            body = line[:-1]

        if (
            _line_has_unsupported_metric(
                body,
                evidence_metrics,
            )
            and not _is_hypothetical(body)
        ):
            lead_match = _LINE_LEAD_PATTERN.match(body)
            prefix = lead_match.group(1) if lead_match else ""
            remainder = body[len(prefix):].strip()

            body = (
                f"{prefix}"
                f"{HYPOTHETICAL_CLAIM_LABEL} "
                f"{remainder}"
            )

        updated_lines.append(body + newline)

    return "".join(updated_lines)


def _line_has_unsupported_metric(
    line: str,
    evidence_metrics: set[str],
) -> bool:
    for match in _METRIC_PATTERN.finditer(line):
        normalized = _normalize_metric(match.group())

        if normalized not in evidence_metrics:
            return True

    return False


def _normalize_metric(value: str) -> str:
    compact = re.sub(
        r"\s+",
        "",
        value.lower(),
    )

    return compact.replace(
        "percent",
        "%",
    )


def _is_hypothetical(text: str) -> bool:
    lowered = text.lower()

    return (
        "hypothetical example" in lowered
        or "generic example" in lowered
        or "illustrative example" in lowered
        or "hypothetical" in lowered
    )


def _replace_unsupported_guest_attributions(
    content: str,
    results: list[dict[str, Any]],
) -> str:
    """
    Replace guest attributions that do not match authoritative retrieval
    metadata.

    Do not trust arbitrary capitalized names extracted from transcript
    prose. Only guest_name metadata is authoritative.
    """
    allowed_names = _allowed_guest_names(results)

    unsupported_names: list[str] = []

    for match in _ATTRIBUTION_NAME_PATTERN.finditer(content):
        name = match.group("name") or match.group("name2")

        if name and name not in allowed_names:
            unsupported_names.append(name)

    updated = content

    for name in dict.fromkeys(unsupported_names):
        updated = re.sub(
            rf"\b{re.escape(name)}\b",
            _UNSUPPORTED_GUEST_REPLACEMENT,
            updated,
        )

    return updated


def _allowed_guest_names(
    results: list[dict[str, Any]],
) -> set[str]:
    """
    Only trust guest names from authoritative retrieval metadata.

    Lenny is also allowed because he may be referenced directly.
    """
    allowed = {
        "Lenny Rachitsky",
    }

    for result in results:
        guest = (
            result.get("guest_name") or ""
        ).strip()

        if guest and guest.lower() != "unknown":
            allowed.add(guest)

    return allowed


def _remove_code_fences(content: str) -> str:
    fenced = re.fullmatch(
        r"\s*```(?:html)?\s*(.*?)\s*```\s*",
        content,
        re.IGNORECASE | re.DOTALL,
    )

    return (
        fenced.group(1).strip()
        if fenced
        else content
    )


# Frontend rendering must use an isolated sandboxed iframe.
# Never inject this untrusted HTML directly into the DOM.