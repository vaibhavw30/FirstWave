import json
import logging
import os
import re

from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Pydantic models ──────────────────────────────────────────────────────────

class ContextModel(BaseModel):
    hour: int = 20
    dow: int = 4
    weather: str = "none"
    ambulances: int = 5
    top_zones: list = []   # [{"zone": str, "borough": str, "count": float}]
    coverage: dict = {}    # {"pct_static": float, "pct_staged": float, "median_saved_sec": float}


class AiRequest(BaseModel):
    message: str | None = None
    context: ContextModel = ContextModel()


class AiResponse(BaseModel):
    reply: str
    controls: dict | None = None


# ── Helper: build context string ────────────────────────────────────────────

_DOW_LABELS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

def _build_context_str(ctx: ContextModel) -> str:
    hour_label = f"{ctx.hour % 12 or 12}{'AM' if ctx.hour < 12 else 'PM'}"
    day_label = _DOW_LABELS[ctx.dow] if 0 <= ctx.dow <= 6 else f"day {ctx.dow}"

    zones_str = ", ".join(
        f"Zone {z['zone']} ({z['borough']}): {z['count']:.1f} calls/hr"
        for z in (ctx.top_zones or [])[:5]
    ) or "no zone data available"

    cov = ctx.coverage or {}
    pct_static = cov.get("pct_static", "N/A")
    pct_staged = cov.get("pct_staged", "N/A")
    saved = cov.get("median_saved_sec", "N/A")
    if isinstance(pct_static, float): pct_static = f"{pct_static:.1f}"
    if isinstance(pct_staged, float): pct_staged = f"{pct_staged:.1f}"
    if isinstance(saved, float): saved = f"{saved:.0f}"

    return (
        f"Time: {day_label} {hour_label} | Weather: {ctx.weather} | Ambulances: {ctx.ambulances}\n"
        f"Top predicted zones: {zones_str}\n"
        f"Coverage without staging: {pct_static}% within 8 min\n"
        f"Coverage WITH FirstWave staging: {pct_staged}% within 8 min ({saved}s median saved)"
    )


# ── Helper: parse control JSON from reply ───────────────────────────────────

_CONTROLS_RE = re.compile(r'\{"controls"\s*:\s*(\{[^}]+\})\}', re.IGNORECASE)

def _extract_controls(text: str) -> tuple[str, dict | None]:
    """Return (clean_reply, controls_dict | None)."""
    m = _CONTROLS_RE.search(text)
    if not m:
        return text.strip(), None
    try:
        raw = '{"controls":' + m.group(1) + '}'
        parsed = json.loads(raw)
        controls = parsed.get("controls", {})
        # Strip JSON block from reply
        clean = _CONTROLS_RE.sub("", text).strip()
        return clean, controls if controls else None
    except Exception:
        return text.strip(), None


# ── Canned fallback (no API key) ────────────────────────────────────────────

_FALLBACK_BRIEFING = (
    "OPENAI_API_KEY not configured — AI briefing unavailable. "
    "Set OPENAI_API_KEY in backend/.env and restart the server."
)


# ── Main endpoint ────────────────────────────────────────────────────────────

@router.post("/ai", response_model=AiResponse)
async def ai_dispatcher(req: AiRequest):
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key or not api_key.startswith("sk-"):
        return AiResponse(reply=_FALLBACK_BRIEFING, controls=None)

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=api_key)
    except ImportError:
        return AiResponse(reply="openai package not installed. Run: pip install openai>=1.0.0", controls=None)

    ctx_str = _build_context_str(req.context)

    system_prompt = (
        "You are an AI briefing system for FirstWave, an NYC EMS predictive ambulance staging tool. "
        "You help dispatchers understand demand patterns using real ML predictions. "
        "Zone legend: B=Bronx, K=Brooklyn, M=Manhattan, Q=Queens, S=Staten Island. "
        "8 minutes (480 seconds) is the clinical response time target. "
        "Keep responses concise, professional, and actionable.\n\n"
        f"Current snapshot:\n{ctx_str}"
    )

    if req.message is None:
        # Auto-briefing mode
        user_message = (
            "Generate a 3-sentence operational briefing for the dispatcher covering: "
            "which zone has highest demand and why it matters, the coverage improvement FirstWave provides, "
            "and one concrete recommendation. Plain text only, no markdown, professional dispatcher tone."
        )
    else:
        user_message = (
            f'Dispatcher asks: "{req.message}"\n'
            "Respond in 2-3 sentences.\n"
            "Day-of-week mapping (STRICT): Monday=0, Tuesday=1, Wednesday=2, Thursday=3, Friday=4, Saturday=5, Sunday=6.\n"
            "If the message implies a specific day, you MUST include dow in controls. "
            "If it implies a specific time (e.g. 'night'=20, 'evening'=19, 'morning'=8, 'afternoon'=14), include hour. "
            "When both day AND time are implied, include BOTH fields.\n"
            "End your response with a JSON block on its own line ONLY if a control should change:\n"
            '{"controls": {"hour": N, "dow": N}}\n'
            "If nothing should change, omit the JSON block entirely."
        )

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            max_tokens=300,
            temperature=0.7,
        )
        raw_reply = response.choices[0].message.content or ""
        reply, controls = _extract_controls(raw_reply)
        return AiResponse(reply=reply, controls=controls)

    except Exception as exc:
        logger.error("OpenAI call failed: %s", exc)
        return AiResponse(reply=f"AI briefing temporarily unavailable. ({type(exc).__name__})", controls=None)
