"""
Occuris Demo AIS Generator
Generates authentic, realistic synthetic AIS data for the Bay of Bengal scenario.
All vessels navigate strictly in maritime ocean waters (never on land or islands).
All passages to Gate D use official international channels (Ten Degree Channel, Coco Channel).

Scenario: 2024-01-15, 06:00 – 22:00 UTC
Incident time: 18:40 UTC
Estimated release window: 12:00 – 16:00 UTC
Detected oil spill: 13.16°N, 86.19°E
Primary Suspect Tanker: MT DESH SHOBHA (MMSI: 419000042, IMO: 9297503, Flag: IN)

Run: python scripts/generate_ais.py
Output: backend/data/ais/demo_ais.csv
"""

import csv
import math
import random
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

random.seed(42)

# ── Demo scenario constants ─────────────────────────────────────────────────
DEMO_START    = datetime(2024, 1, 15, 6, 0, 0)
INCIDENT_TIME = datetime(2024, 1, 15, 18, 40, 0)
RELEASE_START = datetime(2024, 1, 15, 12, 0, 0)
RELEASE_END   = datetime(2024, 1, 15, 16, 0, 0)

# Real maritime ocean bounds for the Bay of Bengal oceanic box
BOB_WEST, BOB_EAST = 84.0, 93.5
BOB_SOUTH, BOB_NORTH = 6.0, 19.5

# Gateway entry/exit reference coordinates strictly in open sea
GATEWAY_ENTRY = {
    "A": lambda: (random.uniform(7.0, 18.0), 84.0),
    "B": lambda: (19.5, random.uniform(85.0, 92.5)),
    "C": lambda: (6.0, random.uniform(85.0, 92.5)),
    "D": lambda: (random.choice([random.uniform(7.0, 10.0), random.uniform(14.5, 18.5)]), 93.5),
}
GATEWAY_EXIT = {
    "A": lambda: (random.uniform(7.0, 18.0), 84.0),
    "B": lambda: (19.5, random.uniform(85.0, 92.5)),
    "C": lambda: (6.0, random.uniform(85.0, 92.5)),
    "D": lambda: (random.choice([random.uniform(7.0, 10.0), random.uniform(14.5, 18.5)]), 93.5),
}

VESSEL_SPEEDS = {"tanker": 10.0, "cargo": 12.0, "fishing": 6.0, "passenger": 16.0}
VESSEL_NAMES = {
    "tanker": [
        "MT DESH SHOBHA", "MT SWARNA SINDHU", "MT MAERSK TIANJIN", "MT BUNGA KELANA",
        "MT CHENNAI PERUMAL", "MT OCEAN CREST", "MT GULF PEARL", "MT PETRO STAR",
        "MT DELTA PRIDE", "MT ARABIAN TIDE", "MT VISHVA VIJAY", "MT BENGAL PIONEER"
    ],
    "cargo": [
        "MV CHENNAI VALAM", "MV BANGLAR SHOURABH", "MV ASIAN HIGHWAY", "MV ANDAMAN GLORY",
        "MV EVER COURAGE", "MV SEAWIND TRADER", "MV BAY EXPRESS", "MV MONSOON CARRIER",
        "MV PACIFIC VOYAGER", "MV MALACCA STAR", "MV OCEAN LEADER", "MV EASTERN BRIDGE"
    ],
    "fishing": [
        "SAGAR KANYA", "MATSYA JEEVANI", "SAGARA JYOTI", "ANANDA SAGAR",
        "DEEPA VIJAY", "NILUFAR STAR", "SAMUDRA RATNA", "COROMANDEL PEARL",
        "BAY OF BENGAL I", "ANDAMAN HARVEST"
    ],
    "passenger": [
        "MV CORAL QUEEN", "MV SINDHU", "MV ISLAND EXPRESS", "MV FERRY PRINCESS", "MV BAY LINK"
    ]
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


def check_land_conflict(lat, lon):
    """
    Returns True if coordinates intersect the Andaman or Nicobar island land masses.
    """
    # Andaman chain (Port Blair, South/Middle/North Andaman, Rutland)
    if 10.45 <= lat <= 13.85 and 92.35 <= lon <= 93.15:
        return True
    # Nicobar chain (Car Nicobar, Katchal, Camorta, Great Nicobar)
    if 6.70 <= lat <= 9.40 and 92.65 <= lon <= 94.00:
        return True
    # Mainland coast
    if lon <= 83.5:
        return True
    return False


def make_trajectory(
    mmsi, vessel_type, vessel_name, flag,
    entry_gw, exit_gw,
    entry_time,
    waypoints,         # list of (lat, lon, speed_override_or_None)
    gap_windows=None,  # list of (start_dt, end_dt)
):
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
            lat = lat_s + (lat_e - lat_s)*frac + random.gauss(0, 0.01)
            lon = lon_s + (lon_e - lon_s)*frac + random.gauss(0, 0.01)

            # Safety clamp against island zones: nudge if noise puts point near land
            if check_land_conflict(lat, lon):
                if lat < 12.0:
                    lat = 10.00  # Shift safely to Ten Degree Channel
                else:
                    lat = 14.30  # Shift safely to Coco Channel

            spd_val = max(0.1, spd + random.gauss(0, 0.2))
            crs = (bearing(lat_s, lon_s, lat_e, lon_e) + random.gauss(0, 1.0)) % 360

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
                "heading": round(crs + random.gauss(0, 2), 1),
                "nav_status": "underway",
                "name": vessel_name,
                "flag": flag,
            })

    return records


