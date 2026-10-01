"""시연 영상 자동 촬영 (Playwright Chromium headless → webm → ffmpeg mp4)
사전: streamlit run app.py (포트 8501)   실행: python demo/record_demo.py
출력: demo/out/faircard_demo.mp4 (1600x900, H.264, 30fps)
모든 데이터는 DEMO 모드(가상 약관·시뮬레이션 분쟁사례)이며 화면에 표기된다."""
import shutil, subprocess, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

W, H = 1600, 900
OUT = Path(__file__).resolve().parent / "out"; OUT.mkdir(parents=True, exist_ok=True)
APP = "http://localhost:8501"

SLIDE = """<html><body style="margin:0;width:{w}px;height:{h}px;background:#13213C;color:#fff;font-family:'Noto Sans CJK KR',sans-serif;
display:flex;flex-direction:column;justify-content:center;padding:0 120px;box-sizing:border-box">
<div style="color:#AFC8F5;font-size:28px;margin-bottom:18px">{kicker}</div>
<div style="font-size:64px;font-weight:700;line-height:1.25">{title}</div>
<div style="font-size:28px;color:#D8E2F5;margin-top:28px;line-height:1.6">{body}</div>
<div style="margin-top:40px;display:inline-block;background:#FFF1DC;color:#9A5B00;border-radius:999px;padding:8px 22px;font-size:22px;font-weight:700;width:fit-content">{badge}</div>
</body></html>"""

OVERLAY_JS = """
(() => {
 if (document.getElementById('fc-cap')) return;
 const cap = document.createElement('div'); cap.id='fc-cap';
 cap.style.cssText='position:fixed;left:50%;bottom:28px;transform:translateX(-50%);z-index:99999;background:rgba(19,33,60,.92);color:#fff;'+
   'font:600 24px "Noto Sans CJK KR",sans-serif;padding:14px 28px;border-radius:14px;box-shadow:0 6px 24px rgba(0,0,0,.25);transition:opacity .3s;opacity:0;max-width:1300px;text-align:center';
 document.body.appendChild(cap);
 const cur = document.createElement('div'); cur.id='fc-cur';
 cur.style.cssText='position:fixed;left:0;top:0;width:22px;height:22px;border-radius:50%;background:rgba(77,156,254,.55);border:2px solid #fff;'+
   'box-shadow:0 0 0 2px #4D9CFE;z-index:100000;pointer-events:none;transform:translate(-50%,-50%);transition:width .1s,height .1s';
 document.body.appendChild(cur);
 document.addEventListener('mousemove', e => {cur.style.left=e.clientX+'px'; cur.style.top=e.clientY+'px';}, true);
 document.addEventListener('mousedown', () => {cur.style.width='34px';cur.style.height='34px';}, true);
 document.addEventListener('mouseup', () => {cur.style.width='22px';cur.style.height='22px';}, true);
})();
"""


def caption(pg, text, hold=0):
    pg.evaluate(OVERLAY_JS)
    pg.evaluate("t => {const c=document.getElementById('fc-cap'); c.textContent=t; c.style.opacity=t?1:0}", text)
    if hold: pg.wait_for_timeout(hold)


def move_click(pg, loc, wait=400):
    loc.scroll_into_view_if_needed(); box = loc.bounding_box()
    pg.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=25)
    pg.wait_for_timeout(250); pg.mouse.down(); pg.mouse.up(); pg.wait_for_timeout(wait)


def type_into(pg, loc, text, delay=45):
    move_click(pg, loc, 200)
    pg.keyboard.press("Control+A"); pg.keyboard.press("Delete")
    pg.keyboard.type(text, delay=delay); pg.keyboard.press("Enter"); pg.wait_for_timeout(500)


def scroll_main(pg, y, steps=20):
    for _ in range(steps):
        pg.mouse.wheel(0, y / steps); pg.wait_for_timeout(35)


def analyze_url(pg, url, cap):
    caption(pg, cap)
    pg.get_by_role("tab", name="URL로 분석").click(); pg.wait_for_timeout(400)
    type_into(pg, pg.get_by_label("약관 페이지 URL"), url)
    move_click(pg, pg.get_by_role("button", name="수집 후 분석"), 300)
    pg.get_by_text("분석 완료").wait_for(timeout=20000); pg.wait_for_timeout(1500)


def slide(pg, **kw):
    pg.set_content(SLIDE.format(w=W, h=H, **kw)); pg.wait_for_timeout(kw.get("ms", 6000) if False else 0)


