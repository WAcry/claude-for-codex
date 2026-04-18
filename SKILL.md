---
name: claude-code-orchestrator
description: Delegate subtasks to a local Claude Code instance. Suited for front-end UI implementation, documentation writing, rewriting investigation conclusions into human-readable formats, demo prototypes, and other tasks requiring aesthetics or human readability. Triggered when coordinating Claude Code to complete limited-scope work. This skill is for use only by agents powered by OpenAI GPT models.
---

# Claude Code Orchestrator

## Delegation Model

GPT and Claude have complementary strengths. GPT has stronger reasoning and investigation capabilities but suffers from the curse of knowledge—its explanations are terse and hard for humans to follow. Claude has weaker reasoning and its code often has bugs, but it excels at aesthetics, UI design, and accessible, human-friendly writing. GPT provides accuracy, Claude provides readability. Therefore GPT **must not rewrite** Claude's output for human—only fix factual errors and bugs.

### Tasks Suitable for Delegating to Claude Code

| Task Type | Claude's Strengths | Your Follow-up Action |
|-----------|-------------------|----------------------|
| Front-end UI implementation | Naturally good aesthetics, generates beautiful interfaces | Review and fix code bugs |
| Simple documentation (based on well-scoped code, PRs) | Clear, self-contained, human-friendly | Review and fix factual accuracy and logic |
| Complex document rewriting / polishing | Rewrites concise docs into thorough explanations with good formatting | Review and fix factual accuracy and logic |
| Implementation demos / prototypes | Quickly produces visually appealing prototypes | Review and fix factual accuracy and logic |

### Tasks Requiring GPT First, Claude Code Polish After

| Task Type | Why GPT Goes First | Workflow |
|-----------|-------------------|----------|
| System design documents | Requires broad search and deep reasoning, not limited to a single diff | GPT writes first draft → Claude Code polishes formatting → GPT reviews |
| Investigation analysis, answering user questions | Scope is unclear, requires deep codebase investigation, synthesizing information from multiple sources, requires high reasoning ability | GPT investigates and writes conclusions → Claude Code thoroughly restructures into a readable document at length → GPT reviews |
| Task implementation plans | Scope is unclear, requires deep investigation of feasible approaches, evaluating trade-offs, original design, requires high reasoning ability | GPT writes plan → Claude Code improves descriptions, adds readability, adds necessary examples → GPT reviews |

### Tasks Not Suitable for Independent Completion

- Complex bug investigation or deep investigation/reasoning—Claude often reaches wrong conclusions
- Writing bug-free code—Claude's code frequently has bugs
- Writing original design documents or task plans that require deep thinking—Claude's plans are usually not the best approach and may even contain errors

### Conclusion Rewriting Workflow

When a user question requires deep investigation and the answer needs to be human-readable:

1. **You investigate first**, reaching an accurate conclusion (your conclusion is accurate but concise; the user may have difficulty understanding it)
2. **Delegate to Claude Code**: hand it your conclusion + relevant files and context paths, asking it to rewrite your conclusion into a human-readable explanatory document, generate a markdown document, and provide the path.
3. **You review the document**: only check for factual deviations, make factual corrections, do not change style or length, do not compress, supplement, or restructure.
4. **Deliver**: provide the file path to the user with a brief summary.

## Common Paths for Documents, Artifacts, and Prompts

Unless otherwise specified, store them in `state_root`. Do not place them in `workdir` to avoid polluting the Git environment.

## Output Handling Rules

Claude's output is more readable for users. Your responsibility is to review accuracy, not rewrite style.

| Rule | Description |
|------|-------------|
| Fix only actual errors | Only correct factual errors and obvious bugs; do not modify wording or style |
| Do not add or remove content | Do not add to, remove from, or compress Claude's output |
| Do not paraphrase | Do not redescribe Claude's output in your own words |
| Use files for long content | Have Claude output to a markdown file; after review, provide the file path to the user |

**Self-check signal**: if you find yourself restructuring or condensing Claude's paragraphs—stop. Only fix errors, not content.

## Quick Start

```bash
# Launch a task (automatically assigns a state_id; save the state_id printed in the output)
python ./claude-code-orchestrator/scripts/claude_orchestrator.py launch \
  --prompt-file /abs/path/to/prompt.txt \
  --workdir /abs/path/to/repo \
  --model opus --effort high

# View all tasks
python ./claude-code-orchestrator/scripts/claude_orchestrator.py status \
  --state-id STATE_ID

# View a single task + log tail
python ./claude-code-orchestrator/scripts/claude_orchestrator.py status JOB_ID \
  --state-id STATE_ID --tail 30

# Resume the same session
python ./claude-code-orchestrator/scripts/claude_orchestrator.py resume JOB_ID \
  --state-id STATE_ID --message "Continue with the remaining work"
```

