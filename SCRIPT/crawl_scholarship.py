# -*- coding: utf-8 -*-
"""
고려대학교 세종캠퍼스 장학공지 게시판 크롤러
- 목록(1~20페이지)에서 각 글의 상세 페이지를 방문
- 제목, 성격, 신청날짜, 지원대상, 금액을 추출
- 근로·시급 지급형 프로그램은 제외
- 결과를 장학공지_crawling.csv (UTF-8-SIG) 로 저장
"""
import csv
import re
import time
import base64
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, quote

import requests
from bs4 import BeautifulSoup

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "DATA"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CSV_PATH = DATA_DIR / "장학공지_crawling.csv"
LOG_PATH = Path(__file__).resolve().parent / "_crawl_log.txt"
_logf = open(LOG_PATH, "w", encoding="utf-8")


def log(msg):
    _logf.write(str(msg) + "\n")
    _logf.flush()


BASE = "https://secu.korea.ac.kr"
SUBVIEW = "https://secu.korea.ac.kr/koreaSejong/7906/subview.do"

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0 Safari/537.36"),
    "Referer": SUBVIEW,
}

session = requests.Session()
session.headers.update(HEADERS)


def make_enc(page):
    """subview.do 의 enc 파라미터(base64) 생성."""
    inner = (f"/bbs/koreaSejong/659/artclList.do?page={page}"
             f"&findType=&findWord=&findClSeq=&findOpnwrd="
             f"&rgsBgndeStr=&rgsEnddeStr=&")
    raw = f"fnct1|@@|{inner}"
    return base64.b64encode(raw.encode("utf-8")).decode("ascii")


def get_list_page(page):
    enc = make_enc(page)
    url = f"{SUBVIEW}?enc={quote(enc)}"
    r = session.get(url, timeout=20)
    r.encoding = "utf-8"
    return r.text


def parse_list(html):
    """목록에서 (제목, 상세URL) 목록 추출. 중복 제거(상단 고정공지 제외)."""
    soup = BeautifulSoup(html, "html.parser")
    items = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "artclView.do" in href:
            detail = urljoin(BASE, href)
            title = " ".join(a.get_text(" ").split())
            if not title:
                continue
            if detail in seen:
                continue
            seen.add(detail)
            items.append((title, detail))
    return items


def clean(text):
    if not text:
        return ""
    text = text.replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


STOP_WORDS = r"(신청기간|신청 기간|접수기간|신청방법|신청 방법|지원대상|신청자격|신청대상|선발인원|" \
             r"지원금액|장학금액|지원내용|문의|제출서류|접수처|접 수 처|선발방법|유의사항)"
# 다음 항목 번호/글머리표에서 값 자르기
ITEM_BREAK = r"\s(?:\d{1,2}\s*\.\s|[❍○●■□▶◎※*]|\-\s)"


def find_field(body_text, keywords, maxlen=120):
    """본문에서 '항목 제목' 형태의 키워드 뒤 값을 추출. 없으면 빈 문자열.
    - '신청자격 : ...' 처럼 콜론이 붙은 경우
    - '1. 신청대상 ...', '❍ 신청자격 ...' 처럼 번호/글머리 뒤에 오는 경우
    문장 중간의 '대상자로 선정' 같은 표현은 무시한다.
    """
    for kw in keywords:
        for m in re.finditer(re.escape(kw), body_text):
            start, end = m.start(), m.end()
            if body_text[end:end + 1] == "자":  # '대상자', '지원대상자가' 등 제외
                continue
            after = body_text[end:end + maxlen + 40]
            # 키워드 바로 뒤 괄호 설명 제거: 신청자격(모든 요건 충족 필수)
            after = re.sub(r"^\s*\([^)]{0,30}\)", "", after)
            before = body_text[max(0, start - 5):start]
            has_colon = bool(re.match(r"\s*[:：]", after))
            is_header = bool(re.search(r"(?:\d{1,2}\s*[.)]|[❍○●■□▶◎※\-])\s*$", before))
            if not (has_colon or is_header):
                continue
            seg = re.sub(r"^[\s:：]+", "", after)
            seg = re.sub(r"^(?:[❍○●■□▶◎※\-]|\d{1,2}\))\s*", "", seg)
            seg = re.split(STOP_WORDS, seg)[0]
            seg = re.split(ITEM_BREAK, " " + seg)[0]
            val = clean(seg)[:maxlen]
            val = re.sub(r"\s*(?:\d{1,2}\s*[.)]|[(\-,])\s*$", "", val)  # 끝에 남은 번호/기호 제거
            if len(val) >= 2:
                return val
    return ""


