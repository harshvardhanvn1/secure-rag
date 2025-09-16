import os
import random
import re
from typing import Dict, List, Tuple
from uuid import uuid4

import psycopg
from faker import Faker

from ingest.pii import redact_and_report, SUPPORTED_ENTITIES

# Config
N_SAMPLES = int(os.getenv("PII_EVAL_SAMPLES", "100"))
SEED = 42

fake = Faker()
random.seed(SEED)
Faker.seed(SEED)

# Simple generators for our four entities
def gen_person():
    return fake.name()

def gen_email():
    return fake.email()

def gen_phone():
    # Keep simple US-like; Presidio PHONE_NUMBER handles formats
    return fake.phone_number()

def gen_ssn():
    # 3-2-4 digits; not real
    return f"{random.randint(100,999)}-{random.randint(10,99)}-{random.randint(1000,9999)}"

GEN_MAP = {
    "PERSON": gen_person,
    "EMAIL_ADDRESS": gen_email,
    "PHONE_NUMBER": gen_phone,
    "US_SSN": gen_ssn,
}

def make_sentence() -> Tuple[str, List[Tuple[str, str]]]:
    """
    Returns: (text, gold) where gold is list of (entity_type, surface_text).
    We keep it simple: embed 1-3 entities per sentence.
    """
    ents = random.sample(SUPPORTED_ENTITIES, k=random.randint(1, min(3, len(SUPPORTED_ENTITIES))))
    parts = []
    gold = []
    for et in ents:
        val = GEN_MAP[et]()
        gold.append((et, val))
        parts.append({
            "et": et,
            "val": val
        })
    # Simple template shuffle
    random.shuffle(parts)
    # Construct a sentence
    s = f"{parts[0]['val']} reached out to us."
    for p in parts[1:]:
        s += f" Their {p['et'].replace('_',' ').lower()} is {p['val']}."
    return s, gold

def span_match(gold_text: str, detected_count: int, text: str) -> Tuple[int, int, int]:
    """
    Best-effort matching by string containment count.
    For synthetic data this is reliable because we know exact surfaces.
    Returns tp, fp, fn for this entity instance type on a single sentence.
    """
    # Count exact surface occurrences
    gold_occ = len([m for m in re.finditer(re.escape(gold_text), text)])
    # If Presidio found N instances for that type in this sentence, we approximate TP as min(gold_occ, detected_count).
    tp = min(gold_occ, detected_count)
    fn = max(0, gold_occ - tp)
    fp = max(0, detected_count - tp)
    return tp, fp, fn

def micro_compute(total_tp, total_fp, total_fn):
    prec = (total_tp / (total_tp + total_fp)) if (total_tp + total_fp) else 0.0
    rec  = (total_tp / (total_tp + total_fn)) if (total_tp + total_fn) else 0.0
    f1   = (2*prec*rec / (prec + rec)) if (prec + rec) else 0.0
    return prec, rec, f1

def main():
    DSN = os.getenv("POSTGRES_DSN")
    if not DSN:
        raise RuntimeError("POSTGRES_DSN not set.")

    # Accumulators
    per_entity = {et: {"tp":0,"fp":0,"fn":0} for et in SUPPORTED_ENTITIES}

    samples = [make_sentence() for _ in range(N_SAMPLES)]

    for text, gold in samples:
        redacted, counts = redact_and_report(text)  # counts = {entity_type: n}

        # For each entity type present in gold for this sentence, compute tp/fp/fn
        # Based on surface occurrences & detected counts for that type in this sentence
        # (Synthetic → exact surface; for real corpora you’d match spans.)
        per_type_seen = {}
        for et, surface in gold:
            det_count = counts.get(et, 0)
            tp, fp, fn = span_match(surface, det_count, text)
            per_entity[et]["tp"] += tp
            per_entity[et]["fp"] += fp
            per_entity[et]["fn"] += fn
            per_type_seen[et] = True

        # Count false positives for types not in gold but detected
        for et, det_count in counts.items():
            if et not in per_type_seen and det_count > 0:
                per_entity[et]["fp"] += det_count

    # Compute per-entity metrics + micro-average
    overall_tp = overall_fp = overall_fn = 0
    metrics_rows = []
    for et, agg in per_entity.items():
        tp, fp, fn = agg["tp"], agg["fp"], agg["fn"]
        overall_tp += tp; overall_fp += fp; overall_fn += fn
        p, r, f1 = micro_compute(tp, fp, fn)
        metrics_rows.append((et, tp, fp, fn, p, r, f1))

    mp, mr, mf1 = micro_compute(overall_tp, overall_fp, overall_fn)

    # Persist to DB
    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO pii_eval_run (notes) VALUES (%s) RETURNING run_id;", ("synthetic PII eval",))
            run_id = cur.fetchone()[0]

            cur.executemany("""
                INSERT INTO pii_eval_entity_metrics (run_id, entity_type, tp, fp, fn, precision, recall, f1)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
            """, [(run_id, et, tp, fp, fn, p, r, f1) for (et, tp, fp, fn, p, r, f1) in metrics_rows])

            cur.execute("""
                INSERT INTO pii_eval_overall (run_id, micro_precision, micro_recall, micro_f1)
                VALUES (%s, %s, %s, %s);
            """, (run_id, mp, mr, mf1))
        conn.commit()

    print("Synthetic PII eval complete.")
    print(f"Micro-Precision: {mp:.3f}  Micro-Recall: {mr:.3f}  Micro-F1: {mf1:.3f}")

if __name__ == "__main__":
    main()
