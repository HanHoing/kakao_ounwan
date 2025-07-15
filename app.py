from flask import Flask, render_template, request, redirect, send_file
import pandas as pd
import re
from datetime import datetime, timedelta
from collections import defaultdict
import os

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 키워드 리스트 (AI 없이 고정된 버전)
KEYWORDS = ["오운완", "운완", "ㅇㅇㅇ", "오공완", "오스완", "오산완", "운오ㅓㄴ", "/4", "인증","완"]

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

    # 분석 시작
    date_pattern = re.compile(r"-{7,}\s*(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일")
    msg_pattern = re.compile(r"^\[(.+?)\]\s+\[.+?\]\s+(.+)")

    weekly_invited = defaultdict(set)
    weekly_counts = defaultdict(lambda: defaultdict(int))
    already_counted = defaultdict(lambda: defaultdict(bool))
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

            msg_match = msg_pattern.match(line)
            if msg_match and current_date:
                user, message = msg_match.groups()
                time_match = re.search(r"\[(오전|오후)\s*(\d+):(\d+)\]", line)
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

                if message.startswith("사진") or message.startswith("동영상"):
                    if keyword_buffer:
                        k_user, k_date = keyword_buffer
                        if not already_counted[k_date][k_user]:
                            sunday = k_date + timedelta(days=(6 - k_date.weekday()))
                            week_key = sunday.strftime("%Y-%m-%d")
                            weekly_counts[week_key][k_user] += 1
                            already_counted[k_date][k_user] = True
                        keyword_buffer = None
                    else:
                        photo_buffer = (user, logical_date)
                    continue

                if any(re.search(fr"{keyword}", message) for keyword in KEYWORDS):
                    if photo_buffer:
                        p_user, p_date = photo_buffer
                        if not already_counted[p_date][p_user]:
                            sunday = p_date + timedelta(days=(6 - p_date.weekday()))
                            week_key = sunday.strftime("%Y-%m-%d")
                            weekly_counts[week_key][p_user] += 1
                            already_counted[p_date][p_user] = True
                        photo_buffer = None
                    else:
                        keyword_buffer = (user, logical_date)
                else:
                    photo_buffer = None
                    keyword_buffer = None

    data = []
    for week, user_counts in weekly_counts.items():
        invited_users = weekly_invited.get(week, set())
        week_data = []
        new_users = []
        for user, count in user_counts.items():
            display_user = "한혜영" if user == "." else user
            if user in invited_users:
                new_users.append({"Week": week, "User": display_user, "Count": count, "Status": "NEW USER"})
            else:
                status = str(out_count - count) + " OUT     -" + str(money * (out_count - count)) if count < out_count else ""
                week_data.append({"Week": week, "User": display_user, "Count": count, "Status": status})
        week_data.extend(new_users)
        data.extend(week_data)

    df = pd.DataFrame(data)
    df = df.sort_values(by=["Week", "Count", "Status", "User"], ascending=[False, False, False, False])

    result_html = df.to_html(index=False, classes="table table-striped table-bordered", justify="center")
    return render_template("index.html", table=result_html, out_count=out_count, money=money)

if __name__ == "__main__":
    app.run(debug=True)