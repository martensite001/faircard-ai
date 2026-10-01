"""FairCard-AI 웹 데모 (Streamlit 1.64) — 실행: streamlit run app.py
흐름: URL 또는 원문 입력 → 수집 → 조항 분할 → 규칙 탐지 → 근거 검색(RAG) → 공공데이터 분쟁사례 매칭 → 정보카드
DEMO 모드: 가상 도메인 약관 + 시뮬레이션 분쟁사례(실제 기관 데이터 아님). 입력 원문은 저장하지 않음."""
import json, tempfile, time
from pathlib import Path
import streamlit as st
from faircard.engine import analyze, split_sentences, ENGINE_VERSION
from faircard.render import render_png
from faircard import public_api as api

st.set_page_config(page_title="FairCard-AI", page_icon="🪪", layout="wide")
st.markdown("""<style>
.block-container{padding-top:2.2rem;max-width:1500px}
.demo-badge{display:inline-block;background:#FFF1DC;color:#9A5B00;border:1px solid #F2A33A;border-radius:999px;padding:2px 12px;font-size:.85rem;font-weight:600}
.sim{color:#9A5B00;font-weight:600}
</style>""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### FairCard-AI")
    st.markdown(f'<span class="demo-badge">{api.MODE} · 공공데이터 API 시뮬레이션</span>', unsafe_allow_html=True)
    st.caption("DEMO 모드에서는 가상 도메인(*.demo.example) 약관과 시뮬레이션 분쟁사례 DB를 사용합니다. 실제 서비스·기관 데이터가 아닙니다.")
    st.markdown("**가상 서비스 URL**")
    for u, (n, _) in api.DEMO_SITES.items():
        st.code(u, language=None)
    st.caption(f"엔진 {ENGINE_VERSION} · LLM 3단계: API 키 미설정(비활성)")

st.title("FairCard-AI — AI 서비스 정보카드")
st.caption("AI 서비스 약관·개인정보처리방침을 분석해 학습 활용·면책·환불 등 주의 조항을 1장 카드로 보여줍니다. 법률 자문이 아닌 주의 신호입니다.")

c1, c2 = st.columns([5, 6], gap="large")
with c1:
    tab_url, tab_txt = st.tabs(["🔗 URL로 분석", "📝 원문 붙여넣기"])
    with tab_url:
        url = st.text_input("약관 페이지 URL", placeholder="https://photostudio.demo.example/terms", key="url")
        go_url = st.button("수집 후 분석", type="primary", width="stretch", key="go_url")
    with tab_txt:
        name_in = st.text_input("서비스명", value="대상 서비스", key="name")
        text_in = st.text_area("약관 / 개인정보처리방침 원문", height=260, key="text")
        go_txt = st.button("정보카드 생성", type="primary", width="stretch", key="go_txt")
    use_rag = st.toggle("2단계 근거 검색(RAG) 사용", value=True, key="rag")

    if go_url or go_txt:
        try:
            with st.status("분석 파이프라인 실행 중…", expanded=True) as stt:
                if go_url:
                    st.write("① 약관 수집 중…"); name, text, meta = api.fetch_terms(url); time.sleep(0.6)
                    st.write(f"　수집 완료 · {meta['bytes']:,} bytes · robots.txt {meta['robots_txt']}")
                else:
                    name, text = name_in, text_in
                sents = split_sentences(text); time.sleep(0.4)
                st.write(f"② 조항 분할 · {len(sents)}개 문장"); time.sleep(0.4)
                t0 = time.perf_counter(); card = analyze(text, name, use_rag=use_rag); ms = (time.perf_counter() - t0) * 1000
                n_rule = sum(f["source"] == "rule" for f in card["findings"]); n_rag = len(card["findings"]) - n_rule
                st.write(f"③ 규칙 탐지 · {n_rule}건"); time.sleep(0.4)
                st.write(f"④ 근거 검색(RAG) · {'추가 ' + str(n_rag) + '건' if use_rag else '사용 안 함'}"); time.sleep(0.4)
                disp = api.similar_disputes([f["rule_id"] for f in card["findings"]])
                st.write(f"⑤ 분쟁사례 조회 · {disp['total_matched']}건 매칭 (DEMO 시뮬레이션)"); time.sleep(0.4)
                stt.update(label=f"분석 완료 · 엔진 {ms:.1f} ms", state="complete", expanded=False)
            st.session_state["res"] = (card, disp)
        except (KeyError, ValueError) as e:
            st.error(str(e).strip("'"))

with c2:
    res = st.session_state.get("res")
    if not res:
        st.info("왼쪽에서 URL 또는 약관 원문을 입력하세요.")
    else:
        card, disp = res
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Fair-Score", f'{card["score"]}/100'); m2.metric("등급", card["grade"])
        m3.metric("주의 조항", f'{len(card["findings"])}건'); m4.metric("양호 신호", f'{len(card["positives"])}건')
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as fp:
            st.image(str(render_png(card, fp.name)), width="stretch")
        st.markdown(f'#### 유사 분쟁 사례 <span class="demo-badge">시뮬레이션 데이터</span>', unsafe_allow_html=True)
        if disp["items"]:
            st.dataframe([{"사례번호": c["case_id"], "쟁점": c["issue_name"], "요지": c["summary"], "서비스": c["service_type"], "처리": c["result"]}
                          for c in disp["items"]], hide_index=True, width="stretch")
        else:
            st.caption("매칭된 사례 없음")
        st.caption(f'출처: {disp["source"]} — 실제 한국소비자원 데이터가 아니며 LIVE 모드에서 공공데이터 API로 대체됩니다.')
        cA, cB = st.columns(2)
        cA.download_button("카드 JSON 다운로드", json.dumps(card, ensure_ascii=False, indent=2), "faircard.json", "application/json", width="stretch")
        with cB.popover("탐지 근거 상세", width="stretch"):
            for f in card["findings"]:
                st.markdown(f'**{f["label"]}** · `{f["source"]}` · 유사도 {f["similarity"]}\n\n> {f["evidence"]}\n\n근거: {f["legal_ref"]} — {f["gist"]}')
