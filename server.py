from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from datetime import datetime
import os
import json
from google.oauth2.service_account import Credentials
import gspread

app = Flask(__name__)
CORS(app)

# התחברות לחשבון השירות דרך משתנה סביבה
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
google_creds = json.loads(os.environ["GOOGLE_CREDENTIALS"])
creds = Credentials.from_service_account_info(google_creds, scopes=scope)
client = gspread.authorize(creds)

SHEET_NAME = "Users"
SPREADSHEET_ID = "1DQvAegPUtDDsYnxJ2FOnYQvWRy0Z96zgl9AYEkd8usI"
sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

USERS_API = "https://sheetdb.io/api/v1/v88pii4vv3hni"

def normalize(city):
    return city.strip().replace("־", "-").replace("–", "-").replace("״", "").replace("'", "").lower()

def city_match(user_city, alert_data):
    user_city_norm = normalize(user_city)
    if isinstance(alert_data, list):
        candidates = alert_data
    elif isinstance(alert_data, str):
        candidates = [alert_data]
    else:
        return False

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

def fetch_users():
    res = requests.get(USERS_API)
    users = res.json()
    print(f"👥 נשלפו {len(users)} משתמשים מהטבלה")
    return users

def update_user_last_alert(name, alert_date, alert_time):
    url = f"{USERS_API}/name/{name}"
    data = { "last_alert": f"{alert_date} {alert_time}" }
    res = requests.patch(url, json=data)
    if res.status_code == 200:
        print(f"✔️ עודכן last_alert עבור {name}")
    else:
        print(f"⚠️ שגיאה בעדכון last_alert עבור {name}: {res.status_code}")

@app.route("/check-alerts", methods=["GET"])
def check_alerts():
    today = datetime.now().strftime("%d.%m.%Y")
    users = fetch_users()
    alerts = fetch_alerts(today)

    result = []
    print(f"\n📅 {today}: נמצאו {len(alerts)} התראות")
    print("\n📊 תוצאות לפי משתמש:")
    print("───────────────────────────────")

    for u in users:
        user_c = u.get("city")
        matched = [a for a in alerts if city_match(user_c, a["data"])]
        alert_list = [{"date": a["date"], "time": a["time"]} for a in sorted(matched, key=lambda x: x["alertDate"])]

        if alert_list:
            print(f"🔴 {u['name']} ({user_c}) → נמצאו {len(alert_list)} אזעקות")
            for a in alert_list:
                print(f"    • {a['date']} בשעה {a['time']}")
            last_alert = alert_list[-1]
            update_user_last_alert(u["name"], last_alert["date"], last_alert["time"])
        else:
            print(f"🟢 {u['name']} ({user_c}) → לא נמצאה אזעקה")

        result.append({
            "name": u["name"],
            "city": user_c,
            "alerts": alert_list
        })

    print("───────────────────────────────")
    print(f"\n✅ סיום בדיקה - {len(result)} משתמשים עובדו\n")
    return jsonify(result)

if __name__ == "__main__":
    print("🚀 Flask server is starting...")
    app.run(debug=True)
