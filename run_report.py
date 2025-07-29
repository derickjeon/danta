from report_generator import generate_report
from web_server import start_web_server

if __name__ == "__main__":
    print("📊 리포트 생성 중...")
    generate_report()
    print("🌐 웹서버 실행 중: http://localhost:5000")
    start_web_server()
