import datetime
import aiohttp
import logging
import re
import json

os.getenv("SLACK_WEBHOOK_URL")

def format_iso_time(iso_str):
    if not iso_str:
        return "N/A"
    try:
        dt_part = iso_str.split("T")[0]
        tm_part = iso_str.split("T")[1][:5]
        return f"{dt_part} at {tm_part}"
    except Exception:
        return iso_str

def parse_vtec(alert_payload):
    """
    Helper function to parse common VTEC attributes using regex.
    """
    payload_string = json.dumps(alert_payload)
    # Matches: /O.NEW.KOAX.SV.W.0267.260630T0018Z-260630T0100Z/
    vtec_pattern = r"/[A-Z]\.[A-Z]{3}\.([A-Z]{4})\.([A-Z]{2})\.([A-Z])\.(\d{4})\.(\d{6})T(\d{4})Z-"
    match = re.search(vtec_pattern, payload_string)
    return match

def generate_iem_link(alert_payload):
    match = parse_vtec(alert_payload)
    if match:
        try:
            wfo = match.group(1)          
            phenomena = match.group(2)    
            significance = match.group(3) 
            event_id = str(int(match.group(4))) 
            
            props = alert_payload.get("properties", {})
            onset_time = props.get("onset", "")
            year = onset_time.split("-")[0] if onset_time else "2026"
            
            return (
                f"https://mesonet.agron.iastate.edu/vtec/?"
                f"year={year}&wfo={wfo}&phenomena={phenomena}&"
                f"significance={significance}&eventid={event_id}&"
                f"tab=textdata&radar=USCOMP"
            )
        except Exception as e:
            logging.error(f"⚠️ Error formatting matched VTEC string: {e}")

    try:
        props = alert_payload.get("properties", {})
        ugc_codes = props.get("geocode", {}).get("UGC", [])
        state_code = ugc_codes[0][:2].upper() if ugc_codes else "PA"
        return f"https://www.weather.gov/alerts?area={state_code}"
    except Exception:
        return "https://www.weather.gov/alerts"

def generate_afos_image_link(alert_payload):
    """
    Generates a link to the static AFOS text product image on the IEM server.
    """
    match = parse_vtec(alert_payload)
    if not match:
        return None
        
    try:
        wfo = match.group(1)          # e.g., KOAX
        phenomena = match.group(2)    # e.g., SV
        date_part = match.group(5)    # e.g., 260630
        time_part = match.group(6)    # e.g., 0018
        
        # 1. Expand the 2-digit year to a 4-digit year (e.g., "26" -> "2026")
        year_prefix = "20" if int(date_part[:2]) < 90 else "19"
        timestamp = f"{year_prefix}{date_part}{time_part}"
        
        # 2. Map the phenomena shorthand code to the 3-letter AFOS standard
        afos_map = {"SV": "SVR", "TO": "TOR", "FF": "FFW", "MA": "MWW"}
        afos_product = afos_map.get(phenomena, f"{phenomena} ")  # Fallback padding
        
        # 3. Strip leading 'K' from the WFO identifier if present (e.g., KOAX -> OAX)
        wfo_short = wfo[1:] if wfo.startswith("K") else wfo
        
        return f"https://mesonet.agron.iastate.edu/wx/afos/{timestamp}_{afos_product}{wfo_short}.png"
    except Exception as e:
        logging.error(f"⚠️ Error generating AFOS image link: {e}")
        return None

async def dispatch_alert(alert_payload, location_name):
    props = alert_payload["properties"]
    event = props.get("event", "Weather Event")
    severity = props.get("severity", "Unknown")
    headline = props.get("headline", "No headline provided.")
    description = props.get("description", "No detailed description provided.")
    instruction = props.get("instruction", "")
    
    start_time = format_iso_time(props.get("onset"))
    end_time = format_iso_time(props.get("ends"))
    
    iem_tracking_url = generate_iem_link(alert_payload)
    afos_image_url = generate_afos_image_link(alert_payload)
    
    # 💻 TERMINAL LOGGING: Log both endpoints out to the core console
    print("\n" + "=" * 80)
    print(f"📡 INGESTED ALERT: {event} ({severity}) for {location_name}")
    print(f"🔗 VTEC BROWSER:   {iem_tracking_url}")
    if afos_image_url:
        print(f"🖼️ AFOS TEXT IMG:  {afos_image_url}")
    print("=" * 80 + "\n")
    
    if severity in ["Extreme", "Severe"]:
        emoji = "🔴"
        color = "#ff0000"
    else:
        emoji = "🟡"
        color = "#ecc81a"

    full_text_details = f"*📝 NWS DETAILED LOGS:*\n```{description.strip()}```"
    if instruction:
        full_text_details += f"\n\n*💡 SAFETY INSTRUCTIONS:*\n```{instruction.strip()}```"
    
    # Build your button array dynamically based on whether an AFOS image exists
    action_elements = [
        {
            "type": "button",
            "text": {"type": "plain_text", "text": "🗺️ Open VTEC Browser", "emoji": True},
            "url": iem_tracking_url,
            "action_id": "button_click_nws_link"
        }
    ]
    
    if afos_image_url:
        action_elements.append({
            "type": "button",
            "text": {"type": "plain_text", "text": "📄 View Text Image", "emoji": True},
            "url": afos_image_url,
            "action_id": "button_click_afos_image"
        })
    
    slack_payload = {
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"{emoji} NWS ALERT: {event.upper()}", "emoji": True}
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*📍 Location:* {location_name}"},
                    {"type": "mrkdwn", "text": f"*⚠️ Severity:* {severity}"},
                    {"type": "mrkdwn", "text": f"*⏱️ Starts:* {start_time}"},
                    {"type": "mrkdwn", "text": f"*🛑 Expires:* {end_time}"}
                ]
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*📢 Summary:*\n_{headline}_"}
            },
            {
                "type": "actions",
                "elements": action_elements
            }
        ],
        "attachments": [
            {
                "color": color,
                "blocks": [
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": full_text_details}
                    }
                ]
            }
        ]
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(SLACK_WEBHOOK_URL, json=slack_payload) as response:
                if response.status == 200:
                    print(f"📲 SUCCESS: Pushed dual-button VTEC card to Slack channel.")
                else:
                    logging.error(f"❌ Slack webhook error: HTTP {response.status}")
        except Exception as e:
            logging.error(f"❌ Failed to connect to Slack webhook framework: {e}")
