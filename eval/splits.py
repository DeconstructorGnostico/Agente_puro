"""Carga de datasets públicos y partición dev / held-out (determinista).

Regla anti-sobreajuste: las reglas del firewall se escribieron mirando SOLO
el split `dev`. Todo lo demás (`test`) se evalúa una sola vez al final.

- AdvBench: sha256(goal) % 10 < 3  -> dev (≈30%), resto -> test.
- AdvBench MT→ES (Argos): solo se usan en test los items cuyo original está en test;
  el dev en español se tradujo aparte (eval/dev/advbench_dev_es_mt.jsonl).
- Alpaca EN / Alpaca-ES: test = misma muestra que el reporte anterior
  (random.Random(42).sample(…, 200)); dev = 300 items distintos (Random(7)).
- HarmBench, XSTest, Aya (ES nativo) y HarmBench MT→ES: SOLO test, nunca se miraron
  para escribir reglas.
- eval/dev/dev_manual.jsonl: casos escritos a mano (fuente disjunta).
"""
from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

HERE = Path(__file__).parent


def is_dev(text: str) -> bool:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16) % 10 < 3


def _alpaca_prompt(r):
    return r["instruction"] + (("\n" + r["input"]) if r.get("input") else "")


def _alpaca_split(records):
    # La muestra de test replica exactamente la del reporte anterior.
    test = random.Random(42).sample(records, 200)
    test_keys = {_alpaca_prompt(r) for r in test}
    pool = [r for r in records if _alpaca_prompt(r) not in test_keys]
    dev = random.Random(7).sample(pool, 300)
    return dev, test


def load(data_dir: str | Path, split: str) -> list[tuple[str, str, str]]:
    """Devuelve [(dataset, label, prompt)] para split 'dev' o 'test'."""
    import pandas as pd  # dependencia solo de evaluación

    data = Path(data_dir)
    out: list[tuple[str, str, str]] = []
    adv = list(pd.read_csv(data / "advbench.csv").goal)
    al = json.load(open(data / "alpaca.json", encoding="utf-8"))
    ales = pd.read_parquet(data / "alpaca_es.parquet").to_dict("records")
    al_dev, al_test = _alpaca_split(al)
    es_dev, es_test = _alpaca_split(ales)

    if split == "dev":
        out += [("advbench_dev_en", "harmful", g) for g in adv if is_dev(g)]
        mt = HERE / "dev" / "advbench_dev_es_mt.jsonl"
        if mt.exists():
            out += [("advbench_dev_es_mt", "harmful", json.loads(l)["prompt"]) for l in open(mt, encoding="utf-8")]
        out += [("alpaca_dev_en", "benign", _alpaca_prompt(r)) for r in al_dev]
        out += [("alpaca_dev_es", "benign", _alpaca_prompt(r)) for r in es_dev]
        for line in open(HERE / "dev" / "dev_manual.jsonl", encoding="utf-8"):
            if line.strip():
                r = json.loads(line)
                out.append((f"manual_dev_{r['lang']}", r["label"], r["prompt"]))
        return out

    if split != "test":
        raise ValueError(split)
    hb = pd.read_csv(data / "harmbench.csv")
    for _, r in hb.iterrows():
        p = r.Behavior
        if isinstance(r.ContextString, str) and r.ContextString.strip():
            p = r.ContextString + "\n\n---\n\n" + r.Behavior
        out.append(("harmbench_en", "harmful", p))
    out += [("advbench_heldout_en", "harmful", g) for g in adv if not is_dev(g)]
    xs = pd.read_csv(data / "xstest.csv")
    for _, r in xs.iterrows():
        out.append((f"xstest_{r.label}_en", "harmful" if r.label == "unsafe" else "benign", r.prompt))
    for line in open(data / "aya_spa.jsonl", encoding="utf-8"):
        out.append(("aya_redteam_es", "harmful", json.loads(line)["prompt"]))
    tr = data / "translated_es.jsonl"
    if tr.exists():
        for line in open(tr, encoding="utf-8"):
            r = json.loads(line)
            if r["dataset"] == "advbench_es_mt":
                if is_dev(r["source_en"]):
                    continue
                out.append(("advbench_heldout_es_mt", "harmful", r["prompt"]))
            else:
                out.append((r["dataset"], "harmful", r["prompt"]))
    out += [("alpaca_test_en", "benign", _alpaca_prompt(r)) for r in al_test]
    out += [("alpaca_test_es", "benign", _alpaca_prompt(r)) for r in es_test]
    return out
