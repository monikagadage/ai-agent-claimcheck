"""Regression suite for claimcheck. Stdlib unittest, no deps.

python -m unittest discover -s tests -v
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from claimcheck.adapters.claude_code import parse
from claimcheck.checks import run_all_checks
from claimcheck.claims import extract_claims
from claimcheck.cli import main as cli_main
from tests._build import Transcript, hook_input


class TmpMixin(unittest.TestCase):
    def setUp(self) -> None:
        self._d = tempfile.TemporaryDirectory()
        self.dir = Path(self._d.name)
        self.addCleanup(self._d.cleanup)

    def turn(self, final: str, t: Transcript):
        tp = t.dump(self.dir / "t.jsonl")
        return parse(hook_input(final, tp, cwd=str(self.dir)))

    def findings(self, final: str, t: Transcript):
        return run_all_checks(self.turn(final, t), extract_claims(final))

    def run_cli(self, payload, argv=("--from", "claude-code"), raw_stdin=None):
        buf, err = io.StringIO(), io.StringIO()
        old_stdin = sys.stdin
        sys.stdin = io.StringIO(raw_stdin if raw_stdin is not None else json.dumps(payload))
        try:
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
                code = cli_main(list(argv))
        finally:
            sys.stdin = old_stdin
        return code, buf.getvalue().strip()

    def payload(self, final, t, **kw):
        return hook_input(final, t.dump(self.dir / "t.jsonl"), cwd=str(self.dir), **kw)


# --------------------------------------------------------------------------- claims


class TestClaims(unittest.TestCase):
    def test_positive_test_claims(self):
        for m in [
            "All tests pass.",
            "The tests are passing now.",
            "Test suite is green.",
            "I ran the suite and all 42 tests pass.",
        ]:
            self.assertTrue(any(c.kind == "tests" for c in extract_claims(m)), m)

    def test_negative_test_claims(self):
        for m in [
            "Make sure the tests pass before merging.",
            "If the tests pass we can ship.",
            "Do the tests pass?",
            "You should run the tests.",
        ]:
            self.assertFalse(any(c.kind == "tests" for c in extract_claims(m)), m)

    def test_build_claims(self):
        self.assertTrue(any(c.kind == "build" for c in extract_claims("It compiles cleanly now.")))
        self.assertTrue(any(c.kind == "build" for c in extract_claims("No type errors.")))
        self.assertFalse(any(c.kind == "build" for c in extract_claims("Does it build?")))

    def test_edit_claims_capture_path(self):
        cs = extract_claims("I updated `src/auth.py` and created config.toml.")
        self.assertEqual({c.target for c in cs if c.kind == "edit"}, {"src/auth.py", "config.toml"})

    def test_agreement_claim(self):
        cs = extract_claims("As we decided, using Redis for the throttle.")
        self.assertTrue(any(c.kind == "agreement" for c in cs))

    def test_quoted_phrase_is_not_a_claim(self):
        # the agent discussing / quoting a claim, not making one (first dogfood FP)
        msg = 'For example: *"I updated payment_service.py and all tests pass"* would be flagged.'
        self.assertEqual(extract_claims(msg), [])

    def test_blockquote_is_not_a_claim(self):
        self.assertEqual(extract_claims("> I updated auth.py and the tests pass"), [])

    def test_fenced_code_is_not_a_claim(self):
        msg = "Output was:\n```\nI updated main.py, all tests pass\n```\nlooks right."
        self.assertEqual(extract_claims(msg), [])

    def test_backticked_filename_is_still_a_claim(self):
        cs = extract_claims("I updated `auth.py` for the fix.")
        self.assertEqual([c.target for c in cs if c.kind == "edit"], ["auth.py"])

    def test_hypothetical_sentence_is_not_a_claim(self):
        for m in [
            "For example, if I updated auth.py it would be flagged.",
            "A real claim (e.g. I updated config.py) gets checked.",
            "Such as when I created migrations.py during a run.",
        ]:
            self.assertEqual(extract_claims(m), [], m)

    def test_long_parenthetical_aside_is_not_a_claim(self):
        msg = "The fix works (previously I updated auth.py by hand which was error-prone)."
        self.assertEqual(extract_claims(msg), [])

    def test_reported_and_denied_claims_are_not_claims(self):
        for m in [
            "It states that I updated database.py and that integration tests pass — neither happened.",
            "The summary claims that all tests pass, but no test command ran.",
            "I did not run the tests, though the code looks right.",
            "I didn't update config.py in the end.",
            "The README says the tests pass on CI.",
        ]:
            self.assertEqual(extract_claims(m), [], m)

    def test_hedged_and_future_claims_are_not_claims(self):
        for m in [
            "The tests should pass now.",
            "This will compile once you install the SDK.",
            "The build would succeed if the proto files were regenerated.",
            "Assuming the migration ran, all tests pass.",
            "Hopefully the type check passes.",
        ]:
            self.assertEqual(extract_claims(m), [], m)

    def test_restating_the_goal_is_not_a_claim(self):
        for m in [
            "You asked me to make the tests pass and get the build green.",
            "The task was to get all tests passing.",
            "The goal is a clean build with no type errors.",
        ]:
            self.assertEqual(extract_claims(m), [], m)

    def test_other_session_work_is_not_a_claim(self):
        for m in [
            "Previously I updated auth.py and the tests passed.",
            "In an earlier session we ran the full suite and it passed.",
            "Earlier today the build compiled cleanly.",
        ]:
            self.assertEqual(extract_claims(m), [], m)

    def test_transitive_passes_is_not_a_test_claim(self):
        for m in [
            "This test passes a mock database to the constructor.",
            "The helper passes the config through to the client.",
        ]:
            self.assertFalse(any(c.kind == "tests" for c in extract_claims(m)), m)

    def test_hedged_outcome_still_keeps_the_edit_claim(self):
        # "should fix the bug" hedges the outcome, not whether the edit happened
        cs = extract_claims("I updated `parser.py`, which should fix the crash.")
        self.assertEqual([c.target for c in cs if c.kind == "edit"], ["parser.py"])


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
        t = (
            Transcript()
            .user("fix bug")
            .bash("pytest -q", "1 failed", exit_code=1)
            .bash("pytest -q", "12 passed")
        )
        self.assertEqual(self.findings("All tests pass now.", t), [])

    def test_subagent_test_run_counts(self):
        t = Transcript().user("fix bug").bash("go test ./...", "ok", sidechain=True)
        self.assertEqual(self.findings("Tests pass.", t), [])

    def test_python3_dash_m(self):
        t = Transcript().user("x").bash("python3 -m pytest", "3 passed")
        self.assertEqual(self.findings("All tests pass.", t), [])

    def test_n_tests_green_phrasing(self):
        for m in ["12 tests green.", "12 tests passing.", "48 passed.", "12/12 tests green."]:
            self.assertTrue(any(c.kind == "tests" for c in extract_claims(m)), m)

    def test_gradle_jvmtest_counts(self):
        t = Transcript().user("x").bash("./gradlew :shared:jvmTest", "BUILD SUCCESSFUL")
        self.assertEqual(self.findings("12 tests green against the seed.", t), [])

    def test_n_tests_green_with_no_test_run_is_flagged(self):
        t = Transcript().user("x").say("done").bash("ls")
        f = self.findings("12 tests green.", t)
        self.assertEqual([x.kind for x in f], ["tests"])


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
        self.assertEqual([x.kind for x in self.findings("No type errors.", t)], ["build"])


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


# --------------------------------------------------------------------------- CLI / hook flow


class TestCli(TmpMixin):
    def test_clean_session_prints_empty_object(self):
        t = Transcript().user("x").bash("pytest", "5 passed").edit("a.py")
        code, out = self.run_cli(self.payload("Updated a.py, tests pass.", t))
        self.assertEqual((code, out), (0, "{}"))

    def test_warn_only_by_default(self):
        t = Transcript().user("x").say("done")
        _, out = self.run_cli(self.payload("All tests pass.", t))
        data = json.loads(out)
        self.assertIn("systemMessage", data)
        self.assertNotIn("decision", data.get("hookSpecificOutput", {}))
        self.assertIn("no test command ran", data["systemMessage"])
        self.assertIn("claimcheck", data["systemMessage"])

    def test_strict_blocks(self):
        (self.dir / ".claimcheck.json").write_text(json.dumps({"strict": True}))
        t = Transcript().user("x").say("done")
        _, out = self.run_cli(self.payload("All tests pass.", t))
        data = json.loads(out)
        self.assertEqual(data["hookSpecificOutput"]["decision"], "block")
        self.assertIn("additionalContext", data["hookSpecificOutput"])

    def test_stop_hook_active_is_noop(self):
        t = Transcript().user("x").say("done")
        _, out = self.run_cli(self.payload("All tests pass.", t, stop_hook_active=True))
        self.assertEqual(out, "{}")

    def test_no_final_message_is_noop(self):
        t = Transcript().user("x").say("done")
        _, out = self.run_cli(self.payload("", t))
        self.assertEqual(out, "{}")

    def test_missing_transcript_is_noop(self):
        _, out = self.run_cli(hook_input("All tests pass.", "/no/such.jsonl", cwd=str(self.dir)))
        self.assertEqual(out, "{}")

    def test_ignore_config(self):
        (self.dir / ".claimcheck.json").write_text(json.dumps({"ignore": ["tests"]}))
        t = Transcript().user("x").say("done")
        _, out = self.run_cli(self.payload("All tests pass.", t))
        self.assertEqual(out, "{}")

    def test_confirm_off_by_default_stays_silent(self):
        t = Transcript().user("x").bash("pytest", "5 passed").edit("a.py")
        _, out = self.run_cli(self.payload("Tests pass. I updated a.py.", t))
        self.assertEqual(out, "{}")

    def test_confirm_mode_shows_green_signal(self):
        (self.dir / ".claimcheck.json").write_text(json.dumps({"confirm": True}))
        t = Transcript().user("x").bash("pytest", "5 passed").edit("a.py")
        _, out = self.run_cli(self.payload("Tests pass. I updated a.py.", t))
        data = json.loads(out)
        self.assertIn("✅", data["systemMessage"])
        self.assertIn("check out", data["systemMessage"])
        self.assertNotIn("decision", data.get("hookSpecificOutput", {}))

    def test_confirm_mode_still_flags_real_issues(self):
        (self.dir / ".claimcheck.json").write_text(json.dumps({"confirm": True}))
        t = Transcript().user("x").say("done")
        _, out = self.run_cli(self.payload("All tests pass.", t))
        self.assertIn("⚠️", json.loads(out)["systemMessage"])

    def test_confirm_mode_silent_when_no_claims(self):
        (self.dir / ".claimcheck.json").write_text(json.dumps({"confirm": True}))
        t = Transcript().user("x").bash("ls")
        _, out = self.run_cli(self.payload("Here is a summary of the options.", t))
        self.assertEqual(out, "{}")

    def test_text_mode(self):
        t = Transcript().user("x").say("done")
        _, out = self.run_cli(
            self.payload("All tests pass.", t), argv=("--from", "claude-code", "--text")
        )
        self.assertTrue(out.startswith("⚠️"))
        self.assertNotIn("{", out)

    def test_strict_exit_code(self):
        t = Transcript().user("x").say("done")
        code, _ = self.run_cli(
            self.payload("All tests pass.", t), argv=("--from", "claude-code", "--strict-exit")
        )
        self.assertEqual(code, 1)

    def test_garbage_stdin_is_survivable(self):
        code, out = self.run_cli({}, raw_stdin="not json at all {{{")
        self.assertEqual((code, out), (0, "{}"))

    def test_claimcheck_log_env_var(self):
        import os

        logfile = self.dir / "log.jsonl"
        os.environ["CLAIMCHECK_LOG"] = str(logfile)
        self.addCleanup(os.environ.pop, "CLAIMCHECK_LOG", None)
        t = Transcript().user("x").say("done")
        self.run_cli(self.payload("All tests pass.", t))
        lines = logfile.read_text().splitlines()
        self.assertEqual(len(lines), 1)
        rec = json.loads(lines[0])
        self.assertEqual(rec["findings"][0]["kind"], "tests")
        self.assertIn("no test command ran", rec["findings"][0]["reason"])
        self.assertEqual(rec["final_message"], "All tests pass.")

    def test_claimcheck_log_not_written_when_clean(self):
        import os

        logfile = self.dir / "log.jsonl"
        os.environ["CLAIMCHECK_LOG"] = str(logfile)
        self.addCleanup(os.environ.pop, "CLAIMCHECK_LOG", None)
        t = Transcript().user("x").bash("pytest", "5 passed")
        self.run_cli(self.payload("All tests pass.", t))
        self.assertFalse(logfile.exists())


# --------------------------------------------------------------------------- adapter parsing


class TestClaudeCodeAdapter(TmpMixin):
    def test_exit_code_parsed(self):
        turn = self.turn("hi", Transcript().user("x").bash("pytest", "boom", exit_code=1))
        self.assertEqual(turn.commands[0].exit_code, 1)
        self.assertFalse(turn.commands[0].ok)

    def test_real_user_vs_tool_result(self):
        turn = self.turn("hi", Transcript().user("do the thing").bash("ls", "file1"))
        self.assertEqual(turn.user_messages, ["do the thing"])

    def test_garbage_lines_skipped(self):
        t = Transcript().raw({"type": "queue-operation", "junk": 1}).user("x").bash("pytest", "ok")
        self.assertEqual(len(self.turn("hi", t).commands), 1)

    def test_source_and_observed(self):
        turn = self.turn("hi", Transcript().user("x"))
        self.assertEqual(turn.source, "claude-code")
        self.assertTrue(turn.observed)


# --------------------------------------------------------------------------- generic adapter


class TestGenericAdapter(unittest.TestCase):
    def test_maps_payload_to_turn(self):
        from claimcheck.adapters.generic import parse

        turn = parse(
            {
                "final_message": "All tests pass. I updated auth.py.",
                "user_messages": ["fix login"],
                "commands": [{"text": "pytest", "ok": True, "exit_code": 0}],
                "edits": ["src/routes.py", {"path": "config.toml"}],
            }
        )
        self.assertEqual(turn.source, "generic")
        self.assertTrue(turn.observed)
        self.assertEqual(turn.user_messages, ["fix login"])
        self.assertEqual(turn.commands[0].text, "pytest")
        self.assertEqual({e.path for e in turn.edits}, {"src/routes.py", "config.toml"})

    def test_generic_via_cli(self):
        buf, err = io.StringIO(), io.StringIO()
        old = sys.stdin
        sys.stdin = io.StringIO(json.dumps({"final_message": "All tests pass.", "commands": []}))
        try:
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
                code = cli_main(["--from", "generic"])
        finally:
            sys.stdin = old
        self.assertEqual(code, 0)
        self.assertIn("no test command ran", buf.getvalue())


# --------------------------------------------------------------------------- cursor adapter
# transcript format is undocumented; these use a plausible JSONL shape — revisit
# against a real ~/.cursor/.../agent-transcripts/ file.


class TestCursorAdapter(unittest.TestCase):
    def _payload(self, tmp: Path, lines: list[dict], **kw) -> dict:
        tp = tmp / "cursor.jsonl"
        tp.write_text("\n".join(json.dumps(x) for x in lines))
        return {
            "hook_event_name": "stop",
            "workspace_roots": [str(tmp)],
            "transcript_path": str(tp),
            "status": "completed",
            "loop_count": 0,
            **kw,
        }

    def test_parse_transcript(self):
        from claimcheck.adapters.cursor import parse

        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            payload = self._payload(
                tmp,
                [
                    {"role": "user", "content": "fix the bug"},
                    {
                        "role": "assistant",
                        "content": "running tests",
                        "tool_calls": [{"name": "shell", "command": "pytest -q"}],
                    },
                    {"role": "tool", "content": "5 passed", "tool_call_id": "1"},
                    {
                        "role": "assistant",
                        "content": "All tests pass. I updated auth.py.",
                        "tool_calls": [{"name": "edit_file", "path": "auth.py"}],
                    },
                ],
            )
            turn = parse(payload)
            self.assertEqual(turn.source, "cursor")
            self.assertEqual(turn.project_dir, str(tmp))
            self.assertEqual(turn.final_message, "All tests pass. I updated auth.py.")
            self.assertEqual(turn.user_messages, ["fix the bug"])
            self.assertEqual(turn.commands[0].text, "pytest -q")
            self.assertTrue(turn.commands[0].ok)
            self.assertEqual([e.path for e in turn.edits], ["auth.py"])

    def test_loop_guard(self):
        from claimcheck.adapters.cursor import already_reprompted

        self.assertTrue(already_reprompted({"loop_count": 2}))
        self.assertFalse(already_reprompted({"loop_count": 0}))

    def test_hook_output_warn_vs_strict(self):
        from claimcheck.adapters.cursor import to_hook_output

        self.assertEqual(to_hook_output("msg", block=False), {})
        self.assertIn("followup_message", to_hook_output("msg", block=True))


if __name__ == "__main__":
    unittest.main()
