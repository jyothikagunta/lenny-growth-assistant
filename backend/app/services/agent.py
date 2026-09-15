import asyncio
import importlib
import logging
import os
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.services.artifacts import (
    ArtifactResult,
    build_artifact_result,
    detect_artifact_request,
    generate_artifact,
)
from app.services.llm import generate_answer
from app.services.llm import LLMConfigurationError, LLMServiceError
from app.services.retrieval import RetrievalServiceError, search_transcripts
from app.services.skills.ship_30_for_30 import (
    SHIP_30_FOR_30_TOOL_NAME,
    build_ship_30_for_30_instructions,
    build_ship_30_for_30_prompt,
    is_ship_30_for_30_request,
)

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """
You are the Lenny Growth Assistant.

You answer product, growth, startup, and leadership questions using ONLY
Lenny's Podcast transcript excerpts returned by the transcript retrieval
capability.

GROUNDING RULES:
1. Use only information supported by the provided transcript excerpts.
2. Do not invent facts, quotes, guests, episodes, or recommendations.
3. Do not use general model knowledge to fill gaps.
4. You may synthesize information across multiple relevant excerpts.
5. Ignore transcript excerpts that are not relevant to the user's question.
6. If any excerpt contains relevant evidence, answer using the supported
    points even if the evidence is partial. Clearly state what is not
    supported.
7. Use the insufficient-information statement only when the excerpts contain
    no relevant evidence for the question. In that case, say:
   "The available Lenny transcript material does not provide enough
   information to answer this confidently."
8. At the end, include a Sources section.
9. List only sources that directly support the answer.
10. When using evidence, include at least one valid SOURCE N from the
     provided context, using the exact SOURCE number for that evidence. Never
     write "Sources: None" when relevant evidence exists.
11. Conversation history is context for follow-up questions only. It is not
    evidence for factual claims about Lenny's Podcast.
"""

CLAUDE_AUTH_ENV_VARS = ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN")
CLAUDE_TOOL_NAME = "search_lenny_transcripts"
CLAUDE_ALLOWED_TOOL = "mcp__lenny_transcripts__" + CLAUDE_TOOL_NAME
CLAUDE_SKILL_ALLOWED_TOOL = (
    "mcp__lenny_transcripts__" + SHIP_30_FOR_30_TOOL_NAME
)
INSUFFICIENT_CONTEXT_MESSAGE = (
    "The available Lenny transcript material does not provide enough "
    "information to answer this confidently."
)


class AgentConfigurationError(RuntimeError):
    """Raised when the selected agent backend cannot be configured."""


@dataclass
class AgentResponse:
    answer: str
    results: list[Any]
    artifact: ArtifactResult | None = None


def _ensure_retrieval_support_statement(answer: str, results) -> str:
    if results or INSUFFICIENT_CONTEXT_MESSAGE in answer:
        return answer
    return f"{answer.rstrip()}\n\n{INSUFFICIENT_CONTEXT_MESSAGE}"


def build_context(results, start_index: int = 1) -> str:
    if not results:
        return "No relevant transcript material was found."

    context_parts = []
    for index, result in enumerate(results, start=start_index):
        context_parts.append(
            f"""
SOURCE {index}
Episode: {result["episode_title"]}
Guest: {result["guest_name"] or "Unknown"}
Source URL: {result["source_url"] or "Unavailable"}

Transcript excerpt:
{result["content"]}
"""
        )

    return "\n".join(context_parts)


def build_user_prompt(history: str, query: str, context: str) -> str:
    return f"""
Recent conversation history (context only, not evidence):

--- BEGIN HISTORY ---
{history}
--- END HISTORY ---

Retrieved Lenny's Podcast transcript context:

--- BEGIN CONTEXT ---
{context}
--- END CONTEXT ---

User question:
{query}

Answer the question using ONLY the transcript context.

Requirements:
- If the context contains any relevant evidence, answer with the supported
    points even if it is partial. Do not use the insufficient-information
    refusal when relevant evidence exists.
- Ignore irrelevant sources.
- Do not invent information.
- Use the insufficient-information refusal only when the retrieved context
    contains no relevant evidence for the question.
- Clearly distinguish supported points from information that is not available.
- When evidence is used, include at least one valid SOURCE N from the provided
    context, using the exact SOURCE number corresponding to the evidence. Do not
    write "Sources: None" when relevant evidence exists.
- At the end, include:

Sources:
- SOURCE X
- SOURCE Y

Only include SOURCE numbers that directly support the answer.
"""