DATE_RANGE = re.compile(
    r"(20\d{2})[.\-/년]\s*(\d{1,2})[.\-/월]\s*(\d{1,2})[일]?"
    r"\s*[~\-∼–]\s*"
    r"(?:(20\d{2})[.\-/년]\s*)?(\d{1,2})[.\-/월]\s*(\d{1,2})[일]?"
)


def extract_apply_date(body_text):
    """신청/접수 기간을 우선 추출. 없으면 단일 날짜."""
    # '신청기간/접수기간' 키워드 주변 우선 탐색
    for kw in ["신청기간", "신청 기간", "접수기간", "접수 기간", "신청기한", "제출기한", "모집기간"]:
        idx = body_text.find(kw)
        if idx != -1:
            seg = body_text[idx:idx + 120]
            m = DATE_RANGE.search(seg)
            if m:
                return clean(m.group(0))
            m2 = re.search(r"20\d{2}[.\-/년]\s*\d{1,2}[.\-/월]\s*\d{1,2}", seg)
            if m2:
                return clean(m2.group(0))
    # 신청기간 키워드가 없으면 공란
    return ""


AMOUNT_CANDIDATE_PAT = re.compile(
    r"(?:(?P<audience>대학원생|대학생|학부생|전문대(?:학생|생)?|종합대(?:학생|생)?)\s*)?"
    r"(?:(?P<per>1\s*인(?:당)?|인당)\s*)?"
    r"(?P<qualifier>최대|상한(?:액)?|한도|정액)?\s*"
    r"(?P<amount>\d[\d,]*\s*(?:천만원|백만원|만원|만\s*원|백만\s*원|천\s*원|원))"
)
AMOUNT_LABEL_PAT = re.compile(
    r"장\s*학\s*금(?:\s*액)?|지원\s*금액|지급\s*금액|지\s*급\s*액|지원\s*내용"
)


def _format_amount_match(match, context_before):
    """대상·상한 표현을 포함한 읽기 쉬운 금액 문자열을 만든다."""
    audience = match.group("audience") or ""
    if not audience:
        audience_match = re.search(
            r"(대학원생|대학생|학부생|전문대(?:학생|생)?|종합대(?:학생|생)?)\s*[:：,/-]?\s*$",
            context_before,
        )
        if audience_match:
            audience = audience_match.group(1)

    parts = []
    if audience:
        parts.append(clean(audience))
    per = match.group("per") or ("1인당" if re.search(r"1\s*인당[^\d]{0,30}$", context_before) else "")
    if per:
        parts.append("1인당")
    qualifier = match.group("qualifier") or ""
    if not qualifier:
        contextual_qualifier = re.search(r"(최대|상한액|금액한도)[^\d]{0,25}$", context_before)
        if contextual_qualifier:
            qualifier = "한도" if contextual_qualifier.group(1) == "금액한도" else contextual_qualifier.group(1)
    if qualifier:
        parts.append("상한액" if qualifier.startswith("상한") else qualifier)

    amount = clean(match.group("amount"))
    amount = re.sub(r"만\s+원", "만원", amount)
    amount = re.sub(r"백만\s+원", "백만원", amount)
    amount = re.sub(r"천\s+원", "천원", amount)
    amount = re.sub(r"([\d,]+)\s+(천만원|백만원|만원|천원|원)", r"\1\2", amount)
    if amount.endswith("천원"):
        thousands = int(amount[:-2].replace(",", ""))
        won = thousands * 1_000
        amount = f"{won // 10_000}만원" if won % 10_000 == 0 else f"{won:,}원"
    parts.append(amount)
    return " ".join(parts)


