from datetime import datetime, timedelta
import json
import random

def simulate_backward_drift(centroid_lat, centroid_lon, detection_time):
    """
    Backward drift tracking. Reverse wind/current to find origin window.
    """
    # Assuming wind is North-Easterly (from NE to SW), the backward drift 
    # goes towards NE.
    # We'll simulate particles tracing back ~4-6 hours.
    
    # Approx origin (further North-East from the centroid)
    origin_lat = centroid_lat + 0.05
    origin_lon = centroid_lon - 0.20
    
    particles = []
    for i in range(20):
        f = i / 19.0
        plat = origin_lat + (centroid_lat - origin_lat) * f + random.gauss(0, 0.015)
        plon = origin_lon + (centroid_lon - origin_lon) * f + random.gauss(0, 0.015)
        particles.append([round(plon, 5), round(plat, 5)])
        
    # Assume 18:40 UTC detection, backward drift suggests release between 12:00-16:00
    release_start = detection_time - timedelta(hours=6, minutes=40)
    release_end = detection_time - timedelta(hours=2, minutes=40)
        
    return {
        "origin_lat": round(origin_lat, 5),
        "origin_lon": round(origin_lon, 5),
        "origin_radius_km": 15.0,
        "release_start": release_start,
        "release_end": release_end,
        "backward_particles": json.dumps(particles)
    }

def simulate_forward_drift(geometry_zones_json):
    """
    Forward drift polygon expansion for 1h, 3h, 6h based on wind/currents.
    """
    try:
        zones = json.loads(geometry_zones_json)
        coords = zones[0]["coordinates"][0]
    except:
        return {
            "forward_t1h": "[]",
            "forward_t3h": "[]",
            "forward_t6h": "[]"
        }
        
    def expand_polygon(base_coords, offset_lat, offset_lon, expansion):
        new_coords = []
        if not base_coords:
            return new_coords
            
        # Find centroid of base
        c_lon = sum(pt[0] for pt in base_coords) / len(base_coords)
        c_lat = sum(pt[1] for pt in base_coords) / len(base_coords)
        
        for lon, lat in base_coords:
            n_lon = c_lon + (lon - c_lon) * expansion + offset_lon
            n_lat = c_lat + (lat - c_lat) * expansion + offset_lat
            new_coords.append([round(n_lon, 5), round(n_lat, 5)])
        return new_coords

    # Wind pushes SW
    t1h = expand_polygon(coords, -0.01, -0.02, 1.05)
    t3h = expand_polygon(coords, -0.04, -0.05, 1.15)
    t6h = expand_polygon(coords, -0.08, -0.10, 1.30)
    
    return {
        "forward_t1h": json.dumps([t1h]),
        "forward_t3h": json.dumps([t3h]),
        "forward_t6h": json.dumps([t6h])
    }
