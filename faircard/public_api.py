"""
외부 연동 계층 — 약관 수집(Fetcher)과 공공데이터 조회(KCA 분쟁사례 등).

모드
  DEMO (기본, API 키 없음) : 가상 도메인(*.example, RFC 2606 예약)의 약관과
                             시드 고정 '시뮬레이션 분쟁사례' DB를 반환. 화면에 'DEMO · 시뮬레이션' 배지 표시.
  LIVE (FAIRCARD_LIVE=1)   : 실제 HTTP 수집 + 공공데이터포털 API (서비스 키 필요, 구현 예정 — 엔드포인트 확인 필요)
주의: 시뮬레이션 데이터는 실제 한국소비자원·공정위 데이터가 아니며 기능 시연용이다.
"""
from __future__ import annotations
import json, os, random, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIVE = os.getenv("FAIRCARD_LIVE") == "1"
MODE = "LIVE" if LIVE else "DEMO"

DEMO_SITES = {
    "https://photostudio.demo.example/terms": ("가상 AI 포토스튜디오", "sample_bad"),
    "https://lite.photostudio.demo.example/terms": ("가상 AI 포토스튜디오 Lite", "sample_mid"),
    "https://chatmate.demo.example/terms": ("가상 AI 챗봇 ChatMate", "sample_para"),
    "https://writer.demo.example/terms": ("가상 AI 글쓰기 도우미", "sample_good"),
}


def fetch_terms(url: str) -> tuple[str, str, dict]:
    """URL → (서비스명, 약관 원문, 메타). DEMO는 가상 도메인만 허용."""
    url = url.strip()
    if LIVE:
        raise NotImplementedError("LIVE 수집기는 robots.txt 확인·HTML 본문 추출 구현 후 활성화")
    if url not in DEMO_SITES:
        raise KeyError("DEMO 모드에서는 가상 도메인(*.demo.example)만 수집할 수 있습니다.")
    t0 = time.perf_counter()
    name, stem = DEMO_SITES[url]
    text = (ROOT / "samples" / f"{stem}.txt").read_text(encoding="utf-8")
    meta = {"mode": MODE, "url": url, "bytes": len(text.encode()), "fetch_ms": round((time.perf_counter() - t0) * 1000, 1),
            "robots_txt": "allow (simulated)"}
    return name, text, meta


# ---------------------------------------------------------------- 시뮬레이션 분쟁사례 DB
_ISSUES = {
    "T1": ("AI 학습 활용 고지 미흡", ["업로드 사진이 동의 없이 학습에 쓰였다며 삭제 요구", "대화 기록 학습 활용 사실을 사후에 인지"]),
    "T2": ("보관기간 불명확", ["탈퇴 후에도 이미지가 남아 있어 파기 요청", "보유기간 미고지로 삭제 요구"]),
    "T3": ("국외 이전 고지 미흡", ["해외 서버 이전 사실 미고지 문의"]),
    "B1": ("AI 결과물 면책", ["AI 생성 결과 오류로 인쇄 비용 손해 배상 요구", "번역 오류로 계약 손해, 면책조항 근거 거절"]),
    "B2": ("환불·청약철회 거부", ["미사용 크레딧 환불 거부", "결제 직후 철회 요청 거절"]),
    "B3": ("일방적 서비스 변경", ["사전 공지 없는 요금 인상", "기능 축소 후 보상 거부"]),
    "B4": ("자동갱신 고지 미흡", ["무료체험 후 자동 결제 인지 못함", "연간 구독 자동 갱신 환불 요구"]),
    "B5": ("관할 조항", ["사업자 소재지 관할로 소송 부담 호소"]),
}
_RESULT = ["환급 권고", "합의(부분 환급)", "정보제공·상담 종결", "시정 권고", "조정 성립"]


def _build_db(seed: int = 20261001, n: int = 48) -> list[dict]:
    rng = random.Random(seed); db = []
    keys = list(_ISSUES)
    for i in range(n):
        k = keys[i % len(keys)]; title, cases = _ISSUES[k]
        db.append({"case_id": f"SIM-2026-{i + 1:04d}", "issue": k, "issue_name": title,
                   "summary": rng.choice(cases), "service_type": rng.choice(["생성형 이미지", "AI 챗봇", "AI 번역", "AI 학습앱"]),
                   "result": rng.choice(_RESULT), "month": f"2026-{rng.randint(1, 9):02d}", "simulated": True})
    return db


_DB = _build_db()


def similar_disputes(rule_ids: list[str], k: int = 4) -> dict:
    """탐지된 rule_id 목록 → 유사 분쟁사례 상위 k건 (DEMO: 시뮬레이션 DB)."""
    t0 = time.perf_counter()
    hits = [c for c in _DB if c["issue"] in set(rule_ids)]
    hits.sort(key=lambda c: (rule_ids.index(c["issue"]), c["month"]), reverse=False)
    out = []
    seen = set()
    for c in hits:  # 신호별 1건씩 우선
        if c["issue"] not in seen:
            out.append(c); seen.add(c["issue"])
    out += [c for c in hits if c not in out]
    return {"mode": MODE, "source": "시뮬레이션 분쟁사례 DB (seed 20261001, 48건)" if not LIVE else "한국소비자원 공공데이터",
            "latency_ms": round((time.perf_counter() - t0) * 1000, 2), "total_matched": len(hits), "items": out[:k]}


def dump_mock_db(path: Path = ROOT / "data" / "mock_kca_cases.json"):
    path.write_text(json.dumps({"_note": "가상 데이터 — 실제 한국소비자원 데이터 아님", "items": _DB}, ensure_ascii=False, indent=1), encoding="utf-8")
    return path
