from data_fetcher import get_korea_market_summary, get_crypto_market_summary, get_main_news
from pycoingecko import CoinGeckoAPI
from datetime import datetime
import os
import requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from bs4 import BeautifulSoup
import matplotlib
matplotlib.rc('font', family='Malgun Gothic')  # Windows: 맑은 고딕
plt.rcParams['axes.unicode_minus'] = False    # 마이너스 폰트 깨짐 방지


# 🔍 상위 30 종목 수집
def get_top_30_stocks():
    base_url = "https://finance.naver.com/sise/sise_rise.nhn?page="
    stock_list = []
    for page in range(1, 4):
        url = base_url + str(page)
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        table = soup.select_one('table.type_2')
        rows = table.find_all('tr')
        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 10:
                continue
            try:
                name = cols[1].get_text(strip=True)
                code = cols[1].find('a')['href'].split('=')[-1]
                price = int(cols[2].get_text(strip=True).replace(',', ''))
                change = float(cols[4].get_text(strip=True).replace('%', '').replace('+', '').replace('-', ''))
                volume = int(cols[6].get_text(strip=True).replace(',', ''))
                stock_list.append({'종목명': name, '종목코드': code, '현재가': price, '등락률': change, '거래량': volume})
            except:
                continue
    return pd.DataFrame(stock_list).head(30)


