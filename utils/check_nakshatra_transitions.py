
from datetime import date
from typing import Dict, List
from core.astronomy.nakshatra_transition import NakshatraTransition
from utils.santhigiri_events import PanchangamData


def check_nakshatra_transitions_miss(cache: Dict[date, PanchangamData]):
    total_nakshatra_transitions: List[NakshatraTransition] = []

    sorted_cache = dict(sorted(cache.items()))

    for _, v in sorted_cache.items():
        total_nakshatra_transitions += v.nakshatra_transitions

    print(f"total_nakshatra_transitions: {len(total_nakshatra_transitions)}")

    for i, nt in enumerate(total_nakshatra_transitions):
        if i + 1 < len(total_nakshatra_transitions):
            curr = nt.nakshatra.id
            next = total_nakshatra_transitions[i+1].nakshatra.id

            diff = (next - curr) % 27
            if abs(diff) > 1:
                print(f"diff is not close by for {nt.nakshatra.en} {nt.start_time} -> {nt.end_time} DIFF: {diff}")

