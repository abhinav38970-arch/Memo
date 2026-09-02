"""
Pattern generation service.
Takes raw text + user preferences → returns memory-aid patterns in JSON.
"""
import json
from typing import Dict, List, Optional

from app.models.schemas import GeneratePatternsResponse, GeneratedPattern, PatternPreference
from app.services.groq_client import GroqClient

VARIATIONS_PER_TYPE = 4

# Completion-token budget: ~120 tokens per pattern (label + 1-4 sentences +
# JSON overhead) plus a little headroom for the model's (low-effort) reasoning.
TOKENS_PER_PATTERN = 120
BUDGET_HEADROOM = 256


SYSTEM_PROMPT = """You are SchemaMind, an AI that transforms educational text into memory-optimized patterns.
You analyze text the user needs to memorize and generate creative memory aids in formats that work for THEM.

Your output MUST be valid JSON matching this exact structure:
{
  "patterns": [
    {
      "type": "acronym" | "acrostic" | "analogy" | "number" | "story" | "custom",
      "label": "Short descriptive label",
      "content": "The full pattern/explanation",
      "variation": 1
    }
  ]
}

RULES:
1. Generate EXACTLY FOUR distinct variations per preferred type the user selected — no more, no less. Number them "variation": 1, 2, 3, 4 within each type.
2. The four variations of a type must take genuinely DIFFERENT approaches — different angles, hooks, images, examples, or wordings — never four rephrasings of the same idea.
3. Each pattern must be genuinely useful for memorizing the key concepts in the text.
4. For "custom" types, follow the user's description of how they memorize best.
5. Be creative but accurate — don't invent facts.
6. Keep patterns concise (1-4 sentences each). Do not repeat the source text.
7. The content should be something the user can actually recall from memory. If the user picks custom preference, adapt to their style exactly.
8. Output only the JSON object — no markdown, no commentary."""


def _build_user_prompt(text: str, preferences: List[PatternPreference]) -> str:
    prefs_lines = []
    for p in preferences:
        if p.type == "custom":
            prefs_lines.append(f"- Custom: {p.custom_description}")
        else:
            prefs_lines.append(f"- {p.type}")
    prefs_str = "\n".join(prefs_lines)

    return f"""Here is the text the user needs to memorize:
---START TEXT---
{text.strip()}
---END TEXT---

The user wants memory patterns in these formats:
{prefs_str}

Generate exactly FOUR distinct variations (numbered "variation": 1-4) for EACH format requested, so the user can pick the one that clicks. Group them by format. Return as JSON."""


def _variation_number(value) -> Optional[int]:
    """Coerce the model's "variation" field to an int, tolerating strings."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def completion_budget(n_preferences: int) -> Dict[str, int]:
    """``max_tokens`` / ``min_tokens`` hints for ``n_preferences`` pattern types.

    ``max_tokens`` comfortably fits 4 variations per type; ``min_tokens`` is the
    smallest budget that still yields a useful (if slightly shorter) answer —
    below it the client waits for the rate-limit window instead of sending a
    request that would be truncated.
    """
    n = max(1, n_preferences)
    patterns = n * VARIATIONS_PER_TYPE
    desired = patterns * TOKENS_PER_PATTERN + BUDGET_HEADROOM
    minimum = patterns * (TOKENS_PER_PATTERN // 2) + BUDGET_HEADROOM
    return {"max_tokens": max(desired, 1024), "min_tokens": max(minimum, 512)}


def parse_patterns(raw: str, default_label: str = "Memory Pattern", key: str = "patterns") -> List[GeneratedPattern]:
    """Turn the model's JSON into validated ``GeneratedPattern`` objects.

    Tolerates a bare list, a list under a different key, missing/invalid
    variation numbers (filled in per type), and skips empty entries.
    """
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []

    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = data.get(key)
        if not isinstance(items, list):
            # Accept any list-valued field (models sometimes rename the key).
            items = next((v for v in data.values() if isinstance(v, list)), [])
    else:
        items = []

    patterns: List[GeneratedPattern] = []
    counters: Dict[str, int] = {}
    for p in items:
        if not isinstance(p, dict):
            continue
        content = p.get("content")
        if not isinstance(content, str) or not content.strip():
            continue
        ptype = p.get("type")
        ptype = ptype.strip().lower() if isinstance(ptype, str) and ptype.strip() else "custom"
        label = p.get("label")
        label = label.strip() if isinstance(label, str) and label.strip() else default_label
        counters[ptype] = counters.get(ptype, 0) + 1
        variation = _variation_number(p.get("variation"))
        if variation is None or variation < 1:
            variation = counters[ptype]
        patterns.append(GeneratedPattern(
            type=ptype,
            label=label,
            content=content.strip(),
            variation=variation,
        ))
    return patterns


async def generate_patterns(
    text: str,
    preferences: List[PatternPreference],
) -> GeneratePatternsResponse:
    client = GroqClient()
    user = _build_user_prompt(text, preferences)
    raw = await client.chat_json(SYSTEM_PROMPT, user, **completion_budget(len(preferences)))
    return GeneratePatternsResponse(patterns=parse_patterns(raw))
