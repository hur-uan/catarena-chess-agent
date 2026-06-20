#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Tuple, Dict, List
import json
import os

# Standard IMP table (WBF) from raw point difference
IMP_THRESHOLDS = [
    (20, 1), (50, 2), (90, 3), (130, 4), (170, 5), (220, 6), (270, 7), (320, 8),
    (370, 9), (430, 10), (500, 11), (600, 12), (750, 13), (900, 14), (1100, 15),
    (1300, 16), (1500, 17), (1750, 18), (2000, 19), (2250, 20), (2500, 21),
    (3000, 22), (3500, 23)
]

def points_to_imp(points_diff: int) -> int:
    """Convert raw points difference to IMPs (signed).
    Uses standard thresholds up to 4000+ -> 24.
    """
    sign = 1 if points_diff >= 0 else -1
    x = abs(points_diff)
    imp = 0
    for threshold, val in IMP_THRESHOLDS:
        if x < threshold:
            imp = val - 1  # previous bucket
            break
    else:
        # 3500 ≤ x < 4000 -> 23; 4000+ -> 24
        imp = 23 if x < 4000 else 24
        return imp * sign

    # Adjust because we used previous bucket
    # Find exact val for x
    prev_val = 0
    for threshold, val in IMP_THRESHOLDS:
        if x < threshold:
            return prev_val * sign
        prev_val = val
    return 24 * sign

# ===================== WBF VP table support =====================

_VP_TABLES: Dict[str, List[Tuple[int, float]]] = {}

def _load_wbf_vp_tables():
    """Load WBF VP tables from configs/wbf_vp_tables.json if present.
    The JSON format:
    {
      "12": [ [0,10.0], [1,10.5], [2,11.0], ..., [20,20.0] ]
    }
    The list is interpreted as: for IMP difference >= threshold, VP for the winner is that value.
    """
    global _VP_TABLES
    here = os.path.dirname(__file__)
    path = os.path.join(here, 'configs', 'wbf_vp_tables.json')
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # store as boards->list of (imp_threshold, vp_for_winner)
            _VP_TABLES = {str(k): [(int(th), float(vp)) for th, vp in v] for k, v in data.items()}
        except Exception:
            _VP_TABLES = {}

def imp_to_vp20(imp_diff: int, boards: int) -> Tuple[float, float]:
    """Map IMP diff to 20-0 VP pair using WBF table if available, else fallback to linear."""
    if not _VP_TABLES:
        _load_wbf_vp_tables()
    table = _VP_TABLES.get(str(boards))
    if table:
        x = abs(int(imp_diff))
        vp_winner = 10.0
        for th, vp in table:
            if x >= th:
                vp_winner = vp
            else:
                break
        if imp_diff > 0:
            return round(vp_winner, 2), round(20.0 - vp_winner, 2)
        elif imp_diff < 0:
            return round(20.0 - vp_winner, 2), round(vp_winner, 2)
        else:
            return 10.0, 10.0
    # Fallback linear quantized
    X = 20.0 if boards == 12 else (12.0 if boards <= 8 else (20.0 if boards <= 16 else (27.0 if boards <= 24 else max(30.0, boards * 1.2))))
    vp_a = 10.0 + max(min(imp_diff, X), -X) * (10.0 / X)
    vp_a = round(max(0.0, min(20.0, vp_a)) * 2.0) / 2.0
    vp_b = 20.0 - vp_a
    return round(vp_a, 2), round(vp_b, 2)