def extract_amount(body_text):
    """본문의 모든 금액 후보 중 대학생·1인당 지급액을 우선 추출한다.

    '장 학 금'처럼 띄어 쓴 라벨과 대상별 금액 표기를 지원하며, 총예산보다
    대학생 개인이 실제 받을 수 있는 금액을 우선한다.
    """
    # 표에서 띄어 쓴 주요 표현을 정규화해 동일한 패턴으로 비교한다.
    amount_text = re.sub(r"대\s*학\s*생", "대학생", body_text)
    amount_text = re.sub(r"1\s*인\s*당", "1인당", amount_text)

    candidates = []
    for match in AMOUNT_CANDIDATE_PAT.finditer(amount_text):
        before = amount_text[max(0, match.start() - 100):match.start()]
        nearby = before[-55:]
        audience = match.group("audience") or ""
        score = 0

        raw_amount = clean(match.group("amount"))
        amount_number = int(re.match(r"[\d,]+", raw_amount).group(0).replace(",", ""))
        # '421백만원'처럼 개인 기준 없이 큰 백만원 단위로 제시된 값은 총예산이다.
        if ("백만원" in raw_amount and amount_number >= 10
                and not audience and not match.group("per") and not match.group("qualifier")):
            continue
        if (re.search(r"천\s*원", raw_amount) and amount_number >= 10_000
                and not audience and not match.group("per") and not match.group("qualifier")):
            continue

        if audience in ("대학생", "대학원생", "학부생"):
            score += 150
        elif audience.startswith("종합대"):
            score += 145
        elif audience.startswith("전문대"):
            score += 135
        elif re.search(r"(?:대학원생|대학생|학부생)\s*[:：,/-]?\s*$", nearby):
            score += 145

        if match.group("per"):
            score += 110
        elif re.search(r"1인당(?:\s*최대)?(?:\s*지급)?금액[^\d]{0,25}$", nearby):
            score += 110
        if match.group("qualifier"):
            score += 45
        elif re.search(r"(?:최대|상한액|금액한도)[^\d]{0,20}$", nearby):
            score += 45
        if AMOUNT_LABEL_PAT.search(before[-60:]):
            score += 55
        if re.search(r"(?:생활비|등록금|학업보조비|지원금)\s*$", nearby):
            score += 35
        if re.search(r"(?:총액|총예산|예산액|지원총액)\s*[:：]?\s*$", nearby):
            score -= 120
        if "백만원" in match.group("amount") and not (audience or match.group("per")):
            score -= 35

        value = _format_amount_match(match, before)
        candidates.append((score, match.start(), value))

    # 숫자 대신 전액 지원으로 명시된 경우도 금액 정보로 보존한다.
    for match in re.finditer(r"(?:등록금|수업료)\s*(?:전액\s*지원|전액)", amount_text):
        candidates.append((130, match.start(), clean(match.group(0))))

    if not candidates:
        return ""
    # 점수가 같으면 본문에서 먼저 명시된 값을 선택한다.
    return max(candidates, key=lambda item: (item[0], -item[1]))[2]


def normalize_amount(amount):
    """금액을 '숫자만원' 또는 '최대 숫자만원' 형식으로 통일한다.

    금액을 숫자로 환산할 수 없는 등록금·수업료 전액 지원은 '전액'으로 둔다.
    """
    amount = clean(amount)
    if not amount:
        return ""
    if "전액" in amount:
        return "전액"

    use_max = any(word in amount for word in ("최대", "한도", "상한액", "상한"))
    compact = re.sub(r"\s+", "", amount).replace(",", "")

    value_manwon = None
    match = re.search(r"(\d+(?:\.\d+)?)천만원", compact)
    if match:
        value_manwon = float(match.group(1)) * 1_000
    else:
        match = re.search(r"(\d+(?:\.\d+)?)백만원", compact)
        if match:
            value_manwon = float(match.group(1)) * 100
        else:
            match = re.search(r"(\d+(?:\.\d+)?)만원", compact)
            if match:
                value_manwon = float(match.group(1))
            else:
                match = re.search(r"(\d+(?:\.\d+)?)천원", compact)
                if match:
                    value_manwon = float(match.group(1)) / 10
                else:
                    match = re.search(r"(\d+(?:\.\d+)?)원", compact)
                    if match:
                        value_manwon = float(match.group(1)) / 10_000

    if value_manwon is None:
        return ""
    number = (str(int(value_manwon)) if value_manwon.is_integer()
              else f"{value_manwon:.4f}".rstrip("0").rstrip("."))
    prefix = "최대 " if use_max else ""
    return f"{prefix}{number}만원"


