#!/usr/bin/env python3
"""Coordinate tracked Claude Code CLI jobs for Codex."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


DEFAULT_STATE_ROOT = ".claude-orchestrator-state"
JOBS_DIRNAME = "jobs"
REGISTRY_FILENAME = "registry.json"
JOB_FILENAME = "job.json"
SETTINGS_FILENAME = "settings.json"
PROMPT_FILENAME = "prompt.txt"
STDOUT_FILENAME = "stdout.log"
STDERR_FILENAME = "stderr.log"
PENDING_TOOL_FILENAME = "pending-tool.json"
PENDING_ANSWER_FILENAME = "pending-answer.json"
ATTEMPT_INPUT_TEMPLATE = "attempt-{attempt:04d}-input.txt"
WORKER_FAILURE_EXIT_CODE = 127


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def remove_tree(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


def resolve_state_root(raw_path: str | None, workdir: str | None = None) -> Path:
    if raw_path:
        return Path(raw_path).expanduser().resolve()
    base = Path(workdir).expanduser().resolve() if workdir else Path.cwd()
    return (base / DEFAULT_STATE_ROOT).resolve()


def resolve_followup_state_root(args: argparse.Namespace) -> Path:
    return resolve_state_root(getattr(args, "state_root", None), getattr(args, "workdir", None))


def jobs_root(state_root: Path) -> Path:
    return state_root / JOBS_DIRNAME


def job_root(state_root: Path, job_id: str) -> Path:
    return jobs_root(state_root) / job_id


def job_file(state_root: Path, job_id: str) -> Path:
    return job_root(state_root, job_id) / JOB_FILENAME


def prompt_preview(prompt: str, limit: int = 120) -> str:
    collapsed = " ".join(prompt.split())
    if len(collapsed) <= limit:
        return collapsed
    return f"{collapsed[: limit - 3]}..."


def shell_join(parts: Iterable[str]) -> str:
    return shlex.join(list(parts))


def wrap_with_login_shell(command: list[str]) -> list[str]:
    return ["bash", "-lc", shell_join(command)]


def is_process_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def load_job(state_root: Path, job_id: str) -> dict[str, Any]:
    path = job_file(state_root, job_id)
    payload = read_json(path)
    if payload is None:
        raise SystemExit(f"Unknown job id: {job_id}")
    return payload


def save_job(state_root: Path, payload: dict[str, Any]) -> None:
    payload["updated_at"] = utc_now()
    write_json(job_file(state_root, payload["id"]), payload)
    rebuild_registry(state_root)


def fail_job(
    state_root: Path,
    job: dict[str, Any],
    attempt: dict[str, Any],
    *,
    error_message: str,
    exit_code: int = WORKER_FAILURE_EXIT_CODE,
) -> None:
    attempt["finished_at"] = utc_now()
    attempt["exit_code"] = exit_code
    attempt["status"] = "failed"
    attempt["error"] = error_message
    job["exit_code"] = exit_code
    job["status"] = "failed"
    job["error"] = error_message
    save_job(state_root, job)


def refresh_job(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("status") == "running":
        runner_pid = payload.get("runner_pid")
        if runner_pid and not is_process_alive(runner_pid) and payload.get("exit_code") is None:
            payload["status"] = "unknown"
    pending_tool = Path(payload["job_dir"]) / PENDING_TOOL_FILENAME
    if pending_tool.exists() and payload.get("status") in {"running", "succeeded", "failed", "unknown"}:
        payload["status"] = "awaiting_input"
    return payload


def rebuild_registry(state_root: Path) -> None:
    root = jobs_root(state_root)
    root.mkdir(parents=True, exist_ok=True)
    summaries: list[dict[str, Any]] = []
    for path in sorted(root.glob(f"*/{JOB_FILENAME}")):
        payload = read_json(path)
        if not payload:
            continue
        payload = refresh_job(payload)
        summary = {
            "id": payload["id"],
            "title": payload.get("title"),
            "status": payload.get("status"),
            "session_id": payload.get("session_id"),
            "created_at": payload.get("created_at"),
            "updated_at": payload.get("updated_at"),
            "workdir": payload.get("workdir"),
            "current_attempt": payload.get("current_attempt"),
            "model": payload.get("model"),
            "effort": payload.get("effort"),
            "use_bare": payload.get("use_bare"),
        }
        summaries.append(summary)
        write_json(path, payload)
    registry = {
        "version": 1,
        "updated_at": utc_now(),
        "state_root": str(state_root),
        "jobs": sorted(summaries, key=lambda item: item["created_at"], reverse=True),
    }
    write_json(state_root / REGISTRY_FILENAME, registry)


def read_prompt(args: argparse.Namespace) -> str:
    prompt: str | None = None
    if args.prompt is not None:
        prompt = args.prompt
    elif args.prompt_file:
        prompt = Path(args.prompt_file).read_text(encoding="utf-8")
    elif not sys.stdin.isatty():
        prompt = sys.stdin.read()
    if prompt is not None:
        if prompt.strip():
            return prompt
        raise SystemExit("Prompt content is empty. Provide non-empty --prompt, --prompt-file, or stdin.")
    raise SystemExit("Provide --prompt, --prompt-file, or pipe prompt text on stdin.")


def build_settings(job_dir: Path) -> dict[str, Any]:
    script_path = Path(__file__).resolve()
    hook_command = shell_join(
        [
            sys.executable,
            str(script_path),
            "hook",
            "--job-dir",
            str(job_dir),
        ]
    )
    return {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "AskUserQuestion|ExitPlanMode",
                    "hooks": [
                        {
                            "type": "command",
                            "command": hook_command,
                        }
                    ],
                }
            ]
        }
    }


def build_common_claude_args(job: dict[str, Any]) -> list[str]:
    command = ["claude", "-p"]
    command.extend(["--session-id", job["session_id"]])
    return append_shared_runtime_args(command, job)


def append_shared_runtime_args(command: list[str], job: dict[str, Any]) -> list[str]:
    command.extend(["--permission-mode", job["permission_mode"]])
    command.extend(["--output-format", job["output_format"]])
    if job["output_format"] == "stream-json":
        command.append("--verbose")
    command.extend(["--settings", str(Path(job["job_dir"]) / SETTINGS_FILENAME)])
    if job.get("title"):
        command.extend(["--name", job["title"]])
    if job.get("model"):
        command.extend(["--model", job["model"]])
    if job.get("effort"):
        command.extend(["--effort", job["effort"]])
    if job.get("use_bare"):
        command.append("--bare")
    for extra_dir in job.get("add_dirs", []):
        command.extend(["--add-dir", extra_dir])
    if job.get("allowed_tools"):
        command.extend(["--allowedTools", ",".join(job["allowed_tools"])])
    return command


def append_attempt(
    job: dict[str, Any],
    *,
    kind: str,
    prompt: str | None,
    command: list[str],
    dry_run: bool,
) -> dict[str, Any]:
    attempts = job.setdefault("attempts", [])
    attempt_number = len(attempts) + 1
    stdin_path = write_attempt_input(job, attempt_number, prompt, kind)
    entry = {
        "number": attempt_number,
        "kind": kind,
        "created_at": utc_now(),
        "status": "dry_run" if dry_run else "queued",
        "dry_run": dry_run,
        "command": command,
        "command_text": shell_join(command),
        "prompt_preview": prompt_preview(prompt or ""),
        "prompt_path": str(Path(job["job_dir"]) / PROMPT_FILENAME) if kind == "launch" and prompt else None,
        "stdin_path": str(stdin_path) if stdin_path else None,
    }
    attempts.append(entry)
    job["current_attempt"] = attempt_number
    job["last_command"] = entry["command"]
    job["last_command_text"] = entry["command_text"]
    job["status"] = entry["status"]
    job["prompt_preview"] = entry["prompt_preview"]
    return entry


def write_job_artifacts(job: dict[str, Any], prompt: str | None) -> None:
    job_dir = Path(job["job_dir"])
    job_dir.mkdir(parents=True, exist_ok=True)
    write_json(job_dir / SETTINGS_FILENAME, build_settings(job_dir))
    if prompt is not None:
        write_text(job_dir / PROMPT_FILENAME, prompt)


def write_attempt_input(
    job: dict[str, Any], attempt_number: int, payload: str | None, kind: str
) -> Path | None:
    if not payload:
        return None
    job_dir = Path(job["job_dir"])
    if kind == "launch":
        path = job_dir / PROMPT_FILENAME
    else:
        path = job_dir / ATTEMPT_INPUT_TEMPLATE.format(attempt=attempt_number)
    write_text(path, payload)
    return path


def print_payload(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return
    print(payload.get("message", ""))
    if payload.get("job"):
        job = payload["job"]
        print(f"job_id: {job['id']}")
        print(f"status: {job['status']}")
        print(f"session_id: {job['session_id']}")
        print(f"command: {job['last_command_text']}")


def cmd_launch(args: argparse.Namespace) -> int:
    prompt = read_prompt(args)
    workdir = Path(args.workdir or Path.cwd()).expanduser().resolve()
    state_root = resolve_state_root(args.state_root, str(workdir))
    job_id = args.job_id or uuid.uuid4().hex[:12]
    session_id = args.session_id or str(uuid.uuid4())
    job_dir = job_root(state_root, job_id)
    existing_job_path = job_file(state_root, job_id)
    if existing_job_path.exists() and not args.replace:
        raise SystemExit(
            f"Job id '{job_id}' already exists. Use a new id or pass --replace after stopping that job."
        )
    if existing_job_path.exists() and args.replace:
        existing_job = read_json(existing_job_path, default={})
        if is_process_alive(existing_job.get("runner_pid")):
            raise SystemExit(f"Job id '{job_id}' is still running; refusing to replace it.")
        remove_tree(job_dir)
    job = {
        "id": job_id,
        "title": args.title or f"claude-{job_id}",
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "state_root": str(state_root),
        "job_dir": str(job_dir),
        "workdir": str(workdir),
        "session_id": session_id,
        "status": "created",
        "model": args.model,
        "effort": args.effort,
        "use_bare": args.bare,
        "permission_mode": args.permission_mode,
        "output_format": args.output_format,
        "add_dirs": [str(Path(item).expanduser().resolve()) for item in (args.add_dir or [])],
        "allowed_tools": args.allowed_tools or [],
        "runner_pid": None,
        "exit_code": None,
        "attempts": [],
    }
    command = wrap_with_login_shell(build_common_claude_args(job))
    append_attempt(job, kind="launch", prompt=prompt, command=command, dry_run=args.dry_run)
    write_job_artifacts(job, prompt)
    save_job(state_root, job)
    if args.dry_run:
        print_payload(
            {
                "message": "Created a dry-run Claude job.",
                "job": job,
            },
            args.json,
        )
        return 0
    return start_worker(job, args.json)


def start_worker(job: dict[str, Any], as_json: bool) -> int:
    script_path = Path(__file__).resolve()
    worker = subprocess.Popen(
        [sys.executable, str(script_path), "_run-job", "--job-file", str(Path(job["job_dir"]) / JOB_FILENAME)],
        cwd=job["workdir"],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    state_root = Path(job["state_root"])
    fresh = load_job(state_root, job["id"])
    fresh["runner_pid"] = worker.pid
    fresh["status"] = "running"
    fresh["attempts"][fresh["current_attempt"] - 1]["status"] = "running"
    save_job(state_root, fresh)
    print_payload(
        {
            "message": "Launched a background Claude job.",
            "job": fresh,
        },
        as_json,
    )
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    state_root = resolve_followup_state_root(args)
    rebuild_registry(state_root)
    if args.job_id:
        job = refresh_job(load_job(state_root, args.job_id))
        save_job(state_root, job)
        output = {
            "id": job["id"],
            "title": job["title"],
            "status": job["status"],
            "session_id": job["session_id"],
            "current_attempt": job.get("current_attempt"),
            "last_command_text": job.get("last_command_text"),
            "pending_tool_path": str(Path(job["job_dir"]) / PENDING_TOOL_FILENAME)
            if (Path(job["job_dir"]) / PENDING_TOOL_FILENAME).exists()
            else None,
            "stdout_log": str(Path(job["job_dir"]) / STDOUT_FILENAME),
            "stderr_log": str(Path(job["job_dir"]) / STDERR_FILENAME),
            "stdout_tail": read_log_tail(Path(job["job_dir"]) / STDOUT_FILENAME, args.tail)
            if args.tail
            else [],
            "stderr_tail": read_log_tail(Path(job["job_dir"]) / STDERR_FILENAME, args.tail)
            if should_tail_stderr(job.get("status"), args)
            else [],
        }
        if args.json:
            json.dump(output, sys.stdout, indent=2, sort_keys=True)
            sys.stdout.write("\n")
            return 0
        print(f"{output['id']} {output['status']} session={output['session_id']}")
        print(output["last_command_text"])
        print(f"stdout_log: {output['stdout_log']}")
        print(f"stderr_log: {output['stderr_log']}")
        if output["pending_tool_path"]:
            print(f"pending_tool: {output['pending_tool_path']}")
        if output["stdout_tail"]:
            print("-- stdout tail --")
            for line in output["stdout_tail"]:
                print(line)
        if output["stderr_tail"]:
            print("-- stderr tail --")
            for line in output["stderr_tail"]:
                print(line)
        return 0
    registry = read_json(state_root / REGISTRY_FILENAME, default={"jobs": []})
    if args.json:
        json.dump(registry, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0
    for item in registry.get("jobs", []):
        print(
            f"{item['id']} {item['status']} session={item['session_id']} "
            f"model={item.get('model') or '-'} effort={item.get('effort') or '-'}"
        )
    return 0


def read_log_tail(path: Path, tail_lines: int) -> list[str]:
    if tail_lines <= 0 or not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return lines[-tail_lines:]


def should_tail_stderr(status: str | None, args: argparse.Namespace) -> bool:
    if not args.tail:
        return False
    if getattr(args, "tail_both", False) or getattr(args, "tail_stderr", False):
        return True
    return status in {"failed", "unknown"}


def cmd_resume(args: argparse.Namespace) -> int:
    state_root = resolve_followup_state_root(args)
    job = refresh_job(load_job(state_root, args.job_id))
    if job.get("status") == "running" and is_process_alive(job.get("runner_pid")):
        raise SystemExit(
            f"Job '{job['id']}' is still running. Wait for it to finish before resuming."
        )
    override_model = args.model if args.model is not None else job.get("model")
    override_effort = args.effort if args.effort is not None else job.get("effort")
    override_bare = args.bare if args.bare else job.get("use_bare", False)
    if args.no_bare:
        override_bare = False
    job["model"] = override_model
    job["effort"] = override_effort
    job["use_bare"] = override_bare
    command = wrap_with_login_shell(
        append_shared_runtime_args(["claude", "-p", "--resume", job["session_id"]], job)
    )
    append_attempt(job, kind="resume", prompt=args.message, command=command, dry_run=args.dry_run)
    save_job(state_root, job)
    if args.dry_run:
        print_payload({"message": "Prepared a dry-run resume attempt.", "job": job}, args.json)
        return 0
    return start_worker(job, args.json)


def cmd_answer(args: argparse.Namespace) -> int:
    state_root = resolve_followup_state_root(args)
    job = refresh_job(load_job(state_root, args.job_id))
    pending_path = Path(job["job_dir"]) / PENDING_TOOL_FILENAME
    if not pending_path.exists():
        raise SystemExit("No pending tool payload found for this job.")
    updated_input = read_updated_input(args)
    payload = {
        "written_at": utc_now(),
        "job_id": job["id"],
        "session_id": job["session_id"],
        "updated_input": updated_input,
        "note": args.note,
    }
    write_json(Path(job["job_dir"]) / PENDING_ANSWER_FILENAME, payload)
    if args.resume_now:
        resume_args = argparse.Namespace(
            job_id=args.job_id,
            workdir=args.workdir,
            state_root=args.state_root,
            model=None,
            effort=None,
            bare=False,
            no_bare=False,
            dry_run=args.dry_run,
            json=args.json,
            message=args.message,
        )
        return cmd_resume(resume_args)
    if args.json:
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        print(f"Queued updatedInput for job {job['id']}.")
    return 0


def read_updated_input(args: argparse.Namespace) -> Any:
    if args.updated_input_json:
        return json.loads(args.updated_input_json)
    if args.updated_input_file:
        return json.loads(Path(args.updated_input_file).read_text(encoding="utf-8"))
    raise SystemExit("Provide --updated-input-json or --updated-input-file.")


def extract_tool_name(payload: dict[str, Any]) -> str:
    return (
        payload.get("tool_name")
        or payload.get("toolName")
        or payload.get("tool", {}).get("name")
        or ""
    )


def extract_tool_input(payload: dict[str, Any]) -> Any:
    return payload.get("tool_input") or payload.get("toolInput") or payload.get("input") or {}


def cmd_hook(args: argparse.Namespace) -> int:
    job_dir = Path(args.job_dir).resolve()
    incoming = json.load(sys.stdin)
    tool_name = extract_tool_name(incoming)
    if tool_name not in {"AskUserQuestion", "ExitPlanMode"}:
        json.dump({}, sys.stdout)
        sys.stdout.write("\n")
        return 0
    pending = {
        "captured_at": utc_now(),
        "job_dir": str(job_dir),
        "session_id": incoming.get("session_id") or incoming.get("sessionId"),
        "hook_event_name": incoming.get("hook_event_name") or incoming.get("hookEventName"),
        "tool_name": tool_name,
        "tool_input": extract_tool_input(incoming),
        "raw_input": incoming,
    }
    write_json(job_dir / PENDING_TOOL_FILENAME, pending)
    answer = read_json(job_dir / PENDING_ANSWER_FILENAME)
    if answer and answer.get("updated_input") is not None:
        response = {
            "permissionDecision": "allow",
            "updatedInput": answer["updated_input"],
        }
        os.remove(job_dir / PENDING_ANSWER_FILENAME)
        if (job_dir / PENDING_TOOL_FILENAME).exists():
            os.remove(job_dir / PENDING_TOOL_FILENAME)
    else:
        response = {
            "permissionDecision": "defer",
            "permissionDecisionReason": "Waiting for orchestrator-provided updatedInput.",
        }
    json.dump(response, sys.stdout)
    sys.stdout.write("\n")
    return 0


def cmd_run_job(args: argparse.Namespace) -> int:
    job_path = Path(args.job_file).resolve()
    job = read_json(job_path)
    if not job:
        raise SystemExit(f"Missing job file: {job_path}")
    state_root = Path(job["state_root"])
    job = refresh_job(job)
    attempt = job["attempts"][job["current_attempt"] - 1]
    stdout_path = Path(job["job_dir"]) / STDOUT_FILENAME
    stderr_path = Path(job["job_dir"]) / STDERR_FILENAME
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    with stdout_path.open("a", encoding="utf-8") as stdout_handle, stderr_path.open(
        "a", encoding="utf-8"
    ) as stderr_handle:
        stdout_handle.write(f"\n[{utc_now()}] starting attempt {attempt['number']}\n")
        stdout_handle.flush()
        try:
            stdin_text = None
            stdin_path = attempt.get("stdin_path")
            if stdin_path:
                stdin_text = Path(stdin_path).read_text(encoding="utf-8")
            process = subprocess.Popen(
                attempt["command"],
                cwd=job["workdir"],
                stdin=subprocess.PIPE,
                stdout=stdout_handle,
                stderr=stderr_handle,
                text=True,
            )
            job["claude_pid"] = process.pid
            save_job(state_root, job)
            _, _ = process.communicate(stdin_text)
            return_code = process.returncode
        except Exception as exc:
            error_message = f"{type(exc).__name__}: {exc}"
            stderr_handle.write(f"\n[{utc_now()}] worker error: {error_message}\n")
            stderr_handle.write(traceback.format_exc())
            stderr_handle.flush()
            job = load_job(state_root, job["id"])
            attempt = job["attempts"][job["current_attempt"] - 1]
            fail_job(state_root, job, attempt, error_message=error_message)
            return 0

        job = load_job(state_root, job["id"])
        attempt = job["attempts"][job["current_attempt"] - 1]
        attempt["finished_at"] = utc_now()
        attempt["exit_code"] = return_code
        job["exit_code"] = return_code
        pending_exists = (Path(job["job_dir"]) / PENDING_TOOL_FILENAME).exists()
        if pending_exists:
            attempt["status"] = "awaiting_input"
            job["status"] = "awaiting_input"
        elif return_code == 0:
            attempt["status"] = "succeeded"
            job["status"] = "succeeded"
        else:
            attempt["status"] = "failed"
            job["status"] = "failed"
        if not pending_exists and (Path(job["job_dir"]) / PENDING_ANSWER_FILENAME).exists():
            os.remove(Path(job["job_dir"]) / PENDING_ANSWER_FILENAME)
        save_job(state_root, job)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    launch = subparsers.add_parser("launch", help="Create and optionally start a tracked Claude job.")
    launch.add_argument("--prompt")
    launch.add_argument("--prompt-file")
    launch.add_argument("--workdir")
    launch.add_argument("--output-dir", "--state-root", dest="state_root")
    launch.add_argument("--job-id")
    launch.add_argument("--session-id")
    launch.add_argument("--title")
    launch.add_argument("--model")
    launch.add_argument("--effort")
    launch.add_argument("--permission-mode", default="acceptEdits")
    launch.add_argument("--output-format", default="stream-json")
    launch.add_argument("--add-dir", action="append")
    launch.add_argument("--allowed-tools", nargs="*")
    launch.add_argument("--bare", action="store_true")
    launch.add_argument("--replace", action="store_true")
    launch.add_argument("--dry-run", action="store_true")
    launch.add_argument("--json", action="store_true")
    launch.set_defaults(func=cmd_launch)

    status = subparsers.add_parser("status", help="Show job status or the full registry.")
    status.add_argument("job_id", nargs="?")
    status.add_argument("--workdir")
    status.add_argument("--output-dir", "--state-root", dest="state_root")
    status.add_argument("--tail", type=int, default=0)
    status.add_argument("--tail-stderr", action="store_true")
    status.add_argument("--tail-both", action="store_true")
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=cmd_status)

    resume = subparsers.add_parser("resume", help="Resume a saved Claude session.")
    resume.add_argument("job_id")
    resume.add_argument("--workdir")
    resume.add_argument("--output-dir", "--state-root", dest="state_root")
    resume.add_argument("--message")
    resume.add_argument("--model")
    resume.add_argument("--effort")
    resume.add_argument("--bare", action="store_true")
    resume.add_argument("--no-bare", action="store_true")
    resume.add_argument("--dry-run", action="store_true")
    resume.add_argument("--json", action="store_true")
    resume.set_defaults(func=cmd_resume)

    answer = subparsers.add_parser(
        "answer", help="Write updatedInput for a deferred tool call and optionally resume."
    )
    answer.add_argument("job_id")
    answer.add_argument("--workdir")
    answer.add_argument("--output-dir", "--state-root", dest="state_root")
    answer.add_argument("--updated-input-json")
    answer.add_argument("--updated-input-file")
    answer.add_argument("--note")
    answer.add_argument("--resume-now", action="store_true")
    answer.add_argument("--message")
    answer.add_argument("--dry-run", action="store_true")
    answer.add_argument("--json", action="store_true")
    answer.set_defaults(func=cmd_answer)

    hook = subparsers.add_parser("hook", help="Internal per-job Claude hook.")
    hook.add_argument("--job-dir", required=True)
    hook.set_defaults(func=cmd_hook)

    run_job = subparsers.add_parser("_run-job", help=argparse.SUPPRESS)
    run_job.add_argument("--job-file", required=True)
    run_job.set_defaults(func=cmd_run_job)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
