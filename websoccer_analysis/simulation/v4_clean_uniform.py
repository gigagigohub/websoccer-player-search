from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional


UNIFORM_SLOT_WEIGHT = 0.57938903
UNIFORM_KEY_WEIGHT = 0.03754174

_REQUIRED_SLOTS = set(range(1, 12))
_VALID_KEY_NOS = set(range(1, 5))


@dataclass(frozen=True)
class SlotUniformContribution:
    slot_no: int
    player_id: int
    player_point: float
    slot_expected_point: float
    adjusted_point: float
    weight: float
    contribution: float
    is_keyslot: bool


@dataclass(frozen=True)
class KeyslotUniformContribution:
    key_no: int
    slot_no: int
    player_id: int
    player_point: float
    slot_expected_point: float
    adjusted_point: float
    weight: float
    contribution: float


@dataclass(frozen=True)
class TeamUniformIndexResult:
    total_index: float
    formation_contribution: float
    starting11_point_sum: float
    starting11_adjusted_sum: float
    starting11_contribution: float
    keyslot_point_sum: float
    keyslot_adjusted_sum: float
    keyslot_contribution: float
    coach_contribution: float
    slot_breakdown: List[SlotUniformContribution]
    keyslot_breakdown: List[KeyslotUniformContribution]


def _as_float(value: object, field_name: str) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be numeric: {value!r}") from exc


def _validate_required_slots(slot_player_ids: Mapping[int, int]) -> None:
    missing = sorted(_REQUIRED_SLOTS - set(slot_player_ids.keys()))
    if missing:
        raise ValueError(f"slot_player_ids is missing required slots: {missing}")


def _player_point(player_id: int, player_point_by_id: Mapping[int, float]) -> float:
    if player_id not in player_point_by_id:
        raise ValueError(f"player_point_by_id is missing player_id: {player_id}")
    return _as_float(player_point_by_id[player_id], f"player_point_by_id[{player_id}]")


def _valid_key_slots(
    formation_id: int,
    formation_key_slots: Mapping[int, Mapping[int, int]],
) -> Dict[int, int]:
    raw_key_slots = formation_key_slots.get(formation_id, {})
    valid_key_slots: Dict[int, int] = {}
    for key_no, slot_no in raw_key_slots.items():
        if key_no not in _VALID_KEY_NOS:
            continue
        if slot_no not in _REQUIRED_SLOTS:
            raise ValueError(
                f"formation_key_slots[{formation_id}][{key_no}] has invalid slot: {slot_no}"
            )
        valid_key_slots[int(key_no)] = int(slot_no)
    return valid_key_slots


def _formation_slot_expected_point(
    formation_id: int,
    slot_no: int,
    formation_slot_expected: Optional[Mapping[object, object]],
) -> float:
    if not formation_slot_expected:
        return 0.0

    flat_key = f"{formation_id}:{slot_no}"
    if flat_key in formation_slot_expected:
        return _as_float(formation_slot_expected[flat_key], f"formation_slot_expected[{flat_key}]")

    nested = formation_slot_expected.get(formation_id)
    if nested is None:
        nested = formation_slot_expected.get(str(formation_id))
    if isinstance(nested, Mapping):
        if slot_no in nested:
            return _as_float(nested[slot_no], f"formation_slot_expected[{formation_id}][{slot_no}]")
        if str(slot_no) in nested:
            return _as_float(nested[str(slot_no)], f"formation_slot_expected[{formation_id}][{slot_no}]")
    return 0.0


def calc_team_v4_clean_uniform_index(
    *,
    formation_id: int,
    headcoach_id: Optional[int],
    slot_player_ids: Mapping[int, int],
    player_point_by_id: Mapping[int, float],
    formation_key_slots: Mapping[int, Mapping[int, int]],
    formation_power: Mapping[int, float],
    formation_slot_expected: Optional[Mapping[object, object]] = None,
    coach_power_by_id: Optional[Mapping[int, float]] = None,
    include_coach_power: bool = False,
) -> TeamUniformIndexResult:
    """Calculate the single-team v4_clean_uniform index.

    This is a side-effect-free calculation. It does not read databases,
    files, APIs, match results, or post-match headcoach_pts.
    """

    _validate_required_slots(slot_player_ids)
    valid_key_slots = _valid_key_slots(formation_id, formation_key_slots)
    key_slot_numbers = set(valid_key_slots.values())

    slot_breakdown: List[SlotUniformContribution] = []
    starting11_point_sum = 0.0
    starting11_adjusted_sum = 0.0

    for slot_no in range(1, 12):
        player_id = int(slot_player_ids[slot_no])
        player_point = _player_point(player_id, player_point_by_id)
        slot_expected = _formation_slot_expected_point(formation_id, slot_no, formation_slot_expected)
        adjusted_point = player_point - slot_expected
        contribution = UNIFORM_SLOT_WEIGHT * adjusted_point
        starting11_point_sum += player_point
        starting11_adjusted_sum += adjusted_point
        slot_breakdown.append(
            SlotUniformContribution(
                slot_no=slot_no,
                player_id=player_id,
                player_point=player_point,
                slot_expected_point=slot_expected,
                adjusted_point=adjusted_point,
                weight=UNIFORM_SLOT_WEIGHT,
                contribution=contribution,
                is_keyslot=slot_no in key_slot_numbers,
            )
        )

    starting11_contribution = UNIFORM_SLOT_WEIGHT * starting11_adjusted_sum

    keyslot_breakdown: List[KeyslotUniformContribution] = []
    keyslot_point_sum = 0.0
    keyslot_adjusted_sum = 0.0

    for key_no in sorted(valid_key_slots):
        slot_no = valid_key_slots[key_no]
        player_id = int(slot_player_ids[slot_no])
        player_point = _player_point(player_id, player_point_by_id)
        slot_expected = _formation_slot_expected_point(formation_id, slot_no, formation_slot_expected)
        adjusted_point = player_point - slot_expected
        contribution = UNIFORM_KEY_WEIGHT * adjusted_point
        keyslot_point_sum += player_point
        keyslot_adjusted_sum += adjusted_point
        keyslot_breakdown.append(
            KeyslotUniformContribution(
                key_no=key_no,
                slot_no=slot_no,
                player_id=player_id,
                player_point=player_point,
                slot_expected_point=slot_expected,
                adjusted_point=adjusted_point,
                weight=UNIFORM_KEY_WEIGHT,
                contribution=contribution,
            )
        )

    keyslot_contribution = UNIFORM_KEY_WEIGHT * keyslot_adjusted_sum
    formation_contribution = _as_float(
        formation_power.get(formation_id, 0.0),
        f"formation_power[{formation_id}]",
    )

    if include_coach_power and coach_power_by_id is not None and headcoach_id is not None:
        coach_contribution = _as_float(
            coach_power_by_id.get(headcoach_id, 0.0),
            f"coach_power_by_id[{headcoach_id}]",
        )
    else:
        coach_contribution = 0.0

    total_index = (
        formation_contribution
        + starting11_contribution
        + keyslot_contribution
        + coach_contribution
    )

    return TeamUniformIndexResult(
        total_index=total_index,
        formation_contribution=formation_contribution,
        starting11_point_sum=starting11_point_sum,
        starting11_adjusted_sum=starting11_adjusted_sum,
        starting11_contribution=starting11_contribution,
        keyslot_point_sum=keyslot_point_sum,
        keyslot_adjusted_sum=keyslot_adjusted_sum,
        keyslot_contribution=keyslot_contribution,
        coach_contribution=coach_contribution,
        slot_breakdown=slot_breakdown,
        keyslot_breakdown=keyslot_breakdown,
    )
