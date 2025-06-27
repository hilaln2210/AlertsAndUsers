from flask import Flask, jsonify
from flask_cors import CORS
import requests
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

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

def fetch_users():
    res = requests.get(USERS_API)
    users = res.json()
    print(f"👥 נשלפו {len(users)} משתמשים מהטבלה")
    return users

def fetch_alerts_range_multi(from_date, to_date):
    start = datetime.strptime(from_date, "%d.%m.%Y")
    end = datetime.strptime(to_date, "%d.%m.%Y")
    all_alerts = []

    while start <= end:
        date_str = start.strftime("%d.%m.%Y")
        url = f"https://alerts-history.oref.org.il/Shared/Ajax/GetAlarmsHistory.aspx?lang=he&fromDate={date_str}&toDate={date_str}&mode=0"
        res = requests.get(url)
        alerts = [a for a in res.json() if str(a.get("category")) == "1"]
        print(f"📅 {date_str}: נמצאו {len(alerts)} התראות")
        all_alerts.extend(alerts)
        start += timedelta(days=1)

    print(f"\n📦 סה״כ {len(all_alerts)} התראות בכל הטווח")
    return all_alerts

def update_last_alert(name, last_str):
    url = f"{USERS_API}/name/{name}"
    payload = { "data": { "last_alert": last_str } }
    res = requests.patch(url, json=payload)
    if res.status_code == 200:
        print(f"📌 עודכן last_alert עבור {name}: {last_str}")
    else:
        print(f"⚠️ שגיאה בעדכון last_alert עבור {name}")

@app.route("/check-alerts", methods=["GET"])
def check_alerts():
    today = datetime.now().strftime("%d.%m.%Y")
    users = fetch_users()
    alerts = fetch_alerts_range_multi(today, today)

    result = []
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
            latest = alert_list[-1]
            last_str = f"{latest['date']} {latest['time']}"
            update_last_alert(u["name"], last_str)
        else:
            print(f"🟢 {u['name']} ({user_c}) → לא נמצאה אזעקה")

        result.append({
            "name": u["name"],
            "city": user_c,
            "alerts": alert_list,
            "last_alert": alert_list[-1] if alert_list else None
        })

    print("───────────────────────────────")
    print(f"\n✅ סיום בדיקה - {len(result)} משתמשים עובדו\n")
    return jsonify(result)

if __name__ == "__main__":
    print("🚀 Flask server is starting on http://localhost:5000 ...")
    app.run(debug=True)
