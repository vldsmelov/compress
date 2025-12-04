from typing import Dict, Any, List
from ..core.config import CONFIG

def _norm_str(s: str) -> str:
    # normalize spaces and quotes
    return str(s).strip().replace('\u00A0', ' ').replace('“', '"').replace('”', '"').replace('«','"').replace('»','"')

def compare_dicts(expected: Dict[str, Any], predicted: Dict[str, Any]) -> (List[Dict[str, Any]], Dict[str, Any]):
    rows = []
    mismatches = 0
    total = 0
    for key in expected.keys():
        total += 1
        e = expected.get(key)
        p = predicted.get(key)
        match = False
        note = ""

        if isinstance(e, (int, float)) and isinstance(p, (int, float)):
            diff = abs(float(e) - float(p))
            match = diff <= CONFIG.numeric_tolerance
            if not match:
                mismatches += 1
                note = f"Δ={diff:.4f}"
        else:
            match = (_norm_str(e) == _norm_str(p))
            if not match:
                mismatches += 1

        rows.append({
            "field": key,
            "expected": e,
            "predicted": p,
            "match": match,
            **({"note": note} if note else {})
        })

    summary = {
        "total_fields": total,
        "matches": total - mismatches,
        "mismatches": mismatches,
        "numeric_tolerance": CONFIG.numeric_tolerance
    }
    return rows, summary