def normalize_target(target, title=""):
    """긴 지원자격 원문을 학적·거주지·소득·특수요건 중심으로 축약한다."""
    text = clean(target)
    title = clean(title)
    if not text or len(text) < 5:
        return ""
    if re.match(r"^(?:및\s*(?:구비서류|성적기준|장학금 내역)|공고일\s*\(`?$)", text):
        return ""

    text = re.sub(r"대학\s*\(\s*원\s*\)\s*생", "대학(원)생", text)
    text = re.sub(r"\s*([,·])\s*", r"\1 ", text)
    conditions = []

    def add(value):
        value = clean(value).strip(" ,.-")
        if value and value not in conditions:
            conditions.append(value)

    # 학적 조건
    if re.search(r"학부\s*4\s*학년\s*여학생", text):
        add("학부 4학년 여학생")
    elif "초·중·고·대 재학생" in text:
        add("초·중·고·대 재학생")
    elif "대학 신입생·재학생" in text:
        add("대학 신입생·재학생")
    elif re.search(r"고등학교의?\s*재학생.*대학교.*신입생", text):
        add("고등학생·대학 신입생")
    elif re.search(r"자연과학\s*및\s*공학계열.*3\s*학년", text):
        add("자연·공학계열 3학년 재학생")
    elif "박사과정" in text:
        add("박사과정 신입생·재학생" if "신입생" in text else "박사과정 재학생")
    elif re.search(r"초\s*[・·‧.]?\s*중\s*[・·‧.]?\s*고.*대학", text):
        add("초·중·고·대 재학생")
    elif "대학(원)생" in text:
        add("대학(원)생" + ("·미취업 졸업생" if "미취업 졸업생" in text else ""))
    elif "세종캠퍼스" in text and "재학생" in text:
        add("세종캠퍼스 재학생")
    elif re.search(r"대학교?\s*신입생\s*및\s*재학생|재학생\s*및\s*신입생", text):
        add("대학 신입생·재학생")
    elif "학부 재학생" in text or re.search(r"학부생", text):
        add("학부 재학생")
    elif re.search(r"대학(?:교)?\s*재학생|전국\s*소재\s*대학\s*재학생", text):
        add("대학 재학생")
    elif "재학생" in text:
        add("재학생")
    elif "대학생" in text:
        add("대학생")

    if "1 학년 학생" in text or "1학년 학생" in text:
        add("대학 1학년")
    if "휴학생 제외" in text or "휴학생" in text and "제외" in text:
        add("휴학생 제외")
    elif "휴학" in text and "졸업생 포함" in text:
        add("휴학생·졸업생 포함")

    # 거주지 조건
    if "서울 소재 대학교" in text or "서울시민" in text:
        add("서울 소재 대학 재학생·서울시민 자녀")
    else:
        place_match = re.search(
            r"([가-힣]{2,12}(?:특별자치시|광역시|특별시|시|군|구))(?=에|에서|\s|민|\b)", text
        )
        if place_match and re.search(r"거주|주민등록|주소|구민|시민", text):
            place = place_match.group(1)
            around = text[max(0, place_match.start() - 35):place_match.end() + 35]
            years = re.findall(r"(\d+)\s*년\s*이상", around)
            duration = f" {years[0]}년 이상" if years else ""
            if re.search(r"자녀|부모|보호자|직계존속|부\s*,\s*모", text):
                add(f"{place}{duration} 거주자·자녀")
            else:
                add(f"{place}{duration} 거주자")

    # 소득·성적 조건
    section = re.search(r"(?:학자금\s*지원구간|소득분위)\s*(\d+)\s*[~～-]\s*(\d+)\s*(?:구간|분위)?", text)
    if section:
        add(f"학자금 지원구간 {section.group(1)}~{section.group(2)}구간")
    else:
        section = re.search(r"학자금\s*지원구간\s*(\d+)\s*구간\s*이내", text)
        if section:
            add(f"학자금 지원구간 {section.group(1)}구간 이내")
    income = re.search(r"중위소득\s*(\d+)%\s*이하", text)
    if income:
        add(f"중위소득 {income.group(1)}% 이하")
    grade = re.search(r"평균\s*평점\s*(\d+(?:\.\d+)?)\s*이상", text)
    if grade:
        add(f"평점 {grade.group(1)} 이상")

    # 프로그램별 특수 자격
    if "고속도로 사고" in text:
        add("고속도로 사고 피해자·자녀")
    if "장애의 정도가 심한" in text or "중증장애" in text:
        add("중증장애인·자녀")
    if "골프선수" in text or "골프 선수" in text:
        add("골프선수·경력자")
    if "장기복무" in text and "제대군인" in text:
        add("10년 이상 장기복무 제대군인")
    if "다문화" in text or "귀화한 다문화 가정" in text:
        add("다문화가정 학생")
    if "가계곤란" in text or "복지 사각지대" in text:
        add("가계곤란 학생")
    if "학자금대출을 받은 자" in text:
        add("한국장학재단 학자금대출 이용자")
    if "전기관련학과" in text:
        add("전기관련학과 재학생")
    if "조합원" in text and "자녀" in text:
        add("조합원·임직원 및 자녀")
    if "5 자녀 이상" in text or "5자녀 이상" in text:
        add("5자녀 이상 가구")
    if "CPTA" in title:
        add("전문자격시험 합격자")
    if "성적경고해제자" in text:
        add("성적경고 해제 재학생")
    if "대한민국 국적" in text or "외국국적자 지원 불가" in text:
        add("대한민국 국적자")

    if not conditions:
        fallback = re.split(r"\s+(?:가|나|다|라)\s*[.)]|\s+\d+\)|\s*[①-⑳]", text)[0]
        fallback = re.sub(r"^(?:지원\s*)?(?:대상|자격|공통사항)\s*[:：]?\s*", "", fallback)
        if len(fallback) < 8 or fallback.endswith(("및", "중에서", "사람")):
            return ""
        add(fallback[:45].rstrip() + ("…" if len(fallback) > 45 else ""))

    return ", ".join(conditions[:4])


