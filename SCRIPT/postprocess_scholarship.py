# -*- coding: utf-8 -*-
"""기존 장학공지 CSV를 표준화하고 행정성·시급 지급형 항목을 제거한다."""
import csv
import os
from pathlib import Path

from crawl_scholarship import (
    date_to_quarter,
    is_excluded,
    is_hourly_program,
    normalize_amount,
    normalize_target,
    normalize_title,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "DATA"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CSV_PATH = DATA_DIR / "장학공지_crawling.csv"
TMP_PATH = DATA_DIR / "장학공지_crawling.tmp.csv"
FIELDS = ["제목", "성격", "신청날짜", "지원대상", "금액"]


def write_rows(path, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as target:
        writer = csv.DictWriter(target, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main():
    with open(CSV_PATH, newline="", encoding="utf-8-sig") as source:
        rows = list(csv.DictReader(source))

    filtered = []
    hourly_count = 0
    for row in rows:
        original_title = row.get("제목", "").strip()
        if not original_title or is_excluded(original_title):
            continue

        row["제목"] = normalize_title(original_title)
        row["신청날짜"] = date_to_quarter(row.get("신청날짜", ""))
        if is_hourly_program(row):
            hourly_count += 1
            continue

        row["금액"] = normalize_amount(row.get("금액", ""))
        row["지원대상"] = normalize_target(row.get("지원대상", ""), row["제목"])
        row.pop("특징", None)
        filtered.append(row)

    write_rows(TMP_PATH, filtered)
    try:
        os.replace(TMP_PATH, CSV_PATH)
    except PermissionError:
        # Dropbox 동기화 폴더에서 파일 교체가 거부되면 내용을 직접 덮어쓴다.
        write_rows(CSV_PATH, filtered)
        os.remove(TMP_PATH)

    print(
        f"완료: {len(rows)}건 중 {len(filtered)}건 저장, "
        f"시급 지급형 {hourly_count}건 제외"
    )


if __name__ == "__main__":
    main()