def _elapsed(waypoints, seg_idx, frac, vessel_type):
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


def route_nautical(start_pt, end_pt, spd):
    """
    Ensures vessel trajectories navigate strictly through real maritime deep-water channels
    and NEVER cross over the Andaman & Nicobar islands or Port Blair.
    """
    lat_s, lon_s = start_pt
    lat_e, lon_e = end_pt

    crosses_archipelago = (lon_s < 92.2 and lon_e > 92.8) or (lon_s > 92.8 and lon_e < 92.2)

    if not crosses_archipelago:
        return [
            (lat_s, lon_s, spd),
            ((lat_s + lat_e) / 2, (lon_s + lon_e) / 2, spd),
            (lat_e, lon_e, spd)
        ]

    avg_lat = (lat_s + lat_e) / 2
    if avg_lat >= 13.5:
        # Route North of Andaman via Coco Channel (14.3°N) - 100% open deep sea
        return [
            (lat_s, lon_s, spd),
            (14.3, 91.5, spd),
            (14.3, 92.5, spd),
            (14.3, 93.2, spd),
            (lat_e, lon_e, spd)
        ]
    elif avg_lat <= 8.5:
        # Route South via Great Channel (6.5°N)
        return [
            (lat_s, lon_s, spd),
            (6.5, 91.0, spd),
            (6.5, 92.5, spd),
            (lat_e, lon_e, spd)
        ]
    else:
        # Route via Ten Degree Channel (10.0°N) - 150 km wide open deep ocean!
        return [
            (lat_s, lon_s, spd),
            ((lat_s + 10.0) / 2, 89.5, spd),
            (10.0, 91.5, spd),
            (10.0, 92.5, spd),
            (10.0, 93.2, spd),
            (lat_e, lon_e, spd)
        ]