def date_to_quarter(date_text):
    """신청 시작월을 1~4분기로 변환한다. 날짜가 없으면 공란을 유지한다."""
    date_text = clean(date_text)
    if not date_text:
        return ""
    if re.fullmatch(r"[1-4]분기", date_text):
        return date_text

    patterns = [
        r"(?:20\d{2}|['’]?\d{2})\s*년\s*(1[0-2]|0?[1-9])\s*월",
        r"(?:20\d{2}|['’]?\d{2})\s*[./-]\s*(1[0-2]|0?[1-9])(?:\s*[./-])",
        r"(?<!\d)(1[0-2]|0?[1-9])\s*월",
        r"(?<!\d)(1[0-2]|0?[1-9])\s*[./-]\s*\d{1,2}",
    ]
    for pattern in patterns:
        match = re.search(pattern, date_text)
        if match:
            month = int(match.group(1))
            return f"{(month - 1) // 3 + 1}분기"
    return ""


FEATURE_SKIP_WORDS = (
    "첨부파일", "붙임", "공고문", "신청서", "카드뉴스", "자세한 사항", "홈페이지 참조",
    "신청기간", "신청 기간", "접수기간", "접수 기간",
)
FEATURE_KEYWORDS = (
    "지원", "선발", "신청", "지급", "장학", "근로", "등록금", "생활비", "대출", "인재", "대상",
)


