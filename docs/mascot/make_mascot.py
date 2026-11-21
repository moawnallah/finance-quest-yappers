"""Draws the CrocoCash mascot in six poses and expressions as SVG.

Original vector art for CrocoCash, in the spirit of the team's sketches
(Paulina): a small croc in a collared shirt and tie, crest spikes, yellow slit
eyes and a curled tail. Run: python3 make_mascot.py  ->  svg/<pose>.svg
Render to PNG with render_mascot.mjs (Playwright).
"""
from pathlib import Path

OUT = Path(__file__).parent / "svg"
OUT.mkdir(exist_ok=True)

C = dict(skin="#3FAE3A", skin_dark="#2A8F2F", belly="#A6E58A", shirt="#F4F1E8", shirt_shade="#DCD8CC",
         tie="#2F6B2A", line="#0B3D16", eye="#FFD84A", pupil="#151515", mouth="#7A2E2E", tooth="#FFFFFF",
         spark="#FFC83D", sweat="#7CC7FF", phone="#1E2A3A", screen="#8DE46D")
S = f'stroke="{C["line"]}" stroke-width="6" stroke-linejoin="round" stroke-linecap="round"'


def arm(x1, y1, cx, cy, x2, y2):
    """A thick arm (sleeve then green forearm) ending in a hand."""
    return (f'<path d="M{x1},{y1} Q{cx},{cy} {x2},{y2}" fill="none" stroke="{C["line"]}" stroke-width="34" stroke-linecap="round"/>'
            f'<path d="M{x1},{y1} Q{cx},{cy} {x2},{y2}" fill="none" stroke="{C["skin"]}" stroke-width="22" stroke-linecap="round"/>'
            f'<path d="M{x1},{y1} Q{(x1+cx)/2},{(y1+cy)/2} {(x1+2*cx)/3},{(y1+2*cy)/3}" fill="none" stroke="{C["line"]}" stroke-width="40" stroke-linecap="round"/>'
            f'<path d="M{x1},{y1} Q{(x1+cx)/2},{(y1+cy)/2} {(x1+2*cx)/3},{(y1+2*cy)/3}" fill="none" stroke="{C["shirt"]}" stroke-width="28" stroke-linecap="round"/>'
            f'<circle cx="{x2}" cy="{y2}" r="15" fill="{C["skin"]}" {S}/>')


def body():
    tail = (f'<path d="M205,392 C150,420 95,440 70,405 C55,385 72,360 96,372 C82,392 118,402 150,385 C170,375 188,368 200,360 Z" '
            f'fill="{C["skin"]}" {S}/>'
            + "".join(f'<path d="M{x},{y} l-8,-16 l16,4 Z" fill="{C["skin_dark"]}" {S}/>' for x, y in [(98, 412), (125, 414), (152, 402)]))
    legs = "".join(f'<path d="M{x},405 L{x},450" stroke="{C["line"]}" stroke-width="34" stroke-linecap="round"/>'
                   f'<path d="M{x},405 L{x},450" stroke="{C["skin"]}" stroke-width="22" stroke-linecap="round"/>'
                   f'<ellipse cx="{x+8}" cy="458" rx="24" ry="11" fill="{C["skin"]}" {S}/>' for x in (222, 280))
    shirt = (f'<path d="M188,272 Q250,248 312,272 L322,408 Q250,428 178,408 Z" fill="{C["shirt"]}" {S}/>'
             f'<path d="M188,272 Q182,340 178,408 Q200,416 212,418 Q205,340 210,280 Z" fill="{C["shirt_shade"]}"/>'
             f'<path d="M228,262 L250,292 L272,262" fill="{C["shirt"]}" {S}/>'          # collar
             f'<path d="M244,286 L256,286 L262,346 L250,360 L238,346 Z" fill="{C["tie"]}" {S}/>'  # tie
             f'<rect x="276" y="300" width="30" height="16" rx="3" fill="#FFFFFF" {S} stroke-width="4"/>')  # name badge
    return tail + legs + shirt