def make_all_vessels():
    records = []

    # ─── PRIMARY SUSPECT (HIGH PRIORITY) ────────────────────────────────────
    # MMSI 419000042 — MT DESH SHOBHA (Crude Tanker, SCI, Flag: IN)
    # Enters Gate A, slows down, releases oil at 13.16°N, 86.19°E, AIS gap 12:30-14:45.
    # Exits Gate D through Ten Degree Channel (10.0°N) — ZERO LAND INTERSECTION.
    records += make_trajectory(
        mmsi="419000042", vessel_type="tanker",
        vessel_name="MT DESH SHOBHA", flag="IN",
        entry_gw="A", exit_gw="D",
        entry_time=datetime(2024, 1, 15, 6, 30, 0),
        waypoints=[
            (13.25, 84.0, 10.0),   # Gate A entry (open sea 84.0°E)
            (13.22, 84.8, 10.0),   # Eastward transit
            (13.20, 85.4, 6.0),    # Slowdown begins
            (13.18, 85.8, 4.5),    # Continued slowdown
            (13.16, 86.19, 9.5),   # EXACT OVER DETECTED OIL SPILL ZONE → AIS GAP STARTS 12:30
            # ← AIS GAP 12:30 – 14:45 (discharge window) ←
            (12.80, 88.0, 9.5),    # AIS RESUMES past origin zone
            (11.80, 89.8, 10.5),   # Route turn southeast toward Ten Degree Channel fairway
            (10.50, 91.2, 10.5),   # Approaches Ten Degree Channel fairway (west of Little Andaman)
            (10.00, 92.0, 10.5),   # Enters Ten Degree Channel (150 km wide open deep sea)
            (10.00, 92.8, 10.5),   # Transiting Ten Degree Channel safely south of Little Andaman
            (10.00, 93.5, 10.0),   # Gate D exit into Andaman Sea
        ],
        gap_windows=[
            (datetime(2024, 1, 15, 12, 30, 0), datetime(2024, 1, 15, 14, 45, 0)),
        ],
    )

    # ─── SECONDARY CANDIDATE (MEDIUM PRIORITY) ──────────────────────────────
    # MMSI 419000040 — EASTERN STAR (Cargo), bilge dumping filament in Ten Degree Channel (10.13°N, 92.64°E)
    records += make_trajectory(
        mmsi="419000040", vessel_type="cargo",
        vessel_name="EASTERN STAR", flag="SG",
        entry_gw="A", exit_gw="D",
        entry_time=datetime(2024, 1, 15, 0, 30, 0),
        waypoints=[
            (10.28, 89.20, 11.5),
            (10.22, 90.50, 11.5),
            (10.18, 91.80, 10.5),
            (10.13, 92.64, 8.5),   # REACHES TEN DEGREE CHOKEPOINT AT ~18:40 UTC S1 DETECTION
            (10.05, 93.30, 11.5),
            (10.00, 94.00, 11.5),  # Gate D exit into Andaman Sea (strictly south of Little Andaman)
        ],
    )

    # ─── THIRD CANDIDATE (LOW PRIORITY) ─────────────────────────────────────
    # MMSI 419000041 — GULF WAVE (Tanker), produced water / rig washing in KG Basin (16.45°N, 84.45°E)
    records += make_trajectory(
        mmsi="419000041", vessel_type="tanker",
        vessel_name="GULF WAVE", flag="MY",
        entry_gw="B", exit_gw="A",
        entry_time=datetime(2024, 1, 15, 8, 45, 0),
        waypoints=[
            (17.80, 85.20, 10.0),
            (17.30, 84.90, 10.0),
            (16.85, 84.65, 8.5),
            (16.45, 84.45, 6.0),   # REACHES KG BASIN OFFSHORE SHELF AT ~18:40 UTC S1 DETECTION
            (16.00, 84.35, 10.0),
            (15.20, 84.20, 10.0),  # Gate A southward exit inside surveillance basin
        ],
    )

    # ─── VESSELS WITH WEATHER-EXPLAINED SLOWDOWNS ───────────────────────────
    records += make_trajectory(
        mmsi="419000036", vessel_type="tanker",
        vessel_name="DELTA TIDE", flag="IN",
        entry_gw="A", exit_gw="C",
        entry_time=datetime(2024, 1, 15, 7, 30, 0),
        waypoints=[
            (12.0, 84.0, 10.0),
            (11.5, 85.0, 10.0),
            (10.5, 86.5, 4.0),   # Weather slowdown
            (9.5, 87.5, 4.5),
            (8.5, 89.0, 10.0),
            (7.5, 90.5, 10.0),
            (6.0, 92.0, 10.0),   # Gate C exit
        ],
    )

    records += make_trajectory(
        mmsi="419000037", vessel_type="cargo",
        vessel_name="BAY EXPRESS", flag="BD",
        entry_gw="B", exit_gw="C",
        entry_time=datetime(2024, 1, 15, 8, 30, 0),
        waypoints=[
            (19.5, 88.0, 12.0),
            (17.5, 88.5, 12.0),
            (15.0, 89.0, 5.0),   # Weather slowdown
            (12.5, 89.5, 5.0),
            (10.0, 90.0, 12.0),
            (7.5, 90.5, 12.0),
            (6.0, 91.0, 12.0),   # Gate C exit
        ],
    )

    # ─── VESSELS WITH OPERATIONAL STOPS ─────────────────────────────────────
    records += make_trajectory(
        mmsi="419000038", vessel_type="fishing",
        vessel_name="SAGARA JYOTI", flag="IN",
        entry_gw="A", exit_gw="C",
        entry_time=datetime(2024, 1, 15, 6, 0, 0),
        waypoints=[
            (10.0, 84.0, 6.0),
            (9.5, 84.8, 6.0),
            (9.0, 85.5, 0.4),    # Operational stop (fishing)
            (8.8, 85.8, 0.3),
            (8.7, 86.0, 0.2),
            (8.6, 86.2, 0.2),
            (8.5, 86.5, 6.0),
            (7.5, 87.0, 6.0),
            (6.5, 88.5, 6.0),
            (6.0, 89.5, 6.0),   # Gate C exit
        ],
    )

    records += make_trajectory(
        mmsi="419000039", vessel_type="tanker",
        vessel_name="MT VISHVA VIJAY", flag="IN",
        entry_gw="C", exit_gw="D",
        entry_time=datetime(2024, 1, 15, 9, 0, 0),
        waypoints=[
            (6.0, 86.5, 10.0),
            (6.5, 87.5, 10.0),
            (7.0, 89.0, 0.5),    # Operational stop
            (7.2, 89.2, 0.3),
            (7.5, 89.5, 10.0),
            (8.5, 91.0, 10.0),
            (9.8, 92.5, 10.0),   # Approaches Ten Degree Channel south of Little Andaman
            (10.0, 93.5, 10.0),  # Gate D exit
        ],
    )

    # ─── AIS GAP FAR FROM INCIDENT ──────────────────────────────────────────
    records += make_trajectory(
        mmsi="419000043", vessel_type="cargo",
        vessel_name="MV SEAWIND TRADER", flag="PH",
        entry_gw="B", exit_gw="C",
        entry_time=datetime(2024, 1, 15, 9, 30, 0),
        waypoints=[
            (19.5, 90.0, 12.0),
            (17.5, 90.5, 12.0),
            (15.0, 91.0, 12.0),  # AIS gap here (well west of Andaman)
            (12.5, 91.2, 12.0),
            (10.0, 91.0, 12.0),
            (7.5, 90.5, 12.0),
            (6.0, 90.0, 12.0),   # Gate C exit
        ],
        gap_windows=[
            (datetime(2024, 1, 15, 13, 0, 0), datetime(2024, 1, 15, 14, 30, 0)),
        ],
    )

    # ─── EARLY-EXIT VESSELS ────────────────────────────────────────────────
    early_vessels = [
        ("A", "C", "fishing",   "ANANDA SAGAR",        "IN",  [(9.0, 84.0, 6.0), (7.5, 85.0, 6.0), (6.0, 86.0, 6.0)]),
        ("B", "A", "cargo",     "MV CORAL TRADER",     "MY",  [(19.5, 88.5, 12.0), (14.0, 86.0, 12.0), (9.0, 84.0, 12.0)]),
        ("C", "A", "tanker",    "MT PETRO STAR",       "LK",  [(6.0, 86.0, 10.0), (7.5, 85.0, 10.0), (9.0, 84.0, 10.0)]),
        ("D", "C", "fishing",   "NILUFAR STAR",        "BD",  [(10.0, 93.5, 6.0), (8.0, 92.5, 6.0), (6.0, 91.0, 6.0)]),
        ("A", "D", "passenger", "MV CORAL QUEEN",      "IN",  [(12.0, 84.0, 14.0), (10.0, 89.0, 14.0), (10.0, 92.0, 14.0), (10.0, 93.5, 14.0)]),
    ]
    for i, (entry_gw, exit_gw, vtype, name, flag, wpts) in enumerate(early_vessels):
        records += make_trajectory(
            mmsi=f"41900004{8+i}", vessel_type=vtype,
            vessel_name=name, flag=flag,
            entry_gw=entry_gw, exit_gw=exit_gw,
            entry_time=datetime(2024, 1, 15, 6, 0, 0),
            waypoints=wpts,
        )

    # ─── NORMAL BACKGROUND VESSELS (35) ─────────────────────────────────────
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

    # Staggered temporal offsets so maritime traffic is in realistic steady state:
    # - 15 vessels in ongoing mid-ocean transit (entered 10 to 28 hrs prior to 06:00 UTC)
    # - 10 vessels entered 0.5 to 8 hrs prior or around 06:00 UTC
    # - 6 vessels entering during morning/midday (07:00 to 11:00 UTC)
    # - 4 vessels entering during afternoon (12:00 to 17:00 UTC)
    offsets = (
        [random.uniform(-28.0, -10.0) for _ in range(15)] +
        [random.uniform(-8.0, -0.5) for _ in range(10)] +
        [random.uniform(0.5, 5.0) for _ in range(6)] +
        [random.uniform(5.5, 11.0) for _ in range(4)]
    )
    random.shuffle(offsets)

    for idx, (((egw, xgw), vtype), offset_hr) in enumerate(zip(zip(routes, vtypes), offsets)):
        mmsi = f"4190001{idx+1:02d}"
        spd = VESSEL_SPEEDS[vtype]
        names_list = VESSEL_NAMES[vtype]
        vname = names_list[idx % len(names_list)]
        flag = random.choice(FLAGS)
        entry_t = DEMO_START + timedelta(hours=offset_hr)

        e_lat, e_lon = GATEWAY_ENTRY[egw]()
        x_lat, x_lon = GATEWAY_EXIT[xgw]()

        # Generate nautical channel-safe waypoints
        wpts = route_nautical((e_lat, e_lon), (x_lat, x_lon), spd)

        records += make_trajectory(
            mmsi=mmsi, vessel_type=vtype,
            vessel_name=vname, flag=flag,
            entry_gw=egw, exit_gw=xgw,
            entry_time=entry_t,
            waypoints=wpts,
        )

    return records


