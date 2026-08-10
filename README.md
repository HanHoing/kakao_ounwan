# kakao_ounwan

카카오톡 오운완(운동 인증) 채팅 `.txt`를 분석해 주간 인증 횟수·OUT·벌금을 계산하는 웹 앱입니다.  
안드로이드 Chrome에서 **홈 화면에 추가(PWA)** 해 앱처럼 쓸 수 있습니다.

## 클라우드 배포 (PC 꺼도 동작)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/HanHoing/kakao_ounwan)

1. 위 버튼 클릭 (또는 [Render Dashboard](https://dashboard.render.com/) → New → Blueprint)
2. GitHub 계정(`HanHoing`)으로 로그인 후 `kakao_ounwan` 저장소 연결
3. Blueprint(`render.yaml`) 확인 후 **Apply** / **Create Web Service**
4. 배포가 끝나면 `https://kakao-ounwan.onrender.com` 형태의 URL이 발급됩니다

이후 `main`에 push하면 자동 재배포됩니다.  
무료 플랜은 약 15분 미사용 시 sleep 되며, 첫 접속만 조금 느릴 수 있습니다.

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

## 사용 방법 (안드로이드)

1. 카카오톡 단톡 → 대화 내용 내보내기 → `.txt` 저장
2. 앱(또는 사이트)에서 기준 횟수·벌금 입력
3. 다운로드 폴더의 txt 업로드 → 분석

파싱·집계 규칙(사진+키워드, 새벽 3시 컷오프, 주간 일요일, NEW USER)은 기존과 동일합니다.
