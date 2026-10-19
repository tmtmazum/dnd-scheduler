import os
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone

import boto3
from flask import Flask, flash, g, redirect, render_template, request, send_from_directory, url_for

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "local-development-key-change-me")
app.config["DYNAMODB_TABLE"] = os.environ.get(
    "DYNAMODB_TABLE", "quest-weekend-availability"
)
app.config["AWS_REGION"] = os.environ.get(
    "AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
).strip().strip("\"'").strip()
app.config["DYNAMODB_ENDPOINT_URL"] = os.environ.get("DYNAMODB_ENDPOINT_URL")

DAYS = (("saturday", "Saturday"), ("sunday", "Sunday"))
TIMES = (
    ("morning", "Morning", "10:30 AM–2:30 PM"),
    ("afternoon", "Afternoon", "1:30–5:00 PM"),
    ("evening", "Evening", "5:00–9:00 PM"),
)
SESSION_META_KEY = "__quest_weekend_meta__"


def add_two_months(start):
    month_index = start.month - 1 + 2
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start.day, monthrange(year, month)[1])
    return date(year, month, day)


def get_weekends(start=None):
    start = start or date.today()
    end = add_two_months(start)
    weekend_map = {}
    current = start
    while current <= end:
        if current.weekday() in (5, 6):
            saturday = current - timedelta(days=(current.weekday() - 5) % 7)
            day_key = "saturday" if current.weekday() == 5 else "sunday"
            weekend_map.setdefault(saturday.isoformat(), []).append(
                {
                    "date": current.isoformat(),
                    "day_key": day_key,
                    "day_title": "Saturday" if day_key == "saturday" else "Sunday",
                    "date_label": f"{current.strftime('%a, %b')} {current.day}",
                }
            )
        current += timedelta(days=1)

    return [
        {"key": key, "days": days}
        for key, days in sorted(weekend_map.items())
    ]


def get_table():
    if "dynamodb_table" not in g:
        options = {"region_name": app.config["AWS_REGION"]}
        if app.config["DYNAMODB_ENDPOINT_URL"]:
            options["endpoint_url"] = app.config["DYNAMODB_ENDPOINT_URL"]
        dynamodb = boto3.resource("dynamodb", **options)
        g.dynamodb_table = dynamodb.Table(app.config["DYNAMODB_TABLE"])
    return g.dynamodb_table


@app.get("/img/<path:filename>")
def party_image(filename):
    return send_from_directory(os.path.join(app.root_path, "img"), filename)


