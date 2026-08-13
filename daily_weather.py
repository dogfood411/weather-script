import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import requests

# ==========================================
# CONFIGURATION
# ==========================================
# Coordinates for Snoqualmie, WA
LAT = 47.5287
LON = -121.8254

# Gmail Settings pulled securely from GitHub Secrets
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
RECIPIENT_EMAIL = "dogfood411@gmail.com"


# ==========================================
# FETCH WEATHER DATA FROM NWS
# ==========================================
def get_nws_data(lat, lon):
    headers = {"User-Agent": "(MyWeatherScript, contact@example.com)"}

    # Step 1: Get Grid Endpoints
    point_url = f"https://api.weather.gov/points/{lat},{lon}"
    res = requests.get(point_url, headers=headers)
    res.raise_for_status()
    properties = res.json()["properties"]

    daily_url = properties["forecast"]
    hourly_url = properties["forecastHourly"]

    # Step 2: Fetch Daily Forecast (for Subject Line & 5-Day View)
    daily_res = requests.get(daily_url, headers=headers).json()
    daily_periods = daily_res["properties"]["periods"]

    # Step 3: Fetch Hourly Forecast
    hourly_res = requests.get(hourly_url, headers=headers).json()
    hourly_periods = hourly_res["properties"]["periods"]

    return daily_periods, hourly_periods


# ==========================================
# FORMAT EMAIL DATA
# ==========================================
def build_email_content(daily_periods, hourly_periods):
    # Today's high/low and headline
    today = daily_periods[0]
    tonight = daily_periods[1] if len(daily_periods) > 1 else None

    high = today["temperature"] if today["isDaytime"] else "N/A"
    low = tonight["temperature"] if tonight else "N/A"

    headline = today["shortForecast"]
    subject_line = f"{headline} {low}-{high}°F"

    # --- Build Hourly Rows (Next 12 Hours) ---
    hourly_rows_html = ""
    for hour in hourly_periods[:12]:
        time_str = hour["startTime"].split("T")[1][:5]  # Format HH:MM
        hour_num = int(time_str.split(":")[0])
        ampm = "AM" if hour_num < 12 else "PM"
        display_hour = hour_num % 12
        if display_hour == 0:
            display_hour = 12

        precip = hour.get("probabilityOfPrecipitation", {}).get("value", 0) or 0

        hourly_rows_html += f"""
        <tr style="border-bottom: 1px solid #e2e8f0;">
            <td style="padding: 8px; font-weight: bold;">{display_hour} {ampm}</td>
            <td style="padding: 8px;">{hour['temperature']}°{hour['temperatureUnit']}</td>
            <td style="padding: 8px; color: #0284c7;">{precip}% rain</td>
            <td style="padding: 8px; color: #64748b;">{hour['shortForecast']}</td>
        </tr>
        """

    # --- Build 5-Day Forecast Rows (Low & High Temps) ---
    five_day_html = ""
    count = 0

    # Start after today's periods (index 2 onwards)
    for idx, period in enumerate(daily_periods[2:], start=2):
        if period["isDaytime"] and count < 5:
            high_temp = period["temperature"]
            unit = period["temperatureUnit"]

            # Match with the corresponding nighttime period for the low temp
            if idx + 1 < len(daily_periods):
                low_temp = daily_periods[idx + 1]["temperature"]
                temp_display = f"{low_temp}° – {high_temp}°{unit}"
            else:
                temp_display = f"{high_temp}°{unit}"

            five_day_html += f"""
            <tr style="border-bottom: 1px solid #e2e8f0;">
                <td style="padding: 10px 8px; font-weight: bold;">{period['name']}</td>
                <td style="padding: 10px 8px; font-size: 15px; font-weight: bold; color: #0284c7; white-space: nowrap;">{temp_display}</td>
                <td style="padding: 10px 8px; color: #475569;">{period['shortForecast']}</td>
            </tr>
            """
            count += 1

    # --- Complete HTML Document ---
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #1e293b; max-width: 550px; margin: 0 auto; padding: 20px;">
        <div style="border: 1px solid #cbd5e1; border-radius: 8px; padding: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
            
            <h2 style="margin-top: 0; color: #0f172a; border-bottom: 2px solid #2563eb; padding-bottom: 8px;">
                Today's Hourly Forecast
            </h2>
            
            <table style="width: 100%; border-collapse: collapse; text-align: left; margin-bottom: 25px;">
                <thead>
                    <tr style="background-color: #f8fafc; border-bottom: 2px solid #e2e8f0;">
                        <th style="padding: 8px;">Time</th>
                        <th style="padding: 8px;">Temp</th>
                        <th style="padding: 8px;">Rain</th>
                        <th style="padding: 8px;">Condition</th>
                    </tr>
                </thead>
                <tbody>
                    {hourly_rows_html}
                </tbody>
            </table>

            <h2 style="color: #0f172a; border-bottom: 2px solid #2563eb; padding-bottom: 8px;">
                5-Day Forecast
            </h2>

            <table style="width: 100%; border-collapse: collapse; text-align: left;">
                <tbody>
                    {five_day_html}
                </tbody>
            </table>

        </div>
    </body>
    </html>
    """

    return subject_line, html_body


# ==========================================
# SEND EMAIL VIA GMAIL
# ==========================================
def send_email(subject, html_body):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECIPIENT_EMAIL

    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(msg)


if __name__ == "__main__":
    try:
        daily_periods, hourly_periods = get_nws_data(LAT, LON)
        subject, html_body = build_email_content(daily_periods, hourly_periods)
        send_email(subject, html_body)
        print(f"Sent email with subject: '{subject}'")
    except Exception as e:
        print(f"Error executing script: {e}")
