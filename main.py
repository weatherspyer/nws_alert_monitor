import os
import json
import asyncio
import aiohttp
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from src.engine import WeatherStreamEngine

# Load local environment secrets if running on your MacBook Air
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def parse_nws_time(iso_str):
    """
    Parses an ISO-8601 timestamp string from the NWS API, converts it
    explicitly to Eastern Time (America/New_York), and formats it into 
    'M/D/YYYY I:M p' (e.g., '7/3/2026 11:00PM').
    """
    if not iso_str:
        return "N/A"
    try:
        # fromisoformat handles offsets natively
        dt = datetime.fromisoformat(iso_str)
        
        # Convert explicitly to Eastern Time Zone (handles EST/EDT transitions dynamically)
        eastern_tz = ZoneInfo("America/New_York")
        dt_eastern = dt.astimezone(eastern_tz)
        
        # Format string, then split to strip out leading zeros manually
        formatted_time = dt_eastern.strftime("%m/%d/%Y %I:%M%p")
        parts = formatted_time.split(" ")
        date_part = "/".join([str(int(x)) for x in parts[0].split("/")])
        time_part = parts[1].lstrip("0")
        
        return f"{date_part} {time_part}"
    except Exception as e:
        print(f"⚠️ Internal parser failed to extract ISO timestamp: {e}")
        return "N/A"

def generate_iem_link(alert):
    """
    Parses the VTEC string from the NWS API and constructs a dynamic
    Iowa Environmental Mesonet (IEM) VTEC browser link.
    """
    properties = alert.get("properties", {})
    vtec_list = properties.get("parameters", {}).get("VTEC", [])
    fallback_link = properties.get("@id", "https://www.weather.gov")
    
    if not vtec_list:
        return fallback_link
        
    try:
        vtec_string = vtec_list[0]
        parts = vtec_string.split('.')
        
        wfo = parts[2]          # e.g., KCLE
        phenomena = parts[3]    # e.g., XH
        significance = parts[4] # e.g., W
        event_id = int(parts[5]) # Strips leading zeros (e.g., 0001 -> 1)
        
        sent_time = properties.get("sent", "")
        year = sent_time.split("-")[0] if sent_time else "2026"
        
        return f"https://mesonet.agron.iastate.edu/vtec/?year={year}&wfo={wfo}&phenomena={phenomena}&significance={significance}&eventid={event_id}"
    except Exception as e:
        print(f"⚠️ Error parsing VTEC string for IEM link: {e}")
        return fallback_link

def generate_iem_image_link(alert):
    """
    Parses the VTEC string from the NWS API and constructs a dynamic
    Iowa Environmental Mesonet (IEM) GIS radmap image URL.
    """
    properties = alert.get("properties", {})
    vtec_list = properties.get("parameters", {}).get("VTEC", [])
    
    if not vtec_list:
        return None
        
    try:
        vtec_string = vtec_list[0]
        parts = vtec_string.split('.')
        
        wfo = parts[2]          # e.g., KCLE
        phenomena = parts[3]    # e.g., XH
        significance = parts[4] # e.g., W
        
        # Keep leading zeros by padding the integer back to 4 digits (e.g., 1 -> 0001)
        event_id_padded = f"{int(parts[5]):04d}"
        
        sent_time = properties.get("sent", "")
        year = sent_time.split("-")[0] if sent_time else "2026"
        
        return (
            f"https://mesonet.agron.iastate.edu/GIS/radmap.php"
            f"?layers=nexrad&layers=sbw&layers=sbwh&layers=uscounties"
            f"&vtec={year}.{wfo}.{phenomena}.{significance}.{event_id_padded}"
        )
    except Exception as e:
        print(f"⚠️ Error parsing VTEC string for IEM radar image: {e}")
        return None

def generate_iem_text_link(alert):
    """
    Parses parameters from the NWS API to construct an Iowa Environmental Mesonet
    AFOS text product image link (e.g., .../wx/afos/202606301637_NPWPBZ.png).
    """
    properties = alert.get("properties", {})
    parameters = properties.get("parameters", {})
    fallback_link = properties.get("@id", "https://www.weather.gov")
    
    awips_list = parameters.get("AWIPSidentifier", [])
    wmo_list = parameters.get("WMOidentifier", [])
    
    if not awips_list or not wmo_list:
        return fallback_link
        
    try:
        # 1. Extract AWIPS ID (e.g., "NPWPBZ")
        awips_id = awips_list[0].strip()
        
        # 2. Extract day/time digits from WMO (e.g., "WWUS71 KPBZ 301637" -> "301637")
        wmo_string = wmo_list[0].strip()
        wmo_parts = wmo_string.split()
        time_digits = wmo_parts[-1]
        
        # 3. Pull Year & Month dynamically from 'sent' transformed cleanly to UTC
        sent_raw = properties.get("sent", "")
        if sent_raw:
            dt_utc = datetime.fromisoformat(sent_raw).astimezone(timezone.utc)
            year_month = dt_utc.strftime("%Y%m")
        else:
            year_month = datetime.now(timezone.utc).strftime("%Y%m")
            
        return f"https://mesonet.agron.iastate.edu/wx/afos/{year_month}{time_digits}_{awips_id}.png"
    except Exception as e:
        print(f"⚠️ Error parsing layout for AFOS text link: {e}")
        return fallback_link