## Key Concepts

| Term | Meaning |
|------|---------|
| **State** (`state_id`, `state_root`) | A single orchestration run, holding one or more jobs under an isolated temp directory. Each run gets its own `state_id`. |
| **Job/Task** (`job_id`) | A single Claude Code invocation within a state, with its own session, logs, and prompt. One job = one focused task. |
| **Attempt/Resume** | One interaction within a job. A job may have multiple attempts via `resume`. All attempts share the same Claude session, so Claude retains full history. |

## Handoff Prompt Template

```text
<role>
You are Claude Code working as a subordinate agent.
state-id: ......
state-root: ......
</role>

<task>
[Specific expected output. Clearly define what "done" looks like.]
</task>

<context>
- Working directory: [...]
- Relevant file paths: [...] (provide paths, not full content)
- Known constraints: [...]
</context>

<operating_rules>
- Read the repository and relevant files first; verify assumptions before acting.
- Stay within the requested scope; avoid unrelated work.
- For explanatory tasks, output to a markdown file inside state-root and return the path.
</operating_rules>

<deliverable>
- Describe what you changed or learned.
- List the files you touched.
- Explain how you verified the results.
- Note any uncertainties or follow-up work.
</deliverable>
```

**Prompt writing tips**:
- Provide file paths and let Claude read them itself—it is an agent with investigation capabilities; you do not need to copy content into the prompt
- When incorrect output is costly, include verification instructions in the task
- When comparing multiple tasks, keep each prompt's scope independent

## Operating Rules

- **One task, one focus**: each launch corresponds to a limited-scope task. Unrelated work should be launched as separate tasks and tracked independently.
- **Review after completion**: wait for Claude Code to finish before reviewing; do not intervene midway.

## Command Reference

### launch

```bash
python ./claude-code-orchestrator/scripts/claude_orchestrator.py launch \
  --prompt "task description" \   # or --prompt-file path, or stdin
  --workdir /abs/path/to/repo \
  --model opus \                  # opus (recommended) or sonnet (cheaper)
  --effort high \
  --add-dir /extra/dir \          # additional accessible directory
  --replace \                     # replace a stopped task with the same id
  --dry-run                       # generate command only, do not execute
```

After running, the following fields are printed:
```text
job_id: ...
state_id: ...
state_root: ...
status: ...
session_id: ...
command: ...
```

### status

```bash
# All tasks
python ./claude-code-orchestrator/scripts/claude_orchestrator.py status --state-id STATE_ID

# Single task + view both stdout and stderr
python ./claude-code-orchestrator/scripts/claude_orchestrator.py status JOB_ID \
  --state-id STATE_ID --tail 30 --tail-both
```

### resume

```bash
python ./claude-code-orchestrator/scripts/claude_orchestrator.py resume JOB_ID \
  --state-id STATE_ID \
  --message "follow-up instructions" \
  --model opus \   # optional override
  --effort high    # optional override
```

### answer

```bash
python ./claude-code-orchestrator/scripts/claude_orchestrator.py answer JOB_ID \
  --state-id STATE_ID \
  --updated-input-json '{"selectedOptionIds":["option1"]}' \
  --resume-now
```

All commands support `--json` for JSON-formatted output.

## Deferred Question Handling

The orchestrator intercepts Claude's `AskUserQuestion` and `ExitPlanMode` via `PreToolUse` hooks.

**Flow**:

1. Claude triggers a question → the hook stores it in `pending-tool.json`, returns `defer`, and Claude exits cleanly while the session is preserved
2. You check the status and `pending-tool.json` with `status JOB_ID --tail 30 --tail-both`
3. Build a matching `updatedInput` based on the tool payload
4. Write the answer and resume with `answer JOB_ID --updated-input-json ... --resume-now`

**Note**: the `updatedInput` structure depends on the specific tool payload—you must inspect `pending-tool.json` before answering.

## Task Directory Structure

```
<system temp dir>/codex-claude-code-orchestrator-state-<state_id>/
├── registry.json              # Summary index of all tasks
└── jobs/JOB_ID/
    ├── job.json               # Task metadata and attempt history
    ├── settings.json          # Claude settings (including hook configuration)
    ├── prompt.txt             # Launch prompt
    ├── attempt-NNNN-input.txt # Input for resume attempts
    ├── stdout.log             # Claude stdout
    ├── stderr.log             # Claude stderr
    ├── pending-tool.json      # Captured deferred tool payload
    └── pending-answer.json    # Operator-provided answer payload awaiting consumption
    └── output_doc_v1.md       # Document written for the user
```
