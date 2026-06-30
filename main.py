import os
import sys
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# Import your core engineering logic from the src directory
try:
    from src.engine import run_monitoring_loop
except ImportError as e:
    print(f"❌ Critical Error: Could not import monitoring loop from 'src/engine'. Ensure your 'src' folder contains 'engine.py'. Details: {e}")
    sys.exit(1)

# ==========================================
# 1. LIGHTWEIGHT WEB SERVER FOR RENDER FREE TIER
# ==========================================
class RenderHealthCheckHandler(BaseHTTPRequestHandler):
    """
    Responds to Render's internal port scans and health checks
    to prevent 'Port scan timeout' deployment failures.
    """
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"📡 NWS Weather Alert Monitor is running smoothly on Render free tier.")

    def log_message(self, format, *args):
        # Silence standard HTTP request logging to keep the dashboard log clean
        return

def start_health_check_server():
    """
    Binds to the port provided by Render's environment, defaulting to 10000.
    """
    port = int(os.environ.get("PORT", 10000))
    server_address = ("0.0.0.0", port)
    
    try:
        httpd = HTTPServer(server_address, RenderHealthCheckHandler)
        print(f"🌍 Internal health check server listening on port {port}...")
        httpd.serve_forever()
    except Exception as e:
        print(f"⚠️ Port binder warning: {e}")

# ==========================================
# 2. MAIN EXECUTION ENTRYPOINT
# ==========================================
if __name__ == "__main__":
    print("🚀 Initializing NWS Weather Monitoring Engine setup...")

    # Validate that the necessary environment variable is injected before booting
    if not os.getenv("SLACK_WEBHOOK_URL"):
        print("❌ Critical Deployment Error: SLACK_WEBHOOK_URL is missing from environment variables!")
        print("Please inject it securely in your Render dashboard under the 'Environment' tab.")
        sys.exit(1)

    # Launch the health check server inside a separate background thread.
    # This immediately satisfies Render's port checks while leaving the main
    # thread open for your infinite async polling workflow.
    web_thread = threading.Thread(target=start_health_check_server, daemon=True)
    web_thread.start()

    print("✅ Port binder active. Starting main asynchronous alerting loop...")

    # Run your engine loop continuously inside the main asyncio context
    try:
        asyncio.run(run_monitoring_loop())
    except KeyboardInterrupt:
        print("\n👋 Monitoring engine manually stopped. Shutting down gracefully.")
    except Exception as e:
        print(f"❌ Unhandled engine failure: {e}")
        sys.exit(1)
