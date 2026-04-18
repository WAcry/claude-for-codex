import importlib.util
import io
import json
import tempfile
import unittest
from unittest import mock
from contextlib import redirect_stdout
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent
    / "claude-code-orchestrator"
    / "scripts"
    / "claude_orchestrator.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("claude_orchestrator", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ClaudeOrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.module = load_module()

    def run_main_quietly(self, argv):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.module.main(argv)
        return buffer.getvalue()

    def patch_tempdir(self, tempdir):
        return mock.patch.object(self.module.tempfile, "gettempdir", return_value=tempdir)

    def state_root(self, tempdir, state_id):
        return Path(tempdir) / f"claude-code-orchestrator-{state_id}"

    def test_launch_dry_run_records_two_distinct_jobs(self):
        with tempfile.TemporaryDirectory() as tempdir:
            state_id = "abc123"
            state_root = self.state_root(tempdir, state_id)
            workdir = Path(tempdir) / "repo"
            workdir.mkdir()
            with self.patch_tempdir(tempdir):
                self.run_main_quietly(
                    [
                        "launch",
                        "--prompt",
                        "Build a demo page.",
                        "--workdir",
                        str(workdir),
                        "--state-id",
                        state_id,
                        "--job-id",
                        "job-one",
                        "--dry-run",
                    ]
                )
                self.run_main_quietly(
                    [
                        "launch",
                        "--prompt",
                        "Draft release notes.",
                        "--workdir",
                        str(workdir),
                        "--state-id",
                        state_id,
                        "--job-id",
                        "job-two",
                        "--dry-run",
                    ]
                )
            registry = json.loads((state_root / "registry.json").read_text(encoding="utf-8"))
            self.assertEqual(2, len(registry["jobs"]))
            self.assertNotEqual(registry["jobs"][0]["id"], registry["jobs"][1]["id"])

    def test_launch_dry_run_preserves_model_effort_and_non_bare_default(self):
        with tempfile.TemporaryDirectory() as tempdir:
            state_id = "def456"
            state_root = self.state_root(tempdir, state_id)
            workdir = Path(tempdir) / "repo"
            workdir.mkdir()
            prompt = "Polish the UI with a launch-specific secret token."
            with self.patch_tempdir(tempdir):
                self.run_main_quietly(
                    [
                        "launch",
                        "--prompt",
                        prompt,
                        "--workdir",
                        str(workdir),
                        "--state-id",
                        state_id,
                        "--job-id",
                        "job-ui",
                        "--model",
                        "sonnet",
                        "--effort",
                        "high",
                        "--dry-run",
                    ]
                )
            job = json.loads(
                (state_root / "jobs" / "job-ui" / "job.json").read_text(encoding="utf-8")
            )
            command = job["last_command"]
            self.assertEqual("bash", command[0])
            self.assertEqual("-lc", command[1])
            self.assertIn("claude -p", command[2])
            self.assertIn("--model sonnet", command[2])
            self.assertIn("--effort high", command[2])
            self.assertNotIn("--bare", command[2])
            self.assertIn("--verbose", command[2])
            self.assertNotIn(prompt, command[2])
            self.assertNotIn(prompt, job["last_command_text"])
            self.assertEqual(
                prompt,
                (state_root / "jobs" / "job-ui" / "prompt.txt").read_text(encoding="utf-8"),
            )

    def test_launch_without_state_id_allocates_short_id_in_system_temp(self):
        with tempfile.TemporaryDirectory() as tempdir:
            workdir = Path(tempdir) / "repo"
            workdir.mkdir()
            with self.patch_tempdir(tempdir):
                payload = self.run_main_quietly(
                    [
                        "launch",
                        "--prompt",
                        "Create a short-lived job.",
                        "--workdir",
                        str(workdir),
                        "--job-id",
                        "job-auto",
                        "--dry-run",
                        "--json",
                    ]
                )
            result = json.loads(payload)
            state_id = result["job"]["state_id"]
            self.assertRegex(state_id, r"^[a-z0-9]{6}$")
            self.assertEqual(
                str(self.state_root(tempdir, state_id)),
                result["job"]["state_root"],
            )

    def test_hook_defers_without_answer_and_allows_with_updated_input(self):
        with tempfile.TemporaryDirectory() as tempdir:
            job_dir = Path(tempdir)
            incoming = {
                "session_id": "session-1",
                "hook_event_name": "PreToolUse",
                "tool_name": "AskUserQuestion",
                "tool_input": {
                    "question": "Which area should I tackle?",
                    "options": [{"id": "frontend", "label": "Frontend"}],
                },
            }

            stdin_backup = self.module.sys.stdin
            stdout_buffer = io.StringIO()
            try:
                self.module.sys.stdin = io.StringIO(json.dumps(incoming))
                with redirect_stdout(stdout_buffer):
                    self.module.main(["hook", "--job-dir", str(job_dir)])
            finally:
                self.module.sys.stdin = stdin_backup
            response = json.loads(stdout_buffer.getvalue())
            self.assertEqual("defer", response["permissionDecision"])
            self.assertTrue((job_dir / "pending-tool.json").exists())

            answer_payload = {"updated_input": {"selectedOptionIds": ["frontend"]}}
            (job_dir / "pending-answer.json").write_text(
                json.dumps(answer_payload), encoding="utf-8"
            )

            stdout_buffer = io.StringIO()
            try:
                self.module.sys.stdin = io.StringIO(json.dumps(incoming))
                with redirect_stdout(stdout_buffer):
                    self.module.main(["hook", "--job-dir", str(job_dir)])
            finally:
                self.module.sys.stdin = stdin_backup
            response = json.loads(stdout_buffer.getvalue())
            self.assertEqual("allow", response["permissionDecision"])
            self.assertEqual(
                {"selectedOptionIds": ["frontend"]},
                response["updatedInput"],
            )

    def test_resume_dry_run_preserves_extra_runtime_flags(self):
        with tempfile.TemporaryDirectory() as tempdir:
            state_id = "ghi789"
            state_root = self.state_root(tempdir, state_id)
            workdir = Path(tempdir) / "repo"
            extra_dir = Path(tempdir) / "shared"
            workdir.mkdir()
            extra_dir.mkdir()
            with self.patch_tempdir(tempdir):
                self.run_main_quietly(
                    [
                        "launch",
                        "--prompt",
                        "Build the first version.",
                        "--workdir",
                        str(workdir),
                        "--state-id",
                        state_id,
                        "--job-id",
                        "job-resume",
                        "--title",
                        "frontend-pass",
                        "--model",
                        "sonnet",
                        "--effort",
                        "high",
                        "--add-dir",
                        str(extra_dir),
                        "--allowed-tools",
                        "Read",
                        "Edit",
                        "--dry-run",
                    ]
                )
                self.run_main_quietly(
                    [
                        "resume",
                        "job-resume",
                        "--state-id",
                        state_id,
                        "--message",
                        "Continue from the previous stopping point.",
                        "--dry-run",
                    ]
                )
            job = json.loads(
                (state_root / "jobs" / "job-resume" / "job.json").read_text(encoding="utf-8")
            )
            command = job["attempts"][-1]["command"]
            self.assertEqual("bash", command[0])
            self.assertEqual("-lc", command[1])
            self.assertIn("--resume", command[2])
            self.assertIn("--name frontend-pass", command[2])
            self.assertIn(f"--add-dir {str(extra_dir)}", command[2])
            self.assertIn("--allowedTools Read,Edit", command[2])
            self.assertIn("--verbose", command[2])
            self.assertNotIn("Continue from the previous stopping point.", command[2])
            self.assertEqual(
                "Continue from the previous stopping point.",
                Path(job["attempts"][-1]["stdin_path"]).read_text(encoding="utf-8"),
            )

    def test_launch_rejects_duplicate_job_id_without_replace(self):
        with tempfile.TemporaryDirectory() as tempdir:
            state_id = "jkl012"
            workdir = Path(tempdir) / "repo"
            workdir.mkdir()
            with self.patch_tempdir(tempdir):
                self.run_main_quietly(
                    [
                        "launch",
                        "--prompt",
                        "First version.",
                        "--workdir",
                        str(workdir),
                        "--state-id",
                        state_id,
                        "--job-id",
                        "shared",
                        "--dry-run",
                    ]
                )
                with self.assertRaises(SystemExit) as ctx:
                    self.run_main_quietly(
                        [
                            "launch",
                            "--prompt",
                            "Second version.",
                            "--workdir",
                            str(workdir),
                            "--state-id",
                            state_id,
                            "--job-id",
                            "shared",
                            "--dry-run",
                        ]
                    )
            self.assertIn("already exists", str(ctx.exception))

    def test_status_resume_and_answer_use_state_id(self):
        with tempfile.TemporaryDirectory() as tempdir:
            state_id = "mno345"
            workdir = Path(tempdir) / "repo"
            workdir.mkdir()
            prompt = "Inspect the cross-repo state behavior."
            state_root = self.state_root(tempdir, state_id)
            with self.patch_tempdir(tempdir):
                self.run_main_quietly(
                    [
                        "launch",
                        "--prompt",
                        prompt,
                        "--workdir",
                        str(workdir),
                        "--state-id",
                        state_id,
                        "--job-id",
                        "job-cross",
                        "--dry-run",
                    ]
                )
                status_output = self.run_main_quietly(
                    [
                        "status",
                        "job-cross",
                        "--state-id",
                        state_id,
                    ]
                )
            self.assertIn("job-cross", status_output)

            with self.patch_tempdir(tempdir):
                self.run_main_quietly(
                    [
                        "resume",
                        "job-cross",
                        "--state-id",
                        state_id,
                        "--message",
                        "Continue carefully.",
                        "--dry-run",
                    ]
                )
            pending_tool_path = state_root / "jobs" / "job-cross" / "pending-tool.json"
            pending_tool_path.write_text("{}", encoding="utf-8")
            with self.patch_tempdir(tempdir):
                self.run_main_quietly(
                    [
                        "answer",
                        "job-cross",
                        "--state-id",
                        state_id,
                        "--updated-input-json",
                        '{"selectedOptionIds":["frontend"]}',
                    ]
                )
            self.assertTrue((state_root / "jobs" / "job-cross" / "pending-answer.json").exists())

    def test_answer_resume_now_uses_state_id(self):
        with tempfile.TemporaryDirectory() as tempdir:
            state_id = "pqr678"
            workdir = Path(tempdir) / "repo"
            workdir.mkdir()
            state_root = self.state_root(tempdir, state_id)
            with self.patch_tempdir(tempdir):
                self.run_main_quietly(
                    [
                        "launch",
                        "--prompt",
                        "Inspect deferred resume.",
                        "--workdir",
                        str(workdir),
                        "--state-id",
                        state_id,
                        "--job-id",
                        "job-answer",
                        "--dry-run",
                    ]
                )
            pending_tool_path = state_root / "jobs" / "job-answer" / "pending-tool.json"
            pending_tool_path.write_text("{}", encoding="utf-8")
            with self.patch_tempdir(tempdir):
                self.run_main_quietly(
                    [
                        "answer",
                        "job-answer",
                        "--state-id",
                        state_id,
                        "--updated-input-json",
                        '{"selectedOptionIds":["frontend"]}',
                        "--resume-now",
                        "--dry-run",
                    ]
                )
            job = json.loads(
                (state_root / "jobs" / "job-answer" / "job.json").read_text(encoding="utf-8")
            )
            self.assertEqual(2, len(job["attempts"]))
            self.assertEqual("resume", job["attempts"][-1]["kind"])

    def test_status_output_includes_log_paths_and_stderr_tail_for_failed_jobs(self):
        with tempfile.TemporaryDirectory() as tempdir:
            state_id = "stu901"
            state_root = self.state_root(tempdir, state_id)
            job_dir = state_root / "jobs" / "job-failed"
            job_dir.mkdir(parents=True)
            (job_dir / "stdout.log").write_text("stdout line\n", encoding="utf-8")
            (job_dir / "stderr.log").write_text("first error\nsecond error\n", encoding="utf-8")
            job = {
                "id": "job-failed",
                "state_id": state_id,
                "title": "failed-job",
                "created_at": "2026-04-17T00:00:00+00:00",
                "updated_at": "2026-04-17T00:00:01+00:00",
                "state_root": str(state_root),
                "job_dir": str(job_dir),
                "workdir": str(Path(tempdir) / "repo"),
                "session_id": "session-failed",
                "status": "failed",
                "model": None,
                "effort": None,
                "use_bare": False,
                "permission_mode": "acceptEdits",
                "output_format": "stream-json",
                "add_dirs": [],
                "allowed_tools": [],
                "runner_pid": None,
                "exit_code": 1,
                "current_attempt": 1,
                "last_command_text": "claude -p --output-format stream-json --verbose",
                "attempts": [],
            }
            self.module.write_json(job_dir / "job.json", job)
            self.module.rebuild_registry(state_root)
            with self.patch_tempdir(tempdir):
                output = self.run_main_quietly(
                    [
                        "status",
                        "job-failed",
                        "--state-id",
                        state_id,
                        "--tail",
                        "2",
                    ]
                )
            self.assertIn("stdout_log:", output)
            self.assertIn("stderr_log:", output)
            self.assertIn("-- stderr tail --", output)
            self.assertIn("second error", output)

    def test_run_job_records_worker_start_failure_in_stderr_log(self):
        with tempfile.TemporaryDirectory() as tempdir:
            state_id = "vwx234"
            state_root = self.state_root(tempdir, state_id)
            workdir = Path(tempdir) / "repo"
            workdir.mkdir()
            with self.patch_tempdir(tempdir):
                self.run_main_quietly(
                    [
                        "launch",
                        "--prompt",
                        "Try to launch Claude.",
                        "--workdir",
                        str(workdir),
                        "--state-id",
                        state_id,
                        "--job-id",
                        "job-error",
                        "--dry-run",
                    ]
                )
            job_file = state_root / "jobs" / "job-error" / "job.json"
            with mock.patch.object(self.module.subprocess, "Popen", side_effect=FileNotFoundError("claude")):
                self.module.main(["_run-job", "--job-file", str(job_file)])
            job = json.loads(job_file.read_text(encoding="utf-8"))
            self.assertEqual("failed", job["status"])
            self.assertEqual(self.module.WORKER_FAILURE_EXIT_CODE, job["exit_code"])
            stderr_text = (state_root / "jobs" / "job-error" / "stderr.log").read_text(
                encoding="utf-8"
            )
            self.assertIn("FileNotFoundError", stderr_text)

    def test_resume_rejects_running_job_with_live_runner_pid(self):
        with tempfile.TemporaryDirectory() as tempdir:
            state_id = "yz0123"
            state_root = self.state_root(tempdir, state_id)
            workdir = Path(tempdir) / "repo"
            workdir.mkdir()
            with self.patch_tempdir(tempdir):
                self.run_main_quietly(
                    [
                        "launch",
                        "--prompt",
                        "Build the first pass.",
                        "--workdir",
                        str(workdir),
                        "--state-id",
                        state_id,
                        "--job-id",
                        "job-running",
                        "--dry-run",
                    ]
                )
            job_path = state_root / "jobs" / "job-running" / "job.json"
            job = json.loads(job_path.read_text(encoding="utf-8"))
            job["status"] = "running"
            job["runner_pid"] = 999999
            job_path.write_text(json.dumps(job), encoding="utf-8")
            with mock.patch.object(self.module, "is_process_alive", return_value=True):
                with self.assertRaises(SystemExit) as ctx:
                    with self.patch_tempdir(tempdir):
                        self.run_main_quietly(
                            [
                                "resume",
                                "job-running",
                                "--state-id",
                                state_id,
                                "--message",
                                "Continue.",
                                "--dry-run",
                            ]
                        )
            self.assertIn("still running", str(ctx.exception))

    def test_launch_rejects_empty_prompt_from_stdin(self):
        stdin_backup = self.module.sys.stdin
        try:
            self.module.sys.stdin = io.StringIO("")
            with self.assertRaises(SystemExit) as ctx:
                self.run_main_quietly(["launch", "--dry-run"])
        finally:
            self.module.sys.stdin = stdin_backup
        self.assertIn("Prompt content is empty", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
