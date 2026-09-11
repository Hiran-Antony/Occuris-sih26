"""
AIS ingestion and validation service.
"""
import pandas as pd
from datetime import datetime
from typing import List, Dict, Tuple
from app.algorithms.geometry import implied_speed_knots

IMPOSSIBLE_SPEED_THRESHOLD = 45.0   # knots


def parse_ais_csv(filepath: str) -> List[Dict]:
    """Read and parse the AIS CSV file into a list of record dicts."""
    df = pd.read_csv(filepath, parse_dates=["timestamp"])
    df = df.sort_values(["mmsi", "timestamp"]).reset_index(drop=True)
    return df.to_dict("records")


def validate_position(record: Dict) -> Tuple[bool, str]:
    """
    Validate a single AIS position record.
    Returns (is_valid, reason).
    """
    lat = record.get("latitude")
    lon = record.get("longitude")
    spd = record.get("speed")
    ts  = record.get("timestamp")

    if lat is None or lon is None:
        return False, "Missing coordinates"
    if not (-90 <= lat <= 90):
        return False, f"Invalid latitude {lat}"
    if not (-180 <= lon <= 180):
        return False, f"Invalid longitude {lon}"
    if ts is None or pd.isnull(ts):
        return False, "Invalid or missing timestamp"
    if spd is not None and spd < 0:
        return False, f"Negative speed {spd}"
    return True, ""


def flag_impossible_jumps(records: List[Dict]) -> List[Dict]:
    """
    For each vessel, flag records where the implied speed from the previous
    position is physically impossible.  The record is flagged but kept.
    """
    vessel_last: Dict[str, Dict] = {}

    for rec in records:
        mmsi = str(rec["mmsi"])
        prev = vessel_last.get(mmsi)
        if prev is not None:
            spd = implied_speed_knots(
                prev["latitude"], prev["longitude"], prev["timestamp"],
                rec["latitude"], rec["longitude"], rec["timestamp"],
            )
            if spd > IMPOSSIBLE_SPEED_THRESHOLD:
                rec["flagged"] = True
                rec["flag_reason"] = (
                    f"Possible AIS anomaly — implied speed {spd:.0f} kn exceeds physical limit"
                )
        vessel_last[mmsi] = rec

    return records


def group_by_vessel(records: List[Dict]) -> Dict[str, List[Dict]]:
    """Group validated records by MMSI."""
    groups: Dict[str, List[Dict]] = {}
    for rec in records:
        mmsi = str(rec["mmsi"])
        groups.setdefault(mmsi, []).append(rec)
    return groups
