import ssl
from pathlib import Path

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry


class TLS12HttpAdapter(HTTPAdapter):
    """Use TLS 1.2 context for servers that reset newer TLS handshakes."""

    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        # Keep cert verification enabled while pinning minimum TLS version.
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


# 1. 이전 단계에서 확인한 엔드포인트 URL
url = "https://www.childcare.go.kr/icms/nursery/NurseryContentData.html"
home_url = "https://www.childcare.go.kr/"

# 2. 이미지에서 확인한 Form Data (Payload)
payload = {
    "searchType": "list",
    # 브라우저 캡처 기준: NSSlPLMAP (소문자 l)
    "flag": "NSSlPLMAP",
    "offset": "0",
    "chCnt": "",
    "reqCnt": "",
    "menuno": "166",
    "pageNum": "1",
    "pagingCnt": "704",
    "searchDetailCrtype": "",
    "searchDetailCrspec": "",
    "setSearchKeyword1": "",
    "setSearchKeyword2": "",
    "setSearchKeyword3": "",
    "setSearchKeyword4": "",
    "setSearchKeyword5": "",
    "setSearchKeyword6": "",
    "setSearchKeyword7": "",
    "setSearchKeyword8": "",
    "setSearchKeyword9": "",
    "crrepre_sort": "asc",
    "class_sum_num_sort": "",
    "crcapat_sort": "",
    "crchcnt_sort": "",
    "tchertcnt_sort": "",
    "ewcnt_sort": "",
    "spcedctchcnt_sort": "",
    "helthtchercnt_sort": "",
    "nrtrroom_cnt_sort": "",
    "plgrdco_cnt_sort": "",
    "searchPublic": "",
    "searchEvalute": "",
    "searchOpen": "",
    "sessionId": "",
    "ctprvn": "41000",  # 경기도 코드
    "ctprvnName": "경기도",
    "signgu": "",
    "signguName": "화성시",
    "dong": "",
    "callType": "road",
    "cname": "",
}

# 3. 브라우저인 척 하기 위한 Headers (필요시 추가)
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Origin": "https://www.childcare.go.kr",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.childcare.go.kr/",
}

retry = Retry(
    total=4,
    connect=4,
    read=2,
    backoff_factor=0.8,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=frozenset(["POST"]),
)

session = requests.Session()
session.mount("https://", TLS12HttpAdapter(max_retries=retry))

# API 원본 key를 사람이 읽기 쉬운 헤더로 변환
DISPLAY_COLUMNS = [
    ("stcode", "어린이집 코드"),
    ("crname", "어린이집명"),
    ("crtypenm", "유형"),
    ("crspecnm", "특성"),
    ("craddr", "주소"),
    ("tel_no", "전화번호"),
    ("crhome", "홈페이지"),
    ("crrepre", "대표자"),
    ("crcapat", "정원"),
    ("crchcnt", "현원"),
    ("tchertcnt", "교사수"),
    ("ewcnt", "평가등급수"),
    ("etnrtrynnm", "연장보육"),
    ("stsmrycn", "행정구역"),
]


def fetch_page(page_num: int) -> dict:
    page_payload = payload.copy()
    page_payload["pageNum"] = str(page_num)
    response = session.post(url, data=page_payload, headers=headers, timeout=(10, 30))
    response.raise_for_status()
    return response.json()


def collect_nursery_list(start_page: int = 1, max_pages: int = 2000) -> pd.DataFrame:
    rows = []

    for page in range(start_page, max_pages + 1):
        try:
            data = fetch_page(page)
        except requests.exceptions.RequestException as exc:
            print(f"{page}페이지 요청 실패로 수집 종료: {exc!r}")
            break

        result = data.get("result")
        nursery_list = data.get("nurseryList") or []

        # 요청 성공이 아니거나 결과가 비어 있으면 수집을 끝낸다.
        if result != "SUCCESS":
            print(f"{page}페이지에서 서버 result={result!r}, 수집 종료")
            break

        if not nursery_list:
            print(f"{page}페이지 nurseryList 비어 있음, 수집 종료")
            break

        rows.extend(nursery_list)
        print(f"{page}페이지 수집 완료: {len(nursery_list)}건 (누적 {len(rows)}건)")

    return pd.DataFrame(rows)


def to_display_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    available = [(src, dst) for src, dst in DISPLAY_COLUMNS if src in df.columns]
    if not available:
        return df.copy()

    selected = df[[src for src, _ in available]].copy()
    selected.columns = [dst for _, dst in available]
    return selected

try:
    # 일부 엔드포인트는 세션/쿠키가 없으면 런타임 오류를 반환한다.
    warmup = session.get(home_url, headers={"User-Agent": headers["User-Agent"]}, timeout=(10, 30))
    warmup.raise_for_status()
    print(f"워밍업 성공: {warmup.status_code}, 쿠키 수: {len(session.cookies)}")

    df = collect_nursery_list(start_page=1)
    if df.empty:
        print("수집된 nurseryList 데이터가 없습니다.")
    else:
        display_df = to_display_dataframe(df)
        out_dir = Path("results")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "nursery_list_kr.csv"
        display_df.to_csv(out_path, index=False, encoding="utf-8-sig")

        print("nurseryList 표 미리보기:")
        print(display_df.head(10).to_string(index=False))
        print(f"총 {len(df)}건 저장 완료: {out_path}")
except requests.exceptions.RequestException as exc:
    print("요청 실패:", repr(exc))
    print("힌트: 서버가 TLS handshake에서 연결을 끊는 경우 VPN/회사망/방화벽 또는 서버 측 차단 가능성이 큽니다.")