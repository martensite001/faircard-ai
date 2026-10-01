"""
FairCard-AI 분석 엔진 v0.2  (Python ≥3.10, scikit-learn 1.8, Pillow 12)

파이프라인
  ① split_sentences : 약관 원문 → 조항 문장
  ② Stage-1 규칙     : 위험 신호 8종 / 양호 신호 3종 정규식 (높은 정밀도, 설명 가능)
  ③ Stage-2 검색(RAG): 규칙 미탐 문장을 근거 코퍼스(refs/legal_refs.json)의 예시 표현과
                        TF-IDF(char 2–3gram) 코사인 유사도로 대조 → τ 이상이면 '검토 필요'로 승격
                        + 모든 탐지 문장에 근거 조문 요지를 검색해 첨부
  ④ Stage-3 LLM(선택): ANTHROPIC_API_KEY 가 있으면 JSON Schema 강제 출력으로 재판정(llm_verify)
  ⑤ score / grade   : Fair-Score = 100 − Σ감점 + Σ가점 − 6
입력 : str(UTF-8 약관 원문)   출력 : dict(card JSON, 스키마는 CARD_SCHEMA)
실패 : 빈 입력 → ValueError / 근거 코퍼스 누락 → FileNotFoundError
"""
from __future__ import annotations
import hashlib, json, os, re
from pathlib import Path
from functools import lru_cache

ENGINE_VERSION = "hybrid-0.2"
REFS_PATH = Path(__file__).resolve().parent.parent / "refs" / "legal_refs.json"
TAU = 0.45  # dev 셋 그리드 탐색(0.20–0.45)으로 결정 — test 셋은 τ 선택에 미사용 (eval.py)

# (id, 영역, 라벨, 정규식, 감점, 행동 가이드)
RULES = [
    ("T1", "투명성", "입력 데이터의 AI 학습 활용",
     r"(학습|훈련|모델\s*(개선|고도화)|성능\s*(향상|개선)).{0,25}(활용|이용|사용)|(활용|이용|사용).{0,25}(학습|훈련)", 12,
     "설정에서 '학습 활용 거부(옵트아웃)' 여부를 확인하세요"),
    ("T2", "투명성", "장기 보관(1년 이상) 또는 기간 불명확",
     r"(\d+\s*년|영구|무기한|별도\s*고지\s*시까지).{0,15}(보관|보유)", 8,
     "보유기간 경과 후 삭제 요청이 가능한지 확인하세요"),
    ("T3", "투명성", "개인정보 국외 이전",
     r"(국외|해외|해외\s*서버|미국|클라우드\s*사업자).{0,20}(이전|전송|보관|처리\s*위탁)", 6,
     "이전 국가·업체·거부 방법 기재 여부를 확인하세요"),
    ("B1", "권익", "AI 결과물 일방 면책·책임 전가",
     r"(일체|어떠한|모든).{0,15}(책임|보상|배상).{0,10}(지지\s*않|하지\s*않|없)|책임은.{0,10}(이용자|회원|고객).{0,6}(에게|본인)", 15,
     "고의·중과실 면책은 무효 소지 — 소비자원 상담 가능"),
    ("B2", "권익", "환불·청약철회 제한",
     r"(환불|청약\s*철회|해지).{0,15}(불가|하지\s*않|제한|불가능)", 12,
     "결제 후 7일 이내 미사용분 철회 가능 여부 확인"),
    ("B3", "권익", "사전 통지 없는 일방 변경",
     r"(사전\s*(통지|고지|안내)\s*없이|임의로|회사의\s*판단에\s*따라).{0,20}(변경|중단|종료|해지)", 10,
     "변경 공지 방법·기간이 명시돼 있는지 확인"),
    ("B4", "권익", "자동갱신·유료전환 고지 미흡",
     r"(자동\s*(갱신|연장|결제)|유료\s*(전환|결제)).{0,30}(별도\s*(통지|고지|안내)\s*(없이|하지\s*않))", 10,
     "갱신 전 알림 설정·해지 경로를 확인하세요"),
    ("B5", "권익", "고객에 불리한 전속 관할",
     r"(회사|본사).{0,15}(소재지|주소지).{0,15}(관할|법원)", 5,
     "분쟁 시 소비자원 분쟁조정(무료)을 먼저 활용"),
]
GOOD = [
    ("G1", "AI 사용 사실 고지", r"(인공지능|AI).{0,20}(생성|이용|사용).{0,20}(고지|표시|안내)", 4),
    ("G2", "학습 거부(옵트아웃) 제공", r"(학습|훈련).{0,30}(거부|옵트\s*아웃|opt-?out|중단\s*요청|철회)", 6),
    ("G3", "결과물 오류 이의제기 절차", r"(이의\s*제기|정정\s*요청|재생성).{0,20}(절차|신청|가능)", 3),
]
# 소비자 보호 문맥(안전 신호) — Stage-2 오탐 억제용
SAFE = re.compile(r"(사용|이용|활용|제공)하지\s*않|\d+\s*일\s*(이내|전)|전에?\s*(공지|안내|알려)|법령에\s*따라|민사소송법|"
                  r"대한민국\s*내|(신청|요청|선택)\S{0,2}\s*(가능|할\s*수)|국내.{0,6}(에만|만)|파기|철회할\s*수|환불받을\s*수|분쟁해결기준|표시합니다|목적으로만")
SPLIT = re.compile(r"(?<=[.!?。])\s+|\n+")
RULE_MAP = {r[0]: r for r in RULES}


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in SPLIT.split(text) if len(s.strip()) > 4]


