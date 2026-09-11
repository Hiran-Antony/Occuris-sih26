"""
Occuris Demo AIS Generator
Generates realistic synthetic AIS data for the Bay of Bengal demo scenario.

Demo scenario: 2024-01-15, 06:00 – 22:00 UTC
Incident time: 18:40 UTC
Estimated release window: 12:00 – 16:00 UTC
Estimated origin: ~86°E, 13°N

Run: python scripts/generate_ais.py
Output: backend/data/ais/demo_ais.csv
"""
import csv
import math
import random
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime, timedelta

random.seed(42)

# ── Demo scenario constants ─────────────────────────────────────────────────
DEMO_START   = datetime(2024, 1, 15, 6, 0, 0)
INCIDENT_TIME = datetime(2024, 1, 15, 18, 40, 0)
RELEASE_START = datetime(2024, 1, 15, 12, 0, 0)
RELEASE_END   = datetime(2024, 1, 15, 16, 0, 0)

# Region bounds
BOB_WEST, BOB_EAST = 80.0, 100.0
BOB_SOUTH, BOB_NORTH = 5.0, 22.0

# Gateway entry/exit reference coordinates
GATEWAY_ENTRY = {
    "A": lambda: (random.uniform(9, 20), 79.8),
    "B": lambda: (22.2, random.uniform(82, 98)),
    "C": lambda: (4.8, random.uniform(82, 98)),
    "D": lambda: (random.uniform(8, 19), 100.2),
}
GATEWAY_EXIT = {
    "A": lambda: (random.uniform(9, 20), 79.8),
    "B": lambda: (22.2, random.uniform(82, 98)),
    "C": lambda: (4.8, random.uniform(82, 98)),
    "D": lambda: (random.uniform(8, 19), 100.2),
}
GATEWAY_INSIDE = {
    "A": lambda la, lo: (la, 80.3),
    "B": lambda la, lo: (21.7, lo),
    "C": lambda la, lo: (5.3, lo),
    "D": lambda la, lo: (la, 99.7),
}

VESSEL_SPEEDS = {"tanker": 10.0, "cargo": 12.0, "fishing": 6.0, "passenger": 16.0}
VESSEL_NAMES = {
    "tanker":    ["OCEAN CARRIER", "GULF WAVE", "DELTA TIDE", "INDIAN STAR", "PETROMAR"],
    "cargo":     ["EASTERN STAR", "BAY EXPRESS", "SEAWIND", "CORAL TRADER", "MONSOON"],
    "fishing":   ["ANANDA", "SAGARA", "NILUFAR", "DEEPA", "MATSYA"],
    "passenger": ["FERRY QUEEN", "ANDAMAN JOY", "BAY LINK", "ISLAND STAR"],
}
FLAGS = ["IN", "BD", "MY", "SG", "PH", "LK", "MM"]


def haversine_nm(lat1, lon1, lat2, lon2):
    R = 3440.065
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.asin(math.sqrt(max(0, a)))


def bearing(lat1, lon1, lat2, lon2):
    lat1, lat2 = math.radians(lat1), math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    x = math.sin(dlon)*math.cos(lat2)
    y = math.cos(lat1)*math.sin(lat2) - math.sin(lat1)*math.cos(lat2)*math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def interpolate_pos(lat1, lon1, lat2, lon2, frac):
    return lat1 + (lat2 - lat1)*frac, lon1 + (lon2 - lon1)*frac


def make_trajectory(
    mmsi, vessel_type, vessel_name, flag,
    entry_gw, exit_gw,
    entry_time,
    waypoints,         # list of (lat, lon, speed_override_or_None)
    gap_windows=None,  # list of (start_dt, end_dt) — positions removed in these windows
):
    """
    Generate AIS positions along a sequence of waypoints.
    Each segment travels from waypoint[i] to waypoint[i+1].
    """
    gap_windows = gap_windows or []
    records = []

    for seg in range(len(waypoints) - 1):
        lat_s, lon_s, spd_s = waypoints[seg]
        lat_e, lon_e, spd_e = waypoints[seg + 1]
        spd = spd_s or VESSEL_SPEEDS.get(vessel_type, 10.0)
        dist = haversine_nm(lat_s, lon_s, lat_e, lon_e)
        if dist == 0:
            continue
        seg_hours = dist / spd
        n_pts = max(2, int(seg_hours * 4))  # one point every ~15 min

        for i in range(n_pts):
            frac = i / (n_pts - 1)
            t = entry_time + timedelta(hours=_elapsed(waypoints, seg, frac, vessel_type))
            lat = lat_s + (lat_e - lat_s)*frac + random.gauss(0, 0.06)
            lon = lon_s + (lon_e - lon_s)*frac + random.gauss(0, 0.06)
            spd_val = spd + random.gauss(0, 0.4)
            spd_val = max(0.1, spd_val)
            crs = bearing(lat_s, lon_s, lat_e, lon_e) + random.gauss(0, 2)
            crs = crs % 360

            # Skip records inside AIS gap windows
            in_gap = any(g[0] <= t <= g[1] for g in gap_windows)
            if in_gap:
                continue

            records.append({
                "mmsi": mmsi,
                "timestamp": t.strftime("%Y-%m-%dT%H:%M:%S"),
                "latitude": round(lat, 5),
                "longitude": round(lon, 5),
                "speed": round(spd_val, 1),
                "course": round(crs, 1),
                "vessel_type": vessel_type,
                "heading": round(crs + random.gauss(0, 3), 1),
                "nav_status": "underway",
                "name": vessel_name,
                "flag": flag,
            })

    return records


