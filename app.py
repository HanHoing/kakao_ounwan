from flask import Flask, render_template, request, redirect, send_file
import pandas as pd
import re
from datetime import datetime, timedelta
from collections import defaultdict
import os

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 키워드 리스트
KEYWORDS = ["오운완", "운완", "ㅇㅇㅇ", "오스완", "오산완", "운오ㅓㄴ", "/4", "인증", "수완", "완"]

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/run", methods=["POST"])
def run_analysis():
    out_count = int(request.form["outCount"])
    money = int(request.form["money"])
    file = request.files["chatFile"]
    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(file_path)

    date_pattern = re.compile(r"-{7,}\s*(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일")
    msg_pattern = re.compile(r"^\[(.+?)\]\s+\[.+?\]\s+(.+)")
    time_pattern = re.compile(r"\[(오전|오후)\s*(\d+):(\d+)\]")

    weekly_invited = defaultdict(set)
    daily_counts = defaultdict(lambda: defaultdict(int))
    already_counted = set()

    photo_buffer = None
    keyword_buffer = None
    current_date = None

    with open(file_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            date_match = date_pattern.match(line)
            if date_match:
                year, month, day = map(int, date_match.groups())
                current_date = datetime(year, month, day)
                continue

            if "님이 " in line and "초대했습니다" in line and current_date:
                invite_match = re.match(r"(.*?)님이 (.*?)님을 초대했습니다", line)
                if invite_match:
                    _, invited = invite_match.groups()
                    logical_date = current_date.date()
                    sunday = logical_date + timedelta(days=(6 - logical_date.weekday()))
                    week_key = sunday.strftime("%Y-%m-%d")
                    weekly_invited[week_key].add(invited)
                continue

            msg_match = msg_pattern.match(line)
            if msg_match and current_date:
                user, message = msg_match.groups()
                time_match = time_pattern.search(line)
                if time_match:
                    period, hour, minute = time_match.groups()
                    hour = int(hour)
                    if period == "오후" and hour != 12:
                        hour += 12
                    if period == "오전" and hour == 12:
                        hour = 0
                    msg_time = current_date.replace(hour=hour, minute=int(minute))
                    logical_date = msg_time - timedelta(days=1) if msg_time.hour < 3 else msg_time
                    logical_date = logical_date.date()
                else:
                    continue

                if "사진" in message or "동영상" in message:
                    if keyword_buffer and keyword_buffer[1] == logical_date and keyword_buffer[0] == user:
                        if (user, logical_date) not in already_counted:
                            daily_counts[logical_date][user] += 1
                            already_counted.add((user, logical_date))
                        keyword_buffer = None
                    else:
                        photo_buffer = (user, logical_date)
                    continue

                if any(re.search(fr"{keyword}", message) for keyword in KEYWORDS):
                    if photo_buffer and photo_buffer[1] == logical_date and photo_buffer[0] == user:
                        if (user, logical_date) not in already_counted:
                            daily_counts[logical_date][user] += 1
                            already_counted.add((user, logical_date))
                        photo_buffer = None
                    else:
                        keyword_buffer = (user, logical_date)
                else:
                    photo_buffer = None
                    keyword_buffer = None

    # 주간 단위로 정리
    weekly_counts = defaultdict(lambda: defaultdict(int))
    for logical_date, user_counts in daily_counts.items():
        sunday = logical_date + timedelta(days=(6 - logical_date.weekday()))
        week_key = sunday.strftime("%Y-%m-%d")
        for user, count in user_counts.items():
            weekly_counts[week_key][user] += count

    data = []
    for week, user_counts in weekly_counts.items():
        invited_users = weekly_invited.get(week, set())
        for user, count in user_counts.items():
            if user in invited_users:
                data.append({"Week": week, "User": user, "Count": count, "Status": "NEW USER"})
            else:
                status = str(out_count - count) + " OUT     -" + str(money * (out_count - count)) if count < out_count else ""
                data.append({"Week": week, "User": user, "Count": count, "Status": status})

    df = pd.DataFrame(data)
    df = df.sort_values(by=["Week", "Count", "Status", "User"], ascending=[False, False, False, False])
    result_html = df.to_html(index=False, classes="table table-striped table-bordered", justify="center")

    return render_template("index.html", table=result_html, out_count=out_count, money=money)

if __name__ == "__main__":
    app.run(debug=True)
