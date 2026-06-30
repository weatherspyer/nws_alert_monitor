import asyncio
import aiohttp
import logging

class WeatherStreamEngine:
    def __init__(self, monitored_places: dict):
        self.monitored_places = monitored_places
        # CRITICAL: Keep your email inside to prevent security firewall drops
        self.headers = {"User-Agent": "(WeatherStreamerProject, your_email@example.com)"}
        self.seen_alerts = set()

    async def fetch_point_alerts(self, session, lat, lon):
        # The ultimate NWS endpoint for a house pinpoint: pulls BOTH zones and storm polygons
        url = f"https://api.weather.gov/alerts/active?point={lat},{lon}"
        try:
            async with session.get(url, headers=self.headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("features", [])
                elif response.status == 429:
                    logging.warning("⚠️ Hit NWS rate limit. Backing off...")
        except Exception as e:
            logging.error(f"Stream connection glitch: {e}")
        return []

    async def start_loop(self, callback_func):
        async with aiohttp.ClientSession() as session:
            print("🚀 Pinpoint Live Stream Engine active. Monitoring your precise coordinates...")
            while True:
                for location_name, data in self.monitored_places.items():
                    lat, lon = data["lat"], data["lon"]
                    alerts = await self.fetch_point_alerts(session, lat, lon)
                    
                    for alert in alerts:
                        alert_id = alert["properties"]["id"]
                        
                        if alert_id not in self.seen_alerts:
                            self.seen_alerts.add(alert_id)
                            await callback_func(alert, location_name)
                            
                # Sleep between loops to respect rate limits
                await asyncio.sleep(15) 