def generate_grounded_answer(
    db: Session,
    query: str,
    history: str,
    limit: int,
) -> AgentResponse:
    backend = os.getenv("AGENT_BACKEND", "local").lower()
    try:
        if backend == "local":
            return _generate_local_answer(db, query, history, limit)

        if backend == "claude":
            return _generate_claude_answer(db, query, history, limit)

        raise AgentConfigurationError("Unsupported agent backend configuration.")
    except (AgentConfigurationError, LLMConfigurationError, LLMServiceError, RetrievalServiceError):
        logger.error(
            "Agent execution failed",
            extra={
                "event": "agent_execution_failure",
                "provider": backend,
                "operation": "generate_grounded_answer",
                "error_type": "agent_or_provider",
            },
        )
        raise


def _generate_local_answer(
    db: Session,
    query: str,
    history: str,
    limit: int,
) -> AgentResponse:
    results = search_transcripts(db=db, query=query, limit=limit)
    if detect_artifact_request(query):
        try:
            artifact = generate_artifact(
                history=history,
                query=query,
                context=build_context(results),
                results=results,
                generate_fn=generate_answer,
            )
        except Exception as error:
            logger.error(
                "Artifact generation failed",
                extra={
                    "event": "artifact_generation_failure",
                    "provider": os.getenv("LLM_PROVIDER", "ollama").lower(),
                    "operation": "generate_artifact",
                    "error_type": type(error).__name__,
                },
            )
            return AgentResponse(
                answer="Artifact generation is temporarily unavailable. Please try again.",
                results=results,
            )
        return AgentResponse(
            answer=artifact.content,
            results=results,
            artifact=artifact,
        )

    if is_ship_30_for_30_request(query):
        answer = generate_answer(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=build_ship_30_for_30_prompt(
                history=history,
                query=query,
                context=build_context(results),
            ),
        )
        return AgentResponse(
            answer=_ensure_retrieval_support_statement(answer, results),
            results=results,
        )

    answer = generate_answer(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=build_user_prompt(
            history=history,
            query=query,
            context=build_context(results),
        ),
    )
    return AgentResponse(
        answer=_ensure_retrieval_support_statement(answer, results),
        results=results,
    )


