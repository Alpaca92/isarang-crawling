import ssl

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

try:
    # 일부 엔드포인트는 세션/쿠키가 없으면 런타임 오류를 반환한다.
    warmup = session.get(home_url, headers={"User-Agent": headers["User-Agent"]}, timeout=(10, 30))
    warmup.raise_for_status()
    print(f"워밍업 성공: {warmup.status_code}, 쿠키 수: {len(session.cookies)}")

    # 연결/응답 타임아웃을 분리해서 무한 대기 방지
    response = session.post(url, data=payload, headers=headers, timeout=(10, 30))
    response.raise_for_status()

    print("성공적으로 데이터를 가져왔습니다!")
    try:
        print(response.json())
    except ValueError:
        print(response.text[:1000])
except requests.exceptions.RequestException as exc:
    print("요청 실패:", repr(exc))
    print("힌트: 서버가 TLS handshake에서 연결을 끊는 경우 VPN/회사망/방화벽 또는 서버 측 차단 가능성이 큽니다.")