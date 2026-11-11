"""Run the public Socratic Council with any local Ollama-compatible chat API.

Usage: python -m unlimited.council_cli --question "..." --answers-json answers.json
       --member explorer=llama3.2 --member skeptic=qwen2.5 --chair llama3.2

Requires two expert roles, an Ollama-compatible local server and installed models.
No credentials or external action tools are loaded by this entrypoint.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .socratic_council import QUESTIONS, SocraticCouncil


def ollama_chat(model: str, *, origin: str = "http://127.0.0.1:11434", timeout: int = 90, opener=urlopen):
    parsed = urlsplit(origin)
    if (parsed.scheme != "http" or parsed.hostname not in ("localhost", "127.0.0.1", "::1") or
            parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/")):
        raise ValueError("Local Ollama must use a loopback HTTP origin")
    if not isinstance(model, str) or not model.strip() or len(model) > 128:
        raise ValueError("Nonempty model ID required")
    if not isinstance(timeout, int) or not 1 <= timeout <= 600:
        raise ValueError("Timeout must be between 1 and 600 seconds")

    def invoke(system: str, prompt: str) -> str:
        request = Request(origin.rstrip("/") + "/api/chat", method="POST",
                          data=json.dumps({"model": model, "stream": False,
                                           "messages": [{"role": "system", "content": system},
                                                        {"role": "user", "content": prompt}]}).encode(),
                          headers={"Content-Type": "application/json"})
        try:
            with opener(request, timeout=timeout) as response:
                data = response.read(2_000_001)
        except (OSError, HTTPError, URLError, TimeoutError) as exc:
            raise RuntimeError("Local model request failed") from exc
        if len(data) > 2_000_000:
            raise RuntimeError("Model output exceeds bound")
        try:
            payload = json.loads(data)
        except (ValueError, UnicodeDecodeError):
            raise RuntimeError("Model response is not JSON") from None
        message = payload.get("message") if isinstance(payload, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("Model returned no text")
        return content

    async def call(system: str, prompt: str) -> str:
        return await asyncio.to_thread(invoke, system, prompt)

    return call


def parse_members(values: list[str]) -> dict[str, str]:
    members = {}
    for item in values:
        if "=" not in item:
            raise ValueError("Use --member ROLE=MODEL")
        role, model = item.split("=", 1)
        if not role.strip() or not model.strip() or role in members:
            raise ValueError("Member role and model required; roles must be unique")
        members[role] = model
    if len(members) < 2:
        raise ValueError("At least two expert roles are required")
    return members


async def run(question: str, answers: dict, members: dict, chair: str, origin: str, timeout: int):
    council = SocraticCouncil({role: ollama_chat(model, origin=origin, timeout=timeout)
                               for role, model in members.items()},
                              ollama_chat(chair, origin=origin, timeout=timeout))
    return (await council.run(question, answers)).as_dict()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Local Socratic Council (no external effects)")
    parser.add_argument("--question", required=True)
    parser.add_argument("--answers-json", required=True, type=Path)
    parser.add_argument("--member", action="append", required=True, metavar="ROLE=MODEL")
    parser.add_argument("--chair", required=True)
    parser.add_argument("--origin", default="http://127.0.0.1:11434")
    parser.add_argument("--timeout", type=int, default=90)
    args = parser.parse_args(argv)
    members = parse_members(args.member)
    try:
        answers = json.loads(args.answers_json.read_text(encoding="utf-8"))
        if not isinstance(answers, dict):
            raise ValueError("answers-json must be a JSON object")
        output = asyncio.run(run(args.question, answers, members, args.chair,
                                 args.origin, args.timeout))
    except (ValueError, OSError, RuntimeError) as exc:
        parser.exit(2, "Council failed: " + str(exc) + "\n")
    print(json.dumps(output, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
