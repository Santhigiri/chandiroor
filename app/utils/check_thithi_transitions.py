from datetime import date
from typing import Dict, List
from app.core.astronomy.thithi_transition import ThithiTransition
from app.shared.schemas.panchangam_data import PanchangamData


def check_thithi_transitions_miss(cache: Dict[date, PanchangamData]):
    print("Checking for thithi transition miss...")
    total_thithi_transitions: List[ThithiTransition] = []

    sorted_cache = dict(sorted(cache.items()))

    for _, v in sorted_cache.items():
        total_thithi_transitions += v.thithi_transitions

    print(f"total_thithi_transitions: {len(total_thithi_transitions)}")

    diffs = []

    for i, nt in enumerate(total_thithi_transitions):
        if i + 1 < len(total_thithi_transitions):
            curr = nt.thithi.id
            next = total_thithi_transitions[i+1].thithi.id

            diff = (next - curr) % 30
            if abs(diff) > 1:
                diffs.append(nt)
                print(f"diff is not close by for {nt.thithi.en} {nt.start_time} -> {nt.end_time} DIFF: {diff}")



    if len(diffs) == 0:
        print("No Thithi transitions missed!")

