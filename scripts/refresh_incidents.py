import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from app.database import SessionLocal
from app.services.forensics_service import process_sar_image, scan_sar_images

db = SessionLocal()
images = scan_sar_images()
print(f"[*] Found {len(images)} authentic SAR acquisitions: {images}")

for img in images:
    print(f"\n[*] Processing acquisition: {img}...")
    res = process_sar_image(img, db)
    inc = res["incident"]
    print(f"[OK] Scene {img} successfully ingested -> Incident #{inc['id']}:")
    print(f"     Centroid: {inc['geometry']['centroid_lat']}°N, {inc['geometry']['centroid_lon']}°E")
    print(f"     Area: {inc['geometry']['area_km2']} km² | Confidence: {inc['sar_confidence']*100:.1f}%")
    print(f"     Origin: {inc['origin']['lat']}°N, {inc['origin']['lon']}°E")

db.close()
print("\n[OK] All Copernicus SAR acquisitions populated with distinct real-world oceanic coordinates!")