def main():
    output_path = os.path.join(
        os.path.dirname(__file__), "..", "backend", "data", "ais", "demo_ais.csv"
    )

    print("[*] Generating realistic maritime-only AIS data for Bay of Bengal...")
    records = make_all_vessels()

    # Sort all records by timestamp
    records.sort(key=lambda r: r["timestamp"])

    # Strict geographical verification: verify NO records touch any island or land!
    land_violations = 0
    for r in records:
        if check_land_conflict(r["latitude"], r["longitude"]):
            land_violations += 1
            print(f"[!] Warning: Point on land detected: MMSI {r['mmsi']} at ({r['latitude']}, {r['longitude']})")

    print(f"[*] Geographic validation: {len(records)} points checked. Land violations: {land_violations}")
    assert land_violations == 0, f"Found {land_violations} points intersecting land!"

    fieldnames = ["mmsi","timestamp","latitude","longitude","speed","course",
                  "vessel_type","heading","nav_status","name","flag"]

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    unique_mmsi = len({r["mmsi"] for r in records})
    print(f"[OK] Generated {len(records)} AIS records for {unique_mmsi} vessels (all strictly in maritime sea coordinates).")
    print(f"     Saved to: {os.path.abspath(output_path)}")


if __name__ == "__main__":
    main()
