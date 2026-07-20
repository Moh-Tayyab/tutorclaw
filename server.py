"""TutorClaw MCP server.

A 9-tool tutoring product for OpenClaw (Chapter 58).
Everything runs locally: JSON files hold learner state, markdown files
hold course content, and Stripe/sandbox are mocked so the product
can be built and tested without external accounts.

Tools (free tier):
  1. register_learner     2. get_learner_state    3. update_progress
  4. get_chapter_content  5. get_exercises
  6. generate_guidance    7. assess_response
Tools (paid tier):
  8. submit_code          9. get_upgrade_url
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

from mcp.server.fastmcp import FastMCP

ROOT = Path(__file__).parent
DATA_FILE = ROOT / "data" / "learners.json"
CONTENT_DIR = ROOT / "content"
PAID_TOOLS = {"submit_code", "get_upgrade_url"}
FREE_EXCHANGES_PER_DAY = 5

_lock = threading.Lock()

mcp = FastMCP("TutorClaw")


# --------------------------------------------------------------------------
# State helpers
# --------------------------------------------------------------------------
def _load() -> dict:
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text())
    return {}


def _save(data: dict) -> None:
    DATA_FILE.write_text(json.dumps(data, indent=2))


def _get_learner(learner_id: str) -> dict | None:
    with _lock:
        return _load().get(learner_id)


def _check_tier(learner_id: str) -> str:
    learner = _get_learner(learner_id)
    if learner is None:
        # Unknown learners default to free; registration happens via register_learner.
        return "free"
    return learner.get("tier", "free")


# --------------------------------------------------------------------------
# Free-tier exchange accounting (lightweight gate for paid tools)
# --------------------------------------------------------------------------
def _enforce_tier(learner_id: str, tool: str) -> str | None:
    """Return an error string if a paid tool is used on a free account."""
    if tool in PAID_TOOLS and _check_tier(learner_id) != "paid":
        return (
            f"Tool '{tool}' requires a paid plan. "
            f"Reply 'upgrade me' or call get_upgrade_url to unlock code "
            f"submission and checkout."
        )
    return None


# --------------------------------------------------------------------------
# 1-3: State tools
# --------------------------------------------------------------------------
@mcp.tool()
def register_learner(learner_id: str, name: str, topic: str = "python-basics") -> str:
    """Register a new learner. Creates a JSON profile with tier=free.

    Args:
        learner_id: stable unique id (e.g. telegram chat id).
        name: learner's preferred name.
        topic: starting learning track.
    """
    with _lock:
        data = _load()
        if learner_id in data:
            return f"Learner {name} ({learner_id}) already registered."
        data[learner_id] = {
            "name": name,
            "topic": topic,
            "tier": "free",
            "progress": {},
            "exchanges_today": 0,
            "registered_at": _now(),
        }
        _save(data)
    return (
        f"Welcome, {name}! You're registered for '{topic}'.\n"
        f"Type 'start' to begin, or ask me a question anytime."
    )


@mcp.tool()
def get_learner_state(learner_id: str) -> str:
    """Read a learner's current profile: tier, topic, and progress."""
    learner = _get_learner(learner_id)
    if learner is None:
        return "No learner found. Call register_learner first."
    return json.dumps(learner, indent=2)


@mcp.tool()
def update_progress(learner_id: str, topic: str, score: int, completed: bool = False) -> str:
    """Record a score for a topic and optionally mark it completed.

    Args:
        learner_id: learner id used at registration.
        topic: topic name.
        score: integer 0-100.
        completed: mark the topic done.
    """
    learner = _get_learner(learner_id)
    if learner is None:
        return "No learner found. Call register_learner first."
    with _lock:
        data = _load()
        rec = data[learner_id]
        rec["progress"][topic] = {
            "score": max(0, min(100, int(score))),
            "completed": bool(completed),
            "updated_at": _now(),
        }
        _save(data)
    verb = "completed" if completed else "updated"
    return f"Progress {verb} for '{topic}': score {score}."


# --------------------------------------------------------------------------
# 4-5: Content tools
# --------------------------------------------------------------------------
@mcp.tool()
def get_chapter_content(chapter: str) -> str:
    """Load a course chapter's markdown content from local files.

    Args:
        chapter: chapter slug, e.g. 'chapter-01'.
    """
    path = CONTENT_DIR / f"{chapter}.md"
    if not path.exists():
        available = sorted(p.name[:-3] for p in CONTENT_DIR.glob("*.md"))
        return f"Chapter '{chapter}' not found. Available: {available}"
    return path.read_text()


