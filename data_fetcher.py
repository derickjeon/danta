import requests
from bs4 import BeautifulSoup
from pycoingecko import CoinGeckoAPI
import feedparser

# 📊 국내 증시 요약
def get_korea_market_summary():
    url_sise = 'https://finance.naver.com/sise/'
    url_fx = 'https://finance.naver.com/marketindex/'

    try:
        response = requests.get(url_sise)
        soup = BeautifulSoup(response.text, 'html.parser')
        kospi = soup.select_one('#KOSPI_now').text.strip()
        kosdaq = soup.select_one('#KOSDAQ_now').text.strip()
    except:
        kospi = '정보 없음'
        kosdaq = '정보 없음'

    try:
        ex_response = requests.get(url_fx)
        ex_soup = BeautifulSoup(ex_response.text, 'html.parser')
        usd = ex_soup.select_one('span.value').text.strip()
    except:
        usd = '정보 없음'

    try:
        cad_url = 'https://www.x-rates.com/calculator/?from=CAD&to=KRW&amount=1'
        cad_response = requests.get(cad_url, headers={'User-Agent': 'Mozilla/5.0'})
        cad_soup = BeautifulSoup(cad_response.text, 'html.parser')
        cad_text = cad_soup.select_one('span.ccOutputTrail').previous_sibling
        cad = cad_text.strip()
    except:
        cad = '정보 없음'

    return {
        'KOSPI': kospi,
        'KOSDAQ': kosdaq,
        '환율 (USD/KRW)': usd,
        '환율 (CAD/KRW)': cad
    }

# 🪙 코인 요약
def get_crypto_market_summary():
    cg = CoinGeckoAPI()
    data = cg.get_price(ids=['bitcoin', 'ethereum'], vs_currencies='usd', include_24hr_change='true')

    btc = data['bitcoin']
    eth = data['ethereum']

    return {
        'Bitcoin': f"${btc['usd']} ({btc['usd_24h_change']:.2f}% 변화)",
        'Ethereum': f"${eth['usd']} ({eth['usd_24h_change']:.2f}% 변화)"
    }

# 🌍 중요 경제 뉴스 선별
def get_main_news():
    rss_url = 'https://www.mk.co.kr/rss/30000001/'  # 매일경제 경제 뉴스 RSS
    feed = feedparser.parse(rss_url)

    include_keywords = ['금리', '인플레이션', '환율', '물가', '연준', '경제성장', '무역수지', '수출', '코스피', '코스닥', '원화', '기준금리', '유가', 'GDP']
    exclude_keywords = ['교육', '세미나', '행사', '전시', '후원', '축제', '홍보', '캠페인', '강좌', '전달식']

    filtered_news = []
    for entry in feed.entries[:15]:
        title = entry.title
        link = entry.link

        if any(word in title for word in include_keywords) and not any(word in title for word in exclude_keywords):
            filtered_news.append((title, link))

        if len(filtered_news) >= 5:
            break

    return filtered_news

# 단독 실행 테스트
if __name__ == "__main__":
    print("📊 국내 증시 요약:")
    print(get_korea_market_summary())

    print("\n🪙 코인 요약:")
    print(get_crypto_market_summary())

    print("\n🌍 주요 뉴스:")
    for title, link in get_main_news():
        print("-", title, "->", link)