def head(expr):
    crest = "".join(f'<path d="M{x},{y} l10,-26 l10,24 Z" fill="{C["skin_dark"]}" {S}/>' for x, y in [(186, 150), (204, 134), (224, 126)])
    skull = (f'<path d="M180,205 C170,150 215,118 262,128 C300,136 312,150 330,156 L408,166 C426,168 430,186 424,200 '
             f'C420,214 406,220 392,220 L300,232 C270,250 205,250 180,205 Z" fill="{C["skin"]}" {S}/>'
             f'<path d="M205,228 C240,246 282,240 300,232 L392,220 C400,220 410,216 414,210 L300,214 C265,222 230,224 205,228 Z" fill="{C["belly"]}"/>'
             f'<circle cx="402" cy="176" r="4" fill="{C["line"]}"/>')  # nostril
    eye_bump = f'<circle cx="270" cy="140" r="30" fill="{C["skin"]}" {S}/>'
    e = {"open": (f'<ellipse cx="272" cy="142" rx="17" ry="19" fill="{C["eye"]}" {S} stroke-width="4"/>'
                  f'<ellipse cx="275" cy="143" rx="4" ry="13" fill="{C["pupil"]}"/><circle cx="268" cy="134" r="4" fill="#fff"/>'),
         "up": (f'<ellipse cx="272" cy="142" rx="17" ry="19" fill="{C["eye"]}" {S} stroke-width="4"/>'
                f'<ellipse cx="277" cy="134" rx="4" ry="10" fill="{C["pupil"]}"/>'),
         "down": (f'<ellipse cx="272" cy="144" rx="17" ry="17" fill="{C["eye"]}" {S} stroke-width="4"/>'
                  f'<path d="M253,140 Q272,124 291,140 L291,130 Q272,114 253,130 Z" fill="{C["skin"]}"/>'   # heavy lid
                  f'<path d="M254,140 Q272,128 290,140" fill="none" {S} stroke-width="4"/>'
                  f'<ellipse cx="276" cy="150" rx="4" ry="8" fill="{C["pupil"]}"/>'),
         "happy": f'<path d="M256,146 Q272,126 288,146" fill="none" {S} stroke-width="6"/>',
         "worried": (f'<ellipse cx="272" cy="144" rx="16" ry="18" fill="{C["eye"]}" {S} stroke-width="4"/>'
                     f'<ellipse cx="270" cy="148" rx="4" ry="11" fill="{C["pupil"]}"/>'
                     f'<path d="M250,118 L292,128" fill="none" {S} stroke-width="6"/>')}
    brow = {"teach": f'<path d="M252,112 Q272,100 292,112" fill="none" {S} stroke-width="5"/>'}.get(expr, "")
    mouths = {
        "smile": f'<path d="M300,214 Q350,224 404,206" fill="none" {S} stroke-width="5"/>'
                 + "".join(f'<path d="M{x},{217 - (x-300)//12} l6,9 l6,-10" fill="{C["tooth"]}" {S} stroke-width="3"/>' for x in (316, 338, 360, 382)),
        "grin": f'<path d="M296,212 Q350,250 406,206 Q350,226 296,212 Z" fill="{C["mouth"]}" {S} stroke-width="5"/>'
                + "".join(f'<path d="M{x},{214 + (x-300)//30} l6,10 l6,-10" fill="{C["tooth"]}" {S} stroke-width="3"/>' for x in (312, 334, 356, 378)),
        "flat": f'<path d="M302,216 L398,208" fill="none" {S} stroke-width="5"/>',
        "frown": f'<path d="M304,220 Q330,210 350,218 Q372,226 398,212" fill="none" {S} stroke-width="5"/>',
        "open": f'<path d="M300,212 Q352,262 408,204 Q352,230 300,212 Z" fill="{C["mouth"]}" {S} stroke-width="5"/>'
                + "".join(f'<path d="M{x},{214 + (x-300)//28} l6,11 l6,-11" fill="{C["tooth"]}" {S} stroke-width="3"/>' for x in (314, 340, 366, 390))
                + f'<path d="M330,232 Q352,246 374,232" fill="#E46A6A"/>',
    }
    eye_kind, mouth_kind = {"wave": ("open", "smile"), "teach": ("open", "smile"), "think": ("up", "flat"),
                            "cheer": ("happy", "open"), "oops": ("worried", "frown"), "read": ("down", "smile")}[expr]
    return crest + skull + mouths[mouth_kind] + eye_bump + e[eye_kind] + brow


def pose(name):
    L, R = (192, 286), (308, 286)  # shoulders
    arms = {
        "wave": arm(*L, 170, 340, 200, 380) + arm(*R, 360, 260, 372, 196)
                + f'<path d="M392,184 q10,-8 18,0 M396,206 q12,-2 16,8" fill="none" {S} stroke-width="4"/>',
        "teach": arm(*L, 170, 340, 205, 378) + arm(*R, 350, 270, 360, 216)
                 + f'<path d="M360,200 L362,170" stroke="{C["line"]}" stroke-width="16" stroke-linecap="round"/>'
                   f'<path d="M360,200 L362,170" stroke="{C["skin"]}" stroke-width="8" stroke-linecap="round"/>',
        "think": arm(*L, 175, 340, 210, 375) + arm(*R, 330, 300, 312, 236)
                 + "".join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="#FFFFFF" {S} stroke-width="4"/>' for x, y, r in [(340, 104, 7), (362, 82, 10), (392, 56, 14)]),
        "cheer": arm(*L, 150, 240, 150, 170) + arm(*R, 350, 240, 352, 170)
                 + "".join(f'<path d="M{x},{y} l6,14 l14,6 l-14,6 l-6,14 l-6,-14 l-14,-6 l14,-6 Z" fill="{C["spark"]}" {S} stroke-width="3"/>'
                           for x, y in [(108, 150), (400, 110), (430, 250), (96, 270)]),
        "oops": arm(*L, 160, 320, 186, 262) + arm(*R, 336, 330, 310, 262)
                + f'<path d="M168,128 q-14,22 0,30 q14,-8 0,-30 Z" fill="{C["sweat"]}" {S} stroke-width="4"/>',
        "read": arm(*L, 200, 360, 262, 352) + arm(*R, 300, 360, 286, 340)
                + f'<rect x="248" y="296" width="54" height="76" rx="10" transform="rotate(-12 275 334)" fill="{C["phone"]}" {S} stroke-width="5"/>'
                  f'<rect x="256" y="306" width="38" height="52" rx="5" transform="rotate(-12 275 334)" fill="{C["screen"]}"/>'
                  f'<circle cx="242" cy="352" r="15" fill="{C["skin"]}" {S}/>',
    }[name]
    back_arm_first = name in ("cheer",)
    parts = body() + (arms if back_arm_first else "") + head(name) + ("" if back_arm_first else arms)
    shadow = '<ellipse cx="250" cy="472" rx="120" ry="14" fill="#000" opacity="0.12"/>'
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">{shadow}{parts}</svg>'


for n in ["wave", "teach", "think", "cheer", "oops", "read"]:
    (OUT / f"{n}.svg").write_text(pose(n))
print("wrote", sorted(p.name for p in OUT.glob("*.svg")))