@mcp.tool()
def get_exercises(chapter: str) -> str:
    """Return the exercise section for a chapter (parsed from its markdown)."""
    path = CONTENT_DIR / f"{chapter}.md"
    if not path.exists():
        return f"Chapter '{chapter}' not found."
    text = path.read_text()
    # Exercises live under an '## Exercises' heading.
    if "## Exercises" in text:
        return text.split("## Exercises", 1)[1].strip()
    return f"No exercises section in '{chapter}'."


# --------------------------------------------------------------------------
# 6-7: Pedagogy tools (PRIMM-Lite)
# --------------------------------------------------------------------------
@mcp.tool()
def generate_guidance(topic: str, level: str = "beginner") -> str:
    """Produce a PRIMM-Lite scaffold for a topic.

    PRIMM = Predict, Run, Investigate, Modify, Make.
    Returns a structured prompt the tutor walks the learner through.

    Args:
        topic: the concept to teach.
        level: beginner | intermediate | advanced.
    """
    return f"""# PRIMM-Lite: {topic} ({level})

**Predict** - Before any code, what do you think this prints?
```
print("hello from {topic}")
```

**Run** - Execute it. What actually happened vs your prediction?

**Investigate** - Change the string. What rules govern `print()`?

**Modify** - Make it print your name 3 times using a loop.

**Make** - Write a tiny program using `{topic}` that solves a real problem you have.

Reply with your Predict answer and I'll guide the rest.
"""


@mcp.tool()
def assess_response(learner_id: str, question: str, answer: str) -> str:
    """Grade a learner's answer against a lightweight rubric.

    Returns a score (0-100), what was strong, and one next step.
    This is a heuristic grader (no external LLM call) so it runs offline.
    """
    err = _enforce_tier(learner_id, "assess_response")
    if err:
        return err
    a = (answer or "").strip()
    q = (question or "").strip()
    al = a.lower()
    score = 0
    notes = []
    if len(a) < 10:
        notes.append("Answer is too short to assess meaningfully.")
    else:
        score += 30
        notes.append("Answer has substance.")
    code_markers = ("for ", "while ", "print(", "def ", "=", ":")
    if any(m in al for m in code_markers):
        score += 25
        notes.append("Includes runnable code, not just prose.")
    q_terms = [w for w in q.lower().split() if len(w) > 3]
    if q_terms and any(w in al for w in q_terms):
        score += 25
        notes.append("Addresses the question's key terms.")
    if "\n" in a or len(a) > 80:
        score += 20
        notes.append("Shows reasoning or elaboration.")
    score = min(100, score)
    next_step = (
        "Add a concrete example to strengthen this."
        if score < 70
        else "Solid. Try the Make step to apply it."
    )
    return f"Score: {score}/100\nStrong: {notes[0] if notes else 'n/a'}\nNext: {next_step}"


# --------------------------------------------------------------------------
# 8-9: Code + Upgrade tools (paid)
# --------------------------------------------------------------------------
@mcp.tool()
def submit_code(learner_id: str, code: str) -> str:
    """Submit learner code to a (mock) sandbox and report pass/fail.

    Paid tier only. The sandbox is mocked: it checks the code
    parses as Python and contains no obvious banned calls.
    """
    err = _enforce_tier(learner_id, "submit_code")
    if err:
        return err
    try:
        compile(code, "<learner>", "exec")
    except SyntaxError as e:
        return f"FAILED: syntax error on line {e.lineno}: {e.msg}"
    banned = ("os.system", "subprocess", "eval(", "exec(")
    for b in banned:
        if b in code:
            return f"BLOCKED: discouraged call '{b}' detected. Refactor and resubmit."
    return "PASSED: code parsed and passed the mock sandbox checks. Nice work!"


@mcp.tool()
def get_upgrade_url(learner_id: str) -> str:
    """Return a (mock) Stripe checkout URL to upgrade to the paid plan.

    Paid tier only. In production this calls Stripe and returns a real
    checkout session URL; here it returns a deterministic test-mode link.
    """
    err = _enforce_tier(learner_id, "get_upgrade_url")
    if err:
        return err
    learner = _get_learner(learner_id)
    name = learner.get("name", "learner") if learner else "learner"
    return (
        f"https://checkout.stripe.com/mock/tutorclaw-pro?learner={learner_id}"
        f"&name={name}&plan=pro\n"
        f"(Test mode) Upgrade unlocks submit_code and get_upgrade_url."
    )


# --------------------------------------------------------------------------
def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    mcp.run()