def summarize_feature(text):
    """긴 특징 문장을 최대 3개의 짧은 개조식 항목으로 정리한다."""
    raw_text = (text or "").strip()
    if not raw_text:
        return ""
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    if lines and all(line.startswith("- ") for line in lines):
        return "\n".join(lines[:3])
    text = clean(raw_text)

    # 첨부파일 목록과 공지 제목에서 반복되는 상투 표현을 제거한다.
    text = re.sub(r"\[[^\]]*(?:붙임|공고문)[^\]]*\]", " ", text)
    text = re.sub(r"\S*\.(?:hwpx|hwp|pdf|png|jpe?g|xlsx?|docx?|zip)\b", " ", text)
    # 특징에서는 세부 날짜를 제거한다(신청날짜 열의 분기 정보와 중복 방지).
    text = re.sub(r"\(\s*20\d{2}[^)]{0,80}[~∼][^)]*\)", " ", text)
    text = re.sub(r"(?:20\d{2}|['’]?\d{2})\s*(?:년|[.])\s*\d{1,2}\s*(?:월|[.])\s*\d{1,2}\s*일?", "", text)
    text = re.sub(r"^(?:20\d{2}\s*(?:학년도|년도|년)\s*)", "", text)
    text = re.sub(r"^.*?(?:선발\s*(?:공고|안내)|모집\s*(?:공고|안내)|신청\s*안내)\s+", "", text)
    text = re.sub(r"(?:합니다|됩니다|바랍니다|있습니다|없습니다)\.\s*", "|", text)
    text = re.sub(r"\s+(?=(?:\d{1,2}\s*\.(?!\s*\d)|\d{1,2}\s*\)|[가-하]\s*[.)]|[①-⑳]|[○❍●■□▶◎※])\s*)", "|", text)
    text = re.sub(r"\s+-\s+", "|", text)

    candidates = []
    seen = set()
    for index, part in enumerate(text.split("|")):
        part = clean(part)
        part = re.sub(r"^(?:\d{1,2}\s*\.(?!\s*\d)|\d{1,2}\s*\)|[가-하]\s*[.)]|[①-⑳]|[○❍●■□▶◎※\-])\s*", "", part)
        part = re.sub(r"^(?:안내|공고|참고)\s*[:：-]?\s*", "", part)
        if (len(part) < 8 or any(word in part for word in FEATURE_SKIP_WORDS)
                or "_" in part
                or (re.search(r"[~∼]", part) and re.search(r"\d", part))
                or len(re.findall(r"\d+\s*[-.]\s*\d+", part)) >= 2
                or (len(part) < 25 and re.search(r"(?:에|의|및|로|과|와|을|를)$", part))
                or re.fullmatch(r"\[[^]]{0,30}\]", part)
                or re.fullmatch(r".*(?:선발개요|선발인원 및 장학금액)", part)):
            continue
        # 긴 문장은 의미가 끊기지 않는 선에서 축약한다.
        if len(part) > 72:
            shortened = part[:72]
            cut = shortened.rfind(" ")
            part = (shortened[:cut] if cut >= 45 else shortened).rstrip(" ,.") + "…"
        key = re.sub(r"\s+", "", part)
        if key in seen:
            continue
        seen.add(key)
        score = sum(1 for word in FEATURE_KEYWORDS if word in part)
        candidates.append((score, index, part.rstrip(" .")))

    if not candidates:
        return ""
    selected = sorted(candidates, key=lambda item: (-item[0], item[1]))[:3]
    selected.sort(key=lambda item: item[1])
    return "\n".join(f"- {part}" for _, _, part in selected)


def parse_detail(html, list_title):
    soup = BeautifulSoup(html, "html.parser")

    # 제목: 목록 제목을 신뢰(가장 깔끔). 상세의 .title 은 메타가 붙어 오염되므로 사용 안 함.
    title = list_title
    # 제목 뒤에 붙는 '작성일/작성자/조회수' 메타 제거
    title = re.split(r"\s*작성일\s*20\d{2}", title)[0]
    title = re.split(r"\s*새글\s*$", title)[0]
    title = clean(title)

    # 본문 컨테이너
    body_el = (soup.select_one(".board-view .view")
               or soup.select_one(".board-view")
               or soup.select_one(".view"))
    body_text = clean(body_el.get_text(" ")) if body_el else clean(soup.get_text(" "))

    # 본문에서 상단 메타(제목/작성일/작성자/조회수/첨부) 라인 제거
    body_text = re.sub(r"작성일\s*20\d{2}\.\d{1,2}\.\d{1,2}", " ", body_text)
    body_text = re.sub(r"작성자\s*\S+", " ", body_text)
    body_text = re.sub(r"조회수\s*\d+", " ", body_text)
    body_text = re.sub(r"첨부파일이\(가\) 없습니다\.?", " ", body_text)
    # 첨부파일명(hwp, pdf, 이미지 등) 제거
    body_text = re.sub(r"\S*\.(?:hwpx|hwp|pdf|png|jpe?g|xlsx?|docx?|zip)\b", " ", body_text)
    body_text = clean(body_text)

    apply_date = extract_apply_date(body_text)
    target = find_field(body_text, ["신청자격", "신청 자격", "지원자격", "지원 자격",
                                    "신청대상", "신청 대상", "지원대상", "지원 대상",
                                    "선발대상", "모집대상", "대상"])
    amount = extract_amount(body_text)

    # 성격: 제목 기반 분류
    if "국가근로" in title or "근로장학" in title:
        nature = "근로장학"
    elif "외부" in title or "재단" in title or "장학회" in title or "장학재단" in title:
        nature = "외부장학"
    elif "국가장학" in title:
        nature = "국가장학"
    elif "장학" in title:
        nature = "교내/일반장학"
    else:
        nature = "공지/안내"

    return {
        "제목": normalize_title(title),
        "성격": nature,
        "신청날짜": date_to_quarter(apply_date),
        "지원대상": normalize_target(target, title),
        "금액": amount,
    }


