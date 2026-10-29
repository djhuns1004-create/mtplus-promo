from __future__ import annotations
import json, re
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse
from datetime import datetime, timezone, timedelta
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "feed.json"
BASE = "https://mtplus365.com"

SOURCES = {
    "verification": "https://mtplus365.com/posts/%EB%A8%B9%ED%8A%80%EC%8B%A0%EA%B3%A0",
    "partners": "https://mtplus365.com/posts/%EB%B3%B4%EC%A6%9D%EC%97%85%EC%B2%B4",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MTPlusPromoSync/1.1; +https://mtplus365.com/)",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8"
}

def clean_title(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()

def slug_title(href: str) -> str:
    path = unquote(urlparse(href).path).rstrip("/")
    slug = path.split("/")[-1]
    slug = re.sub(r"-\d+$", "", slug)
    return clean_title(slug.replace("-", " "))

def get_soup(url: str) -> BeautifulSoup:
    r = requests.get(url, headers=HEADERS, timeout=25)
    r.raise_for_status()
    # requests가 잘못 추정한 latin-1 때문에 한글이 깨지는 것을 방지한다.
    # HTML 원본 바이트를 BeautifulSoup에 넘기면 meta/header를 기준으로 인코딩을 판별한다.
    return BeautifulSoup(r.content, "html.parser")

def verification_items(soup: BeautifulSoup):
    found, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = urljoin(BASE, a["href"])
        decoded = unquote(urlparse(href).path)
        if "/posts/먹튀신고/" not in decoded:
            continue
        if href in seen:
            continue
        text = clean_title(a.get_text(" ", strip=True))
        parent_text = clean_title(a.parent.get_text(" ", strip=True) if a.parent else "")
        if not text:
            text = slug_title(href)
        if "공지" in text[:8] or "공지" in parent_text[:12]:
            continue
        # 너무 긴 행 텍스트가 잡히면 slug 기반 제목 사용
        if len(text) > 80 or "조회수" in text or re.search(r"\d{4}\.\d{2}\.\d{2}", text):
            text = slug_title(href)
        if not text:
            continue
        seen.add(href)
        found.append({"title": text, "url": href, "meta": "먹튀신고"})
        if len(found) >= 12:
            break
    return found

def partner_items(soup: BeautifulSoup):
    """Collect partner posts from either current or legacy board routes."""
    found, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = urljoin(BASE, a["href"])
        parsed = urlparse(href)
        if parsed.netloc not in {"mtplus365.com", "www.mtplus365.com"}:
            continue
        path = unquote(parsed.path).rstrip("/")
        match = re.match(r"^/(?:posts/)?보증업체/([^/]+)$", path)
        if not match:
            continue
        if href in seen:
            continue
        parent_text = clean_title(a.parent.get_text(" ", strip=True) if a.parent else "")
        if "공지" in parent_text[:12]:
            continue
        title = slug_title(href)
        if not title or title in {"상세", "상세 +"}:
            continue
        seen.add(href)
        found.append({"title": title, "url": href, "meta": "공식보증업체"})
        if len(found) >= 12:
            break
    return found


def exclude_removed_partners(items):
    # Explicitly excluded from the official partner feed.
    # Keep this exclusion on every scheduled sync, including fallback data.
    return [item for item in items if not any(name in (item.get("title", "") + " " + unquote(item.get("url", ""))) for name in ("하이카지노", "꿀벌", "옐로우벳", "옐러우벳"))]


def sync_partners(previous):
    # Prefer the actual public board route. Fall back to the legacy route only
    # when the first source fails or contains no recognized partner links.
    sources = ["https://mtplus365.com/보증업체", SOURCES["partners"]]
    for source in sources:
        try:
            items = partner_items(get_soup(source))
            print(f"partners source={source} count={len(items)}")
            if items:
                return exclude_removed_partners(items)
        except Exception as exc:
            print(f"partners source failed ({source}): {exc}")
    print("WARNING: no partner posts collected; retaining previous entries")
    return exclude_removed_partners(previous)

def main():
    previous = {}
    if OUT.exists():
        try:
            previous = json.loads(OUT.read_text(encoding="utf-8"))
        except Exception:
            previous = {}

    data = dict(previous)
    try:
        data["verification"] = verification_items(get_soup(SOURCES["verification"])) or previous.get("verification", [])
    except Exception as e:
        print("verification sync failed:", e)
    data["partners"] = exclude_removed_partners(sync_partners(previous.get("partners", [])))

    kst = timezone(timedelta(hours=9))
    data["updatedAt"] = datetime.now(kst).isoformat(timespec="seconds")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("saved", OUT, len(data.get("verification", [])), len(data.get("partners", [])))

if __name__ == "__main__":
    main()