@lru_cache(maxsize=1)
def _index():
    from sklearn.feature_extraction.text import TfidfVectorizer
    refs = json.loads(REFS_PATH.read_text(encoding="utf-8"))
    rows = [(r["rule"], ex) for r in refs["refs"] for ex in r["exemplars"]]
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 3), sublinear_tf=True)
    X = vec.fit_transform([e for _, e in rows])
    return vec, X, rows, {r["rule"]: r for r in refs["refs"]}, refs["_meta"]["version"]


def retrieve(sentence: str):
    """문장 → (가장 유사한 rule_id, 유사도, 근거 dict)"""
    from sklearn.metrics.pairwise import cosine_similarity
    vec, X, rows, refmap, _ = _index()
    sims = cosine_similarity(vec.transform([sentence]), X)[0]
    i = int(sims.argmax())
    rid = rows[i][0]
    return rid, float(sims[i]), refmap[rid]


def rule_hits(s: str) -> list[str]:
    out = []
    for rid, *_r in RULES:
        if re.search(RULE_MAP[rid][3], s):
            if rid == "T1" and re.search(r"(활용|이용|사용)하지\s*않", s):
                continue
            out.append(rid)
    return out


def classify(s: str, use_rag: bool = True, tau: float = TAU):
    """문장 단위 판정 → list[(rule_id, source, sim)]"""
    hits = [(r, "rule", 1.0) for r in rule_hits(s)]
    if not hits and use_rag and not SAFE.search(s):
        rid, sim, _ = retrieve(s)
        if sim >= tau:
            hits.append((rid, "rag", sim))
    return hits


def llm_verify(card: dict, sentences: list[str]) -> dict:
    """Stage-3 (선택): Claude API로 각 finding 재판정. 키가 없으면 그대로 반환.
    JSON 강제: {"keep": bool, "reason": str} — 응답 파싱 실패 시 원 판정 유지(보수적)."""
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key or not card["findings"]:
        return card
    try:
        import anthropic  # pip install anthropic
        client = anthropic.Anthropic(api_key=key)
        for f in card["findings"]:
            msg = client.messages.create(
                model=os.getenv("FAIRCARD_MODEL", "claude-sonnet-4-5"), max_tokens=200,
                system="너는 한국 소비자법 보조 분석가다. 법률 자문이 아닌 '주의 신호' 여부만 판단해 JSON으로만 답한다.",
                messages=[{"role": "user", "content": json.dumps({
                    "clause": f["evidence"], "flag": f["label"], "reference": f["legal_ref"],
                    "answer_format": {"keep": "bool", "reason": "string(60자 이내)"}}, ensure_ascii=False)}])
            out = json.loads(msg.content[0].text)
            f["llm"] = out
        card["findings"] = [f for f in card["findings"] if f.get("llm", {}).get("keep", True)]
        card["engine"] += "+llm"
    except Exception as e:  # 네트워크·파싱 실패 → 원 판정 유지
        card["llm_error"] = str(e)[:120]
    return card


def grade(score: int) -> str:
    for th, g in [(90, "A"), (80, "B+"), (70, "B"), (60, "C+"), (50, "C")]:
        if score >= th:
            return g
    return "D"


def analyze(text: str, service: str = "대상 서비스", use_rag: bool = True) -> dict:
    if not text or not text.strip():
        raise ValueError("빈 약관 텍스트")
    sents = split_sentences(text)
    findings, positives, seen = [], [], set()
    cands = [(s, rid, src, sim) for s in sents for rid, src, sim in classify(s, use_rag)]
    cands.sort(key=lambda c: c[2] != "rule")  # 규칙 근거 우선, 같은 신호의 RAG 후보는 뒤로
    for s, rid, src, sim in cands:
        if rid in seen:
            continue
        seen.add(rid)
        _, area, label, _, pen, act = RULE_MAP[rid]
        ref = _index()[3][rid]
        findings.append({"rule_id": rid, "area": area, "label": label, "evidence": s[:140],
                         "penalty": pen if src == "rule" else pen // 2,  # RAG 승격분은 감점 50%
                         "source": src, "similarity": round(sim, 3),
                         "legal_ref": f'{ref["law"]} {ref["article"]}', "gist": ref["gist"], "action": act})
    for s in sents:
        for gid, label, pat, bonus in GOOD:
            if gid not in seen and re.search(pat, s, re.I):
                seen.add(gid)
                positives.append({"id": gid, "label": label, "bonus": bonus, "evidence": s[:140]})
    score = max(0, min(100, 100 - sum(f["penalty"] for f in findings) + sum(p["bonus"] for p in positives) - 6))
    guide = ["한국소비자원 1372 소비자상담센터 / 피해구제 신청 (kca.go.kr)"]
    if any(f["area"] == "투명성" for f in findings):
        guide.append("개인정보 침해신고센터 118 (privacy.kisa.or.kr)")
    card = {"service": service, "score": score, "grade": grade(score), "findings": findings,
            "positives": positives, "action_guide": guide, "n_sentences": len(sents),
            "source_sha256": hashlib.sha256(text.encode()).hexdigest(), "engine": ENGINE_VERSION,
            "refs_version": _index()[4],
            "disclaimer": "본 카드는 법률 자문이 아닌 주의 신호이며, 근거 조문은 원문 확인이 필요합니다."}
    return llm_verify(card, sents)


CARD_SCHEMA = {
    "type": "object",
    "required": ["service", "score", "grade", "findings", "positives", "action_guide", "source_sha256", "engine"],
    "properties": {
        "score": {"type": "integer", "minimum": 0, "maximum": 100},
        "grade": {"enum": ["A", "B+", "B", "C+", "C", "D"]},
        "findings": {"type": "array", "items": {"type": "object",
                     "required": ["rule_id", "area", "label", "evidence", "penalty", "source", "legal_ref"]}},
    },
}