def _generate_claude_answer(
    db: Session,
    query: str,
    history: str,
    limit: int,
) -> AgentResponse:
    if not any(os.getenv(name) for name in CLAUDE_AUTH_ENV_VARS):
        raise AgentConfigurationError(
            "Claude backend requires ANTHROPIC_API_KEY or "
            "CLAUDE_CODE_OAUTH_TOKEN."
        )

    try:
        sdk = importlib.import_module("claude_agent_sdk")
        AssistantMessage = sdk.AssistantMessage
        ClaudeAgentOptions = sdk.ClaudeAgentOptions
        ClaudeSDKClient = sdk.ClaudeSDKClient
        ResultMessage = sdk.ResultMessage
        TextBlock = sdk.TextBlock
        create_sdk_mcp_server = sdk.create_sdk_mcp_server
        tool = sdk.tool
    except ImportError as error:
        raise AgentConfigurationError(
            "Claude backend requires the claude-agent-sdk package."
        ) from error

    retrieved_results = []
    artifact_request = detect_artifact_request(query)
    skill_enabled = is_ship_30_for_30_request(query)

    @tool(
        CLAUDE_TOOL_NAME,
        "Search Lenny's Podcast transcript excerpts for the user's question.",
        {"query": str, "limit": int},
    )
    async def search_tool(args: dict[str, Any]) -> dict[str, Any]:
        tool_results = search_transcripts(
            db=db,
            query=args["query"],
            limit=min(args["limit"], limit),
        )
        source_start = len(retrieved_results) + 1
        retrieved_results.extend(tool_results)
        return {
            "content": [
                {
                    "type": "text",
                    "text": build_context(tool_results, source_start),
                }
            ]
        }

    tools = [search_tool]
    if skill_enabled:

        @tool(
            SHIP_30_FOR_30_TOOL_NAME,
            "Apply the Ship 30 for 30 writing principles to the requested task.",
            {"request": str},
        )
        async def ship_30_for_30_tool(
            args: dict[str, Any],
        ) -> dict[str, Any]:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": build_ship_30_for_30_instructions(
                            args["request"]
                        ),
                    }
                ]
            }

        tools.append(ship_30_for_30_tool)

    server = create_sdk_mcp_server(
        name="lenny_transcripts",
        version="1.0.0",
        tools=tools,
    )
    options = _build_claude_options(
        ClaudeAgentOptions,
        server,
        skill_enabled=skill_enabled,
    )

    skill_prompt = ""
    if skill_enabled:
        skill_prompt = f"""
This is a Ship 30 for 30 writing request. Use the
{SHIP_30_FOR_30_TOOL_NAME} capability for writing instructions. Those
instructions are not evidence about Lenny's Podcast. Use the transcript search
capability for all Lenny-related factual claims.
"""

    artifact_instructions = ""
    if artifact_request:
        artifact_instructions = f"""
Generate a {artifact_request.artifact_type} artifact titled
\"{artifact_request.title}\". For HTML, return a complete self-contained
document with CSS inside it and never perform backend actions, filesystem
access, shell commands, or API calls. For Markdown, return valid Markdown.
Return only the artifact, then append ARTIFACT_SOURCES: SOURCE X, SOURCE Y
outside the artifact. Use only directly relevant source numbers.
"""

    prompt = f"""
Conversation history (context only, not evidence):
{history}

    {skill_prompt}
User question:
{query}

Use the {CLAUDE_TOOL_NAME} tool to retrieve transcript evidence before
answering. Use only the returned transcript excerpts for factual claims.
Include a Sources section with only the SOURCE numbers that support your
answer. If the tool does not provide enough information, say so explicitly.
{artifact_instructions}
"""

    async def run_agent() -> str:
        final_text = ""
        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt)
            async for message in client.receive_response():
                if isinstance(message, ResultMessage) and message.result:
                    final_text = message.result
                elif isinstance(message, AssistantMessage):
                    final_text = "".join(
                        block.text
                        for block in message.content
                        if isinstance(block, TextBlock)
                    )
        return final_text

    try:
        answer = asyncio.run(run_agent())
    except AgentConfigurationError:
        raise
    except Exception as error:
        raise AgentConfigurationError(
            "Claude agent failed to generate an answer."
        ) from error

    if not answer:
        raise AgentConfigurationError(
            "Claude agent returned an empty answer."
        )

    artifact = None
    if artifact_request:
        try:
            artifact = build_artifact_result(
                artifact_request,
                answer,
                retrieved_results,
            )
        except Exception as error:
            logger.error(
                "Artifact generation failed",
                extra={
                    "event": "artifact_generation_failure",
                    "provider": "claude",
                    "operation": "parse_artifact",
                    "error_type": type(error).__name__,
                },
            )
            return AgentResponse(
                answer="Artifact generation is temporarily unavailable. Please try again.",
                results=retrieved_results,
            )
        answer = artifact.content
    else:
        answer = _ensure_retrieval_support_statement(answer, retrieved_results)

    return AgentResponse(
        answer=answer,
        results=retrieved_results,
        artifact=artifact,
    )


def _build_claude_options(options_type, server, skill_enabled=False):
    allowed_tools = [CLAUDE_ALLOWED_TOOL]
    if skill_enabled:
        allowed_tools.append(CLAUDE_SKILL_ALLOWED_TOOL)

    return options_type(
        system_prompt=SYSTEM_PROMPT,
        tools=[],
        allowed_tools=allowed_tools,
        disallowed_tools=["Read", "Write", "Edit", "Bash", "WebFetch"],
        mcp_servers={"lenny_transcripts": server},
        strict_mcp_config=True,
        setting_sources=[],
        max_turns=2,
    )
