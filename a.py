from data_fetcher import get_korea_market_summary, get_crypto_market_summary, get_main_news
from pycoingecko import CoinGeckoAPI
from datetime import datetime
import os
import requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from bs4 import BeautifulSoup

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
                change = float(cols[4].get_text(strip=True).replace('%', '').replace('+','').replace('-',''))
                volume = int(cols[6].get_text(strip=True).replace(',', ''))
                stock_list.append({'종목명': name, '종목코드': code, '현재가': price, '등락률': change, '거래량': volume})
            except:
                continue
    return pd.DataFrame(stock_list).head(30)

def get_technical_indicators(stock):
    code = stock['종목코드']
    df_list = []

    for page in range(1, 4):  # 3페이지 가져오기 (약 60일치)
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


    if len(df) < 5:
        return None

    close = df['종가']
    volume = df['거래량']
    stock['5일선'] = close.rolling(window=5).mean().iloc[-1]
    stock['5일선돌파'] = stock['현재가'] > stock['5일선']
    stock['거래량변화율'] = (volume.iloc[-2] - volume.iloc[-3]) / volume.iloc[-3] * 100

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = -delta.clip(upper=0).rolling(14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    stock['RSI'] = round(rsi.iloc[-1], 2)

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    stock['MACD'] = macd.iloc[-1]
    stock['MACD_SIGNAL'] = signal.iloc[-1]
    stock['MACD_Golden'] = stock['MACD'] > stock['MACD_SIGNAL']

    score = 0
    if stock['등락률'] >= 5: score += 2.5
    if stock['거래량변화율'] >= 150: score += 2.5
    if stock['5일선돌파']: score += 2
    if 50 <= stock['RSI'] <= 80: score += 1.5
    if stock['MACD_Golden']: score += 1.5
    stock['점수'] = round(score, 1)

    if score >= 6.5:
        stock['추천강도'] = '🚀 Strong Buy'
    elif score >= 5:
        stock['추천강도'] = '✅ Buy'
    else:
        stock['추천강도'] = '⚠️ Hold'

    # 주가 차트 이미지 저장
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

def analyze_top_30_stocks():
    df = get_top_30_stocks()
    analyzed = []
    for _, row in df.iterrows():
        result = get_technical_indicators(row.copy())
        if result is not None:
            analyzed.append(result)
    return pd.DataFrame(analyzed)

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
        table {{ border-collapse: collapse; width: 100%; }}
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
    <table><tr>
    <th>순위</th><th>종목</th><th>현재가</th><th>등락률</th><th>거래량</th>
    <th>5일선돌파</th><th>거래량변화율</th><th>RSI</th><th>MACD</th>
    <th>점수</th><th>추천</th><th>차트</th>
    </tr>"""

    for i, row in stock_df.iterrows():
        html += f"<tr><td>{i+1}</td><td>{row['종목명']}</td><td>{row['현재가']:,}</td><td>{row['등락률']:.2f}%</td><td>{row['거래량']:,}</td>"
        html += f"<td>{'✅' if row['5일선돌파'] else '❌'}</td><td>{row['거래량변화율']:.1f}%</td><td>{row['RSI']}</td>"
        html += f"<td>{'✅' if row['MACD_Golden'] else '❌'}</td><td>{row['점수']}</td><td>{row['추천강도']}</td>"
        html += f"<td><img class='chart' src='{row['차트']}'></td></tr>"
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
        html += f"<tr><td>{coin['이름']}</td><td>{coin['기호']}</td><td>{coin['현재가']}</td><td>{coin['등락률']}</td><td>{coin['거래량']}</td>"
        html += f"<td>{coin['점수']}</td><td>{coin['추천강도']}</td><td><img src='{coin['아이콘']}' width='25'></td></tr>"
    html += "</table></body></html>"

    os.makedirs("reports", exist_ok=True)
    with open(f"reports/{today}.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ {today} 리포트 생성 완료!")

if __name__ == "__main__":
    generate_report()