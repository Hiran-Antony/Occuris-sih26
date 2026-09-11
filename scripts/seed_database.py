"""
Occuris Database Seeder
Reads demo_ais.csv → validates → stores in SQLite → runs behaviour analysis.

Run: python scripts/seed_database.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.database import init_db, SessionLocal
from app.services.ais_service import parse_ais_csv, validate_position, flag_impossible_jumps
from app.services.memory_service import ingest_position, reset_vessel_state
from app.services.behaviour_service import analyse_all_vessels

CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "backend", "data", "ais", "demo_ais.csv")


def clear_database(db):
    """Clear all data (for re-seeding)."""
    from app.models import BehaviourEvent, GatewayCrossing, Journey, AISPosition, Vessel
    db.query(BehaviourEvent).delete()
    db.query(GatewayCrossing).delete()
    db.query(Journey).delete()
    db.query(AISPosition).delete()
    db.query(Vessel).delete()
    db.commit()
    print("[x] Cleared existing data")


def seed():
    print("[*] Occuris Database Seeder")
    print("=" * 50)

    # 1. Init DB schema
    init_db()

    db = SessionLocal()
    try:
        clear_database(db)
        reset_vessel_state()

        # 2. Parse CSV
        print(f"\n[.] Reading AIS data from: {os.path.abspath(CSV_PATH)}")
        records = parse_ais_csv(CSV_PATH)
        print(f"   {len(records)} raw records read")

        # 3. Validate
        valid_records = []
        invalid_count = 0
        for rec in records:
            ok, reason = validate_position(rec)
            if ok:
                rec["flagged"] = False
                valid_records.append(rec)
            else:
                invalid_count += 1
                print(f"   [!] Skipped invalid record: {reason}")

        print(f"   {len(valid_records)} valid records ({invalid_count} invalid skipped)")

        # 4. Flag impossible jumps (keep records, just mark them)
        valid_records = flag_impossible_jumps(valid_records)
        flagged = sum(1 for r in valid_records if r.get("flagged"))
        if flagged:
            print(f"   [~] {flagged} records flagged as possible AIS anomalies")

        # 5. Ingest into Maritime Memory
        print("\n[*] Ingesting into Maritime Memory...")
        batch_size = 500
        for i, rec in enumerate(valid_records):
            ingest_position(rec, db)
            if (i + 1) % batch_size == 0:
                db.commit()
                print(f"   {i+1}/{len(valid_records)} positions stored...")

        db.commit()

        from app.models import Vessel, AISPosition, GatewayCrossing, Journey
        vessels = db.query(Vessel).count()
        positions = db.query(AISPosition).count()
        crossings = db.query(GatewayCrossing).count()
        journeys = db.query(Journey).count()

        print(f"\n[=] Maritime Memory Summary:")
        print(f"   Vessels:           {vessels}")
        print(f"   AIS Positions:     {positions}")
        print(f"   Gateway Crossings: {crossings}")
        print(f"   Journeys:          {journeys}")

        # 6. Behaviour analysis
        print("\n[>] Running behaviour analysis...")
        analyse_all_vessels(db)

        from app.models import BehaviourEvent
        events = db.query(BehaviourEvent).count()
        unexplained = db.query(BehaviourEvent).filter(BehaviourEvent.is_explained == False).count()
        print(f"\n[!] Behaviour Events: {events} ({unexplained} unexplained)")

        print("\n[OK] Seeding complete -- Occuris is ready for the demo!")
        print("\nKey vessels to check:")
        print("  MMSI 419000042 --- Primary suspect (tanker with AIS gap near origin)")
        print("  MMSI 419000040 --- Secondary (cargo with unexplained route deviation)")
        print("  MMSI 419000041 --- Tertiary (tanker, weather explains slowdown)")

    except Exception as e:
        db.rollback()
        print(f"\n[ERROR]: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
