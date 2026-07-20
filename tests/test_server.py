import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import server


def _fresh(tmp_path):
    server.DATA_FILE = tmp_path / "learners.json"
    return tmp_path


def test_register_and_state(tmp_path):
    _fresh(tmp_path)
    out = server.register_learner("u1", "Aisha", "python-basics")
    assert "Welcome" in out
    state = server.get_learner_state("u1")
    assert "Aisha" in state and '"free"' in state


def test_progress_persists_across_calls(tmp_path):
    _fresh(tmp_path)
    server.register_learner("u2", "Bob")
    out = server.update_progress("u2", "loops", 85, True)
    assert "completed" in out
    st = server.get_learner_state("u2")
    assert "loops" in st and "85" in st


def test_double_register_is_idempotent(tmp_path):
    _fresh(tmp_path)
    server.register_learner("u1", "Aisha")
    again = server.register_learner("u1", "Aisha")
    assert "already registered" in again


def test_content_tools():
    c = server.get_chapter_content("chapter-01")
    assert "# Chapter 1" in c
    e = server.get_exercises("chapter-01")
    assert "1." in e
    assert "not found" not in e


def test_missing_chapter():
    assert "not found" in server.get_chapter_content("nope")


def test_guidance_is_prim_lite():
    g = server.generate_guidance("loops", "beginner")
    assert "PRIMM" in g and "Predict" in g and "Make" in g


def test_assess_response_scoring(tmp_path):
    _fresh(tmp_path)
    a = server.assess_response(
        "u3", "what is a loop", "a loop repeats code. for x in range(3): print(x)"
    )
    assert "Score" in a
    score = int(a.split("Score: ")[1].split("/")[0])
    assert score >= 70


def test_paid_tools_block_free_learner(tmp_path):
    _fresh(tmp_path)
    server.register_learner("u4", "Eve")
    blocked1 = server.submit_code("u4", "print(1)")
    blocked2 = server.get_upgrade_url("u4")
    assert "paid" in blocked1 and "paid" in blocked2


def test_submit_code_paid_path(tmp_path):
    _fresh(tmp_path)
    server._save({"u5": {"name": "Paid", "tier": "paid", "progress": {}, "exchanges_today": 0}})
    assert "PASSED" in server.submit_code("u5", "print(1)")
    assert "BLOCKED" in server.submit_code("u5", "import os; os.system('ls')")
    assert "FAILED" in server.submit_code("u5", "def (:")


def test_upgrade_url_paid_path(tmp_path):
    _fresh(tmp_path)
    server._save({"u6": {"name": "Paid", "tier": "paid", "progress": {}, "exchanges_today": 0}})
    url = server.get_upgrade_url("u6")
    assert "stripe.com" in url and "u6" in url
