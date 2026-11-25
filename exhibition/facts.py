"""把来源主张整理成可追溯事实，并查找同边界替换件。"""
from __future__ import annotations

from typing import Any

from .ledger import EditorialLedger, match_claim


def _fmt_numbers(claim) -> dict[str, Any]:
    pp = None
    if claim.baseline is not None and claim.current is not None:
        pp = claim.current - claim.baseline
    return {
        "baseline": claim.baseline,
        "current": claim.current,
        "delta": claim.delta if claim.delta is not None else abs(pp) if pp is not None else None,
        "delta_unit": claim.delta_unit,
        "delta_pp": pp,
        "relative_pct": claim.relative_pct,
        "direction": claim.direction,
    }


def build_facts(ledger: EditorialLedger) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for source_id, claims in ledger.source_claims.items():
        row = ledger.sources[source_id]
        for claim in claims:
            if claim.claim_type != "measurement":
                continue
            channels = {}
            for channel in ("现场中文", "现场英文", "扫码内页"):
                ok, reason = ledger.usable(source_id, channel)
                channels[channel] = {"usable": ok, "reason": reason}
            facts.append(
                {
                    "fact_id": f"F-{claim.claim_id}",
                    "source_id": source_id,
                    "claim_id": claim.claim_id,
                    "trial": row.get("trial") or claim.trial,
                    "audience": row.get("audience"),
                    "lang": claim.lang,
                    "metric": claim.metric,
                    "subject": claim.subject,
                    "scope": claim.scope,
                    **_fmt_numbers(claim),
                    "modality": claim.modality,
                    "measured": claim.measured,
                    "comparator": claim.comparator,
                    "time_phrase": claim.time_phrase,
                    "provisional": claim.provisional,
                    "quote": row["text"],
                    "channels": channels,
                }
            )
    return facts


def coverage_signature(fact_or_claim: dict[str, Any] | Any) -> tuple:
    if isinstance(fact_or_claim, dict):
        metric = fact_or_claim.get("metric")
        scope = fact_or_claim.get("scope", {})
        baseline = fact_or_claim.get("baseline")
        current = fact_or_claim.get("current")
        delta = fact_or_claim.get("delta")
        unit = fact_or_claim.get("delta_unit")
    else:
        metric = fact_or_claim.metric
        scope = fact_or_claim.scope
        baseline = fact_or_claim.baseline
        current = fact_or_claim.current
        delta = fact_or_claim.delta
        unit = fact_or_claim.delta_unit
    return (
        metric,
        scope.get("scale"),
        scope.get("line"),
        scope.get("shift"),
        scope.get("aggregation"),
        scope.get("phase"),
        baseline,
        current,
        delta,
        unit,
    )


def find_equivalent_sources(
    ledger: EditorialLedger, source_id: str, channel: str | None = None
) -> list[dict[str, Any]]:
    """寻找同试验、同覆盖边界、同数值且授权有效的同义/复算替换件。"""
    original_row = ledger.sources[source_id]
    original_claims = [c for c in ledger.source_claims[source_id] if c.claim_type == "measurement"]
    results: list[dict[str, Any]] = []
    for candidate_id, candidate_claims in ledger.source_claims.items():
        if candidate_id == source_id:
            continue
        candidate_row = ledger.sources[candidate_id]
        for original in original_claims:
            best = None
            for candidate in candidate_claims:
                result = match_claim(original, candidate)
                same_trial = original_row.get("trial") == candidate_row.get("trial") and bool(original_row.get("trial"))
                related = source_id in [x for x in candidate_row.get("relates", "").split("|") if x]
                exact_boundary = coverage_signature(original)[:6] == coverage_signature(candidate)[:6]
                equivalent = result["match"] and not result["partial"] and (same_trial or related) and exact_boundary
                authorized = True
                reason = "未按渠道校验"
                if channel:
                    authorized, reason = ledger.usable(candidate_id, channel)
                item = {
                    "candidate_source_id": candidate_id,
                    "candidate_claim_id": candidate.claim_id,
                    "same_trial": same_trial,
                    "explicitly_relates": related,
                    "exact_boundary": exact_boundary,
                    "authorized_for_channel": authorized,
                    "authorization_reason": reason,
                    "equivalent": equivalent and authorized,
                    "quote": candidate_row["text"],
                    "trial": candidate_row.get("trial"),
                    "match": result,
                }
                if best is None or item["match"]["score"] > best["match"]["score"]:
                    best = item
            if best:
                results.append(best)
    results.sort(key=lambda item: (item["equivalent"], item["match"]["score"]), reverse=True)
    return results


def trial_independence(facts: list[dict[str, Any]], source_ids: list[str]) -> dict[str, Any]:
    selected = [fact for fact in facts if fact["source_id"] in set(source_ids)]
    trials = sorted({fact["trial"] for fact in selected if fact.get("trial")})
    fingerprints = {coverage_signature(fact) for fact in selected}
    return {
        "source_ids": list(source_ids),
        "trial_ids": trials,
        "independent_trial_count": len(trials),
        "distinct_coverage_count": len(fingerprints),
        "is_independent_validation": len(trials) >= 2,
        "warning": "同一试验的初稿、复算或不同短写只能记为一次印证" if len(trials) < 2 else None,
    }
