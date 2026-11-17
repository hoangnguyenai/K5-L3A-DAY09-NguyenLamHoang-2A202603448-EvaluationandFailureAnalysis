"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    from lab9.eval import aggregate
    from lab9.graders import GRADERS

    problems, pair_sets, tag_maps = [], [], []
    graded = [m["id"] for m in spec["metrics"] if m["id"] in GRADERS]
    for name, report in (("PR", pr), ("baseline", base)):
        rows, manifest = report.get("rows", []), report.get("manifest", {})
        seeds, size = manifest.get("seeds", []), manifest.get("items", 0)
        keys = [(r.get("item_id"), r.get("seed")) for r in rows]
        item_ids = {i for i, _ in keys}
        if (not seeds or size < 1 or len(set(seeds)) != len(seeds)
                or len(rows) != size * len(seeds) or len(set(keys)) != len(keys)
                or len(item_ids) != size or set(keys) != {(i, s) for i in item_ids for s in seeds}):
            problems.append(f"{name}: incomplete, duplicate or invalid item/seed coverage")
        pair_sets.append(set(keys))
        tags = {}
        for row in rows:
            item, value = row.get("item_id"), frozenset(row.get("slices") or [])
            if item in tags and tags[item] != value:
                problems.append(f"{name}: inconsistent slice tags for {item}")
            tags[item] = value
        tag_maps.append(tags)
        if report.get("evaluator_failures"):
            problems.append(f"{name}: evaluator_failures is nonempty")
        for mid, val in report.get("metrics", {}).items():
            if val is not None and (not isinstance(val, (int, float)) or not math.isfinite(val)):
                problems.append(f"{name}: nonfinite or invalid aggregate {mid}")
        valid = True
        for row in rows:
            for mid in graded:
                value = row.get(mid)
                if not isinstance(value, (bool, int, float)) or not math.isfinite(value) or value not in (0, 1):
                    problems.append(f"{name}: missing/invalid grader {mid} at {row.get('item_id')}@{row.get('seed')}")
                    valid = False
            if "cost" in row and (not isinstance(row["cost"], (int, float))
                                  or not math.isfinite(row["cost"]) or row["cost"] < 0):
                problems.append(f"{name}: invalid cost")
                valid = False
        if rows and valid:
            computed = aggregate([dict(r, cost=r.get("cost", 0)) for r in rows], graded,
                                 k_values=spec.get("pass_k", []))
            for metric in spec["metrics"]:
                mid = metric["id"]
                actual, expected = report.get("metrics", {}).get(mid), computed.get(mid)
                if mid == "cost_per_success" and not all("cost" in r for r in rows):
                    continue
                if actual is None and metric.get("blocking"):
                    problems.append(f"{name}: missing blocking metric {mid}")
                elif mid in computed and expected is not None and (actual is None or
                        not isinstance(actual, (int, float)) or not math.isfinite(actual) or
                        not math.isclose(actual, expected, abs_tol=0.00011)):
                    problems.append(f"{name}: aggregate does not match rows: {mid}")
    if pair_sets[0] != pair_sets[1]:
        problems.append("PR item/seed set differs from baseline")
    if tag_maps[0] != tag_maps[1]:
        problems.append("PR slice tags differ from baseline")
    if base_spec and spec.get("eval_set_version") == base_spec.get("eval_set_version"):
        for section, fields in (("metrics", ("id",)), ("slices", ("name", "metric"))):
            rules = {tuple(r[f] for f in fields): r for r in spec.get(section, [])}
            for old in base_spec.get(section, []):
                key = tuple(old[f] for f in fields)
                new = rules.get(key)
                if new is None:
                    problems.append(f"ratchet: removed {section} {key}")
                    continue
                if old.get("blocking") and not new.get("blocking"):
                    problems.append(f"ratchet: blocking disabled {key}")
                prior = old.get("threshold", old)
                current = new.get("threshold", new)
                for limit in ("min", "max", "max_increase"):
                    if limit not in prior:
                        continue
                    value = current.get(limit)
                    if (not isinstance(value, (int, float)) or not math.isfinite(value)
                            or (value < prior[limit] if limit == "min" else value > prior[limit])):
                        problems.append(f"ratchet: loosened {key}/{limit}")
                if prior.get("no_significant_drop") and not current.get("no_significant_drop"):
                    problems.append(f"ratchet: removed paired comparison {key}")
    return problems


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for rule in spec.get("slices", []):
        name, metric = rule["name"], rule["metric"]
        key = f"slice:{name}/{metric}"
        a, b = per_item(pr, metric, name), per_item(base, metric, name)
        failed = not a or set(a) != set(b)
        value = sum(a.values()) / len(a) if a else None
        note = ""
        if value is not None:
            failed |= value < rule.get("min", -math.inf) or value > rule.get("max", math.inf)
        if a and set(a) == set(b) and rule.get("no_significant_drop"):
            keys = sorted(a)
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027),
                confidence=bs.get("confidence", 0.95))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            failed |= hi < 0
        if failed and rule.get("blocking"):
            blocked.append(key)
        verdict = "BLOCK" if failed and rule.get("blocking") else "warn" if failed else "ok"
        lines.append(f"  {key} {value} {note} {verdict}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027),
                                               confidence=bs.get("confidence", 0.95))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
