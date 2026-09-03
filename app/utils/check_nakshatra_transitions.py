
from datetime import date
from typing import Dict, List
from app.core.astronomy.nakshatra_transition import NakshatraTransition
from app.schemas.panchangam_data import PanchangamData


def check_nakshatra_transitions_miss(cache: Dict[date, PanchangamData]):
    print("Checking for nakshatra transition miss...")
    total_nakshatra_transitions: List[NakshatraTransition] = []

    sorted_cache = dict(sorted(cache.items()))

    for _, v in sorted_cache.items():
        total_nakshatra_transitions += v.nakshatra_transitions

    print(f"total_nakshatra_transitions: {len(total_nakshatra_transitions)}")

    diffs = []


    for i, nt in enumerate(total_nakshatra_transitions):
        if i + 1 < len(total_nakshatra_transitions):
            curr = nt.nakshatra.id
            next = total_nakshatra_transitions[i+1].nakshatra.id

            diff = (next - curr) % 27
            if abs(diff) > 1:
                diffs.append(nt)
                print(f"diff is not close by for {nt.nakshatra.name} {nt.start_time} -> {nt.end_time} DIFF: {diff}")

    if len(diffs) == 0:
        print("No Nakshatra transitions missed!")
