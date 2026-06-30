import asyncio
import aiohttp

class WeatherStreamEngine:
    def __init__(self, monitored_places):
        """
        Initializes the weather engine with location mappings.
        monitored_places: dict of {"Location Name": {"lat": float, "lon": float}}
        """
        self.monitored_places = monitored_places
        self.seen_alerts = set()
        self.seen_skips = set()  # Tracks skipped IDs to prevent log spam
        self.headers = {
            "User-Agent": "(WeatherStreamerProject, weather_monitor_app@internal.com)"
        }

    async def fetch_point_alerts(self, session, lat, lon):
        """
        Queries the precise active alerts coordinate endpoint for a specific point.
        """
        url = f"https://api.weather.gov/alerts/active?point={lat},{lon}"
        try:
            async with session.get(url, headers=self.headers, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("features", [])
                else:
                    print(f"⚠️ NWS API Error down link checkpoint. HTTP Status: {response.status}")
                    return []
        except Exception as e:
            print(f"❌ Failed to reach NWS API node: {e}")
            return []

    async def start_loop(self, callback_func):
        """
        Infinite event loop that checks coordinates every 15 seconds.
        TEMPORARILY MODIFIED: Allows CON alerts to pass through to Slack 
        for live format testing.
        """
        async with aiohttp.ClientSession() as session:
            print("🚀 Pinpoint Live Stream Engine active. Monitoring coordinate feeds...")
            while True:
                print(f"🔄 Scanning for active NWS alerts across {len(self.monitored_places)} regional nodes...")
                
                for location_name, data in self.monitored_places.items():
                    lat, lon = data["lat"], data["lon"]
                    alerts = await self.fetch_point_alerts(session, lat, lon)
                    
                    for alert in alerts:
                        properties = alert.get("properties", {})
                        alert_id = properties.get("id")
                        event_name = properties.get("event", "Unknown Alert Type")
                        
                        # --- VTEC CONTINUANCE FILTER ---
                        vtec_list = properties.get("parameters", {}).get("VTEC", [])
                        is_continuance = False
                        is_critical_convective = False
                        
                        if vtec_list:
                            vtec_string = vtec_list[0]
                            
                            if ".CON." in vtec_string:
                                is_continuance = True
                                
                            if ".TO.W." in vtec_string or ".SV.W." in vtec_string:
                                is_critical_convective = True
                        
                        # Handle the skipped tracking log
                        if is_continuance and not is_critical_convective:
                            if alert_id not in self.seen_skips:
                                self.seen_skips.add(alert_id)
                                print(f"ℹ️ TEST MODE: Logging and FORWARDING CON update for [{event_name}] in {location_name}.")
                            
                            # --- TESTING BYPASS ---
                            # Commented out to let CON alerts pass into Slack for formatting verification
                            # continue 
                        # -------------------------------
                        
                        # Only handle the alert if it hasn't been processed yet
                        if alert_id not in self.seen_alerts:
                            self.seen_alerts.add(alert_id)
                            await callback_func(alert, location_name)
                            
                await asyncio.sleep(15)