def load_participants():
    table = get_table()
    items = []
    scan_options = {}
    while True:
        response = table.scan(**scan_options)
        items.extend(response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        scan_options["ExclusiveStartKey"] = last_key

    participants = []
    for item in items:
        if item.get("name_key") == SESSION_META_KEY:
            continue
        slots = [
            {"date": slot["date"], "period": slot["period"]}
            for slot in item.get("slots", [])
            if slot.get("period") in {period for period, _, _ in TIMES}
        ]
        participants.append(
            {
                "name": item.get("display_name", item.get("name_key", "Adventurer")),
                "updated_at": item.get("updated_at", ""),
                "slots": sorted(slots, key=lambda slot: (slot["date"], slot["period"])),
            }
        )
    return sorted(participants, key=lambda person: person["name"].casefold())


def load_confirmed_session():
    response = get_table().get_item(Key={"name_key": SESSION_META_KEY})
    item = response.get("Item")
    if not item or not item.get("session_date") or not item.get("period"):
        return None
    return {"date": item["session_date"], "period": item["period"]}


@app.get("/")
def index():
    participants = load_participants()
    weekends = get_weekends()
    date_labels = {
        day["date"]: f"{day['day_title']}, {day['date_label'].split(', ', 1)[1]}"
        for weekend in weekends
        for day in weekend["days"]
    }
    slot_names = {
        f"{day['date']}|{period}": (
            f"{date_labels[day['date']]} · {period_title} {period_time}"
        )
        for weekend in weekends
        for day in weekend["days"]
        for period, period_title, period_time in TIMES
    }
    totals = {
        f"{day['date']}|{period}": sum(
            {"date": day["date"], "period": period} in participant["slots"]
            for participant in participants
        )
        for weekend in weekends
        for day in weekend["days"]
        for period, _, _ in TIMES
    }
    return render_template(
        "index.html",
        days=DAYS,
        times=TIMES,
        weekends=weekends,
        participants=participants,
        slot_names=slot_names,
        totals=totals,
        total_participants=len(participants),
        confirmed_session=load_confirmed_session(),
    )


@app.post("/ready")
def ready():
    name = request.form.get("name", "").strip()
    allowed_dates = {
        day["date"] for weekend in get_weekends() for day in weekend["days"]
    }
    selected_slots = set()
    for selection in request.form.getlist("availability"):
        try:
            session_date, period = selection.split("|", 1)
        except ValueError:
            continue
        if session_date in allowed_dates and period in {time[0] for time in TIMES}:
            selected_slots.add((session_date, period))
    if not name:
        flash("Add your name before submitting your availability.", "error")
        return redirect(url_for("index"))
    if len(name) > 60:
        flash("Names must be 60 characters or fewer.", "error")
        return redirect(url_for("index"))
    name_key = name.casefold()
    if name_key == SESSION_META_KEY:
        flash("That name is reserved for the party board. Choose another name.", "error")
        return redirect(url_for("index"))
    if not selected_slots:
        existing = get_table().get_item(Key={"name_key": name_key}).get("Item")
        if not existing:
            flash("Choose at least one time slot to mark yourself ready.", "error")
            return redirect(url_for("index"))

    get_table().put_item(
        Item={
            "name_key": name_key,
            "display_name": name,
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "slots": [
                {"date": session_date, "period": period}
                for session_date, period in sorted(selected_slots)
            ],
        }
    )
    flash(f"You're on the board, {name}! Your availability is saved.", "success")
    return redirect(url_for("index"))


@app.post("/session/confirm")
def confirm_session():
    session_date = request.form.get("session_date", "")
    period = request.form.get("period", "")
    allowed_dates = {
        day["date"] for weekend in get_weekends() for day in weekend["days"]
    }
    if session_date not in allowed_dates or period not in {time[0] for time in TIMES}:
        flash("Choose a valid weekend slot before confirming the session.", "error")
        return redirect(url_for("index"))
    get_table().put_item(
        Item={
            "name_key": SESSION_META_KEY,
            "record_type": "confirmed_session",
            "session_date": session_date,
            "period": period,
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
    )
    flash("The next session has been confirmed for the party.", "success")
    return redirect(url_for("index"))


@app.post("/session/clear")
def clear_confirmed_session():
    get_table().delete_item(Key={"name_key": SESSION_META_KEY})
    flash("The planned session has been cleared.", "success")
    return redirect(url_for("index"))


@app.post("/availability/reset")
def reset_availability():
    table = get_table()
    items = []
    scan_options = {}
    while True:
        response = table.scan(**scan_options)
        items.extend(response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        scan_options["ExclusiveStartKey"] = last_key
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for item in items:
        name_key = item.get("name_key")
        if not name_key or name_key == SESSION_META_KEY:
            continue
        table.put_item(
            Item={
                "name_key": name_key,
                "display_name": item.get("display_name", name_key),
                "updated_at": now,
                "slots": [],
            }
        )
    flash("All availability selections have been reset. Saved names were kept.", "success")
    return redirect(url_for("index"))


@app.get("/api/availability")
def availability_api():
    participants = load_participants()
    return app.json.response(
        {
            "participants": [
            {"name": person["name"], "slots": person["slots"]}
            for person in participants
            ],
            "confirmed_session": load_confirmed_session(),
        }
    )


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true")
