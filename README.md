# TutorClaw — 9-Tool AI Tutor (MCP Server for OpenClaw)

> **Business value:** WhatsApp/Telegram par chalne wala AI tutor jo students ko register karta hai, chapter parhata hai, exercise deta hai, score karta hai — free tier + paid Stripe upgrade ke sath.

**Stack:** Python 3.10+, MCP (FastMCP), JSON state, Markdown content, Stripe (mock → real ready)

![Python](https://img.shields.io/badge/Python-3.10+-blue) ![MCP](https://img.shields.io/badge/MCP-FastMCP-purple) ![License](https://img.shields.io/badge/License-MIT-green)

## Demo
🎥 Loom video: (LINK DALO — 2 min: register → chapter → exercise → score → upgrade)

## 9 Tools
Free (7): `register_learner` `get_learner_state` `update_progress` `get_chapter_content` `get_exercises` `generate_guidance` `assess_response`
Paid (2): `submit_code` (mock sandbox) `get_upgrade_url` (mock Stripe → real ready)

Pedagogy: PRIMM-Lite (Predict → Run → Investigate → Modify → Make). Grader offline heuristic hai, koi LLM cost nahi.

## Run in 3 commands
```bash
pip install "mcp>=1.2.0"
python server.py
pytest tests/ -v
```

Claude Desktop / OpenClaw me as MCP server add karo, phir:
```
register_learner(learner_id="123", name="Ali", topic="python-basics")
get_chapter_content(chapter="chapter-01")
```

## Structure
```
server.py        # 295 lines — all 9 tools + tier gate + sandbox mock
content/         # chapter-01.md (Exercises heading ke neeche exercises)
data/            # learners.json (auto-created state)
tests/           # test_server.py
pyproject.toml   # uv / pip install
```

## Free → Paid logic
`FREE_EXCHANGES_PER_DAY = 5`. Paid tools (`submit_code`, `get_upgrade_url`) free tier par blocked hain — reply me upgrade link milta hai. Production me `get_upgrade_url` ko real Stripe checkout session se replace karo.

## What I can build for you
Same pattern se academy/coaching ke liye WhatsApp homework bot, test-check bot. Email: m.tayyab1263@gmail.com
