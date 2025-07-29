from flask import Flask, render_template
import os

app = Flask(__name__)

REPORTS_DIR = "reports"

@app.route('/')
def index():
    # reports 폴더에서 html 파일 목록 읽기
    files = sorted([f for f in os.listdir(REPORTS_DIR) if f.endswith(".html")], reverse=True)
    latest_report = files[0] if files else None

    latest_html = ""
    if latest_report:
        with open(os.path.join(REPORTS_DIR, latest_report), "r", encoding="utf-8") as f:
            latest_html = f.read()

    return render_template("index.html", latest_html=latest_html, reports=files)

@app.route('/report/<filename>')
def view_report(filename):
    # 선택한 날짜의 리포트를 불러오기
    filepath = os.path.join(REPORTS_DIR, filename)
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            report_html = f.read()
        return report_html
    else:
        return "<h2>리포트를 찾을 수 없습니다.</h2>"

@app.route('/indicators')
def indicators():
    return render_template("indicators.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))  # Render는 기본적으로 PORT 환경 변수를 사용
    app.run(host="0.0.0.0", port=port, debug=False)
