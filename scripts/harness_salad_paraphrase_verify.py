"""Independent validation of Salad task-paraphrase counterfactuals."""
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()

def final_answer(text,expected):
    lines=[x.strip() for x in text.strip().splitlines() if x.strip()]
    if not lines: return False
    x=re.sub(r"^(?:final\s+)?answer\s*:\s*", "", lines[-1], flags=re.I)
    return x.rstrip(".").strip()==expected

def analyze(result,receipt):
    if receipt.get("stopped") is not True:
        raise ValueError("not stopped")
    if receipt.get("provider_result_sha256")!=sha(json.dumps(result,sort_keys=True)):
        raise ValueError("provider receipt hash mismatch")
    phrases=result["phrases"]
    arms=result["arms"]
    if len(phrases)!=2 or set(phrases)!={"squares","logic"} or len(arms)!=4:
        raise ValueError("wrong factor design")
    if result.get("total")!=72 or len(result.get("results",[]))!=72:
        raise ValueError("incomplete")
    seeds=(501,502,503)
    truths={}
    for task,phrase_list in phrases.items():
        if len(phrase_list)!=3:
            raise ValueError("wrong phrase grid")
        for phrase_id,prompt,expected in phrase_list:
            key=(task,phrase_id)
            if key in truths: raise ValueError("duplicate phrase")
            truths[key]=(prompt,expected)
    pairs={}
    for r in result["results"]:
        k=(r["task"],r["phrase_id"],r["arm"],r["replicate"])
        if k in pairs or r["replicate"] not in seeds or r["arm"] not in arms:
            raise ValueError("duplicate or invalid observation")
        if (r["task"],r["phrase_id"]) not in truths:
            raise ValueError("unknown phrase")
        p,e=truths[(r["task"],r["phrase_id"])]
        if r["prompt"]!=p or r["prompt_sha256"]!=sha(p):
            raise ValueError("prompt mutated")
        if r["instruction_sha256"]!=sha(arms[r["arm"]]):
            raise ValueError("instruction mutated")
        if r["expected_sha256"]!=sha(e) or r["answer_sha256"]!=sha(r["answer"]):
            raise ValueError("answer hash mutated")
        exact = r["error"] is None and r["answer"]==e
        semantic = r["error"] is None and final_answer(r["answer"],e)
        if r["exact"] is not exact or r["final_semantic"] is not semantic:
            raise ValueError("scoring mismatch")
        pairs[k]=r
    if len(pairs)!=72:
        raise ValueError("unbalanced")
    report={"n":72,"source_commit":receipt.get("source_commit"),
            "stop_confirmed":True,"model_returned":sorted(set(str(r["model_returned"]) for r in result["results"])),
            "by_task":{},"by_arm":{}}
    for task in phrases:
        report["by_task"][task]={}
        for phrase_id,_,_ in phrases[task]:
            report["by_task"][task][phrase_id]={}
            for arm in arms:
                series=[pairs[(task,phrase_id,arm,rep)] for rep in seeds]
                report["by_task"][task][phrase_id][arm]={
                    "exact":sum(x["exact"] for x in series),
                    "final_semantic":sum(x["final_semantic"] for x in series),
                    "distinct_answers":sorted(set(x["answer"] for x in series))
                }
    for arm in arms:
        rows=[x for x in result["results"] if x["arm"]==arm]
        report["by_arm"][arm]={
            "n":len(rows),"exact":sum(x["exact"] for x in rows),
            "final_semantic":sum(x["final_semantic"] for x in rows),
            "errors":sum(x["error"] is not None for x in rows),
            "mean_tokens_in":round(sum(x["usage"].get("prompt_tokens",0) for x in rows)/len(rows),2),
            "mean_tokens_out":round(sum(x["usage"].get("completion_tokens",0) for x in rows)/len(rows),2),
        }
    report["limitations"]=["Posthoc task selection", "Paraphrase variation is not a direct neural intervention",
        "Model RNG and backend hardware not pinned", "Salad Gateway, not Hermes CLI"]
    return report

def main():
    root=Path("experiments/harness")
    d=json.loads((root/"20261117_paraphrase_raw.json").read_text())
    r=json.loads((root/"20261117_paraphrase_receipt.json").read_text())
    x=analyze(d,r)
    (root/"20261117_paraphrase_verified.json").write_text(json.dumps(x,indent=2,sort_keys=True)+"\n")
    print(json.dumps(x,indent=2,sort_keys=True))

if __name__=="__main__":
    main()
