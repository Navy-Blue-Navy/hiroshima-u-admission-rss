import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timezone, timedelta
from email.utils import format_datetime, parsedate_to_datetime
from urllib.parse import urljoin
import hashlib
import re

URL = "https://www.hiroshima-u.ac.jp/nyushi/news?category=42"
OUTPUT = Path(__file__).parent / "hiroshima_u.xml"

JST = timezone(timedelta(hours=9))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/154.0.0.0 Safari/537.36"
    )
}

# --------------------------------------------------
# 既存RSSを読み込む
# --------------------------------------------------

old_items = {}

if OUTPUT.exists():
    try:
        old_tree = ET.parse(OUTPUT)

        for item in old_tree.getroot().findall("./channel/item"):

            guid = item.findtext("guid", "")

            if guid:
                old_items[guid] = {
                    "title": item.findtext("title", ""),
                    "link": item.findtext("link", ""),
                    "description": item.findtext("description", ""),
                    "pubDate": item.findtext("pubDate", ""),
                    "guid": guid,
                }

    except Exception:
        old_items = {}


# --------------------------------------------------
# 広島大学のページを取得
# --------------------------------------------------

response = requests.get(
    URL,
    headers=HEADERS,
    timeout=30
)

response.raise_for_status()

soup = BeautifulSoup(
    response.text,
    "html.parser"
)


# --------------------------------------------------
# 記事を抽出
# --------------------------------------------------

date_pattern = re.compile(
    r"^\s*(\d{4})/(\d{2})/(\d{2})\s*$"
)

current_items = []
seen_urls = set()

date_nodes = soup.find_all(
    string=date_pattern
)

for date_node in date_nodes:

    match = date_pattern.match(
        date_node.strip()
    )

    if not match:
        continue

    year = int(match.group(1))
    month = int(match.group(2))
    day = int(match.group(3))

    date_text = (
        f"{year:04d}/{month:02d}/{day:02d}"
    )

    # 日付を含む項目全体を探す
    container = date_node.parent

    article_link = None
    raw_title = None

    # 最大5階層まで上にたどって記事リンクを探す
    for _ in range(5):

        if container is None:
            break

        links = container.find_all(
            "a",
            href=True
        )

        for a in links:

            text = a.get_text(
                " ",
                strip=True
            )

            text = re.sub(
                r"\s+",
                " ",
                text
            ).strip()

            if not text:
                continue

            # 日付＋タイトルになっているリンクを採用
            if text.startswith(date_text):

                raw_title = text

                article_link = urljoin(
                    URL,
                    a["href"]
                )

                break

        if article_link:
            break

        container = container.parent

    if not article_link or not raw_title:
        continue

    # タイトル先頭の日付を削除
    title = raw_title[
        len(date_text):
    ].strip()

    if not title:
        continue

    # 同じ記事URLの重複を除外
    if article_link in seen_urls:
        continue

    seen_urls.add(
        article_link
    )

    pub_date = datetime(
        year,
        month,
        day,
        12,
        0,
        0,
        tzinfo=JST
    )

    # 個別記事URLをGUIDにする
    guid = hashlib.sha256(
        article_link.encode("utf-8")
    ).hexdigest()

    current_items.append({
        "title": title,
        "link": article_link,
        "description": "広島大学 入試情報",
        "pubDate": format_datetime(
            pub_date
        ),
        "guid": guid,
    })


# --------------------------------------------------
# 以前取得した記事も残す
# --------------------------------------------------

all_items = []
seen_guids = set()

for item in current_items:

    if item["guid"] not in seen_guids:

        all_items.append(
            item
        )

        seen_guids.add(
            item["guid"]
        )


for guid, item in old_items.items():

    if guid not in seen_guids:

        all_items.append(
            item
        )

        seen_guids.add(
            guid
        )


# --------------------------------------------------
# 新しい順に並べる
# --------------------------------------------------

def get_date(item):

    try:
        return parsedate_to_datetime(
            item["pubDate"]
        )

    except Exception:
        return datetime.min.replace(
            tzinfo=timezone.utc
        )


all_items.sort(
    key=get_date,
    reverse=True
)

# 最大300件保存
all_items = all_items[:300]


# --------------------------------------------------
# RSS 2.0を作成
# --------------------------------------------------

rss = ET.Element(
    "rss",
    version="2.0"
)

channel = ET.SubElement(
    rss,
    "channel"
)

ET.SubElement(
    channel,
    "title"
).text = "広島大学 入試情報"

ET.SubElement(
    channel,
    "link"
).text = URL

ET.SubElement(
    channel,
    "description"
).text = (
    "広島大学 入試情報の"
    "ニュース＆トピックス"
)

ET.SubElement(
    channel,
    "language"
).text = "ja"


# --------------------------------------------------
# RSS記事を書き込む
# --------------------------------------------------

for item in all_items:

    element = ET.SubElement(
        channel,
        "item"
    )

    ET.SubElement(
        element,
        "title"
    ).text = item["title"]

    ET.SubElement(
        element,
        "link"
    ).text = item["link"]

    ET.SubElement(
        element,
        "description"
    ).text = item["description"]

    ET.SubElement(
        element,
        "pubDate"
    ).text = item["pubDate"]

    guid_element = ET.SubElement(
        element,
        "guid"
    )

    guid_element.set(
        "isPermaLink",
        "false"
    )

    guid_element.text = item["guid"]


# --------------------------------------------------
# XML保存
# --------------------------------------------------

tree = ET.ElementTree(
    rss
)

ET.indent(
    tree,
    space="  "
)

tree.write(
    OUTPUT,
    encoding="utf-8",
    xml_declaration=True
)


# --------------------------------------------------
# 結果表示
# --------------------------------------------------

print("RSS作成成功")

print(
    "今回取得:",
    len(current_items),
    "件"
)

print(
    "RSS保存件数:",
    len(all_items),
    "件"
)

print(
    "保存先:",
    OUTPUT
)

print()
print("最新15件:")

for item in current_items[:15]:

    print(
        item["pubDate"],
        item["title"],
        "->",
        item["link"]
    )