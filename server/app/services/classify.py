"""Classify social media posts with Claude: is this a real, current disaster
report, what kind of disaster, and where is it?
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone

import anthropic
from opentelemetry import metrics
from pydantic import BaseModel, Field

from app.config import CLAUDE_MODEL
from app.models import DisasterType, LocationPrecision

logger = logging.getLogger(__name__)
meter = metrics.get_meter(__name__)

CHUNK_SIZE = 25  # posts per Claude request
MAX_CONCURRENCY = 4

SYSTEM_PROMPT = """You review TikTok posts for a disaster-tracking map. For each post, decide:

1. is_current_disaster_report: true only if the post reports or shows a real disaster that is \
happening now or happened in the last few days (eyewitness footage, local news clips, evacuation \
updates). false for hypotheticals, explainers, science or educational content, old footage \
presented as history, memes, ads, prayers or general commentary with no specific event.
2. disaster_type: the kind of disaster, or null if it isn't a disaster report.
3. location: the most specific real place the post identifies, written so a geocoder can find it \
(e.g. "Altadena, California, USA", "Harris County, Texas, USA", "Maui, Hawaii, USA"). Use the \
caption, hashtags and the provided TikTok location fields. Don't guess a place the post doesn't \
support; use null if there's no identifiable location.
4. precision: how specific that location is.

Return one result per post, using the post's id."""


class PostClassification(BaseModel):
    post_id: str
    is_current_disaster_report: bool
    disaster_type: DisasterType | None
    location: str | None
    precision: LocationPrecision | None
    reason: str = Field(description="One short sentence explaining the decision")


class ClassificationBatch(BaseModel):
    results: list[PostClassification]


claude_requests = meter.create_counter(
    "claude.requests", description="Claude classification requests", unit="{request}"
)
claude_duration = meter.create_histogram(
    "claude.request.duration", description="Claude classification request duration", unit="s"
)
claude_tokens = meter.create_counter(
    "claude.tokens", description="Claude tokens used for classification", unit="{token}"
)

_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    # Created lazily so the global OpenTelemetry tracer provider is already
    # registered; the SDK then emits a span per request automatically.
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic()
    return _client


def _post_payload(item: dict) -> dict:
    return {
        "id": str(item.get("id")),
        "caption": item.get("text") or "",
        "hashtags": [h.get("name", "") for h in item.get("hashtags") or []],
        "tiktok_location_country": item.get("locationCreated"),
        "posted_at": item.get("createTimeISO"),
    }


async def classify_posts(items: list[dict]) -> dict[str, PostClassification]:
    """Return classifications keyed by post id. Chunks that fail are skipped."""
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
    chunks = [items[i : i + CHUNK_SIZE] for i in range(0, len(items), CHUNK_SIZE)]

    async def run(chunk: list[dict]) -> list[PostClassification]:
        async with semaphore:
            return await _classify_chunk(chunk)

    results: dict[str, PostClassification] = {}
    for batch in await asyncio.gather(*(run(c) for c in chunks)):
        for r in batch:
            results[r.post_id] = r
    return results


async def _classify_chunk(chunk: list[dict]) -> list[PostClassification]:
    posts = [_post_payload(i) for i in chunk]
    start = time.perf_counter()
    status = "error"
    try:
        response = await _get_client().beta.messages.parse(
            model=CLAUDE_MODEL,
            max_tokens=16000,
            output_config={"effort": "low"},
            # On a safety decline, re-run the request on a fallback model
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                # Today's date goes here, not in the system prompt, so the system prompt stays cacheable
                "content": f"Today is {datetime.now(timezone.utc):%Y-%m-%d}.\n\n"
                + json.dumps(posts, ensure_ascii=False),
            }],
            output_format=ClassificationBatch,
        )
        claude_tokens.add(response.usage.input_tokens, {"direction": "input"})
        claude_tokens.add(response.usage.output_tokens, {"direction": "output"})

        if response.stop_reason == "refusal":
            status = "refusal"
            logger.warning("Claude declined a batch of %d posts", len(chunk))
            return []
        if response.stop_reason == "max_tokens" or response.parsed_output is None:
            status = "truncated"
            logger.warning("Claude output incomplete for %d posts", len(chunk))
            return []

        status = "ok"
        return response.parsed_output.results
    except anthropic.APIStatusError as e:
        logger.error("Claude API error %s (request %s): %s", e.status_code, e.request_id, e.message)
        return []
    except anthropic.APIConnectionError:
        logger.exception("Could not reach the Claude API")
        return []
    finally:
        claude_requests.add(1, {"status": status})
        claude_duration.record(time.perf_counter() - start, {"status": status})
