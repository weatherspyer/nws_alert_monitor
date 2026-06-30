import os
import matplotlib.pyplot as plt
import geopandas as gpd
from shapely.geometry import shape, Point
import contextily as ctx

def plot_warning_map(alert_payload, target_lat, target_lon, location_name):
    """
    Generates a localized, zoomed-out map tracking the warning polygon relative to your house pin.
    """
    geometry = alert_payload.get("geometry")
    if not geometry:
        return
        
    props = alert_payload["properties"]
    event_name = props.get("event", "Warning")
    alert_id = props.get("id", "alert").split("-")[-1]

    try:
        # 1. Convert the raw NWS GeoJSON polygon into a GeoDataFrame
        alert_shape = shape(geometry)
        gdf_poly = gpd.GeoDataFrame(geometry=[alert_shape], crs="EPSG:4326")
        
        # 2. Create your precise house point GeoDataFrame
        house_point = Point(target_lon, target_lat)
        gdf_point = gpd.GeoDataFrame(geometry=[house_point], crs="EPSG:4326")
        
        # 3. Project both to Web Mercator (EPSG:3857) so background maps render properly
        gdf_poly_3857 = gdf_poly.to_crs(epsg=3857)
        gdf_point_3857 = gdf_point.to_crs(epsg=3857)
        
        # 4. Initialize the matplotlib plot
        fig, ax = plt.subplots(figsize=(10, 8))
        
        # Plot the NWS warning polygon
        gdf_poly_3857.plot(ax=ax, facecolor="red", edgecolor="darkred", alpha=0.35, linewidth=2, label="Warning Area")
        
        # Plot your local tracking pin (bright blue star)
        gdf_point_3857.plot(ax=ax, color="cyan", edgecolor="black", marker="*", markersize=250, label=location_name)
        
        # =========================================================================
        # 🗺️ THE CRITICAL ZOOM FIX: Expand the Map view boundaries
        # =========================================================================
        # Get current min/max coordinates of the warning polygon in Web Mercator meters
        xmin, ymin, xmax, ymax = gdf_poly_3857.total_bounds
        
        # Calculate the raw height and width of the polygon box
        width = xmax - xmin
        height = ymax - ymin
        
        # Add a 50% margin buffer to all sides (Change 0.50 to 1.00 or higher for even more zoom-out)
        padding_x = width * 0.50
        padding_y = height * 0.50
        
        # Overwrite the viewport scale bounds with our expanded parameters
        ax.set_xlim(xmin - padding_x, xmax + padding_x)
        ax.set_ylim(ymin - padding_y, ymax + padding_y)
        # =========================================================================
        
        # 5. Automatically pull and stitch the background tile layer
        ctx.add_basemap(ax, source=ctx.providers.CartoDB.Positron)
        
        # 6. Format the window frames beautifully
        plt.title(f"🚨 LIVE NWS TARGET IMPACT MATRICES\n{event_name} - Threatening {location_name}", fontsize=14, fontweight="bold", pad=15)
        ax.set_axis_off()
        plt.legend(loc="upper right")
        
        # Save map plot directly to your system
        output_dir = "outputs"
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, f"{alert_id}_impact_map.png")
        
        plt.savefig(filepath, bbox_inches="tight", dpi=150)
        plt.close()
        print(f"🗺️  SUCCESS: Zoomed-out convective visual map saved to: {filepath}")
        
    except Exception as e:
        print(f"❌ Map rendering error encountered: {e}")
