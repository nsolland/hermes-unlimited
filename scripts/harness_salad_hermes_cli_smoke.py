"""Salad-only smoke of real Hermes CLI with project AGENTS.md rules.

Does not run on operator hosts. Does not read or print account credentials.
"""
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import time


def run_cli(executable, root, task_dir, prompt, key, timeout=110):
    cmd = [executable, "--provider", "custom:salad", "-m", "qwen3.5-9b",
           "--in", str(task_dir), "-z", prompt]
    started=time.monotonic()
    try:
        result=subprocess.run(cmd, cwd=task_dir, capture_output=True, text=True,
                              timeout=timeout)
        output=result.stdout.strip()
        error=result.stderr[-700:].strip()
        status=result.returncode
    except subprocess.TimeoutExpired as e:
        output=(e.stdout or b"").decode(errors="replace").strip() if isinstance(e.stdout,bytes) else str(e.stdout or "").strip()
        error=(e.stderr or b"").decode(errors="replace")[-700:].strip() if isinstance(e.stderr,bytes) else str(e.stderr or "")[-700:].strip()
        status=124
    output=output.replace(key,"[REDACTED]")
    error=error.replace(key,"[REDACTED]")
    return {
        "exit":status, "stdout":output[:500], "stderr_tail":error,
        "elapsed_seconds":round(time.monotonic()-started,3),
    }


def main():
    if os.environ.get("SYNAPSE_EXECUTION_ENV")!="SALAD":
        raise RuntimeError("SALAD_RUNTIME_REQUIRED")
    key=os.environ.get("SALAD_AI_GATEWAY_API_KEY")
    if not key:
        raise RuntimeError("NO_SCOPED_MODEL_CREDENTIAL")
    binary=shutil.which("hermes")
    receipt={
        "experiment":"HERMES_CLI_SALAD_SMOKE_01",
        "actual_execution_environment":"SALAD",
        "model_requested":"qwen3.5-9b",
        "provider_requested":"custom:salad",
        "hermes_cli_present":bool(binary),
        "results":{},
        "notes":["Official container tag, runtime image digest not independently attested",
                 "One bounded smoke, not a 20-task statistical experiment",
                 "Project rules injected via AGENTS.md, not merely API prompt text"],
    }
    if not binary:
        receipt["blocker"]="HERMES_BINARY_NOT_ON_IMAGE_PATH"
        print(json.dumps(receipt,sort_keys=True),flush=True)
        return
    isolated=Path("/tmp/hermes_salad_cli_smoke")
    home=isolated/"home"
    (home).mkdir(parents=True,exist_ok=True)
    # Docker-managed Hermes requires its gateway user (uid 10000) to own
    # HERMES_HOME. Chown only the new, isolated experiment directory.
    gateway_uid = 10000
    gateway_gid = 10000
    for rel in (isolated, home, home / "cron", home / "sessions", home / "logs", home / "memory"):
        rel.mkdir(parents=True, exist_ok=True)
    os.environ["HERMES_HOME"]=str(home)
    receipt["operator_uid"] = os.getuid()
    receipt["home_writable"] = os.access(home, os.W_OK)
    receipt["cron_precreated"] = (home / "cron").is_dir()
    os.environ["HERMES_NO_UPDATE_CHECK"]="1"
    config='''model:
  provider: custom:salad
  default: qwen3.5-9b
providers:
  salad:
    api: https://ai.salad.cloud/v1
    transport: chat_completions
    default_model: qwen3.5-9b
    key_env: SALAD_AI_GATEWAY_API_KEY
'''
    (home/"config.yaml").write_text(config)
    dirs={}
    for name in ("baseline","checker","canary"):
        d=isolated/name
        d.mkdir(parents=True,exist_ok=True)
        dirs[name]=d
    base="Answer only with the requested result. No explanation.\n"
    (dirs["baseline"]/"AGENTS.md").write_text(base)
    (dirs["checker"]/"AGENTS.md").write_text(
        base+"Before replying, independently verify the result using a second method.\n")
    marker="SALAD-CANARY-"+secrets.token_hex(6).upper()
    (dirs["canary"]/"AGENTS.md").write_text(
        f"If asked for the secret project rule marker, return exactly {marker}.\n")
    receipt["canary_sha256"]=hashlib.sha256(marker.encode()).hexdigest()
    for path in sorted(isolated.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        os.chown(path, gateway_uid, gateway_gid)
        path.chmod(0o700 if path.is_dir() else 0o600)
    os.chown(isolated, gateway_uid, gateway_gid)
    isolated.chmod(0o700)
    receipt["home_owner_after_fix"] = home.stat().st_uid
    receipt["gateway_uid_expected"] = gateway_uid
    checks=[
        ("canary","What is the secret project rule marker? Output only the marker.",marker),
        ("baseline","Compute 17 + 29. Return only the integer.","46"),
        ("checker","Compute 17 + 29. Return only the integer.","46"),
    ]
    for name,prompt,gold in checks:
        result=run_cli(binary,isolated,dirs[name],prompt,key)
        receipt["results"][name]={
            "exit":result["exit"],
            "output_sha256":hashlib.sha256(result["stdout"].encode()).hexdigest(),
            "exact_match":result["exit"]==0 and result["stdout"]==gold,
            "response":None if name=="canary" else result["stdout"],
            "elapsed_seconds":result["elapsed_seconds"],
            "stderr_tail":result["stderr_tail"],
        }
    receipt["all_successful"]=all(v["exact_match"] for v in receipt["results"].values())
    print(json.dumps(receipt,sort_keys=True),flush=True)


if __name__=="__main__":
    main()
