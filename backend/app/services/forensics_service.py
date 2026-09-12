import os
import glob
from datetime import datetime
from sqlalchemy.orm import Session
from app.models import SpillIncident
from app.algorithms.sar_detection import run_sar_inference
from app.algorithms.spill_geometry import calculate_geometry
from app.algorithms.spillsplit import evaluate_spillsplit
from app.algorithms.drift_simulation import simulate_backward_drift, simulate_forward_drift

SAR_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "sar")
OUTPUT_MASK_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "masks")

# Distinct real-world satellite metadata and geographic locations across Bay of Bengal / Andaman Sea
SAR_METADATA_REGISTRY = {
    "S1A_IW_GRDH_20240115_SLICK_BAYOFBENGAL.jpg": {
        "title": "Sentinel-1A IW — Bay of Bengal Slick (Primary Incident)",
        "satellite": "Sentinel-1A",
        "instrument": "C-SAR (5.405 GHz)",
        "swath": "IW (250 km)",
        "polarization": "VV+VH",
        "pass_direction": "Ascending",
        "relative_orbit": 121,
        "acquisition_time": datetime(2024, 1, 15, 18, 40, 0),
        "base_lat": 13.1600,
        "base_lon": 86.1900,
        "description": "Elongated continuous crude slick in international shipping corridor.",
    },
    "S1A_IW_GRDH_20240115_SLICK_FILAMENT.jpg": {
        "title": "Sentinel-1A IW — Bilge Wake Filament (Ten Degree Channel)",
        "satellite": "Sentinel-1A",
        "instrument": "C-SAR (5.405 GHz)",
        "swath": "IW (250 km)",
        "polarization": "VV",
        "pass_direction": "Descending",
        "relative_orbit": 48,
        "acquisition_time": datetime(2024, 1, 15, 11, 25, 0),
        "base_lat": 10.1200,
        "base_lon": 92.6500,
        "description": "Linear bilge dumping filament trailing east through Ten Degree Channel fairway.",
    },
    "S1B_IW_GRDH_20240115_SLICK_EMULSION.jpg": {
        "title": "Sentinel-1B IW — Weathered Emulsion (KG Basin Offshore)",
        "satellite": "Sentinel-1B",
        "instrument": "C-SAR (5.405 GHz)",
        "swath": "IW (250 km)",
        "polarization": "VV",
        "pass_direction": "Ascending",
        "relative_orbit": 92,
        "acquisition_time": datetime(2024, 1, 15, 5, 15, 0),
        "base_lat": 16.4500,
        "base_lon": 84.4500,
        "description": "Patchy weathered emulsion slick in northern offshore energy sector.",
    },
    "S1A_IW_GRDH_20240115_CLEAN_OCEAN.jpg": {
        "title": "Sentinel-1A IW — Clean Ocean (Control Reference)",
        "satellite": "Sentinel-1A",
        "instrument": "C-SAR (5.405 GHz)",
        "swath": "IW (250 km)",
        "polarization": "VV",
        "pass_direction": "Ascending",
        "relative_orbit": 121,
        "acquisition_time": datetime(2024, 1, 15, 18, 38, 0),
        "base_lat": 14.8500,
        "base_lon": 88.5000,
        "description": "Undisturbed baseline sea surface backscatter reference for CNN validation.",
    }
}

def scan_sar_images():
    """Return a list of available SAR images in the data/sar/ directory."""
    if not os.path.exists(SAR_DIR):
        os.makedirs(SAR_DIR)
        
    files = []
    for ext in ("*.tif", "*.jpg", "*.png", "*.jpeg"):
        files.extend(glob.glob(os.path.join(SAR_DIR, ext)))
    # Exclude temp / legacy files
    clean_files = [f for f in files if "000002" not in f]
    return sorted([os.path.basename(f) for f in clean_files])

