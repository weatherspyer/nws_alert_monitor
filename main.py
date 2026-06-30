import asyncio
import logging
import sys
import os

# Ensure the script can locate modules inside the src/ directory
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import your core engine checking logic
# (Make sure your engine script has an async 'check_nws_alerts' function)
try:
    from src.engine import check_nws_alerts
except ImportError:
    # Fallback placeholder if your file structural layout names differ slightly
    async def check_nws_alerts():
        logging.warning("⚠️ 'src.engine.check_nws_alerts' not found. Check your file naming structures.")
        await asyncio.sleep(1)

# Configure logging to output directly to Render's live dashboard stream
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

async def main():
    logging.info("🚀 NWS Weather Monitoring Engine initialized successfully!")
    logging.info("🌍 Mode: Continuous 24/7 Cloud Background Worker")
    
    # Verify the Slack Webhook secret was securely injected by the host environment
    if not os.getenv("SLACK_WEBHOOK_URL"):
        logging.warning("⚠️ SLACK_WEBHOOK_URL environment variable is missing! Dispatches may fail.")
    else:
        logging.info("🔒 Secure Slack Webhook environment variable detected.")

    # Core infinite cloud runtime loop
    while True:
        try:
            logging.info("📡 Requesting latest alert updates from NWS active streams...")
            
            # Execute your core spatial scraping and matching logic
            await check_nws_alerts()
            
        except asyncio.CancelledError:
            logging.info("🛑 Cloud container received SIGTERM shutdown signal. Exiting cleanly.")
            break
        except Exception as e:
            # Crucial Guardrail: Catches NWS API drops, 502 Bad Gateways, 
            # and DNS timeouts so the container never encounters a fatal crash.
            logging.error(f"💥 Engine loop encountered an unexpected runtime error: {e}")
            logging.info("🔄 Automatically cooling down before restarting stream connection...")
            await asyncio.sleep(10)  # Short safety buffer block following a bad crash
            
        # Poll interval spacing. The NWS edge cache updates every 1-2 minutes.
        logging.info("😴 Polling execution cycle complete. Sleeping for 60 seconds...")
        await asyncio.sleep(60)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("👋 Execution interrupted manually via keyboard. Shutting down.")
