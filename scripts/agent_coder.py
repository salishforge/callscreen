#!/usr/bin/env python3
"""
Multi-agent coding dispatcher for CallScreen.

Sends well-defined coding tasks to Ollama models (DeepSeek-v3.2, Minimax-m2.7)
and writes the results to specified output files. Claude Code (Opus 4.6) acts as
the orchestrator: planning, specifying tasks, reviewing, and integrating results.

Usage:
    # Single task
    python scripts/agent_coder.py --task task_spec.json

    # From stdin (for piping from Claude Code)
    echo '{"model":"deepseek-v3.2:cloud","output":"path.py","prompt":"..."}' | python scripts/agent_coder.py

    # Batch mode: run multiple tasks in parallel
    python scripts/agent_coder.py --batch tasks_dir/
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "deepseek-v3.2:cloud"
RESULTS_DIR = Path("/home/artificium/dev/projects/callscreen/.agent_results")


def call_ollama(model: str, prompt: str, temperature: float = 0.1) -> str:
    """Send a prompt to Ollama and return the response text."""
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": 16384,
        },
    })

    result = subprocess.run(
        ["curl", "-s", OLLAMA_URL, "-d", payload],
        capture_output=True,
        text=True,
        timeout=300,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Ollama request failed: {result.stderr}")

    response = json.loads(result.stdout)
    return response.get("response", "")


def extract_code(response: str, language: str = "python") -> str:
    """Extract code from markdown code blocks in the response."""
    lines = response.split("\n")
    in_block = False
    code_lines = []
    found_block = False

    for line in lines:
        if line.strip().startswith(f"```{language}") or line.strip().startswith("```py"):
            in_block = True
            found_block = True
            continue
        elif line.strip() == "```" and in_block:
            in_block = False
            continue
        elif in_block:
            code_lines.append(line)

    if found_block and code_lines:
        return "\n".join(code_lines).strip() + "\n"

    # If no code blocks found, return the full response (might be raw code)
    return response.strip() + "\n"


def run_task(task: dict) -> dict:
    """Execute a single coding task and return the result."""
    task_id = task.get("id", "unnamed")
    model = task.get("model", DEFAULT_MODEL)
    output_path = task.get("output", "")
    prompt = task.get("prompt", "")
    language = task.get("language", "python")
    context_files = task.get("context_files", [])

    if not prompt:
        return {"id": task_id, "status": "error", "error": "No prompt provided"}

    # Build full prompt with context
    full_prompt = build_prompt(prompt, context_files, language)

    start = time.time()
    try:
        response = call_ollama(model, full_prompt)
        code = extract_code(response, language)
        elapsed = round(time.time() - start, 1)

        # Write output file
        if output_path:
            abs_path = Path(output_path)
            if not abs_path.is_absolute():
                abs_path = Path("/home/artificium/dev/projects/callscreen") / output_path
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            abs_path.write_text(code)

        # Save result metadata
        result = {
            "id": task_id,
            "status": "completed",
            "model": model,
            "output": str(output_path),
            "elapsed_seconds": elapsed,
            "code_lines": len(code.split("\n")),
            "response_preview": code[:200],
        }

        # Save full result to results dir
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        result_file = RESULTS_DIR / f"{task_id}.json"
        result_file.write_text(json.dumps({**result, "full_code": code}, indent=2))

        return result

    except Exception as e:
        return {
            "id": task_id,
            "status": "error",
            "error": str(e),
            "elapsed_seconds": round(time.time() - start, 1),
        }


def build_prompt(task_prompt: str, context_files: list[str], language: str) -> str:
    """Build the full prompt with file context and coding instructions."""
    parts = []

    parts.append(
        "You are an expert Python developer working on CallScreen, an AI-powered "
        "call screening system built with FastAPI, SQLAlchemy, Redis, and Twilio.\n\n"
        "IMPORTANT RULES:\n"
        "- Return ONLY the complete file content inside a single code block\n"
        "- No explanations before or after the code\n"
        "- Follow existing project patterns and imports\n"
        "- Use type hints throughout\n"
        "- Use async/await for all database and I/O operations\n"
        "- Do not add unnecessary comments\n"
    )

    # Add file context
    if context_files:
        parts.append("\n--- CONTEXT FILES (reference for patterns and imports) ---\n")
        for fpath in context_files:
            abs_path = Path(fpath)
            if not abs_path.is_absolute():
                abs_path = Path("/home/artificium/dev/projects/callscreen") / fpath
            if abs_path.exists():
                content = abs_path.read_text()
                parts.append(f"\n### {fpath}\n```{language}\n{content}\n```\n")

    parts.append(f"\n--- TASK ---\n{task_prompt}\n")

    return "\n".join(parts)


def run_batch(tasks_dir: str, max_workers: int = 3) -> list[dict]:
    """Run multiple tasks in parallel from a directory of task specs."""
    tasks_path = Path(tasks_dir)
    task_files = sorted(tasks_path.glob("*.json"))

    if not task_files:
        print(f"No task files found in {tasks_dir}")
        return []

    tasks = []
    for tf in task_files:
        task = json.loads(tf.read_text())
        if "id" not in task:
            task["id"] = tf.stem
        tasks.append(task)

    return run_parallel(tasks, max_workers)


def run_parallel(tasks: list[dict], max_workers: int = 3) -> list[dict]:
    """Run multiple tasks in parallel using ThreadPoolExecutor."""
    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(run_task, task): task for task in tasks}

        for future in as_completed(futures):
            task = futures[future]
            try:
                result = future.result()
                status = result.get("status", "unknown")
                task_id = result.get("id", "?")
                elapsed = result.get("elapsed_seconds", 0)
                print(f"  [{status}] {task_id} ({elapsed}s)", file=sys.stderr)
                results.append(result)
            except Exception as e:
                results.append({
                    "id": task.get("id", "unknown"),
                    "status": "error",
                    "error": str(e),
                })

    return results


def main():
    parser = argparse.ArgumentParser(description="Multi-agent coding dispatcher")
    parser.add_argument("--task", help="Path to a single task spec JSON file")
    parser.add_argument("--batch", help="Path to directory of task spec JSON files")
    parser.add_argument("--workers", type=int, default=3, help="Max parallel workers")
    args = parser.parse_args()

    if args.batch:
        results = run_batch(args.batch, args.workers)
    elif args.task:
        task = json.loads(Path(args.task).read_text())
        results = [run_task(task)]
    elif not sys.stdin.isatty():
        # Read from stdin
        data = sys.stdin.read().strip()
        if data.startswith("["):
            tasks = json.loads(data)
            results = run_parallel(tasks, args.workers)
        else:
            task = json.loads(data)
            results = [run_task(task)]
    else:
        parser.print_help()
        sys.exit(1)

    # Output results as JSON
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
