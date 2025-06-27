from flask import Flask, jsonify
from flask_cors import CORS
import requests
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)
CORS(app)

SHEET_NAME = "Users"
SPREADSHEET_ID = "1DQvAegPUtDDsYnxJ2FOnYQvWRy0Z96zgl9AYEkd8usI"
creds = Credentials.from_service_account_file("credentials.json", scopes=[
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
])
client = gspread.authorize(creds)
sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

def normalize(city):
    return city.strip().replace("־", "-").replace("–", "-").replace("״", "").replace("'", "").lower()

def city_match(user_city, alert_data):
    user_city_norm = normalize(user_city)
    candidates = alert_data if isinstance(alert_data, list) else [alert_data]
    for loc in candidates:
        loc_norm = normalize(loc)
        if user_city_norm in loc_norm or loc_norm in user_city_norm:
            return True
        if user_city_norm == "אשדוד" and loc_norm.startswith("אשדוד"):
            return True
        if user_city_norm == "מודיעין" and "מודיעין" in loc_norm:
            return True
    return False

def fetch_alerts(date_str):
    url = f"https://alerts-history.oref.org.il/Shared/Ajax/GetAlarmsHistory.aspx?lang=he&fromDate={date_str}&toDate={date_str}&mode=0"
    res = requests.get(url)
    return [a for a in res.json() if str(a.get("category")) == "1"]

@app.route("/check-alerts", methods=["GET"])
def check_alerts():
    users = sheet.get_all_records()
    print(f"👥 נשלפו {len(users)} משתמשים מהגיליון")
    date_today = datetime.now().strftime("%d.%m.%Y")
    alerts = fetch_alerts(date_today)
    print(f"📅 {date_today}: נמצאו {len(alerts)} התראות")

    for i, u in enumerate(users, start=2):
        user_city = u.get("city")
        matched = [a for a in alerts if city_match(user_city, a["data"])]
        if matched:
            last_alert = matched[-1]["date"] + " " + matched[-1]["time"]
            sheet.update_cell(i, u.keys().index("last_alert") + 1, last_alert)
            print(f"🔴 {u['name']} ({user_city}) → {last_alert}")
        else:
            print(f"🟢 {u['name']} ({user_city}) → אין אזעקות")

    print("\n✅ בדיקה הושלמה")
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    print("🚀 Flask server is starting...")
    app.run(debug=True)
