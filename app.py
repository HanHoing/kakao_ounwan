from flask import Flask, render_template, request
from werkzeug.utils import secure_filename
import pandas as pd
import re
from datetime import datetime, timedelta
from collections import defaultdict
import os
import uuid

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {".txt"}
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 키워드 리스트
KEYWORDS = ["오운완", "운완", "ㅇㅇㅇ", "ㅇㄱㅇ", "오스완", "오산완", "운오ㅓㄴ", "/4", "인증", "수완", "완"]


def allowed_file(filename: str) -> bool:
    if not filename or "." not in filename:
        return False
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_EXTENSIONS


def read_chat_lines(file_path: str):
    """utf-8 우선, 실패 시 utf-8-sig / cp949 fallback."""
    encodings = ("utf-8", "utf-8-sig", "cp949")
    last_error = None
    for enc in encodings:
        try:
            with open(file_path, encoding=enc) as f:
                return f.readlines()
        except UnicodeDecodeError as e:
            last_error = e
    raise last_error or UnicodeDecodeError("utf-8", b"", 0, 1, "unable to decode")


def _to_24h(period: str, hour: int) -> int:
    hour = int(hour)
    if period == "오후" and hour != 12:
        hour += 12
    if period == "오전" and hour == 12:
        hour = 0
    return hour


def _logical_date(msg_time: datetime):
    # 새벽 3시 이전은 전날로 집계 (기존 규칙)
    adjusted = msg_time - timedelta(days=1) if msg_time.hour < 3 else msg_time
    return adjusted.date()


def _week_key(d):
    sunday = d + timedelta(days=(6 - d.weekday()))
    return sunday.strftime("%Y-%m-%d")


def _parse_invitees(raw: str):
    """'채재혁님과 정희원님' / '박예서님' → 이름 목록."""
    parts = re.split(r"과|와|,", raw)
    names = []
    for part in parts:
        name = part.strip()
        if name.endswith("님"):
            name = name[:-1].strip()
        if name:
            names.append(name)
    return names