# 📈 기술적 지표 계산
def get_technical_indicators(stock):
    code = stock['종목코드']
    df_list = []

    for page in range(1, 4):  # 3페이지 (약 60일치)
        url = f"https://finance.naver.com/item/sise_day.nhn?code={code}&page={page}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers)
        dfs = pd.read_html(res.text)
        df = dfs[0].dropna()
        df.columns = ['날짜', '종가', '전일비', '시가', '고가', '저가', '거래량']
        df_list.append(df)

    df = pd.concat(df_list, ignore_index=True)
    df['종가'] = df['종가'].astype(int)
    df['거래량'] = df['거래량'].astype(int)
    df = df.sort_index(ascending=False)

    if len(df) < 20:
        return None

    close = df['종가']
    volume = df['거래량']

    # 이동평균선
    stock['5일선'] = close.rolling(window=5).mean().iloc[-1]
    stock['20일선'] = close.rolling(window=20).mean().iloc[-1]
    stock['5일선돌파'] = stock['현재가'] > stock['5일선']

    # 거래량 변화율
    stock['거래량변화율'] = (volume.iloc[-1] - volume.iloc[-2]) / volume.iloc[-2] * 100

    # RSI
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = -delta.clip(upper=0).rolling(14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    stock['RSI'] = round(rsi.iloc[-1], 2)

    # MACD
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    stock['MACD'] = round(macd.iloc[-1], 2)
    stock['MACD_SIGNAL'] = round(signal.iloc[-1], 2)
    stock['MACD_Golden'] = stock['MACD'] > stock['MACD_SIGNAL']

    # 볼린저 밴드
    mid = close.rolling(20).mean()
    std = close.rolling(20).std()
    upper = mid + (2 * std)
    lower = mid - (2 * std)
    stock['볼린저상단'] = round(upper.iloc[-1], 2)
    stock['볼린저하단'] = round(lower.iloc[-1], 2)
    stock['볼린저위치'] = '상단 돌파' if stock['현재가'] > upper.iloc[-1] else '하단 근접' if stock['현재가'] < lower.iloc[-1] else '중앙 부근'

    # 스토캐스틱
    low14 = df['저가'].rolling(14).min()
    high14 = df['고가'].rolling(14).max()
    stock['%K'] = ((close - low14) / (high14 - low14) * 100).iloc[-1]
    stock['%D'] = df['종가'].rolling(3).mean().iloc[-1]

    # 이격도
    stock['이격도'] = round((stock['현재가'] / stock['20일선']) * 100, 2)

    # 캔들패턴
    today_open, today_close = df['시가'].iloc[-1], df['종가'].iloc[-1]
    today_high, today_low = df['고가'].iloc[-1], df['저가'].iloc[-1]
    if today_close > today_open and (today_open - today_low) > 2*(today_close - today_open):
        stock['캔들패턴'] = '망치형(반등 신호)'
    elif today_open > today_close and (today_high - today_close) > 2*(today_open - today_close):
        stock['캔들패턴'] = '역망치형(하락 신호)'
    else:
        stock['캔들패턴'] = '일반형'

    # 점수 계산
    score = 0
    if stock['등락률'] >= 5: score += 2.5
    if stock['거래량변화율'] >= 150: score += 2.5
    if stock['5일선돌파']: score += 2
    if 50 <= stock['RSI'] <= 70: score += 1.5
    if stock['MACD_Golden']: score += 1.5
    stock['점수'] = round(score, 1)
    stock['추천강도'] = '🚀 Strong Buy' if score >= 6.5 else '✅ Buy' if score >= 5 else '⚠️ Hold'

    # 매수전 확인 포인트
    strategy_points = []
    if stock['RSI'] < 30: strategy_points.append("RSI 과매도 → 매수 기회 가능")
    if stock['RSI'] > 70: strategy_points.append("RSI 과매수 → 매도 주의")
    if stock['MACD_Golden']: strategy_points.append("MACD 골든크로스 → 상승 전환 신호")
    if stock['%K'] < 20: strategy_points.append("스토캐스틱 과매도 → 반등 가능")
    if stock['%K'] > 80: strategy_points.append("스토캐스틱 과매수 → 매도 신호")
    if stock['이격도'] < 95: strategy_points.append("이격도 과매도 → 저점 접근")
    if stock['이격도'] > 105: strategy_points.append("이격도 과열 → 조정 우려")
    if stock['캔들패턴'] == '망치형(반등 신호)': strategy_points.append("캔들패턴 반등 신호")
    stock['매수전확인'] = " / ".join(strategy_points) if strategy_points else "중립: 추세 확인 필요"

    # 차트 생성
    chart_dir = 'docs/reports/charts'
    os.makedirs(chart_dir, exist_ok=True)
    plt.figure(figsize=(4, 2))
    plt.plot(close.iloc[::-1].values[-20:], marker='o')
    plt.title(stock['종목명'], fontsize=10)
    plt.tight_layout()
    chart_path = f"{chart_dir}/{stock['종목명']}.png"
    plt.savefig(chart_path)
    plt.close()
    stock['차트'] = chart_path

    return stock


# 🔍 상위 종목 분석
def analyze_top_30_stocks():
    df = get_top_30_stocks()
    analyzed = []
    for _, row in df.iterrows():
        result = get_technical_indicators(row.copy())
        if result is not None:
            analyzed.append(result)
    return pd.DataFrame(analyzed)


# 🔍 코인 분석
def analyze_top_20_coins():
    cg = CoinGeckoAPI()
    data = cg.get_coins_markets(vs_currency='usd', order='volume_desc', per_page=20)
    coin_list = []
    for coin in data:
        price = coin['current_price']
        change_24h = coin['price_change_percentage_24h']
        volume = coin['total_volume']
        score = 0
        if change_24h >= 5: score += 2
        if volume > 1e9: score += 2
        if change_24h > 0: score += 1
        strength = '🚀 Strong Buy' if score >= 4 else '✅ Buy' if score >= 3 else '⚠️ Watch'

        coin_list.append({
            '이름': coin['name'],
            '기호': coin['symbol'].upper(),
            '현재가': f"${price:,.2f}",
            '등락률': f"{change_24h:.2f}%",
            '거래량': f"${volume/1e6:.1f}M",
            '점수': score,
            '추천강도': strength,
            '아이콘': coin['image']
        })
    return coin_list


# 🔧 index.html 자동 업데이트
def update_index_page():
    from data_fetcher import get_korea_market_summary, get_crypto_market_summary, get_main_news

    reports_dir = "docs/reports"
    files = sorted([f for f in os.listdir(reports_dir) if f.endswith(".html")], reverse=True)
    if not files:
        print("⚠ 리포트 파일이 없습니다. index.html 업데이트를 건너뜁니다.")
        return

    latest_report = files[0]
    previous_reports = files[1:6]  # 최근 5개 리포트

    # ✅ 오늘의 요약 데이터
    korea = get_korea_market_summary()
    crypto = get_crypto_market_summary()
    news_list = get_main_news()

    # 이전 리포트 링크 생성
    links = "\n".join([
        f'<li class="list-group-item"><a href="reports/{f}">{f.replace(".html", "")} 리포트</a></li>'
        for f in previous_reports
    ])

    # 뉴스 목록 생성
    news_html = ""
    if news_list:
        for title, link in news_list:
            news_html += f'<li><a href="{link}" target="_blank">{title}</a></li>'
    else:
        news_html = "<li>중요 경제 뉴스가 없습니다.</li>"

    # ✅ index.html 생성 (비밀번호 보호 + 제목 변경 포함)
    index_html = f"""
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Be RICH, J's Family</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {{ font-family: 'Noto Sans KR', sans-serif; background-color: #f8f9fa; display: none; }}
            .header {{ background: linear-gradient(90deg, #4a90e2, #357ab8); color: white; padding: 20px; text-align: center; border-radius: 0 0 15px 15px; margin-bottom: 20px; }}
            .card {{ border-radius: 12px; box-shadow: 0 4px 8px rgba(0,0,0,0.05); margin-bottom: 20px; }}
            .section-title {{ font-size: 1.3rem; font-weight: bold; margin-bottom: 15px; }}
            .report-link {{ text-decoration: none; color: #4a90e2; font-weight: 500; }}
            .report-link:hover {{ text-decoration: underline; color: #357ab8; }}
        </style>
        <script>
            document.addEventListener("DOMContentLoaded", function() {{
                const password = "1234";  // ✅ 원하는 비밀번호로 변경 가능
                let input = prompt("🔒 비밀번호를 입력하세요:");
                if (input === password) {{
                    document.body.style.display = "block";
                }} else {{
                    alert("비밀번호가 틀렸습니다. 접근이 거부됩니다.");
                    window.location.href = "about:blank";
                }}
            }});
        </script>
    </head>
    <body>
        <header class="header">
            <h1>Be RICH, J's Family</h1>
        </header>
        <main class="container">
            <!-- 단타 지표 해설 -->
            <div class="card p-4">
                <div class="section-title">📖 단타 지표 해설</div>
                <p>주요 단타 매매 지표(RSI, MACD, 볼린저밴드 등)를 확인하고 학습하세요.</p>
                <a href="indicators.html" class="btn btn-primary btn-sm">지표 해설 보기</a>
            </div>

            <!-- 오늘의 요약 -->
            <div class="card p-4">
                <div class="section-title">📊 오늘의 국내 증시 / 세계 경제 요약</div>
                <ul>
                    <li>KOSPI: {korea['KOSPI']}</li>
                    <li>KOSDAQ: {korea['KOSDAQ']}</li>
                    <li>환율 (USD/KRW): {korea['환율 (USD/KRW)']}</li>
                    <li>환율 (CAD/KRW): {korea['환율 (CAD/KRW)']}</li>
                </ul>
                <h5 class="mt-3">🪙 오늘의 코인 경제 요약</h5>
                <ul>
                    <li>Bitcoin: {crypto['Bitcoin']}</li>
                    <li>Ethereum: {crypto['Ethereum']}</li>
                </ul>
                <h5 class="mt-3">🌍 주요 경제 뉴스</h5>
                <ul>{news_html}</ul>
            </div>

            <!-- 오늘의 리포트 -->
            <div class="card p-4">
                <div class="section-title">📰 오늘의 리포트</div>
                <a href="reports/{latest_report}" class="btn btn-success btn-lg w-100">📂 {latest_report.replace(".html", "")} 리포트 열기</a>
            </div>

            <!-- 이전 리포트 목록 -->
            <div class="card p-4">
                <div class="section-title">📅 이전 리포트 목록</div>
                <ul class="list-group">
                    {links}
                </ul>
            </div>
        </main>
        <footer class="text-center py-3 mt-4 text-muted">
            © {datetime.now().year} Derick Jeon | <a href="https://github.com/derickjeon/danta" target="_blank">GitHub</a>
        </footer>
    </body>
    </html>
    """

    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(index_html)
    print(f"✅ index.html 자동 업데이트 완료! (최신: {latest_report})")


# 📄 리포트 생성
def generate_report():
    today = datetime.today().strftime('%Y-%m-%d')
    korea = get_korea_market_summary()
    crypto = get_crypto_market_summary()
    news_list = get_main_news()
    stock_df = analyze_top_30_stocks()
    coin_list = analyze_top_20_coins()

    html = f"""
    <html><head><meta charset='UTF-8'><title>{today} 단타 분석 리포트</title>
    <style>
        body {{ font-family: Arial; padding: 30px; }}
        table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
        th, td {{ border: 1px solid #ccc; padding: 5px; text-align: center; }}
        img.chart {{ height: 80px; }}
    </style></head><body>
    <h2>📊 오늘의 국내 증시 / 세계 경제 요약</h2><ul>
        <li>KOSPI: {korea['KOSPI']}</li>
        <li>KOSDAQ: {korea['KOSDAQ']}</li>
        <li>환율 (USD/KRW): {korea['환율 (USD/KRW)']}</li>
        <li>환율 (CAD/KRW): {korea['환율 (CAD/KRW)']}</li>
    </ul>

    <h2>🪙 오늘의 코인 경제 요약</h2><ul>
        <li>Bitcoin: {crypto['Bitcoin']}</li>
        <li>Ethereum: {crypto['Ethereum']}</li>
    </ul>

    <h2>🌍 주요 경제 뉴스 요약</h2><ul>
    """
    for title, link in news_list:
        html += f"<li><a href='{link}' target='_blank'>{title}</a></li>"
    if not news_list:
        html += "<li>중요 경제 뉴스가 없습니다.</li>"
    html += "</ul>"

    # 주식 분석 테이블
    html += """
    <h2>📈 추천 주식 30선</h2>
    <table>
    <tr>
    <th>순위</th><th>종목</th><th>현재가</th><th>등락률</th><th>거래량</th>
    <th>RSI</th><th>MACD</th><th>볼린저위치</th><th>스토캐스틱 %K</th><th>이격도</th>
    <th>캔들패턴</th><th>추천</th><th>매수전 확인 포인트</th>
    </tr>

    <tr style='background:#f2f2f2; font-size:12px;'>
    <td colspan='5'>지표 기준</td>
    <td>과매도 <30 / 정상 50 / 과매수 >70</td>
    <td>골든=상승 / 데드=하락</td>
    <td>상단=강세 / 하단=반등</td>
    <td><20 과매도 / >80 과매수</td>
    <td>95~105 정상</td>
    <td>망치=반등 / 역망치=하락</td>
    <td colspan='2'>참고용</td>
    </tr>
    """

    for i, row in stock_df.iterrows():
        # 색상 처리 (RSI, MACD 등)
        def color_cell(value, low, high, label):
            if label == "RSI":
                if value < 30: return f"<td style='background:#f8e6f8'>{value}</td>"
                elif value > 70: return f"<td style='background:#e6f2ff'>{value}</td>"
            return f"<td>{value}</td>"

        rsi_cell = color_cell(row['RSI'], 30, 70, "RSI")
        macd_status = '골든' if row['MACD_Golden'] else '데드'
        macd_cell = f"<td style='background:{'#f8e6f8' if macd_status=='골든' else '#e6f2ff'}'>{macd_status}</td>"

        boll_cell = f"<td style='background:{'#f8e6f8' if row['볼린저위치']=='하단 근접' else '#e6f2ff' if row['볼린저위치']=='상단 돌파' else 'none'}'>{row['볼린저위치']}</td>"

        stoch_cell = f"<td style='background:{'#f8e6f8' if row['%K']<20 else '#e6f2ff' if row['%K']>80 else 'none'}'>{row['%K']:.1f}</td>"

        gap_cell = f"<td style='background:{'#f8e6f8' if row['이격도']<95 else '#e6f2ff' if row['이격도']>105 else 'none'}'>{row['이격도']}</td>"

        candle_cell = f"<td style='background:{'#f8e6f8' if '망치' in row['캔들패턴'] else '#e6f2ff' if '역망치' in row['캔들패턴'] else 'none'}'>{row['캔들패턴']}</td>"

        if 'Strong Buy' in row['추천강도']:
            recommend_cell = f"<td style='background:#ffcccc'>{row['추천강도']}</td>"
        elif 'Buy' in row['추천강도']:
            recommend_cell = f"<td style='background:#ffe6f0'>{row['추천강도']}</td>"
        else:
            recommend_cell = f"<td>{row['추천강도']}</td>"

        html += f"<tr><td>{i+1}</td><td><a href='https://finance.naver.com/item/main.nhn?code={row['종목코드']}' target='_blank'>{row['종목명']}</a></td><td>{row['현재가']:,}</td><td>{row['등락률']:.2f}%</td><td>{row['거래량']:,}</td>{rsi_cell}{macd_cell}{boll_cell}{stoch_cell}{gap_cell}{candle_cell}{recommend_cell}<td>{row['매수전확인']}</td></tr>"

    html += "</table>"

    html += """
    <h2>🕗 장전 시간외 거래 전략 (08:30~08:40)</h2>
    <ul>
        <li><b>① 전일 고가 이상 시가 + 거래량 증가:</b> 갭상승 후 눌림 매수 가능성 ↑</li>
        <li><b>② 시가가 전일 종가 이하 + 거래량 미미:</b> 매수 보류</li>
        <li><b>③ 시가 = 전일 종가 ±1% + 거래량 급증:</b> 돌파 가능성 높음</li>
    </ul>
    """

    html += "<h2>🪙 추천 코인 20선</h2><table><tr><th>이름</th><th>기호</th><th>가격</th><th>등락률</th><th>거래량</th><th>점수</th><th>추천</th><th>아이콘</th></tr>"
    for coin in coin_list:
        html += f"<tr><td><a href='https://coinmarketcap.com/currencies/{coin['이름'].lower().replace(' ', '-')}/' target='_blank'>{coin['이름']}</a></td><td>{coin['기호']}</td><td>{coin['현재가']}</td><td>{coin['등락률']}</td><td>{coin['거래량']}</td><td>{coin['점수']}</td><td>{coin['추천강도']}</td><td><img src='{coin['아이콘']}' width='25'></td></tr>"
    html += "</table></body></html>"

    os.makedirs("docs/reports", exist_ok=True)
    with open(f"docs/reports/{today}.html", "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ {today} 리포트 생성 완료!")


if __name__ == "__main__":
    generate_report()
    update_index_page()  # ✅ 최신 index.html 자동 업데이트


