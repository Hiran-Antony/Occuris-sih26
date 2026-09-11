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

def scan_sar_images():
    """Return a list of available SAR images in the data/sar/ directory."""
    if not os.path.exists(SAR_DIR):
        os.makedirs(SAR_DIR)
        
    files = glob.glob(os.path.join(SAR_DIR, "*.tif"))
    return sorted([os.path.basename(f) for f in files])

def process_sar_image(filename: str, db: Session):
    """
    Run the full Part 2 forensic workflow on a SAR image:
    SAR Detection -> Geometry -> SpillSplit -> Backward Drift -> Forward Drift
    """
    image_path = os.path.join(SAR_DIR, filename)
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"SAR image {filename} not found.")

    # 1. SAR Detection (Actual Model Inference)
    mask_filename = filename.replace(".tif", "_mask.png")
    mask_path = os.path.join(OUTPUT_MASK_DIR, mask_filename)
    
    print(f"[*] Processing {filename} through SAR inference...")
    sar_result = run_sar_inference(image_path, mask_path)
    
    if not sar_result:
        raise Exception("SAR inference failed.")
        
    # Create incident record
    incident = SpillIncident(
        sar_image_path=image_path,
        mask_path=mask_path,
        acquisition_time=sar_result.get("acquisition_time", datetime(2024, 1, 15, 18, 40, 0)),
        sar_confidence=sar_result["sar_confidence"],
        wind_check=sar_result["wind_check"],
        shape_check=sar_result["shape_check"],
        size_check=sar_result["size_check"],
        look_alike_passed=sar_result["look_alike_passed"]
    )
    db.add(incident)
    db.flush() # Get ID
    
    # 2. Spill Geometry
    print(f"[*] Calculating geometry for incident {incident.id}...")
    geom_result = calculate_geometry(sar_result["mask_array"])
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
    print(f"[*] Simulating backward drift...")
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
    forward = simulate_forward_drift(incident.spillsplit_zones)
    incident.forward_t1h = forward["forward_t1h"]
    incident.forward_t3h = forward["forward_t3h"]
    incident.forward_t6h = forward["forward_t6h"]
    
    incident.status = "processed"
    db.commit()
    
    print(f"[OK] Forensic workflow complete for {filename}.")
    return incident
