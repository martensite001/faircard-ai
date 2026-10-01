# FairCard-AI PoC v0.2 (2026 AI 라이프 솔루션 챌린지 제출용)

- 웹 데모: (배포 후 기재)
- 시연 영상: (업로드 후 기재)

AI 서비스 약관·개인정보처리방침 → 주의 조항 탐지(규칙 + TF-IDF 근거 검색) → Fair-Score → 3단 정보카드(PNG/JSON).

## 실행
```bash
pip install -r requirements.txt
streamlit run app.py                 # http://localhost:8501/?sample=sample_mid
python -m pytest -q                  # 단위·골든 회귀 테스트 7건
python eval.py                       # dev에서 τ 선택 → 동결 test 평가 (out/eval_result.json)
```
## 배포 (공개 테스트 URL)
GitHub 공개 저장소에 올린 뒤 Streamlit Community Cloud → New app → `app.py` 지정. Python 3.11.

## DEMO 모드 (기본)
API 키 없이 실행하면 DEMO 모드로 동작합니다.
- 약관 수집: 가상 도메인(`*.demo.example`, RFC 2606 예약 도메인) 4개만 허용 → `samples/*.txt` 반환
- 분쟁사례 조회: 시드 고정 **시뮬레이션 DB 48건**(메모리 생성, 파일로 보기: `python -c "from faircard.public_api import dump_mock_db; dump_mock_db()"`) — 실제 한국소비자원 데이터 아님
- LLM 3단계: `ANTHROPIC_API_KEY` 설정 시에만 동작
화면 사이드바·표에 'DEMO · 시뮬레이션' 배지가 항상 표시됩니다. `FAIRCARD_LIVE=1`은 실제 수집·공공데이터 API용(구현 예정).

## 시연 영상 재촬영
```bash
streamlit run app.py &            # 포트 8501
python demo/record_demo.py        # → demo/out/faircard_demo.mp4 (Playwright Chromium + ffmpeg)
```

## 구성
- `faircard/engine.py` 분석 엔진 (Stage1 규칙 / Stage2 RAG / Stage3 LLM 훅: `ANTHROPIC_API_KEY` 설정 시)
- `faircard/render.py` 카드 렌더러 · `faircard/public_api.py` 수집·공공데이터 연동(DEMO 시뮬레이션) · `app.py` 웹 데모
- `refs/legal_refs.json` 근거 코퍼스(조문 **요지 의역**, 법령 원문 아님 — law.go.kr 대조 필요)
- `data/dev.jsonl`(32) · `data/test_heldout.jsonl`(40, SHA-256 동결) — **자체 작성 합성 문장**

## 한계
평가셋이 자체 작성이라 실제 약관 성능을 대표하지 않음. 실약관 2인 교차 라벨링 평가가 다음 단계.
법률 자문이 아닌 주의 신호 제공 도구.

## 라이선스
코드 MIT(제안) · 폰트 Noto Sans CJK(SIL OFL 1.1) · 샘플 약관은 가상 텍스트.
