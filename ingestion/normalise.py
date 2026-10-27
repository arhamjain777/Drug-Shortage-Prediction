"""openFDA drug-shortage normalisation + idempotent upsert planning (pure functions).

Field names: status, update_date, change_date, discontinued_date, initial_posting_date and
openfda.* are confirmed in openFDA's official field reference. generic_name, company_name,
availability, shortage_reason, presentation, dosage_form, strength, therapeutic_category,
related_info, update_type, package_ndc come from secondary descriptions of the same API and
MUST be re-checked against a live response (see docs/data_sources.md). Missing fields are tolerated.
"""
from __future__ import annotations
import hashlib, json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping, Optional


def parse_date(s) -> Optional[str]:
    if not s or not isinstance(s, str):
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(s.strip(), fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _txt(v) -> Optional[str]:
    if isinstance(v, list):
        v = v[0] if v else None
    if v is None:
        return None
    v = " ".join(str(v).split())
    return v or None


def _lst(v) -> list:
    if v is None:
        return []
    if not isinstance(v, list):
        v = [v]
    return [x for x in (_txt(i) for i in v) if x]


def _hash(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def normalise_record(raw: Mapping) -> dict:
    """Return a normalised dict, or {'rejected': reason} if unusable."""
    ofda = raw.get("openfda") or {}
    generic = _txt(raw.get("generic_name")) or _txt(ofda.get("generic_name"))
    if not generic:
        return {"rejected": "missing generic_name"}
    rec = {
        "generic_name": generic,
        "company_name": _txt(raw.get("company_name")),
        "status": _txt(raw.get("status")),
        "availability": _txt(raw.get("availability")),
        "shortage_reason": _txt(raw.get("shortage_reason")),
        "presentation": _txt(raw.get("presentation")),
        "dosage_form": _txt(raw.get("dosage_form")) or _txt(ofda.get("dosage_form")),
        "strength": _lst(raw.get("strength")),
        "therapeutic_category": _lst(raw.get("therapeutic_category")),
        "related_info": _txt(raw.get("related_info")),
        "update_type": _txt(raw.get("update_type")),
        "initial_posting_date": parse_date(raw.get("initial_posting_date")),
        "update_date": parse_date(raw.get("update_date")),
        "change_date": parse_date(raw.get("change_date")),
        "discontinued_date": parse_date(raw.get("discontinued_date")),
        "brand_names": _lst(ofda.get("brand_name")),
        "package_ndc": sorted(_lst(raw.get("package_ndc")) or _lst(ofda.get("package_ndc"))),
        "rxcui": _lst(ofda.get("rxcui")),
    }
    # The API exposes no documented stable record id, so we derive a deterministic key
    # from identity fields. If FDA edits one of these, it appears as a new record (documented limit).
    identity = {k: rec[k] for k in ("generic_name", "company_name", "presentation",
                                    "initial_posting_date", "package_ndc")}
    rec["source_key"] = _hash(identity)
    rec["content_hash"] = _hash(raw)      # changes whenever ANY source field changes
    rec["raw"] = dict(raw)                # kept for traceability
    return rec


@dataclass
class UpsertPlan:
    inserts: list = field(default_factory=list)
    updates: list = field(default_factory=list)
    unchanged: int = 0
    duplicates: int = 0
    rejected: list = field(default_factory=list)


def plan_upsert(existing: Mapping[str, str], raw_records) -> UpsertPlan:
    """existing: {source_key: content_hash} already in DB. Re-running with the same input
    yields zero inserts/updates (idempotent)."""
    plan, best = UpsertPlan(), {}
    for raw in raw_records:
        n = normalise_record(raw)
        if "rejected" in n:
            plan.rejected.append(n["rejected"])
            continue
        k = n["source_key"]
        if k in best:
            plan.duplicates += 1
            if (n["update_date"] or "") < (best[k]["update_date"] or ""):
                continue
        best[k] = n
    for k, n in best.items():
        if k not in existing:
            plan.inserts.append(n)
        elif existing[k] != n["content_hash"]:
            plan.updates.append(n)
        else:
            plan.unchanged += 1
    return plan