def main():
    with sync_playwright() as p:
        br = p.chromium.launch()
        ctx = br.new_context(viewport={"width": W, "height": H}, record_video_dir=str(OUT / "raw"),
                             record_video_size={"width": W, "height": H}, locale="ko-KR")
        pg = ctx.new_page()
        # 0. 인트로
        pg.set_content(SLIDE.format(w=W, h=H, kicker="2026 AI 라이프 솔루션 챌린지 · 시연 영상",
                                    title="FairCard-AI<br>AI 서비스의 영양성분표",
                                    body="AI 서비스 약관을 공공 법규 근거와 대조해<br>학습 활용 · 면책 · 환불 위험을 1장 카드로 보여줍니다.",
                                    badge="DEMO 모드 · 가상 서비스와 시뮬레이션 데이터로 시연합니다"))
        pg.wait_for_timeout(6500)
        pg.goto(APP); pg.get_by_text("FairCard-AI — AI 서비스 정보카드").wait_for(timeout=30000); pg.wait_for_timeout(1500)
        caption(pg, "웹 데모 · 왼쪽은 입력, 오른쪽은 정보카드 (사이드바: DEMO 모드 표시)", 3500)

        # 1. 위험 조항이 많은 서비스
        analyze_url(pg, "https://photostudio.demo.example/terms", "① 약관 URL만 넣으면 수집 → 조항 분할 → 탐지가 자동으로 진행됩니다")
        caption(pg, "위험 조항 8건 · Fair-Score 16점 · 등급 D", 3000)
        pg.mouse.move(1200, 600, steps=15)
        scroll_main(pg, 700); caption(pg, "경고마다 근거 조문과 원문 문장을 함께 표시합니다", 3500)
        scroll_main(pg, 900); caption(pg, "탐지된 쟁점과 비슷한 분쟁 사례를 매칭 (DEMO: 시뮬레이션 DB)", 4000)
        pg.get_by_role("button", name="탐지 근거 상세").click(); pg.wait_for_timeout(600)
        caption(pg, "탐지 근거 상세: 판정 단계(rule/rag) · 유사도 · 근거 요지", 3500)
        pg.keyboard.press("Escape"); pg.wait_for_timeout(400)
        scroll_main(pg, -3000, 25); pg.wait_for_timeout(500)

        # 2. 혼합형
        analyze_url(pg, "https://lite.photostudio.demo.example/terms", "② 학습 거부(옵트아웃)·이의제기 절차가 있는 서비스는 가점을 받습니다")
        caption(pg, "주의 2건 · 양호 신호 3건 → B+ (80점)", 3500)

        # 3. 의역 표현 — RAG on/off 비교
        move_click(pg, pg.get_by_text("2단계 근거 검색(RAG) 사용"), 300)
        analyze_url(pg, "https://chatmate.demo.example/terms", "③ 같은 약관을 규칙만으로 분석하면 (근거 검색 OFF)")
        caption(pg, "규칙에 없는 의역 표현은 놓쳐 A 등급이 나옵니다", 3500)
        move_click(pg, pg.get_by_text("2단계 근거 검색(RAG) 사용"), 300)
        caption(pg, "근거 검색 ON으로 다시 분석")
        move_click(pg, pg.get_by_role("button", name="수집 후 분석"), 300)
        pg.get_by_text("분석 완료").wait_for(timeout=20000); pg.wait_for_timeout(1200)
        caption(pg, "‘언제든지 요금제 조정’을 근거 검색이 찾아 ‘AI 검토’로 표시 → B+", 4500)
        caption(pg, "남은 의역 표현(학습 활용·환불 거부 등)은 LLM 3단계 검증 대상입니다 (API 키 연결 시)", 4500)

        # 4. 원문 붙여넣기
        caption(pg, "④ URL이 없으면 약관 원문을 바로 붙여넣어도 됩니다")
        pg.get_by_role("tab", name="원문 붙여넣기").click(); pg.wait_for_timeout(500)
        type_into(pg, pg.get_by_label("서비스명"), "가상 AI 회의록 도우미", 40)
        ta = pg.get_by_label("약관 / 개인정보처리방침 원문"); move_click(pg, ta, 200)
        pg.keyboard.type("제3조 본 서비스는 인공지능을 이용하여 회의록을 생성하며 이를 화면에 표시하여 안내합니다.\n"
                         "제6조 회원은 설정에서 학습 데이터 제공 거부를 선택할 수 있습니다.\n"
                         "제10조 회사는 사전 통지 없이 서비스를 중단할 수 있습니다.", delay=18)
        move_click(pg, pg.get_by_role("button", name="정보카드 생성"), 300)
        pg.get_by_text("분석 완료").wait_for(timeout=20000); pg.wait_for_timeout(1200)
        caption(pg, "AI 고지 · 옵트아웃은 양호, 일방적 중단 조항은 주의로 표시됩니다", 4500)
        caption(pg, "")

        # 5. 아웃트로
        pg.set_content(SLIDE.format(w=W, h=H, kicker="PoC 결과 (자체 작성 합성 데이터 기준)",
                                    title="보류 테스트 F1 0.894<br>근거 표기율 100%",
                                    body="규칙 단독 0.424 → 규칙+근거 검색 0.894 (n=40, 95% CI 0.79–0.98)<br>"
                                         "다음 단계: 실제 약관 라벨링 평가 · LLM 3단계 · 공공데이터 API 연동",
                                    badge="본 영상의 서비스·분쟁사례는 모두 가상 데이터입니다"))
        pg.wait_for_timeout(7000)
        vid = pg.video.path(); ctx.close(); br.close()
    mp4 = OUT / "faircard_demo.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", vid, "-c:v", "libx264", "-preset", "medium", "-crf", "22",
                    "-pix_fmt", "yuv420p", "-r", "30", "-movflags", "+faststart", str(mp4)], check=True)
    shutil.rmtree(OUT / "raw", ignore_errors=True)
    print(mp4)


if __name__ == "__main__":
    sys.exit(main())
