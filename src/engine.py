import asyncio
import aiohttp
import logging

class WeatherStreamEngine:
    def __init__(self, monitored_places: dict):
        self.monitored_places = monitored_places
        # User-Agent string to satisfy NWS API security policies
        self.headers = {"User-Agent": "(WeatherStreamerProject, weather_monitor_app@internal.com)"}
        self.seen_alerts = set()

    async def fetch_point_alerts(self, session, lat, lon):
        """
        Queries the NWS endpoint for a specific coordinate point.
        Pulls both zone-based alerts and precise storm polygons.
        """
        url = f"https://api.weather.gov/alerts/active?point={lat},{lon}"
        try:
            async with session.get(url, headers=self.headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("features", [])
                elif response.status == 429:
                    print("⚠️ Hit NWS rate limit. Backing off safely...")
        except Exception as e:
            print(f"⚠️ Stream connection glitch: {e}")
        return []

    async def start_loop(self, callback_func):
        """
        Infinite event loop that checks coordinates every 15 seconds.
        """
        async with aiohttp.ClientSession() as session:
            print("🚀 Pinpoint Live Stream Engine active. Monitoring coordinate feeds...")
            while True:
                # Heartbeat indicator to verify the container is alive in Render logs
                print(f"🔄 Scanning for active NWS alerts across {len(self.monitored_places)} regional nodes...")
                
                for location_name, data in self.monitored_places.items():
                    lat, lon = data["lat"], data["lon"]
                    alerts = await self.fetch_point_alerts(session, lat, lon)
                    
                    for alert in alerts:
                        alert_id = alert["properties"]["id"]
                        
                        # Only handle the alert if it hasn't been processed yet
                        if alert_id not in self.seen_alerts:
                            self.seen_alerts.add(alert_id)
                            await callback_func(alert, location_name)
                            
                # Sleep interval to prevent API bans or spamming
                await asyncio.sleep(15)