# 수집 대상에서 제외할 행정성 공지 (제목 일부로 판별)
EXCLUDE_KEYWORDS = [
    "KU SEJONG 장학 포탈 OPEN",
    "구매 담당자 사칭 피싱",
    "수혜계좌 등록",
    "계좌 등록 안내",
    "문의사항 모음",
    "문의 사항 모음",
    "자주 묻는 질문",
    "FAQ",
    "지급 내역",
    "지급내역",
    "가구원 동의",
    "사전교육 자료",
    "자체 기준 안내",
    "지급 방법 변경 안내",
    "학자금 지원 구간 개편",
]


def is_loan_title(title):
    compact = re.sub(r"\s+", "", title)
    return ("대출" in compact or "학자금융자" in compact
            or "학자금이자" in compact)


def is_excluded(title):
    """장학 프로그램 자체가 아닌 계좌·FAQ·행정 일정 공지를 제외한다.

    학자금 대출 항목은 일정 안내라도 유지한다.
    """
    if any(k.lower() in title.lower() for k in EXCLUDE_KEYWORDS):
        return True
    if "일정" in title and not is_loan_title(title):
        return True
    return False


def is_hourly_program(row):
    """근로 또는 시간당 단가로 지급하는 프로그램인지 판별한다."""
    title = clean(row.get("제목", ""))
    nature = clean(row.get("성격", ""))
    amount = clean(row.get("금액", ""))
    compact_title = re.sub(r"\s+", "", title).lower()

    # 근로장학은 근무시간에 따라 지급되므로 모두 제외한다.
    if nature == "근로장학" or "근로장학" in compact_title or "국가근로" in compact_title:
        return True

    # 청소년교육지원 멘토와 EBS 화상 튜터링은 시간당 활동비 지급형이다.
    hourly_program_keywords = ("청소년교육지원사업", "ebs화상튜터링")
    if any(keyword in compact_title for keyword in hourly_program_keywords):
        return True

    # '만원/백만원'이 아닌 소액 원 단위 금액은 명시적인 시급으로 간주한다.
    plain_won = re.search(r"([\d,]+)\s*원\s*$", amount)
    if (plain_won and "만원" not in amount and "백만원" not in amount
            and int(plain_won.group(1).replace(",", "")) <= 50_000):
        return True

    return False


def _clean_title_prefix(title):
    """연도·학기·공지 표식처럼 프로그램명이 아닌 제목 요소를 제거한다."""
    title = clean(title)
    title = re.sub(r"\s*작성일\s*20\d{2}.*$", "", title)
    title = re.sub(r"^[☆★\s]+|[☆★\s]+$", "", title)
    title = re.sub(r"\[대출\]\s*", "", title)
    title = re.sub(r"20\d{2}\s*(?:학년도|년도|년)\s*", "", title)
    title = re.sub(r"(?:상반기분|하반기분|상반기|하반기|하계방학|동계방학)\s*", "", title)
    title = re.sub(r"^(?:\(재\)|\[재\]|재\))\s*", "", title)
    title = re.sub(r"^분\s+(?=.*학자금)", "", title)  # 이전 정규화에서 남은 '상반기분' 꼬리 보정
    title = re.sub(r"\d+\s*학기\s*", "", title)
    title = re.sub(r"\d+\s*차\s*", "", title)
    title = re.sub(r"\(\s*(?:기한|기간)\s*연장[^)]*\)", "", title)
    return clean(title).strip("-–—:：,() ")


