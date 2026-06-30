import os
import sys
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# Import your WeatherStreamEngine class from the src directory
try:
    from src.engine import WeatherStreamEngine
except ImportError as e:
    print(f"❌ Critical Error: Could not import WeatherStreamEngine from 'src/engine'. Details: {e}")
    sys.exit(1)

# ==========================================
# 1. LIGHTWEIGHT WEB SERVER FOR RENDER FREE TIER
# ==========================================
class RenderHealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"NWS Weather Alert Monitor is running smoothly on Render free tier.")

    def log_message(self, format, *args):
        return

def start_health_check_server():
    port = int(os.environ.get("PORT", 10000))
    server_address = ("0.0.0.0", port)
    try:
        httpd = HTTPServer(server_address, RenderHealthCheckHandler)
        print(f"🌍 Internal health check server listening on port {port}...")
        httpd.serve_forever()
    except Exception as e:
        print(f"⚠️ Port binder warning: {e}")

# ==========================================
# 2. DUMMY CALLBACK FUNCTION (FOR TESTING)
# ==========================================
async def placeholder_callback(alert, location_name):
    """
    This replaces your slack dispatch function temporarily so the engine 
    has somewhere to send alerts when it finds them.
    """
    event = alert["properties"].get("event", "Unknown Alert")
    print(f"🚨 NEW ALERT FOUND FOR {location_name}: {event}")

# ==========================================
# 3. MAIN EXECUTION ENTRYPOINT
# ==========================================
if __name__ == "__main__":
    print("🚀 Initializing NWS Weather Monitoring Engine setup...")

    if not os.getenv("SLACK_WEBHOOK_URL"):
        print("❌ Critical Deployment Error: SLACK_WEBHOOK_URL is missing!")
        sys.exit(1)

    # Launch the health check server inside a separate background thread
    web_thread = threading.Thread(target=start_health_check_server, daemon=True)
    web_thread.start()

    print("✅ Port binder active. Defining monitored locations...")

    # Define the coordinates you want to pass into your engine
    # (Feel free to adjust these coordinates or add more locations here)
    my_locations = {
        "Pittsburgh Region": {"lat": 40.4406, "lon": -79.9959},
        "Cleveland Region": {"lat": 41.4993, "lon": -81.6944}
    }

    # Initialize your stream engine class
    engine = WeatherStreamEngine(monitored_places=my_locations)

    print("🛰️ Engine initialized. Starting main asynchronous alerting loop...")

    # Run your engine's start_loop continuously inside asyncio
    try:
        asyncio.run(engine.start_loop(placeholder_callback))
    except KeyboardInterrupt:
        print("\n👋 Monitoring engine manually stopped. Shutting down gracefully.")
    except Exception as e:
        print(f"❌ Unhandled engine failure: {e}")
        sys.exit(1)
