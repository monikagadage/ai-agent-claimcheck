"""M0 regression suite for receipts. Stdlib unittest, no deps.

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from receipts.claims import extract_claims
from receipts.checks import run_all_checks
from receipts.session import Session
from receipts.verify import build_output
from tests._build import Transcript, hook_input


class TmpMixin(unittest.TestCase):
    def setUp(self) -> None:
        self._d = tempfile.TemporaryDirectory()
        self.dir = Path(self._d.name)
        self.addCleanup(self._d.cleanup)

    def sess(self, final: str, t: Transcript) -> Session:
        tp = t.dump(self.dir / "t.jsonl")
        return Session.from_hook_input(hook_input(final, tp, cwd=str(self.dir)))

    def findings(self, final: str, t: Transcript):
        s = self.sess(final, t)
        return run_all_checks(s, extract_claims(final))


# --------------------------------------------------------------------------- claims

class TestClaims(unittest.TestCase):
    def test_positive_test_claims(self):
        for m in ["All tests pass.", "The tests are passing now.", "Test suite is green.",
                  "I ran the suite and all 42 tests pass."]:
            self.assertTrue(any(c.kind == "tests" for c in extract_claims(m)), m)

    def test_negative_test_claims(self):
        for m in ["Make sure the tests pass before merging.",
                  "If the tests pass we can ship.",
                  "Do the tests pass?",
                  "You should run the tests."]:
            self.assertFalse(any(c.kind == "tests" for c in extract_claims(m)), m)

    def test_build_claims(self):
        self.assertTrue(any(c.kind == "build" for c in extract_claims("It compiles cleanly now.")))
        self.assertTrue(any(c.kind == "build" for c in extract_claims("No type errors.")))
        self.assertFalse(any(c.kind == "build" for c in extract_claims("Does it build?")))

    def test_edit_claims_capture_path(self):
        cs = extract_claims("I updated `src/auth.py` and created config.toml.")
        paths = {c.target for c in cs if c.kind == "edit"}
        self.assertEqual(paths, {"src/auth.py", "config.toml"})

    def test_agreement_claim(self):
        cs = extract_claims("As we decided, using Redis for the throttle.")
        self.assertTrue(any(c.kind == "agreement" for c in cs))


# --------------------------------------------------------------------------- tests check

class TestTestsCheck(TmpMixin):
    def test_claim_but_no_test_ran(self):
        f = self.findings("All tests pass.", Transcript().user("build it").say("done").bash("ls"))
        self.assertEqual([x.kind for x in f], ["tests"])
        self.assertIn("no test command ran", f[0].reason)

    def test_claim_and_pytest_passed(self):
        t = Transcript().user("fix bug").bash("pytest -q", "12 passed in 0.3s")
        self.assertEqual(self.findings("All tests pass.", t), [])

    def test_claim_and_only_failing_test(self):
        t = Transcript().user("fix bug").bash("pytest -q", "1 failed", exit_code=1)
        f = self.findings("All tests pass now.", t)
        self.assertEqual([x.kind for x in f], ["tests"])
        self.assertIn("failed", f[0].reason)

    def test_failing_then_passing_is_ok(self):
        t = (Transcript().user("fix bug")
             .bash("pytest -q", "1 failed", exit_code=1)
             .bash("pytest -q", "12 passed"))
        self.assertEqual(self.findings("All tests pass now.", t), [])

    def test_subagent_test_run_counts(self):
        t = Transcript().user("fix bug").bash("go test ./...", "ok", sidechain=True)
        self.assertEqual(self.findings("Tests pass.", t), [])


# --------------------------------------------------------------------------- build check

class TestBuildCheck(TmpMixin):
    def test_claim_but_no_build(self):
        f = self.findings("It compiles cleanly.", Transcript().user("x").bash("echo hi"))
        self.assertEqual([x.kind for x in f], ["build"])

    def test_claim_and_javac_ok(self):
        t = Transcript().user("x").bash("javac -d out src/*.java", "")
        self.assertEqual(self.findings("It compiles cleanly now.", t), [])

    def test_claim_and_tsc_failed(self):
        t = Transcript().user("x").bash("npx tsc --noEmit", "error TS2304", exit_code=2)
        f = self.findings("No type errors.", t)
        self.assertEqual([x.kind for x in f], ["build"])


# --------------------------------------------------------------------------- edits check

class TestEditsCheck(TmpMixin):
    def test_claimed_file_not_touched(self):
        t = Transcript().user("x").edit("src/routes.py").edit("src/config.py")
        f = self.findings("I updated `src/auth.py`.", t)
        self.assertEqual([x.kind for x in f], ["edit"])
        self.assertIn("routes.py", f[0].evidence)

    def test_claimed_file_touched(self):
        t = Transcript().user("x").edit("src/auth.py")
        self.assertEqual(self.findings("I updated auth.py.", t), [])

    def test_write_tool_counts(self):
        t = Transcript().user("x").write("config.toml")
        self.assertEqual(self.findings("I created config.toml.", t), [])

    def test_bash_rm_counts(self):
        t = Transcript().user("x").bash("rm old_module.py")
        self.assertEqual(self.findings("I deleted old_module.py.", t), [])


# --------------------------------------------------------------------------- agreements check

class TestAgreementsCheck(TmpMixin):
    def test_invented_agreement(self):
        t = Transcript().user("please add rate limiting to the API")
        f = self.findings("As we agreed, using a Redis token bucket.", t)
        self.assertEqual([x.kind for x in f], ["agreement"])

    def test_real_agreement(self):
        t = Transcript().user("let's use a Redis token bucket for rate limiting")
        self.assertEqual(self.findings("As we agreed, using a Redis token bucket.", t), [])


# --------------------------------------------------------------------------- verify glue

class TestBuildOutput(TmpMixin):
    def _payload(self, final, t, **kw):
        tp = t.dump(self.dir / "t.jsonl")
        return hook_input(final, tp, cwd=str(self.dir), **kw)

    def test_clean_session_no_output(self):
        t = Transcript().user("x").bash("pytest", "5 passed").edit("a.py")
        self.assertEqual(build_output(self._payload("Updated a.py, tests pass.", t)), {})

    def test_warn_only_by_default(self):
        t = Transcript().user("x").say("done")
        out = build_output(self._payload("All tests pass.", t))
        self.assertIn("systemMessage", out)
        self.assertNotIn("decision", out.get("hookSpecificOutput", {}))
        self.assertIn("no test command ran", out["systemMessage"])

    def test_strict_blocks(self):
        (self.dir / ".receipts.json").write_text(json.dumps({"strict": True}))
        t = Transcript().user("x").say("done")
        out = build_output(self._payload("All tests pass.", t))
        self.assertEqual(out["hookSpecificOutput"]["decision"], "block")
        self.assertIn("additionalContext", out["hookSpecificOutput"])

    def test_stop_hook_active_is_noop(self):
        t = Transcript().user("x").say("done")
        self.assertEqual(build_output(self._payload("All tests pass.", t, stop_hook_active=True)), {})

    def test_no_final_message_is_noop(self):
        t = Transcript().user("x").say("done")
        self.assertEqual(build_output(self._payload("", t)), {})

    def test_ignore_config(self):
        (self.dir / ".receipts.json").write_text(json.dumps({"ignore": ["tests"]}))
        t = Transcript().user("x").say("done")
        self.assertEqual(build_output(self._payload("All tests pass.", t)), {})

    def test_missing_transcript_is_noop(self):
        payload = hook_input("All tests pass.", "/no/such/transcript.jsonl", cwd=str(self.dir))
        self.assertEqual(build_output(payload), {})


# --------------------------------------------------------------------------- session parsing

class TestSession(TmpMixin):
    def test_exit_code_parsed(self):
        t = Transcript().user("x").bash("pytest", "boom", exit_code=1)
        s = self.sess("hi", t)
        self.assertEqual(s.commands[0].exit_code, 1)
        self.assertFalse(s.commands[0].ok)

    def test_real_user_vs_tool_result(self):
        t = Transcript().user("do the thing").bash("ls", "file1")
        s = self.sess("hi", t)
        self.assertEqual(s.user_messages, ["do the thing"])

    def test_missing_transcript_is_survivable(self):
        s = Session.from_hook_input({"last_assistant_message": "hey", "transcript_path": "/nope/x.jsonl"})
        self.assertEqual(s.final_message, "hey")
        self.assertFalse(s.transcript_found)

    def test_garbage_lines_skipped(self):
        t = Transcript().raw({"type": "queue-operation", "junk": 1}).user("x").bash("pytest", "ok")
        s = self.sess("hi", t)
        self.assertEqual(len(s.commands), 1)


if __name__ == "__main__":
    unittest.main()