def _elapsed(waypoints, seg_idx, frac, vessel_type):
    """Total hours from start to current position."""
    total = 0.0
    for i in range(seg_idx):
        lat_s, lon_s, spd_s = waypoints[i]
        lat_e, lon_e, spd_e = waypoints[i+1]
        spd = spd_s or VESSEL_SPEEDS.get(vessel_type, 10.0)
        dist = haversine_nm(lat_s, lon_s, lat_e, lon_e)
        total += dist / spd
    lat_s, lon_s, spd_s = waypoints[seg_idx]
    lat_e, lon_e, spd_e = waypoints[seg_idx+1]
    spd = spd_s or VESSEL_SPEEDS.get(vessel_type, 10.0)
    dist = haversine_nm(lat_s, lon_s, lat_e, lon_e)
    total += (dist / spd) * frac
    return total


# ─────────────────────────────────────────────────────────────────────────────
# VESSEL DEFINITIONS
# ─────────────────────────────────────────────────────────────────────────────

def make_all_vessels():
    records = []

    # ─── PRIMARY SUSPECT (HIGH PRIORITY) ────────────────────────────────────
    # MMSI 419000042 — Tanker, enters Gate A, AIS gap covers release window,
    # route passes directly through estimated origin zone (86°E, 13°N)
    records += make_trajectory(
        mmsi="419000042", vessel_type="tanker",
        vessel_name="OCEAN CARRIER I", flag="IN",
        entry_gw="A", exit_gw="D",
        entry_time=datetime(2024, 1, 15, 6, 30, 0),
        waypoints=[
            (15.2, 79.8, 10.0),   # Gate A entry (outside)
            (14.8, 80.5, 10.0),   # enters region
            (14.2, 83.0, 10.0),   # normal movement
            (13.8, 85.0, 4.5),    # slowdown begins (weather)
            (13.5, 85.8, 4.0),    # continued slowdown — 10:30-12:00 (will be explained)
            (13.2, 86.0, 9.5),    # near ORIGIN ZONE → AIS GAP STARTS 12:30
            # ← gap 12:30 – 14:45 (inside release window) ←
            (12.8, 87.5, 9.5),    # AIS RESUMES — has moved through origin zone
            (12.5, 89.0, 10.5),   # route deviation detected
            (12.0, 92.0, 10.0),   # continuing east
            (11.5, 96.0, 10.0),
            (11.2, 100.2, 10.0),  # Gate D exit (outside)
        ],
        gap_windows=[
            (datetime(2024, 1, 15, 12, 30, 0), datetime(2024, 1, 15, 14, 45, 0)),
        ],
    )

    # ─── SECONDARY CANDIDATE (MEDIUM PRIORITY) ──────────────────────────────
    # MMSI 419000040 — Cargo, route deviation near origin, no AIS gap
    records += make_trajectory(
        mmsi="419000040", vessel_type="cargo",
        vessel_name="EASTERN STAR", flag="SG",
        entry_gw="A", exit_gw="D",
        entry_time=datetime(2024, 1, 15, 8, 0, 0),
        waypoints=[
            (14.0, 79.8, 12.0),
            (13.5, 81.0, 12.0),
            (13.0, 84.0, 12.0),
            (13.2, 87.0, 5.0),   # deviates northward toward origin zone
            (13.8, 89.0, 12.0),  # unexplained deviation
            (13.5, 92.0, 12.0),
            (13.0, 96.0, 12.0),
            (12.8, 100.2, 12.0),
        ],
    )

    # ─── THIRD CANDIDATE (LOW PRIORITY) ─────────────────────────────────────
    # MMSI 419000041 — Tanker, passes near origin zone but weather explains slowdown
    records += make_trajectory(
        mmsi="419000041", vessel_type="tanker",
        vessel_name="GULF WAVE", flag="MY",
        entry_gw="B", exit_gw="D",
        entry_time=datetime(2024, 1, 15, 7, 0, 0),
        waypoints=[
            (22.2, 88.0, 10.0),
            (21.5, 88.5, 10.0),
            (19.0, 89.0, 10.0),
            (16.0, 90.0, 4.5),  # weather slowdown (10:30–12:30) — will be EXPLAINED
            (14.5, 91.0, 4.0),
            (12.5, 93.0, 10.0),
            (11.0, 97.0, 10.0),
            (10.5, 100.2, 10.0),
        ],
    )

    # ─── VESSELS WITH WEATHER-EXPLAINED SLOWDOWNS ───────────────────────────
    records += make_trajectory(
        mmsi="419000036", vessel_type="tanker",
        vessel_name="DELTA TIDE", flag="IN",
        entry_gw="A", exit_gw="C",
        entry_time=datetime(2024, 1, 15, 7, 30, 0),
        waypoints=[
            (12.0, 79.8, 10.0),
            (11.5, 81.0, 10.0),
            (10.5, 84.0, 4.0),   # weather slowdown
            (9.5, 86.0, 4.5),
            (9.0, 89.0, 10.0),
            (8.5, 92.0, 10.0),
            (7.0, 94.0, 10.0),
            (6.0, 95.0, 4.8),
        ],
    )

    records += make_trajectory(
        mmsi="419000037", vessel_type="cargo",
        vessel_name="BAY EXPRESS", flag="BD",
        entry_gw="B", exit_gw="C",
        entry_time=datetime(2024, 1, 15, 8, 30, 0),
        waypoints=[
            (22.2, 86.0, 12.0),
            (20.0, 87.0, 12.0),
            (17.0, 88.0, 5.0),   # weather slowdown
            (14.0, 89.0, 5.0),
            (11.0, 90.0, 12.0),
            (8.0, 90.5, 12.0),
            (4.8, 91.0, 12.0),
        ],
    )

    # ─── VESSELS WITH OPERATIONAL STOPS ─────────────────────────────────────
    records += make_trajectory(
        mmsi="419000038", vessel_type="fishing",
        vessel_name="ANANDA", flag="IN",
        entry_gw="A", exit_gw="C",
        entry_time=datetime(2024, 1, 15, 6, 0, 0),
        waypoints=[
            (10.0, 79.8, 6.0),
            (9.5, 81.0, 6.0),
            (9.0, 83.0, 0.4),    # operational stop (fishing)
            (8.8, 83.2, 0.3),
            (8.7, 83.5, 0.2),
            (8.6, 83.8, 0.2),
            (8.5, 84.0, 6.0),
            (7.5, 87.0, 6.0),
            (6.0, 90.0, 6.0),
            (4.8, 92.0, 6.0),
        ],
    )

    records += make_trajectory(
        mmsi="419000039", vessel_type="tanker",
        vessel_name="INDIAN STAR", flag="IN",
        entry_gw="C", exit_gw="D",
        entry_time=datetime(2024, 1, 15, 9, 0, 0),
        waypoints=[
            (4.8, 87.0, 10.0),
            (5.5, 88.0, 10.0),
            (7.0, 89.0, 0.5),    # operational stop
            (7.2, 89.2, 0.3),
            (7.5, 89.5, 10.0),
            (9.0, 92.0, 10.0),
            (10.5, 96.0, 10.0),
            (11.0, 100.2, 10.0),
        ],
    )

    # ─── AIS GAP FAR FROM INCIDENT (should rank LOW) ────────────────────────
    records += make_trajectory(
        mmsi="419000043", vessel_type="cargo",
        vessel_name="SEAWIND", flag="PH",
        entry_gw="B", exit_gw="C",
        entry_time=datetime(2024, 1, 15, 9, 30, 0),
        waypoints=[
            (22.2, 96.0, 12.0),
            (20.0, 96.5, 12.0),
            (17.0, 97.0, 12.0),  # AIS gap here (far east, away from origin zone)
            (14.0, 97.5, 12.0),
            (11.0, 97.0, 12.0),
            (8.0, 96.5, 12.0),
            (4.8, 96.0, 12.0),
        ],
        gap_windows=[
            (datetime(2024, 1, 15, 13, 0, 0), datetime(2024, 1, 15, 14, 30, 0)),
        ],
    )

    # ─── EARLY-EXIT VESSELS (exit before release window, should be filtered) ─
    for i, (entry_gw, exit_gw, vtype, name, flag, lat_s, lon_s, lat_e, lon_e) in enumerate([
        ("A", "C", "fishing",   "SAGARA",     "IN",  9.0,  79.8, 4.8, 84.0),
        ("B", "A", "cargo",     "CORAL TRADER","MY", 22.2, 85.0, 9.0, 79.8),
        ("C", "A", "tanker",    "PETROMAR",   "LK",  4.8,  82.0, 9.0, 79.8),
        ("D", "C", "fishing",   "NILUFAR",    "BD", 12.0, 100.2, 4.8, 91.0),
        ("A", "D", "passenger", "FERRY QUEEN","IN", 17.0,  79.8,16.0,100.2),
    ]):
        records += make_trajectory(
            mmsi=f"41900004{8+i}", vessel_type=vtype,
            vessel_name=name, flag=flag,
            entry_gw=entry_gw, exit_gw=exit_gw,
            entry_time=datetime(2024, 1, 15, 6, 0, 0),
            waypoints=[
                (lat_s, lon_s, VESSEL_SPEEDS.get(vtype, 10.0)),
                ((lat_s+lat_e)/2, (lon_s+lon_e)/2, VESSEL_SPEEDS.get(vtype, 10.0)),
                (lat_e, lon_e, VESSEL_SPEEDS.get(vtype, 10.0)),
            ],
        )

    # ─── NORMAL VESSELS (35) ────────────────────────────────────────────────
    routes = [
        ("A","D"), ("A","C"), ("A","B"), ("B","C"), ("B","D"),
        ("C","D"), ("C","A"), ("D","A"), ("D","B"), ("D","C"),
        ("A","D"), ("B","C"), ("C","D"), ("A","C"), ("D","A"),
        ("B","D"), ("C","B"), ("A","D"), ("B","C"), ("D","C"),
        ("A","B"), ("D","A"), ("C","D"), ("B","A"), ("A","C"),
        ("D","B"), ("C","A"), ("B","D"), ("A","D"), ("D","C"),
        ("B","C"), ("C","D"), ("A","B"), ("D","A"), ("B","D"),
    ]
    vtypes = (["tanker"]*8 + ["cargo"]*12 + ["fishing"]*10 + ["passenger"]*5)
    random.shuffle(vtypes)

    for idx, ((egw, xgw), vtype) in enumerate(zip(routes, vtypes)):
        mmsi = f"4190001{idx+1:02d}"
        spd = VESSEL_SPEEDS[vtype]
        names_list = VESSEL_NAMES[vtype]
        vname = f"{random.choice(names_list)} {idx+1}"
        flag = random.choice(FLAGS)
        entry_hr = random.uniform(6, 12)
        entry_t = DEMO_START + timedelta(hours=entry_hr)

        # Random entry/exit positions
        e_lat, e_lon = GATEWAY_ENTRY[egw]()
        x_lat, x_lon = GATEWAY_EXIT[xgw]()
        mid_lat = (e_lat + x_lat)/2 + random.gauss(0, 1.5)
        mid_lon = (e_lon + x_lon)/2 + random.gauss(0, 1.5)

        records += make_trajectory(
            mmsi=mmsi, vessel_type=vtype,
            vessel_name=vname, flag=flag,
            entry_gw=egw, exit_gw=xgw,
            entry_time=entry_t,
            waypoints=[
                (e_lat, e_lon, spd),
                (mid_lat, mid_lon, spd + random.gauss(0, 0.5)),
                (x_lat, x_lon, spd),
            ],
        )

    return records


# ─────────────────────────────────────────────────────────────────────────────

def main():
    output_path = os.path.join(
        os.path.dirname(__file__), "..", "backend", "data", "ais", "demo_ais.csv"
    )

    print("[*] Generating Occuris demo AIS data...")
    records = make_all_vessels()

    # Sort all records by timestamp
    records.sort(key=lambda r: r["timestamp"])

    fieldnames = ["mmsi","timestamp","latitude","longitude","speed","course",
                  "vessel_type","heading","nav_status","name","flag"]

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    unique_mmsi = len({r["mmsi"] for r in records})
    print(f"[OK] Generated {len(records)} AIS records for {unique_mmsi} vessels")
    print(f"     Saved to: {os.path.abspath(output_path)}")
    print("\nKey demo vessels:")
    print("  419000042 --- PRIMARY SUSPECT (tanker, AIS gap 12:30-14:45 near origin)")
    print("  419000040 --- SECONDARY (cargo, unexplained route deviation near origin)")
    print("  419000041 --- TERTIARY (tanker, passes near origin, weather explains slowdown)")


if __name__ == "__main__":
    main()
