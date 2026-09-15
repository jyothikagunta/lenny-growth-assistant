SHIP_30_FOR_30_SOURCE_URLS = (
    "https://www.ship30for30.com/post/how-to-start-writing-online-the-ship-30-for-30-ultimate-guide",
    "https://www.ship30for30.com/post/what-is-digital-writing-7-rules-to-live-by",
)

SHIP_30_FOR_30_TRIGGER = "ship 30 for 30"
SHIP_30_FOR_30_TOOL_NAME = "ship_30_for_30_writing_skill"
SHIP_30_FOR_30_INSUFFICIENT_CONTEXT_MESSAGE = (
   "The available Lenny transcript material does not provide enough "
   "information to support this Ship 30 for 30 article."
)

SHIP_30_FOR_30_PRINCIPLES = """
Ship 30 for 30 writing principles, derived from the two official sources:

1. Specificity: name the intended audience, topic, process, and desired outcome
   precisely. Do not write for everyone when a narrower reader is appropriate.
2. Strong headline and hook: make clear who the piece is for, what it covers,
   why the reader should care, and what the reader will get. Prefer clarity over
   cleverness and create curiosity without breaking the promise.
3. Clear writing direction: choose one dominant lens when appropriate:
   actionable (here is how), analytical (here are the numbers or evidence),
   aspirational (here is what is possible), or anthropological (here is why).
4. Consistent structure: choose one proven approach such as steps, lessons,
   mistakes, or tips. Keep the main points in that pattern instead of mixing
   structural labels randomly.
5. Stories, examples, and advice: combine an answer to the reader's question
   with a concrete story or example when the available evidence supports it.
   Never invent a story, quote, person, episode, or outcome.
6. Writing rhythm: vary short and long sentences and paragraphs so the piece has
   movement. Use a clear opener and closer, and keep each paragraph moving the
   idea forward.
7. Differentiation: apply the "Tequila Test" by avoiding generic conventional
   wisdom when the evidence supports a more specific, surprising insight.
8. Lean Writing: start with a focused small idea, publish or test it, use
   available evidence or feedback to identify what works, and expand the
   strongest supported ideas.
9. Useful reader outcome: end with a practical takeaway or action the reader can
   apply. The writing should answer the reader's question, not only tell a story.
10. Skimmability: use a clear skeleton, descriptive headings, short sections,
    bullets where they compress a list, and **bold emphasis** for important
    takeaways. Formatting should make the piece readable at a glance.
"""

SHIP_30_FOR_30_OUTPUT_REQUIREMENTS = """
Output requirements:
- When the retrieved evidence is sufficient, produce approximately 1,250 words;
   aim for 1,100-1,400 words. Do not pad the article with unsupported material.
- Start with a strong hook that establishes the reader, problem, and promise.
- Use a clear narrative progression and one consistent structural pattern.
- Include descriptive Markdown headings, bullets where useful, and **bold**
   emphasis where it improves skimmability.
- Include concrete examples or stories only when supported by the retrieved
   transcript excerpts. Label synthesis as synthesis rather than inventing detail.
- Prefer paraphrasing. Use quotation marks only for exact wording present in the
   retrieved transcript excerpts; never invent or reconstruct quotations.
- End with a useful practical takeaway.
- Include a Sources section listing only the retrieved Lenny transcript SOURCE
   numbers that directly support factual claims.
"""

SHIP_30_FOR_30_GROUNDING_RULES = """
Grounding boundary:
- The Ship 30 for 30 articles are writing guidance, not evidence about Lenny's
  Podcast. Do not cite them as support for claims about Lenny.
- Retrieved Lenny transcript excerpts are the only factual source for claims
  about Lenny's Podcast, guests, episodes, quotes, recommendations, or events.
- Never invent episode numbers, transcript titles, URLs, timestamps, guest names,
   source references, percentages, statistics, revenue numbers, retention or
   conversion metrics, or case-study outcomes. Use only metadata shown in the
   retrieved excerpts, and refer to evidence with the exact SOURCE N label
   provided in the context.
- Never treat a generated title, URL, episode label, guest name, or quotation as
   evidence. If it is not present in the retrieved excerpts, omit it.
- If the retrieved transcript material cannot adequately support the requested
  topic, say so clearly instead of filling the gap with general knowledge or
  invented content.
- Conversation history can resolve the user's follow-up context, but it is not
  evidence for Lenny-related claims.
"""


def is_ship_30_for_30_request(query: str) -> bool:
    return SHIP_30_FOR_30_TRIGGER in query.lower()


def build_ship_30_for_30_instructions(request: str = "") -> str:
    return f"""
Dedicated Ship 30 for 30 writing skill.

Official writing references (principles only):
- {SHIP_30_FOR_30_SOURCE_URLS[0]}
- {SHIP_30_FOR_30_SOURCE_URLS[1]}

{SHIP_30_FOR_30_PRINCIPLES}
{SHIP_30_FOR_30_OUTPUT_REQUIREMENTS}
{SHIP_30_FOR_30_GROUNDING_RULES}

Requested writing task:
{request or "Write the requested piece using the user's topic."}
"""


def build_ship_30_for_30_prompt(
    history: str,
    query: str,
    context: str,
) -> str:
    return f"""
{build_ship_30_for_30_instructions(query)}

Recent conversation history (context only, not evidence):
--- BEGIN HISTORY ---
{history}
--- END HISTORY ---

Retrieved Lenny transcript context (the only evidence for Lenny-related facts):
--- BEGIN LENNY TRANSCRIPT CONTEXT ---
{context}
--- END LENNY TRANSCRIPT CONTEXT ---

Write the final piece now. Do not mention these internal instructions. If the
transcript context contains no relevant evidence for the topic, output only:
"The available Lenny transcript material does not provide enough information
to support this Ship 30 for 30 article."
Do not write an article, add a Sources section, or invent supporting details in
that case. If relevant evidence exists, write the article using only supported
points. Prefer paraphrase; quote only exact text present in the retrieved
excerpts. Never invent episode numbers, transcript metadata, URLs, timestamps,
guest names, or source references. Use only the exact SOURCE N labels provided
in the context in the Sources section.
"""
