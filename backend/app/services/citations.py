import re
from typing import Any


_SOURCE_REFERENCE_PATTERN = re.compile(r"\bSOURCE\s+(\d+)\b", re.IGNORECASE)


def extract_source_numbers(text: str) -> list[int]:
    """Return unique, ordered source references found in model text."""
    numbers = []
    seen = set()
    for match in _SOURCE_REFERENCE_PATTERN.finditer(text):
        number = int(match.group(1))
        if number not in seen:
            numbers.append(number)
            seen.add(number)
    return numbers


def map_source_references(
    generated_text: str,
    retrieved_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Map valid model references to authoritative retrieved metadata only."""
    return [
        source_metadata(retrieved_results[number - 1])
        for number in extract_source_numbers(generated_text)
        if 1 <= number <= len(retrieved_results)
    ]


def resolve_source_references(
    generated_text: str,
    retrieved_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Use valid model citations, or expose retrieved sources in order."""
    sources = map_source_references(generated_text, retrieved_results)
    if sources or not retrieved_results:
        return sources
    return [source_metadata(result) for result in retrieved_results]


def source_metadata(result: dict[str, Any]) -> dict[str, Any]:
    """Copy only metadata owned by the transcript database result."""
    return {
        "episode_title": result["episode_title"],
        "guest_name": result["guest_name"],
        "source_url": result["source_url"],
    }


def ensure_grounding_acknowledgement(answer: str, sources: list[dict[str, Any]]) -> str:
    if sources or "No valid transcript source citation" in answer:
        return answer
    return (
        f"{answer.rstrip()}\n\n"
        "No valid transcript source citation was provided; transcript support "
        "for this answer is insufficient."
    )
