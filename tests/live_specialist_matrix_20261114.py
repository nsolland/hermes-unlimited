#!/usr/bin/env python3
"""Real Hermes CLI multi-model read_file benchmark; no simulated model outputs."""
import concurrent.futures, json, os, pathlib, subprocess, time
from datetime import datetime, timezone

ROOT=pathlib.Path("/tmp/hermes-specialist-live-benchmark-20261114")
ROOT.mkdir(parents=True,exist_ok=True)
CASES={
 "ticket": ("TICKET=INC-2048\nPRIORITY=HIGH\nSTATE=ESCALATE\n", "STATE", "ESCALATE"),
 "invoice": ("INVOICE=F-271\nNET_NOK=1750\nVAT_NOK=438\nTOTAL_NOK=2188\n", "TOTAL_NOK", "2188"),
}
MODELS=[("nous","upstage/solar-mini4:free"),("gemini","gemini-3.1-flash-lite-preview")]
REPS=3
for case,(content,field,expected) in CASES.items():
 (ROOT/(case+".txt")).write_text(content)
jobs=[(provider,model,case,rep) for provider,model in MODELS for case in CASES for rep in range(1,REPS+1)]

def run(job):
 provider,model,case,rep=job
 field,expected=CASES[case][1:]
 slug=provider+"-"+case+"-"+str(rep)
 usage=ROOT/(slug+"-usage.json")
 prompt=(f"Read the exact file at {ROOT/(case+'.txt')} using the read_file tool. "
         f"Report ONLY the value for {field}, with no other characters. "
         "You must access the file; do not guess.")
 cmd=["/home/njaal/.local/bin/hermes","-z",prompt,"--provider",provider,"-m",model,
      "-t","file","--safe-mode","--usage-file",str(usage)]
 start=time.monotonic()
 try:
  process=subprocess.run(cmd,capture_output=True,text=True,timeout=90,cwd=str(ROOT))
  status="returned" if process.returncode==0 else "cli_error"
  output=(process.stdout or "").strip()
  err=(process.stderr or "")[-600:]
 except subprocess.TimeoutExpired as exc:
  status="timeout";output=(exc.stdout or b"").decode(errors="replace") if isinstance(exc.stdout,bytes) else (exc.stdout or "")
  err="TIMEOUT";process=None
 elapsed=round(time.monotonic()-start,3)
 try:data=json.loads(usage.read_text())
 except (OSError,ValueError):data={}
 passed=(status=="returned" and output==expected and data.get("completed") is True and
         data.get("failed") is False and (data.get("api_calls") or 0)>=2)
 return {"model":model,"provider":provider,"case_id":case,"repetition":rep,"expected":expected,
         "observed":output[-160:],"passed":passed,"status":status,"seconds":elapsed,
         "input_tokens":data.get("input_tokens"),"output_tokens":data.get("output_tokens"),
         "api_calls":data.get("api_calls"),"cost_usd_estimated":data.get("estimated_cost_usd"),
         "cost_source":data.get("cost_source"),"error":err,"usage_file":str(usage)}

results=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
 futures={pool.submit(run,job):job for job in jobs}
 for fut in concurrent.futures.as_completed(futures):
  result=fut.result()
  results.append(result)
  with (ROOT/"runs.jsonl").open("a") as f:f.write(json.dumps(result,ensure_ascii=False)+"\n")
  print(json.dumps({"model":result["model"],"case":result["case_id"],
                    "rep":result["repetition"],"passed":result["passed"],
                    "secs":result["seconds"],"calls":result["api_calls"],
                    "cost_estimated_usd":result["cost_usd_estimated"]}),flush=True)
summary={}
for provider,model in MODELS:
 rr=[r for r in results if r["model"]==model]
 summary[model]={"n":len(rr),"pass":sum(x["passed"] for x in rr),
                 "pass_rate":sum(x["passed"] for x in rr)/len(rr),
                 "total_cost_usd_estimated":sum(x["cost_usd_estimated"] or 0 for x in rr),
                 "total_input_tokens":sum(x["input_tokens"] or 0 for x in rr),
                 "total_output_tokens":sum(x["output_tokens"] or 0 for x in rr),
                 "mean_seconds":sum(x["seconds"] for x in rr)/len(rr),
                 "failures":[{"case":x["case_id"],"rep":x["repetition"],
                              "output":x["observed"],"error":x["error"]} for x in rr if not x["passed"]]}
record={"timestamp_utc":datetime.now(timezone.utc).isoformat(),"fixture_source":"locally-created controlled files",
        "method":"Actual Hermes CLI -z --provider --model -t file --safe-mode with --usage-file",
        "note":"Actual tool usage requires trace to independently prove tool invocation; api_calls>=2 is a proxy only. Costs are provider estimates, not independently billed prices.",
        "models":summary,"runs":sorted(results,key=lambda x:(x["model"],x["case_id"],x["repetition"]))}
(ROOT/"report.json").write_text(json.dumps(record,indent=2))
print("FINAL",json.dumps(summary),flush=True)
