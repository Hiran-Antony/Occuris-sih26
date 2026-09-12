import cv2
import numpy as np

def calculate_geometry(mask_array: np.ndarray, base_lat=13.15, base_lon=86.20, km_per_pixel=0.015):
    """
    Calculate actual geometry from the predicted segmentation mask.
    Returns geographic centroid and physical dimensions in km.
    """
    if mask_array is None or mask_array.sum() == 0:
        return {
            "centroid_lat": base_lat,
            "centroid_lon": base_lon,
            "area_km2": 0,
            "perimeter_km": 0,
            "length_km": 0,
            "width_km": 0,
            "orientation_deg": 0,
            "pixel_count": 0,
            "contours_geo": []
        }

    # Find contours
    contours, _ = cv2.findContours(mask_array, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        return None

    # Get the largest contour (assuming it's the main spill body)
    main_contour = max(contours, key=cv2.contourArea)
    
    # Total slick footprint from all positive mask pixels
    total_area_px = int(mask_array.sum())
    area_px = cv2.contourArea(main_contour)
    perimeter_px = cv2.arcLength(main_contour, True)
    
    # Bounding rotated rectangle for length/width/orientation
    rect = cv2.minAreaRect(main_contour)
    (cx_px, cy_px), (w_px, h_px), angle = rect

    # Convert pixels to physical units
    area_km2 = total_area_px * (km_per_pixel ** 2)
    perimeter_km = perimeter_px * km_per_pixel
    length_km = max(w_px, h_px) * km_per_pixel
    width_km = min(w_px, h_px) * km_per_pixel
    
    # Adjust orientation to standard geographic (North = 0, East = 90)
    if w_px < h_px:
        orientation = angle + 90
    else:
        orientation = angle
        
    if orientation < 0:
        orientation += 180
    elif orientation >= 180:
        orientation -= 180

    # Convert pixel centroid to geo-coordinates (mock mapping for demo)
    # We assume the center of the image is at base_lat, base_lon
    h, w = mask_array.shape
    deg_per_pixel_lat = km_per_pixel / 111.32
    deg_per_pixel_lon = km_per_pixel / (111.32 * np.cos(np.radians(base_lat)))
    
    centroid_lat = base_lat - ((cy_px - h/2) * deg_per_pixel_lat)
    centroid_lon = base_lon + ((cx_px - w/2) * deg_per_pixel_lon)

    # Convert contour points to geo for visualization
    contours_geo = []
    for pt in main_contour:
        px, py = pt[0]
        plat = base_lat - ((py - h/2) * deg_per_pixel_lat)
        plon = base_lon + ((px - w/2) * deg_per_pixel_lon)
        contours_geo.append([round(plon, 5), round(plat, 5)])

    # Close the polygon
    if contours_geo:
        contours_geo.append(contours_geo[0])

    return {
        "centroid_lat": round(centroid_lat, 5),
        "centroid_lon": round(centroid_lon, 5),
        "area_km2": round(area_km2, 2),
        "perimeter_km": round(perimeter_km, 2),
        "length_km": round(length_km, 2),
        "width_km": round(width_km, 2),
        "orientation_deg": round(orientation, 1),
        "pixel_count": int(area_px),
        "contours_geo": contours_geo
    }
