import os
from flask import Flask, send_from_directory, render_template_string

app = Flask(__name__)
REPORT_DIR = 'reports'

@app.route('/')
def home():
    # reports 폴더 내의 HTML 파일 목록 가져오기 (최신순 정렬)
    files = sorted(
        [f for f in os.listdir(REPORT_DIR) if f.endswith('.html')],
        reverse=True
    )

    # HTML 템플릿 문자열 (간단한 리포트 목록 페이지)
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>📊 단타 리포트 홈</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            h1 { color: #1a73e8; }
            ul { list-style: none; padding-left: 0; }
            li { margin: 10px 0; }
            a { text-decoration: none; color: #1a1a1a; font-size: 18px; }
            a:hover { color: #1a73e8; }
        </style>
    </head>
    <body>
        <h1>📅 Daily 단타 리포트</h1>
        <p>리포트를 클릭해서 확인하세요:</p>
        <ul>
            {% for file in files %}
                <li><a href="/reports/{{ file }}">{{ file.replace('.html', '') }}</a></li>
            {% endfor %}
        </ul>
        <hr>
        <p><a href="/guide">📘 단타 지표 설명 보기</a> (준비 중)</p>
    </body>
    </html>
    """
    return render_template_string(html_template, files=files)

# 리포트 파일 제공
@app.route('/reports/<path:filename>')
def serve_report(filename):
    return send_from_directory(REPORT_DIR, filename)

# 앞으로 만들 해설 페이지용 placeholder
@app.route('/guide')
def guide_page():
    return "<h1>📘 단타 지표 설명 페이지 (준비 중)</h1><p>나중에 여기에 해설이 들어갑니다.</p>"

# 외부에서 실행할 수 있게 함수 정의
def start_web_server():
    app.run(debug=False, port=5000)
