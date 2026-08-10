# kakao_ounwan

카카오톡 오운완(운동 인증) 채팅 `.txt`를 분석해 주간 인증 횟수·OUT·벌금을 계산하는 웹 앱입니다.  
안드로이드 Chrome에서 **홈 화면에 추가(PWA)** 해 앱처럼 쓸 수 있습니다.

## 로컬 실행

```bash
pip install -r requirements.txt
python app.py
```

브라우저에서 `http://127.0.0.1:5000` 접속.

gunicorn:

```bash
set PORT=8000
gunicorn -b 0.0.0.0:8000 app:app
```

## 배포 (HTTPS 권장)

Railway / Render / Fly.io 등에 올리고 `Procfile`로 실행합니다.  
PWA 홈 화면 추가는 **HTTPS** 환경에서 가능합니다.

1. 저장소 연결 후 배포
2. 폰 Chrome으로 URL 접속
3. 메뉴(⋮) → 홈 화면에 추가 / 설치

## 사용 방법 (안드로이드)

1. 카카오톡 단톡 → 대화 내용 내보내기 → `.txt` 저장
2. 앱(또는 사이트)에서 기준 횟수·벌금 입력
3. 다운로드 폴더의 txt 업로드 → 분석

파싱·집계 규칙(사진+키워드, 새벽 3시 컷오프, 주간 일요일, NEW USER)은 기존과 동일합니다.
