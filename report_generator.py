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
    chart_dir = 'reports/charts'
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

    <!-- 🔽 기준 값 행 추가 -->
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

    # 종목 데이터 반복문
    for i, row in stock_df.iterrows():
        # RSI 색상
        if row['RSI'] < 30:
            rsi_cell = f"<td style='background-color:#f8e6f8'>{row['RSI']}</td>"
        elif row['RSI'] > 70:
            rsi_cell = f"<td style='background-color:#e6f2ff'>{row['RSI']}</td>"
        else:
            rsi_cell = f"<td>{row['RSI']}</td>"

        # MACD 색상
        macd_status = '골든' if row['MACD_Golden'] else '데드'
        if macd_status == '골든':
            macd_cell = f"<td style='background-color:#f8e6f8'>{macd_status}</td>"
        else:
            macd_cell = f"<td style='background-color:#e6f2ff'>{macd_status}</td>"

        # 볼린저 색상
        if row['볼린저위치'] == '하단 근접':
            boll_cell = f"<td style='background-color:#f8e6f8'>{row['볼린저위치']}</td>"
        elif row['볼린저위치'] == '상단 돌파':
            boll_cell = f"<td style='background-color:#e6f2ff'>{row['볼린저위치']}</td>"
        else:
            boll_cell = f"<td>{row['볼린저위치']}</td>"

        # 스토캐스틱 색상
        if row['%K'] < 20:
            stoch_cell = f"<td style='background-color:#f8e6f8'>{row['%K']:.1f}</td>"
        elif row['%K'] > 80:
            stoch_cell = f"<td style='background-color:#e6f2ff'>{row['%K']:.1f}</td>"
        else:
            stoch_cell = f"<td>{row['%K']:.1f}</td>"

        # 이격도 색상
        if row['이격도'] < 95:
            gap_cell = f"<td style='background-color:#f8e6f8'>{row['이격도']}</td>"
        elif row['이격도'] > 105:
            gap_cell = f"<td style='background-color:#e6f2ff'>{row['이격도']}</td>"
        else:
            gap_cell = f"<td>{row['이격도']}</td>"

        # 캔들패턴 색상
        if '망치' in row['캔들패턴']:
            candle_cell = f"<td style='background-color:#f8e6f8'>{row['캔들패턴']}</td>"
        elif '역망치' in row['캔들패턴']:
            candle_cell = f"<td style='background-color:#e6f2ff'>{row['캔들패턴']}</td>"
        else:
            candle_cell = f"<td>{row['캔들패턴']}</td>"
        
        # 추천강도 색상
        if 'Strong Buy' in row['추천강도']:
            recommend_cell = f"<td style='background-color:#ffcccc'>{row['추천강도']}</td>"  # 옅은 빨간색
        elif 'Buy' in row['추천강도']:
            recommend_cell = f"<td style='background-color:#ffe6f0'>{row['추천강도']}</td>"  # 옅은 핑크색
        else:
            recommend_cell = f"<td>{row['추천강도']}</td>"


        # 행 생성
        html += f"<tr><td>{i+1}</td><td><a href='https://finance.naver.com/item/main.nhn?code={row['종목코드']}' target='_blank'>{row['종목명']}</a></td><td>{row['현재가']:,}</td><td>{row['등락률']:.2f}%</td><td>{row['거래량']:,}</td>"

        html += f"{rsi_cell}{macd_cell}{boll_cell}{stoch_cell}{gap_cell}{candle_cell}"
        html += f"{recommend_cell}<td>{row['매수전확인']}</td></tr>"


    html += "</table>"

    # 장전 전략
    html += """
    <h2>🕗 장전 시간외 거래 전략 (08:30~08:40)</h2>
    <ul>
        <li><b>① 전일 고가 이상 시가 + 거래량 증가:</b> 갭상승 후 눌림 매수 가능성 ↑</li>
        <li><b>② 시가가 전일 종가 이하 + 거래량 미미:</b> 매수 보류</li>
        <li><b>③ 시가 = 전일 종가 ±1% + 거래량 급증:</b> 돌파 가능성 높음</li>
    </ul>
    """

    # 코인 추천
    html += "<h2>🪙 추천 코인 20선</h2><table><tr><th>이름</th><th>기호</th><th>가격</th><th>등락률</th><th>거래량</th><th>점수</th><th>추천</th><th>아이콘</th></tr>"
    for coin in coin_list:
        html += f"<tr><td><a href='https://coinmarketcap.com/currencies/{coin['이름'].lower().replace(' ', '-')}/' target='_blank'>{coin['이름']}</a></td><td>{coin['기호']}</td><td>{coin['현재가']}</td><td>{coin['등락률']}</td><td>{coin['거래량']}</td>"

        html += f"<td>{coin['점수']}</td><td>{coin['추천강도']}</td><td><img src='{coin['아이콘']}' width='25'></td></tr>"
    html += "</table></body></html>"

    os.makedirs("reports", exist_ok=True)
    with open(f"reports/{today}.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ {today} 리포트 생성 완료!")


if __name__ == "__main__":
    generate_report()
