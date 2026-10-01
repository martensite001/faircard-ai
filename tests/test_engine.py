"""단위·골든 회귀 테스트 — 실행: python -m pytest -q"""
import json, pytest
from pathlib import Path
from faircard.engine import analyze, classify, CARD_SCHEMA

ROOT = Path(__file__).resolve().parent.parent

def test_empty_input_raises():
    with pytest.raises(ValueError):
        analyze("   ")

def test_negation_not_flagged():
    assert not classify("회사는 고객 데이터를 학습 목적으로 사용하지 않습니다.")

def test_paraphrase_caught_by_rag_only():
    s = "AI가 제공한 정보의 오류로 발생한 손해에 대해 회사는 책임이 없습니다."
    assert not classify(s, use_rag=False)
    assert [r for r, src, _ in classify(s)] == ["B1"]

@pytest.mark.parametrize("name,grade", [("sample_bad", "D"), ("sample_mid", "B+"), ("sample_good", "A")])
def test_golden_grades(name, grade):
    card = analyze((ROOT / "samples" / f"{name}.txt").read_text(encoding="utf-8"), name)
    assert card["grade"] == grade
    for k in CARD_SCHEMA["required"]:
        assert k in card
    assert 0 <= card["score"] <= 100
    assert all(f["legal_ref"] for f in card["findings"])  # 근거 표기율 100%

def test_frozen_testset_hash():
    import hashlib
    h = hashlib.sha256((ROOT / "data/test_heldout.jsonl").read_bytes()).hexdigest()
    assert h == (ROOT / "data/test_heldout.sha256").read_text().split()[0]
