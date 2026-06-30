import os
import sys
import json
import asyncio
import threading
import aiohttp
from http.server import HTTPServer, BaseHTTPRequestHandler

# Safeguard the system import pathway
try:
    from src.engine import WeatherStreamEngine
except ImportError as e:
    print(f"❌ Critical Error: Could not import WeatherStreamEngine from 'src/engine'. Details: {e}")
    sys.exit(1)

# ==========================================
# 1. LIGHTWEIGHT HEALTH WEB SERVER
# ==========================================
class RenderHealthCheckHandler(BaseHTTPRequestHandler):
    """
    Responds to internal network port checks to prevent 
    Render Free tier 'Port scan timeouts'.
    """
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"NWS Weather Alert Monitor is running smoothly on Render free tier.")

    def log_message(self, format, *args):
        # Silence HTTP asset logging to keep standard stdout clean
        return

def start_health_check_server():
    port = int(os.environ.get("PORT", 10000))
    server_address = ("0.0.0.0", port)
    try:
        httpd = HTTPServer(server_address, RenderHealthCheckHandler)
        print(f"🌍 Internal health check engine listening on port {port}...")
        httpd.serve_forever()
    except Exception as e:
        print(f"⚠️ Port binder configuration alert: {e}")

# ==========================================
# 2. SLACK DISPATCH CALLBACK
# ==========================================
async def send_slack_alert(alert, location_name):
    """
    Formats raw NWS JSON payloads into rich Slack message attachments.
    """
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    properties = alert["properties"]
    
    event = properties.get("event", "Weather Alert")
    headline = properties.get("headline", "No specific headline available.")
    description = properties.get("description", "No extended descriptions provided.")
    severity = properties.get("severity", "Unknown")
    
    # Establish attachment accent boundaries based on event criteria
    color = "#ff0000" if severity == "Extreme" else "#ff9900" if severity == "Severe" else "#36a64f"

    slack_payload = {
        "attachments": [
            {
                "fallback": f"🚨 {event} issued for {location_name}",
                "color": color,
                "pretext": f"🚨 *New NWS Alert Detected for {location_name}*",
                "title": event,
                "text": f"*{headline}*\n\n{description[:1200]}...",  # Safe boundary split
                "fields": [
                    {"title": "Severity", "value": severity, "short": True},
                    {"title": "Monitored Region", "value": location_name, "short": True}
                ]
            }
        ]
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=slack_payload) as response:
                if response.status == 200:
                    print(f"✅ Successfully dispatched '{event}' to Slack for {location_name}!")
                else:
                    print(f"⚠️ Slack server rejected submission. HTTP Status: {response.status}")
    except Exception as e:
        print(f"❌ Structural webhook drop: {e}")

# ==========================================
# 3. RUNTIME INITIALIZATION
# ==========================================
if __name__ == "__main__":
    print("🚀 Initializing cloud environment structures...")

    # Terminate early if the critical API target isn't present
    if not os.getenv("SLACK_WEBHOOK_URL"):
        print("❌ Critical Deployment Error: SLACK_WEBHOOK_URL is missing!")
        sys.exit(1)

    # Detach the HTTP portal to an isolated thread context
    web_thread = threading.Thread(target=start_health_check_server, daemon=True)
    web_thread.start()

    print("✅ Web port listener isolated. Loading geolocation targets from JSON...")

    # Load locations from locations.json dynamically
    try:
        with open("config/locations.json", "r") as f:
            my_locations = json.load(f)
        print(f"✅ Successfully loaded target keys from JSON: {list(my_locations.keys())}")
    except Exception as e:
        print(f"⚠️ Failed to load locations.json ({e}). Falling back to hardcoded defaults.")
        # Backup regional defaults if the JSON file is missing or formatted incorrectly
        my_locations = {
            "Pittsburgh Region": {"lat": 40.4406, "lon": -79.9959},
            "Cleveland Region": {"lat": 41.4993, "lon": -81.6944}
        }

    # Instantiate our engine object with the dynamic coordinates
    engine = WeatherStreamEngine(monitored_places=my_locations)

    print("🛰️ Systems online. Invoking core asynchronous tracking runtime...")

    try:
        asyncio.run(engine.start_loop(send_slack_alert))
    except KeyboardInterrupt:
        print("\n👋 Process termination received. Shutting down runtime components.")
    except Exception as e:
        print(f"❌ Fatal execution intercept: {e}")
        sys.exit(1)
