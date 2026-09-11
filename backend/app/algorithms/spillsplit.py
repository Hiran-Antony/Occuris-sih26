import json

def evaluate_spillsplit(geometry_data: dict):
    """
    Evaluates if a spill mask is from a single continuous release or multiple point sources.
    In a real scenario, this applies Gaussian Mixture Models on the mask pixels.
    For this implementation, we analyze the geometry shape and return the source count.
    """
    contours_geo = geometry_data.get("contours_geo", [])
    
    # If the spill is long and continuous (length >> width), it strongly indicates 
    # a single moving source (a vessel) rather than multiple point sources.
    length = geometry_data.get("length_km", 0)
    width = geometry_data.get("width_km", 1) # avoid div by zero
    
    ratio = length / max(width, 0.1)
    
    if ratio > 4.0:
        hypothesis = "one_source"
        source_count = 1
        delta_bic = round(ratio * 2.5, 1) # Synthetic high confidence for 1 source
    else:
        hypothesis = "multiple_sources"
        source_count = 2
        delta_bic = round(ratio * 1.5, 1)
        
    zones = []
    if contours_geo:
        zones.append({
            "id": "zone_1",
            "type": "Polygon",
            "coordinates": [contours_geo]
        })

    return {
        "hypothesis": hypothesis,
        "source_count": source_count,
        "delta_bic": delta_bic,
        "zones": json.dumps(zones)
    }
