"""``mmsafety build | evaluate | explain``."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .defenses import DEFENSES
from .evaluate import evaluate_all, family_table
from .suite import build_suite, dump, fingerprint, load

DEFAULT_SUITE = "benchmark/suite.jsonl"


def _build(args) -> int:
    samples = build_suite(args.per_family, args.seed, heldout=args.heldout)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    dump(samples, args.out)
    print(f"{len(samples)} samples, fingerprint {fingerprint(samples)} → {args.out}")
    return 0


def _evaluate(args) -> int:
    samples = load(args.suite)
    results = evaluate_all(samples)
    report = {"suite": {"samples": len(samples), "fingerprint": fingerprint(samples)}, "results": results}
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(f"{len(samples)} samples, fingerprint {report['suite']['fingerprint']}\n")
    print("| Defense | Attack success | False refusal | Precision | Recall | F1 |")
    print("|---|---:|---:|---:|---:|---:|")
    for r in results:
        print(
            f"| {r['defense']} | {100 * r['attack_success_rate']:.1f}% | {100 * r['false_refusal_rate']:.1f}% | "
            f"{r['precision']:.3f} | {r['recall']:.3f} | {r['f1']:.3f} |"
        )
    print("\nPer family (unsafe: attack success rate; benign: false refusal rate)\n")
    print(family_table(results))
    return 0


def _explain(args) -> int:
    samples = {s.sample_id: s for s in load(args.suite)}
    sample = samples[args.sample_id]
    print(
        json.dumps({"text": sample.text, "image_text": sample.image_text, "unsafe": sample.unsafe}, ensure_ascii=False)
    )
    for defense in DEFENSES:
        decision = defense.decide(sample)
        print(f"{defense.name:<32} {'BLOCK' if decision.blocked else 'allow':<6} {'; '.join(decision.reasons)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mmsafety", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help="regenerate the seeded suite")
    build.add_argument("--per-family", type=int, default=60)
    build.add_argument("--seed", type=int, default=7)
    build.add_argument("--heldout", action="store_true", help="use phrasings unseen during development")
    build.add_argument("--out", default=DEFAULT_SUITE)
    build.set_defaults(func=_build)
    ev = sub.add_parser("evaluate", help="score every defense on the suite")
    ev.add_argument("--suite", default=DEFAULT_SUITE)
    ev.add_argument("--out")
    ev.set_defaults(func=_evaluate)
    ex = sub.add_parser("explain", help="show each defense's decision and reasons for one sample")
    ex.add_argument("sample_id")
    ex.add_argument("--suite", default=DEFAULT_SUITE)
    ex.set_defaults(func=_explain)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