def analyze_chat(lines, out_count: int, money: int):
    """파싱·집계 로직.
    - PC 내보내기: --------------- 날짜 --- / [이름] [오전 6:46] 메시지
    - 안드로이드 내보내기: 2026년 1월 5일 오후 10:58, 이름 : 메시지
    인증 규칙(사진+키워드, 새벽 3시, 주간 일요일, NEW USER)은 동일.
    """
    # PC 형식
    pc_date_pattern = re.compile(r"-{7,}\s*(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일")
    pc_msg_pattern = re.compile(r"^\[(.+?)\]\s+\[.+?\]\s+(.+)")
    pc_time_pattern = re.compile(r"\[(오전|오후)\s*(\d+):(\d+)\]")
    pc_invite_pattern = re.compile(r"^(.*?)님이\s+(.+?)을 초대했습니다")

    # 안드로이드 형식
    android_msg_pattern = re.compile(
        r"^(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일\s*(오전|오후)\s*(\d{1,2}):(\d{2}),\s*(.+?)\s*:\s*(.*)$"
    )
    android_invite_pattern = re.compile(
        r"^(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일\s*(오전|오후)\s*(\d{1,2}):(\d{2}),\s*(.+?)님이\s+(.+?)을 초대했습니다"
    )

    weekly_invited = defaultdict(set)
    daily_counts = defaultdict(lambda: defaultdict(int))
    already_counted = set()

    photo_buffer = None
    keyword_buffer = None
    current_date = None

    def register_invite(invite_date, invited_raw: str):
        for invited in _parse_invitees(invited_raw):
            weekly_invited[_week_key(invite_date)].add(invited)

    def count_cert(user, logical_date):
        nonlocal photo_buffer, keyword_buffer
        if (user, logical_date) not in already_counted:
            daily_counts[logical_date][user] += 1
            already_counted.add((user, logical_date))
        photo_buffer = None
        keyword_buffer = None

    def handle_message(user, message, logical_date):
        nonlocal photo_buffer, keyword_buffer
        has_media = "사진" in message or "동영상" in message
        has_keyword = any(re.search(fr"{keyword}", message) for keyword in KEYWORDS)

        # 한 메시지에 사진+키워드가 같이 있으면 즉시 인증
        if has_media and has_keyword:
            count_cert(user, logical_date)
            return

        if has_media:
            if keyword_buffer and keyword_buffer[1] == logical_date and keyword_buffer[0] == user:
                count_cert(user, logical_date)
            else:
                photo_buffer = (user, logical_date)
            return

        if has_keyword:
            if photo_buffer and photo_buffer[1] == logical_date and photo_buffer[0] == user:
                count_cert(user, logical_date)
            else:
                keyword_buffer = (user, logical_date)
        else:
            photo_buffer = None
            keyword_buffer = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # --- 안드로이드 초대 ---
        android_invite = android_invite_pattern.match(line)
        if android_invite:
            y, mo, d, period, hour, minute, _inviter, invited_raw = android_invite.groups()
            msg_time = datetime(int(y), int(mo), int(d), _to_24h(period, hour), int(minute))
            register_invite(_logical_date(msg_time), invited_raw)
            continue

        # --- 안드로이드 메시지 ---
        android_msg = android_msg_pattern.match(line)
        if android_msg:
            y, mo, d, period, hour, minute, user, message = android_msg.groups()
            msg_time = datetime(int(y), int(mo), int(d), _to_24h(period, hour), int(minute))
            current_date = msg_time.replace(hour=0, minute=0, second=0, microsecond=0)
            handle_message(user, message, _logical_date(msg_time))
            continue

        # --- PC 날짜 구분선 ---
        date_match = pc_date_pattern.match(line)
        if date_match:
            year, month, day = map(int, date_match.groups())
            current_date = datetime(year, month, day)
            continue

        # --- PC 초대 ---
        if "님이 " in line and "초대했습니다" in line and current_date:
            invite_match = pc_invite_pattern.match(line)
            if invite_match:
                _, invited_raw = invite_match.groups()
                register_invite(current_date.date(), invited_raw)
            continue

        # --- PC 메시지 ---
        msg_match = pc_msg_pattern.match(line)
        if msg_match and current_date:
            user, message = msg_match.groups()
            time_match = pc_time_pattern.search(line)
            if not time_match:
                continue
            period, hour, minute = time_match.groups()
            msg_time = current_date.replace(hour=_to_24h(period, hour), minute=int(minute))
            handle_message(user, message, _logical_date(msg_time))

    # 주간 단위로 정리
    weekly_counts = defaultdict(lambda: defaultdict(int))
    for logical_date, user_counts in daily_counts.items():
        week_key = _week_key(logical_date)
        for user, count in user_counts.items():
            weekly_counts[week_key][user] += count

    data = []
    for week, user_counts in weekly_counts.items():
        invited_users = weekly_invited.get(week, set())
        for user, count in user_counts.items():
            if user in invited_users:
                data.append({
                    "Week": week,
                    "User": user,
                    "Count": count,
                    "Status": "NEW USER",
                    "kind": "new",
                    "deficit": 0,
                    "fine": 0,
                })
            elif count < out_count:
                deficit = out_count - count
                fine = money * deficit
                data.append({
                    "Week": week,
                    "User": user,
                    "Count": count,
                    "Status": f"{deficit} OUT     -{fine}",
                    "kind": "out",
                    "deficit": deficit,
                    "fine": fine,
                })
            else:
                data.append({
                    "Week": week,
                    "User": user,
                    "Count": count,
                    "Status": "",
                    "kind": "ok",
                    "deficit": 0,
                    "fine": 0,
                })

    df = pd.DataFrame(data)
    if not df.empty:
        df = df.sort_values(by=["Week", "Count", "Status", "User"], ascending=[False, False, False, False])
        rows = df.to_dict(orient="records")
    else:
        rows = []

    # 주별로 묶기 (카드 UI용)
    weeks = []
    current_week = None
    for row in rows:
        if row["Week"] != current_week:
            current_week = row["Week"]
            weeks.append({"week": current_week, "rows": []})
        weeks[-1]["rows"].append(row)

    return rows, weeks


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/run", methods=["POST"])
def run_analysis():
    error = None
    out_count = request.form.get("outCount", "5")
    money = request.form.get("money", "5000")

    try:
        out_count = int(out_count)
        money = int(money)
    except (TypeError, ValueError):
        return render_template(
            "index.html",
            error="기준 횟수와 벌금은 숫자여야 합니다.",
            out_count=5,
            money=5000,
        )

    file = request.files.get("chatFile")
    if not file or not file.filename:
        return render_template(
            "index.html",
            error="채팅 파일을 선택해 주세요.",
            out_count=out_count,
            money=money,
        )

    if not allowed_file(file.filename):
        return render_template(
            "index.html",
            error=".txt 파일만 업로드할 수 있습니다.",
            out_count=out_count,
            money=money,
        )

    safe_name = secure_filename(file.filename) or "chat.txt"
    if not safe_name.lower().endswith(".txt"):
        safe_name += ".txt"
    file_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4().hex}_{safe_name}")
    file.save(file_path)

    try:
        lines = read_chat_lines(file_path)
        rows, weeks = analyze_chat(lines, out_count, money)
    except UnicodeDecodeError:
        return render_template(
            "index.html",
            error="파일 인코딩을 읽을 수 없습니다. UTF-8 또는 ANSI(CP949) txt로 다시 내보내 주세요.",
            out_count=out_count,
            money=money,
        )
    finally:
        try:
            os.remove(file_path)
        except OSError:
            pass

    return render_template(
        "index.html",
        rows=rows,
        weeks=weeks,
        out_count=out_count,
        money=money,
        error=error,
    )


@app.route("/manifest.webmanifest")
def manifest():
    return app.send_static_file("manifest.webmanifest")


@app.route("/sw.js")
def service_worker():
    response = app.send_static_file("sw.js")
    response.headers["Service-Worker-Allowed"] = "/"
    response.headers["Cache-Control"] = "no-cache"
    return response


@app.errorhandler(413)
def too_large(_e):
    return render_template(
        "index.html",
        error="파일이 너무 큽니다. 50MB 이하로 업로드해 주세요.",
        out_count=5,
        money=5000,
    ), 413


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