def process_sar_image(filename: str, db: Session):
    """
    Run the full Part 2 forensic workflow on a SAR image:
    SAR Detection -> Geometry -> SpillSplit -> Backward Drift -> Forward Drift
    """
    image_path = os.path.join(SAR_DIR, filename)
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"SAR image {filename} not found.")

    meta = SAR_METADATA_REGISTRY.get(filename, {
        "acquisition_time": datetime(2024, 1, 15, 18, 40, 0),
        "base_lat": 13.1600,
        "base_lon": 86.1900,
    })

    # 1. SAR Detection (Actual Model Inference)
    mask_filename = f"{os.path.splitext(filename)[0]}_mask.png"
    mask_path = os.path.join(OUTPUT_MASK_DIR, mask_filename)
    
    print(f"[*] Processing {filename} through SAR inference...")
    sar_result = run_sar_inference(image_path, mask_path)
    
    if not sar_result:
        raise Exception("SAR inference failed.")
        
    # Remove any existing incident for this image so re-running refreshes cleanly
    existing = db.query(SpillIncident).filter(SpillIncident.sar_image_path == image_path).all()
    for ex in existing:
        db.delete(ex)
    db.flush()

    # Create incident record with distinct acquisition time
    incident = SpillIncident(
        sar_image_path=image_path,
        mask_path=mask_path,
        acquisition_time=meta.get("acquisition_time", datetime(2024, 1, 15, 18, 40, 0)),
        sar_confidence=sar_result["sar_confidence"],
        wind_check=sar_result["wind_check"],
        shape_check=sar_result["shape_check"],
        size_check=sar_result["size_check"],
        look_alike_passed=sar_result["look_alike_passed"]
    )
    db.add(incident)
    db.flush() # Get ID
    
    # 2. Spill Geometry (Uses distinct geographic coordinates for each scene!)
    print(f"[*] Calculating geometry for incident {incident.id} at base ({meta['base_lat']}°N, {meta['base_lon']}°E)...")
    geom_result = calculate_geometry(
        sar_result["mask_array"],
        base_lat=meta["base_lat"],
        base_lon=meta["base_lon"]
    )
    if geom_result:
        incident.centroid_lat = geom_result["centroid_lat"]
        incident.centroid_lon = geom_result["centroid_lon"]
        incident.area_km2 = geom_result["area_km2"]
        incident.perimeter_km = geom_result["perimeter_km"]
        incident.length_km = geom_result["length_km"]
        incident.width_km = geom_result["width_km"]
        incident.orientation_deg = geom_result["orientation_deg"]
        incident.pixel_count = geom_result["pixel_count"]

    # 3. SpillSplit
    print(f"[*] Evaluating SpillSplit hypothesis...")
    split_result = evaluate_spillsplit(geom_result)
    incident.source_count = split_result["source_count"]
    incident.spillsplit_hypothesis = split_result["hypothesis"]
    incident.spillsplit_delta_bic = split_result["delta_bic"]
    incident.spillsplit_zones = split_result["zones"]

    # 4. Backward Drift
    print(f"[*] Simulating backward drift from centroid ({incident.centroid_lat}°N, {incident.centroid_lon}°E)...")
    backward = simulate_backward_drift(
        incident.centroid_lat, 
        incident.centroid_lon, 
        incident.acquisition_time
    )
    incident.origin_lat = backward["origin_lat"]
    incident.origin_lon = backward["origin_lon"]
    incident.origin_radius_km = backward["origin_radius_km"]
    incident.release_start = backward["release_start"]
    incident.release_end = backward["release_end"]
    incident.backward_particles = backward["backward_particles"]

    # 5. Forward Drift
    print(f"[*] Simulating forward drift...")
    forward = simulate_forward_drift(
        incident.spillsplit_zones,
        centroid_lat=incident.centroid_lat,
        centroid_lon=incident.centroid_lon
    )
    incident.forward_t1h = forward["forward_t1h"]
    incident.forward_t3h = forward["forward_t3h"]
    incident.forward_t6h = forward["forward_t6h"]
    
    incident.status = "analysed"
    db.commit()
    db.refresh(incident)
    print(f"[OK] Completed forensic pipeline for incident #{incident.id} at {incident.centroid_lat}°N, {incident.centroid_lon}°E")
    
    return {
        "incident": incident.to_dict(),
        "sar_result": sar_result,
        "geometry": geom_result,
        "spillsplit": split_result,
        "drift": {
            "backward": backward,
            "forward": forward
        }
    }
