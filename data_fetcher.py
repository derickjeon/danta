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
import feedparser

def get_main_news():
    korean_feeds = [
        ('매일경제', 'https://www.mk.co.kr/rss/30000001/'),
        ('한국경제', 'https://rss.hankyung.com/economy.xml'),
        ('연합뉴스', 'https://www.yna.co.kr/economy/rss'),
    ]
    english_feeds = [
        ('Bloomberg', 'https://feeds.bloomberg.com/markets/news.rss'),
        ('Reuters', 'https://feeds.reuters.com/reuters/businessNews'),
        ('CNBC', 'https://www.cnbc.com/id/100003114/device/rss/rss.html'),
    ]

    exclude_keywords = ['교육', '세미나', '행사', '전시', '후원', '축제', '홍보', '캠페인', '강좌', '전달식']

    def fetch_from_source(name, url, per_feed=3):
        news_items = []
        feed = feedparser.parse(url)
        for entry in feed.entries:
            title = entry.title if hasattr(entry, 'title') else entry.get('summary', 'No Title')
            link = entry.link
            if not any(word in title for word in exclude_keywords):
                news_items.append((f"[{name}] {title}", link))
            if len(news_items) >= per_feed:
                break
        # 만약 뉴스가 부족하면 "현재 뉴스 없음"으로 채움
        while len(news_items) < per_feed:
            news_items.append((f"[{name}] 현재 뉴스 없음", "#"))
        return news_items

    korean_news = []
    for name, url in korean_feeds:
        korean_news.extend(fetch_from_source(name, url, per_feed=3))

    english_news = []
    for name, url in english_feeds:
        english_news.extend(fetch_from_source(name, url, per_feed=3))

    return korean_news + english_news  # 한국+영어 뉴스 합치기



# 단독 실행 테스트
if __name__ == "__main__":
    print("📊 국내 증시 요약:")
    print(get_korea_market_summary())

    print("\n🪙 코인 요약:")
    print(get_crypto_market_summary())

    print("\n🌍 주요 뉴스:")
    for title, link in get_main_news():
        print("-", title, "->", link)