def normalize_title(title):
    """공지 제목을 장학금·장학생 선발·학자금 대출 이름으로 표준화한다."""
    title = _clean_title_prefix(title)

    if is_loan_title(title):
        # 문의/일정/안내 같은 공지 표현은 버리고 대출 제도명만 유지한다.
        title = re.sub(r"\s*(?:신청|실행)?\s*일정.*$", "", title)
        title = re.sub(r"\s*신규\s*제도.*$", "", title)
        title = re.sub(r"\s*(?:신청\s*)?(?:안내|공지|공고).*$", "", title)
        title = re.sub(r"분납\s*대출", "분납 학자금 대출", title)
        title = re.sub(r"학자금\s*융자", "학자금 대출", title)
        title = re.sub(r"학자금\s*이자", "학자금 대출이자", title)
        title = re.sub(r"학자금\s*대출", "학자금 대출", title)
        title = re.sub(r"대학\(원\)생\s*학자금", "대학(원)생 학자금", title)
        title = re.sub(r"\s*관련분야.*$", "", title)
        title = re.sub(r"\s*\([^)]*$", "", title)  # 잘린 원문 제목의 열린 괄호 제거
        title = re.sub(r"\s+장학금$", "", title)  # 이전 변환에서 붙은 불필요한 접미어 제거
        return clean(title).strip("-–—:：,() ")

    # '~장학생'이 포함된 공지는 반드시 '~장학생 선발'로 끝낸다.
    student = re.search(r"장학생", title)
    if student:
        return clean(title[:student.end()]).strip("-–—:：,() ") + " 선발"

    # 명시된 장학금 이름이 있으면 첫 장학금까지를 프로그램명으로 사용한다.
    scholarship = re.search(r"장학\s*금", title)
    if scholarship:
        normalized = title[:scholarship.end()]
        normalized = re.sub(r"장학\s*금", "장학금", normalized)
        return clean(normalized).strip("-–—:：,() ")

    # '장학사업/장학 프로그램/근로장학'도 '~장학금'으로 통일한다.
    scholarship_word = re.search(r"장학(?:\s*(?:사업|프로그램))?", title)
    if scholarship_word and not title[scholarship_word.start():].startswith(("장학회", "장학재단")):
        prefix = title[:scholarship_word.start()]
        word = scholarship_word.group(0)
        if word not in ("장학회", "장학재단"):
            return clean(prefix + "장학금").strip("-–—:：,() ")

    # 장학 게시판의 모집·지원사업은 사업명 뒤에 '장학금'을 붙인다.
    title = re.sub(r"\s*(?:신청|모집|선발|접수)\s*(?:안내|공지|공고|요강)?.*$", "", title)
    title = re.sub(r"\s*(?:안내|공지|공고).*$", "", title)
    return clean(title).strip("-–—:：,() ") + " 장학금"


def _fetch_detail(index, title, detail):
    """상세 글 하나를 가져온다. 일시적 실패는 한 번 재시도한다."""
    last_error = None
    for attempt in range(2):
        try:
            response = requests.get(detail, headers=HEADERS, timeout=30)
            response.raise_for_status()
            response.encoding = "utf-8"
            return index, parse_detail(response.text, title), None
        except Exception as error:
            last_error = error
            if attempt == 0:
                time.sleep(1)
    fallback = {
        "제목": normalize_title(title),
        "성격": "",
        "신청날짜": "",
        "지원대상": "",
        "금액": "",
    }
    return index, fallback, last_error


def main():
    targets = []
    seen_detail = set()  # 페이지 간 중복(고정공지) 제거용

    # 목록 20페이지에서 고유한 상세 글 대상을 먼저 수집한다.
    for page in range(1, 21):
        try:
            html = get_list_page(page)
        except Exception as error:
            log(f"[page {page}] 목록 요청 실패: {error}")
            continue
        items = parse_list(html)
        log(f"[page {page}] 글 {len(items)}건")
        if not items and page > 1:
            log(f"[page {page}] 항목 없음 - 종료")
            break
        for title, detail in items:
            if is_excluded(title) or detail in seen_detail:
                continue
            seen_detail.add(detail)
            targets.append((title, detail))

    # 사이트 부하를 과도하게 높이지 않도록 상세 조회는 4개까지만 병렬 처리한다.
    indexed_rows = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(_fetch_detail, index, title, detail)
            for index, (title, detail) in enumerate(targets)
        ]
        for completed, future in enumerate(as_completed(futures), start=1):
            index, row, error = future.result()
            if error:
                log(f"  상세 실패 {row['제목'][:30]}: {error}")
            if not is_hourly_program(row):
                row["금액"] = normalize_amount(row.get("금액", ""))
                indexed_rows[index] = row
            if completed % 25 == 0 or completed == len(futures):
                log(f"상세 처리 {completed}/{len(futures)}건")

    rows = [indexed_rows[index] for index in sorted(indexed_rows)]
    out = CSV_PATH
    with open(out, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["제목", "성격", "신청날짜", "지원대상", "금액"],
        )
        writer.writeheader()
        writer.writerows(rows)
    log(f"저장 완료: {out} (총 {len(rows)}건)")
    _logf.close()


if __name__ == "__main__":
    main()