def get_vtec_action_data(alert):
    """
    Extracts the 3-letter action code from the VTEC string and maps it
    to human-readable alert lifecycle text and its corresponding literal Unicode emoji.
    Returns (action_text, emoji_string) or ("", "") if not found.
    """
    vtec_actions = {
        "NEW": ("New event", "🆕"),
        "CON": ("Event continued", "🔁"),
        "EXT": ("Event extended (time)", "➕"),
        "EXA": ("Event extended (area)", "➕"),
        "EXB": ("Event extended (time and area)", "➕"),
        "UPG": ("Event upgraded", "⏫"),
        "CAN": ("Event cancelled", "❌"),
        "EXP": ("Event expired", "⏳"),
        "COR": ("Correction", "✍️"),
        "ROU": ("Routine", "🔁")
    }
    
    properties = alert.get("properties", {})
    vtec_list = properties.get("parameters", {}).get("VTEC", [])
    
    if not vtec_list:
        return "", ""
        
    try:
        vtec_string = vtec_list[0]
        parts = vtec_string.split('.')
        action_code = parts[1].upper() # Grabs the item right after the first period
        return vtec_actions.get(action_code, ("", ""))
    except Exception:
        return "", ""

def format_slack_block_kit(alert, location_name):
    """
    Assembles a complete Slack Block Kit payload replicating the requested format guidelines.
    """
    properties = alert.get("properties", {})
    alert_name = properties.get("event", "Unknown Alert")
    
    # Generate dynamic links using utility logic
    alert_link = generate_iem_link(alert)
    alert_image_link = generate_iem_image_link(alert)
    alert_link_text = generate_iem_text_link(alert)
    
    # Parse timestamps using the correct 'onset' field for start time
    onset_raw = properties.get("onset")
    ends_raw = properties.get("ends") or properties.get("expires")
    
    effective_time = parse_nws_time(onset_raw)  
    ends_time = parse_nws_time(ends_raw)
    
    # Generate current UTC epoch timestamp cleanly
    unix_time = int(datetime.now(timezone.utc).timestamp())
    
    # Fetch the dynamic VTEC lifestyle string and literal emoji
    action_prefix, action_emoji = get_vtec_action_data(alert)
    
    if action_prefix:
        # Added a clean newline layout split (\n) to drop the warning info to the second row
        alert_body = f"{action_prefix}\n{alert_name} from {effective_time} to {ends_time} for {location_name}"
        push_title = f"{action_emoji} {alert_name.upper()} for {location_name.upper()} from {effective_time} to {ends_time}"
        header_text = f"{action_emoji} {alert_name.upper()} for\n{location_name.upper()}"
    else:
        alert_body = f"{alert_name} from {effective_time} to {ends_time} for {location_name}"
        push_title = f"{alert_name.upper()} for {location_name.upper()} from {effective_time} to {ends_time}"
        header_text = f"{alert_name.upper()} for\n{location_name.upper()}"
    
    # Set fallback top-level channel icon string variables
    if "Tornado" in alert_name or "Severe Thunderstorm" in alert_name:
        icon_emoji = "🚨"
    else:
        icon_emoji = "⚠️"
        
    # Build core blocks layout matrix
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": header_text,
                "emoji": True
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": alert_body
            }
        }
    ]
    
    # Safely inject the image block ONLY if an active VTEC block exists
    if alert_image_link:
        blocks.append({
            "type": "image",
            "image_url": alert_image_link,
            "alt_text": "Storm Based Warning Map"
        })
        
    # Complete rest of layout block assignment tracking with side-by-side action buttons
    blocks.extend([
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "More Info"
                    },
                    "style": "primary",
                    "url": alert_link,
                    "action_id": "more_info_button"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Text Product"
                    },
                    "style": "primary",
                    "url": alert_link_text,
                    "action_id": "text_product_button"
                }
            ]
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"<@weatherspyer>\t<!date^{unix_time}^{{date_pretty}} {{time}}|NA>"
                }
            ]
        },
        {
            "type": "divider"
        }
    ])
        
    payload = {
        "icon_emoji": icon_emoji,
        "text": push_title, 
        "blocks": blocks
    }
    return payload

async def send_slack_alert(alert, location_name):
    """
    Dispatches the formatted block kit payload directly to the Slack Webhook channel.
    """
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook_url:
        print("❌ Critical Deployment Error: SLACK_WEBHOOK_URL is missing!")
        return

    payload = format_slack_block_kit(alert, location_name)
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=payload) as response:
                if response.status == 200:
                    print(f"✅ Dispatched [{alert['properties']['event']}] payload node to Slack successfully.")
                else:
                    print(f"⚠️ Slack incoming webhook server rejected payload data. Status: {response.status}")
    except Exception as e:
        print(f"❌ Error dispatching asynchronous event webhook: {e}")

async def main():
    print("🚀 Initializing cloud environment structures...")
    
    # Path to your custom local JSON file relative to your project root
    config_path = os.path.join("config", "locations.json")
    
    try:
        with open(config_path, "r") as f:
            places_to_monitor = json.load(f)
        print(f"📂 Loaded locations configuration from '{config_path}' successfully.")
    except FileNotFoundError:
        print(f"❌ Error: Configuration file not found at '{config_path}'. Falling back to empty track matrix.")
        places_to_monitor = {}
    except json.JSONDecodeError:
        print(f"❌ Error: '{config_path}' is corrupted or contains invalid formatting.")
        places_to_monitor = {}
    
    if not places_to_monitor:
        print("⚠️ Monitoring matrix is completely empty. Stream engine aborted.")
        return

    engine = WeatherStreamEngine(places_to_monitor)
    await engine.start_loop(send_slack_alert)

if __name__ == "__main__":
    asyncio.run(main())
