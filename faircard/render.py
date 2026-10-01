"""카드 렌더러: card dict → PNG (Pillow). 폰트: Noto Sans CJK KR (OFL)."""
from __future__ import annotations
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

_REG = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
_BLD = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
NAVY, BLUE, RED, ORG, GRN, INK, MUTE, TINT = "#13213C", "#4D9CFE", "#E5484D", "#F2A33A", "#1E9E5A", "#1F2937", "#6B7280", "#F3F7FE"
GCOL = {"A": GRN, "B+": BLUE, "B": BLUE, "C+": ORG, "C": ORG, "D": RED}


def _f(size, bold=False):
    try:
        return ImageFont.truetype(_BLD if bold else _REG, size, index=1)  # index 1 = KR
    except OSError:
        return ImageFont.load_default()


def _wrap(d, text, font, width):
    out, line = [], ""
    for ch in text:
        if d.textlength(line + ch, font=font) > width:
            out.append(line); line = ch
        else:
            line += ch
    return out + ([line] if line else [])


def render_png(card: dict, path: str | Path, scale: int = 2) -> Path:
    W = 900 * scale; S = lambda v: int(v * scale)
    im = Image.new("RGB", (W, S(2400)), "white"); d = ImageDraw.Draw(im)
    # 헤더
    d.rectangle([0, 0, W, S(150)], fill=NAVY)
    d.text((S(36), S(26)), "FairCard-AI · AI 서비스 정보카드", font=_f(S(18)), fill="#AFC8F5")
    d.text((S(36), S(54)), card["service"], font=_f(S(32), True), fill="white")
    d.text((S(36), S(108)), f'주의 조항 {len(card["findings"])}건 · 양호 신호 {len(card["positives"])}건 · {card["engine"]}',
           font=_f(S(15)), fill="#D8E2F5")
    # 등급 배지 + 점수 게이지
    gx = W - S(170)
    d.ellipse([gx, S(22), gx + S(106), S(128)], fill=GCOL[card["grade"]])
    d.text((gx + S(53), S(75)), card["grade"], font=_f(S(40), True), fill="white", anchor="mm")
    d.text((gx - S(16), S(75)), f'{card["score"]}', font=_f(S(34), True), fill="white", anchor="rm")
    d.text((gx - S(16), S(108)), "/100", font=_f(S(14)), fill="#AFC8F5", anchor="rm")
    y = S(176)

    def head(title, tag, col):
        nonlocal y
        d.rounded_rectangle([S(24), y, W - S(24), y + S(46)], S(10), fill=TINT)
        d.text((S(42), y + S(23)), title, font=_f(S(20), True), fill=NAVY, anchor="lm")
        d.rounded_rectangle([W - S(120), y + S(9), W - S(40), y + S(37)], S(14), fill=col)
        d.text((W - S(80), y + S(23)), tag, font=_f(S(15), True), fill="white", anchor="mm")
        y += S(60)

    def item(ok, label, sub, badge=None):
        nonlocal y
        col = GRN if ok else RED
        d.ellipse([S(42), y + S(4), S(60), y + S(22)], fill=col)
        d.text((S(51), y + S(13)), "✓" if ok else "!", font=_f(S(13), True), fill="white", anchor="mm")
        d.text((S(72), y + S(13)), label, font=_f(S(18), True), fill=INK, anchor="lm")
        if badge:
            tw = d.textlength(label, font=_f(S(18), True))
            bx = S(72) + tw + S(10)
            d.rounded_rectangle([bx, y + S(2), bx + S(78), y + S(24)], S(10), outline=ORG, width=S(1))
            d.text((bx + S(39), y + S(13)), badge, font=_f(S(12), True), fill=ORG, anchor="mm")
        y += S(30)
        for ln in _wrap(d, sub, _f(S(14)), W - S(140))[:2]:
            d.text((S(72), y), ln, font=_f(S(14)), fill=MUTE); y += S(21)
        y += S(10)

    def tag_of(rows):
        p = sum(r["penalty"] for r in rows)
        return ("경고", RED) if p >= 20 else (("주의", ORG) if rows else ("양호", GRN))

    for area, title, gids in [("투명성", "1. AI 투명성", ("G1", "G2")), ("권익", "2. 소비자 권익·환불", ("G3",))]:
        rows = [f for f in card["findings"] if f["area"] == area]
        head(title, *tag_of(rows))
        for f in rows:
            item(False, f["label"], f'{f["legal_ref"]} — “{f["evidence"][:46]}…”', "AI 검토" if f["source"] == "rag" else None)
        for p in card["positives"]:
            if p["id"] in gids:
                item(True, p["label"], f'“{p["evidence"][:56]}”')
        if not rows and not any(p["id"] in gids for p in card["positives"]):
            item(True, "확인된 주의 조항 없음", "규칙·검색 단계 모두 해당 신호 미검출")
        y += S(6)
    head("3. 피해 구제 가이드", "행동", BLUE)
    for g in card["action_guide"]:
        d.text((S(46), y), "→  " + g, font=_f(S(16)), fill=INK); y += S(30)
    y += S(14)
    d.line([S(24), y, W - S(24), y], fill="#E5E7EB", width=S(1)); y += S(12)
    d.text((S(28), y), f'원문 SHA-256 {card["source_sha256"][:16]}… · {card.get("refs_version", "")} · AI 자동 분석 결과 · 법률 자문이 아닌 주의 신호',
           font=_f(S(12)), fill=MUTE)
    y += S(30)
    im = im.crop((0, 0, W, y)); path = Path(path); im.save(path)
    return path
