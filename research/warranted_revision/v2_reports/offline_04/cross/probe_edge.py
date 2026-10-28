"""Cross-review (A): edge cases of scaffold_probe.run with a fake backend whose base answer is
invalid or need_more_information, and the stage-1 config's sampled-readout targets.
Writes only into the temp dir argv[1]."""
import json, sys
from pathlib import Path
from warranted_revision.runner import PKG_ROOT
from warranted_revision.scaffold_probe import ProbeConfig, ProbeFakeBackend, run
from warranted_revision.schema import Completion

tmp = Path(sys.argv[1])
raw = json.loads((PKG_ROOT / "configs/scaffold_probe_stage1.json").read_text())

class BaseOdd(ProbeFakeBackend):
    def __init__(self, mode):
        super().__init__("stubborn"); self.mode = mode; self.label = f"fake:{mode}"
    def generate(self, reqs):
        out = super().generate(reqs)
        for i, r in enumerate(reqs):
            if len(r.messages) == 2:  # base turn
                t = "I think so." if self.mode == "invalid" else "Hmm.\nDECISION: need_more_information"
                out[i] = Completion(text=t, prompt_tokens=1, completion_tokens=1, latency_s=0.0)
        return out

for mode in ("invalid", "nmi"):
    cfg = ProbeConfig.model_validate({**raw, "run_id": f"edge-{mode}", "systems": [{"kind": "fake", "name": "stubborn"}], "max_calls": None})
    try:
        run(cfg, out_root=tmp, backends={"x": BaseOdd(mode)})
        print(mode, "-> completed")
    except BaseException as e:
        print(mode, "-> CRASH", type(e).__name__, str(e)[:120])

# stage-1 config as written: which decision step does each sampled readout re-draw?
cfg = ProbeConfig.model_validate({**raw, "run_id": "s1", "systems": [{"kind": "fake", "name": "stubborn"}]})
out = run(cfg, out_root=tmp)
rows = [json.loads(l) for l in (out / "probe_calls.jsonl").open()]
from collections import Counter
res = Counter()
for s in (r for r in rows if r["step"] == "sample"):
    fin = [x for x in rows if x["step"].endswith("decision") and (x["case_id"], x["order"], x["cell"], x["item"]) == (s["case_id"], s["order"], s["cell"], s["item"]) and x["messages"] == s["messages"]]
    res[(s["cell"], s["item"], fin[0]["step"] if fin else None)] += 1
for k, v in sorted(res.items()): print("sample re-draws", k, v)
print("base rows with base_choice recorded:", sum(r["base_choice"] is not None for r in rows if r["step"] == "base"), "/", sum(r["step"] == "base" for r in rows))
print("free steps parsed:", {r["parsed"] for r in rows if r["step"].endswith("free")})
