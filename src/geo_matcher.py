from shapely.geometry import shape, Point

def evaluate_proximity(alert_payload, target_lat, target_lon, target_county_name=None):
    props = alert_payload.get("properties", {})
    geometry = alert_payload.get("geometry")
    
    # 1. Try strict polygon intersection first
    if geometry:
        try:
            warning_polygon = shape(geometry)
            target_point = Point(target_lon, target_lat) 
            if warning_polygon.contains(target_point):
                return True
        except Exception as e:
            print(f"Error parsing geometry shape: {e}")

    # 2. FALLBACK: Check if your local county name is mentioned in the NWS text area description
    if target_county_name:
        area_desc = props.get("areaDesc", "")
        if target_county_name.lower() in area_desc.lower():
            return True
            
    return False
