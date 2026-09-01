"""
Adaptation service.
When the user struggles, this service regenerates patterns using different
approaches — simpler language, different format, more examples, etc.
"""
import json
from typing import List
from app.models.schemas import (
    PatternPreference, GeneratedPattern,
    AdaptPatternsRequest, AdaptPatternsResponse,
)
from app.services.groq_client import GroqClient


SYSTEM_PROMPT = """You are SchemaMind Adapt. The user failed to remember certain concepts using the initial patterns.
Your job is to adapt and try a DIFFERENT approach.

Output valid JSON:
{
  "adapted_patterns": [
    {
      "type": "acronym" | "acrostic" | "analogy" | "number" | "story" | "custom",
      "label": "Short label",
      "content": "The adapted pattern"
    }
  ],
  "adaptation_note": "Brief explanation of what you changed and why"
}

RULES:
1. If a pattern type failed, SWITCH to a different type for that content.
2. If the user got specific concepts wrong, focus on those concepts.
3. Use simpler language, more vivid imagery, more concrete examples.
4. Keep it concise — adapt, don't rewrite everything."""


async def adapt_patterns(req: AdaptPatternsRequest) -> AdaptPatternsResponse:
    client = GroqClient()

    prefs_str = ", ".join(
        p.custom_description if p.type == "custom" else p.type
        for p in req.preferences
    )

    wrong_items = "\n".join(f"- {w}" for w in req.wrong_answers) if req.wrong_answers else "None yet"
    failed_types = ", ".join(req.failed_pattern_types) if req.failed_pattern_types else "None"

    user = f"""The user is studying this text:
---START---
{req.original_text}
---END---

Their preferred pattern types: {prefs_str}

Pattern types that DID NOT work: {failed_types}

Concepts they got wrong / struggled with:
{wrong_items}

Generate NEW adapted patterns that approach the material differently. If a type failed, don't use it again for that same content. Try simpler or more creative approaches."""

    raw = await client.chat_json(SYSTEM_PROMPT, user, temperature=0.4)

    try:
        data = json.loads(raw)
        patterns_data = data.get("adapted_patterns", [])
        note = data.get("adaptation_note", "Patterns adapted based on your progress.")
    except (json.JSONDecodeError, KeyError):
        patterns_data = []
        note = "Adjusted patterns to better match your learning style."

    patterns = []
    for p in patterns_data:
        patterns.append(GeneratedPattern(
            type=p.get("type", "custom"),
            label=p.get("label", "Adapted Pattern"),
            content=p.get("content", ""),
        ))

    return AdaptPatternsResponse(
        adapted_patterns=patterns,
        adaptation_note=note,
    )