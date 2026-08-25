"""
Build the SIH 2026 Idea-Presentation deck for Thermal-Shelter (PS 26051, DRDO).

Renders the mandated 6-slide format:
    1. Problem Statement & Team Details
    2. Proposed Solution (the Idea)
    3. Technical Approach
    4. Feasibility & Viability
    5. Impact & Benefits
    6. Research & References

Primary output (no extra install needed) — a submittable, print-clean PDF plus a
PNG of every slide:
    ./.venv/bin/python scripts/build_ppt.py
    → docs/Thermal-Shelter_SIH2026_PS26051.pdf
    → docs/slides/slide1.png … slide6.png

Optional editable PowerPoint (needs python-pptx):
    ./.venv/bin/pip install python-pptx
    ./.venv/bin/python scripts/build_ppt.py --pptx

Team name / ID / members / institute are placeholders in the TEAM block below —
edit them here and re-run (or edit directly in the .pptx).
"""
from __future__ import annotations

import argparse
import os
import tempfile
import textwrap

# matplotlib powers the figure + PDF rendering. The editable-.pptx path needs only
# python-pptx + Pillow, so keep this import soft: on an interpreter that has pptx but
# not matplotlib (e.g. the system Python), we can still build the .pptx from the
# pre-rendered figures.
try:
    os.environ.setdefault("MPLCONFIGDIR", os.path.join(tempfile.gettempdir(), "mpl"))
    os.makedirs(os.environ["MPLCONFIGDIR"], exist_ok=True)

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    from matplotlib.image import imread
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle

    HAVE_MPL = True
except ModuleNotFoundError:
    HAVE_MPL = False

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DOCS = os.path.join(ROOT, "docs")
SLIDES_DIR = os.path.join(DOCS, "slides")
os.makedirs(SLIDES_DIR, exist_ok=True)

# --------------------------------------------------------------------------- #
#  EDIT ME — team details (placeholders; fill in before submitting)
# --------------------------------------------------------------------------- #
TEAM = {
    "team_name": "‹ Team name ›",
    "team_id": "‹ Team ID ›",
    "institute": "‹ College / Institute ›",
    "members": [
        "‹ Member 1 — Team Lead ›",
        "‹ Member 2 ›",
        "‹ Member 3 ›",
        "‹ Member 4 ›",
        "‹ Member 5 ›",
        "‹ Member 6 ›",
    ],
    "repo": "github.com/ritikx-36/sih-2026",
}

# --------------------------------------------------------------------------- #
#  Problem statement + verified results (fixed)
# --------------------------------------------------------------------------- #
PS_ID = "26051"
PS_TITLE = ("Software-Based Model Development for Design of Area-Specific "
            "Shelter for Thermal Comfort Maintenance")
ORG = "DRDO"
CATEGORY = "Software"
THEME = "‹ as listed on the SIH portal ›"
IDEA_TITLE = "Thermal-Shelter — a shelter that stays warm on sunlight, not fuel"

REGION_SAVINGS = [  # (site, % less heating, design kWh/day, baseline kWh/day)
    ("Leh, Ladakh", 84, 27.6, 170.5),
    ("Drass, Kargil", 82, 39.5, 222.4),
    ("Siachen (base)", 82, 43.5, 241.1),
    ("Tawang", 86, 15.0, 110.4),
]

# ---- slide copy (shared by both the PDF and the .pptx renderers) ---------- #
S2_LEAD = "A software model for passive-shelter design"
S2_BODY = ("From a site's climate, a shelter's geometry and its materials, it predicts how "
           "warm the shelter stays and how little heating it needs — then lets you redesign "
           "it live to need, ideally, zero active heating.")
S2_OUTPUTS = [
    "Indoor temperature over time — full day–night cycle",
    "Solar thermal energy captured through the day",
    "Heat-flow vs ambient over a time period",
]
S2_DIFF = [
    "Transient, not a static average — catches the post-sunset crash that breaks comfort",
    "Models night-sky radiative cooling — clear Leh night: air −14 °C, sky ≈ −45 °C",
    "Thermal-mass “battery” — stone · water wall · PCM store day-sun for the night",
    "Area-specific — one engine, any cold site (Leh · Drass · Siachen · Tawang)",
    "Fast (< 1 s / design) → optimize, don't just simulate; ANSYS validates the winner",
]
S3_METHOD = [
    "Lumped resistance–capacitance thermal network, explicitly time-stepped",
    "Outdoor forcing = sol-air temperature + long-wave night-sky cooling",
    "Solar irradiance on every wall / roof / window via pvlib (incl. snow albedo)",
    "Comfort & energy scored per design; fast enough to sweep hundreds",
]
S3_STACK = [
    "Python 3.12 · NumPy / SciPy · pandas",
    "pvlib — solar position & clear-sky irradiance",
    "Streamlit + Plotly — live design dashboard (working prototype)",
    "matplotlib — reporting & figures",
    "ANSYS — CFD / thermal cross-validation (later phase)",
]
S4_FEAS = [
    "Standard, peer-reviewed physics — ASHRAE sol-air & RC networks; Berdahl–Martin sky emissivity",
    "Built on the mature pvlib solar model — not a black box",
    "Pure software — runs on any laptop; no field hardware to design",
    "Working prototype already reproduces expected passive-design behaviour",
]
S4_VIA = ("Cheap, fast, reusable across regions — screen hundreds of designs in software, "
          "validate one in CFD.")
S4_CHALL = [  # (challenge, mitigation)
    ("Sparse climate data for remote posts", "accept user CSV + typical-day generator + region presets"),
    ("Lumped RC simplifies 3-D heat flow", "validate & calibrate the shortlisted design in ANSYS CFD"),
    ("Material properties vary by source", "sourced, editable material-property database"),
]
S5_HEAD = "82–86% less heating than a baseline hut"
S5_SUB = "Verified across cold sites over 5 clear winter days, holding 20 °C."
S5_WHO = "Armed forces & border posts · high-altitude communities · disaster relief"
S5_BEN = [
    "Economic — far less diesel / kerosene hauled to remote posts; design in minutes, not months",
    "Environmental — less combustion → lower emissions in fragile Himalayan ecosystems",
    "Operational & social — energy resilience where supply lines are fragile; warmer, safer "
    "shelters; fewer cold injuries",
]
REFS = [
    "pvlib-python (Sandia National Laboratories) — solar position & clear-sky irradiance models",
    "Berdahl, P. & Martin, M. (1984), “Emissivity of clear skies” — long-wave radiative sky cooling",
    "ASHRAE Handbook of Fundamentals — sol-air temperature, RC thermal networks, U-values & SHGC",
    "Balcomb, J. D. / U.S. Department of Energy — passive-solar design: Trombe & water walls, thermal mass",
    "DRDO–DIHAR — high-altitude habitat & thermal-comfort context (Ladakh)",
    f"Project repository — {TEAM['repo']}",
]
S6_NOTE = ("The physics is standard building science; our contribution is packaging it into a "
           "fast, area-specific design-and-optimization tool a non-specialist can drive.")

# --------------------------------------------------------------------------- #
#  Palette
# --------------------------------------------------------------------------- #
NAVY = "#12233b"
NAVY2 = "#1b3a5c"
ACCENT = "#1f77b4"
ACCENT_L = "#4a97cf"
INK = "#1f2937"
MUT = "#6b7280"
GREEN = "#1e8f45"
LINE = "#9aa5b1"
BG_SOFT = "#eef3f8"
CARD_EDGE = "#d5e0ec"

FLOW_PNG = os.path.join(DOCS, "deck_flow.png")
REGION_PNG = os.path.join(DOCS, "deck_regions.png")
HERO_PNG = os.path.join(DOCS, "demo_curve.png")


# --------------------------------------------------------------------------- #
#  Embedded figures
# --------------------------------------------------------------------------- #
def make_flow(path: str = FLOW_PNG) -> str:
    stages = [
        ("Climate", "temperature · sun\nirradiance · site"),
        ("Solar engine", "pvlib: sun on every\nwall · roof · window"),
        ("Transient RC engine", "lumped R–C · sol-air +\nnight-sky · time-stepped"),
        ("Comfort + Energy", "% time in 18–24 °C\nkWh/day to hold 20 °C"),
        ("Compare / Optimize", "rank by material · size\norientation · glazing"),
    ]
    shades = ["#16324f", "#1c4a72", "#216697", ACCENT, ACCENT_L]
    fig, ax = plt.subplots(figsize=(12, 3.2), dpi=200)
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 3.2)
    ax.axis("off")
    n = len(stages)
    m, gap = 0.10, 0.42
    bw = (12 - 2 * m - (n - 1) * gap) / n
    bh, y = 1.9, 1.0
    centers = []
    for i, (title, sub) in enumerate(stages):
        x = m + i * (bw + gap)
        ax.add_patch(FancyBboxPatch((x, y), bw, bh,
                                    boxstyle="round,pad=0.015,rounding_size=0.10",
                                    fc=shades[i], ec="none"))
        cx = x + bw / 2
        centers.append((x, x + bw))
        ax.text(cx, y + bh - 0.44, title, ha="center", va="center",
                color="white", fontsize=11.2, fontweight="bold")
        ax.text(cx, y + 0.64, sub, ha="center", va="center",
                color="#dce8f4", fontsize=9.0, linespacing=1.3)
    for i in range(n - 1):
        ax.add_patch(FancyArrowPatch((centers[i][1] + 0.05, y + bh / 2),
                                     (centers[i + 1][0] - 0.05, y + bh / 2),
                                     arrowstyle="-|>", mutation_scale=16, lw=2.2, color=LINE))
    ax.text(6, 0.44, "A shelter gains heat (sun on walls/roof and through the glazing) and loses it "
                     "(envelope conduction · air leakage · long-wave to the cold night sky);",
            ha="center", va="center", color="#374151", fontsize=9.4)
    ax.text(6, 0.15, "heavy materials — stone · water wall · PCM — store daytime sun and release it "
                     "after sunset.", ha="center", va="center", color="#374151", fontsize=9.4)
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    fig.savefig(path, dpi=200, facecolor="white")
    plt.close(fig)
    return path


def make_regions(path: str = REGION_PNG) -> str:
    labels = [f"{name}\n{a:.0f} vs {b:.0f} kWh/day" for name, pct, a, b in REGION_SAVINGS]
    vals = [pct for _, pct, _, _ in REGION_SAVINGS]
    fig, ax = plt.subplots(figsize=(7.1, 3.5), dpi=200)
    ypos = list(range(len(vals)))
    ax.barh(ypos, vals, color=ACCENT, height=0.62, zorder=3)
    ax.set_yticks(ypos)
    ax.set_yticklabels(labels, fontsize=10)
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    for i, v in enumerate(vals):
        ax.text(v - 2, i, f"{v}%", ha="right", va="center",
                color="white", fontsize=13, fontweight="bold", zorder=4)
    ax.set_xlabel("less heating than a baseline hut  ·  5 clear winter days, holding 20 °C",
                  fontsize=9.5, color=MUT)
    ax.tick_params(axis="both", length=0)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#d5dbe2")
    ax.xaxis.grid(True, color="#e8edf2", zorder=0)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(path, dpi=200, facecolor="white")
    plt.close(fig)
    return path


def make_figures():
    make_flow()
    make_regions()


def ensure_figures():
    """Regenerate the embedded figures when matplotlib is available; otherwise fall
    back to the pre-rendered PNGs (and fail loudly if any are missing)."""
    if HAVE_MPL:
        make_figures()
        return
    missing = [p for p in (FLOW_PNG, REGION_PNG, HERO_PNG) if not os.path.exists(p)]
    if missing:
        raise SystemExit(
            "Can't regenerate figures here (matplotlib not installed) and these are missing:\n  "
            + "\n  ".join(missing)
            + "\n\nBuild them once with the venv Python:\n"
              "    ./.venv/bin/python scripts/build_ppt.py --figures-only"
        )


# --------------------------------------------------------------------------- #
#  PDF deck — rendered directly (no third-party dependency)
# --------------------------------------------------------------------------- #
SW, SH = 13.333, 7.5
MARGIN = 0.7
BAND_H = 1.02
BODY_TOP = BAND_H + 0.40
COL_GAP = 0.55
COL_W = (SW - 2 * MARGIN - COL_GAP) / 2
COL2_X = MARGIN + COL_W + COL_GAP


def _new_slide(title: str, idx: int):
    fig = plt.figure(figsize=(SW, SH), dpi=200)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, SW)
    ax.set_ylim(0, SH)
    ax.axis("off")
    ax.add_patch(Rectangle((0, SH - BAND_H), SW, BAND_H, fc=NAVY, ec="none"))
    ax.add_patch(Rectangle((0, SH - BAND_H - 0.055), SW, 0.055, fc=ACCENT, ec="none"))
    ax.text(MARGIN, SH - BAND_H / 2, title, va="center", ha="left",
            fontsize=25, fontweight="bold", color="white")
    ax.text(SW - MARGIN, SH - BAND_H / 2, f"PS {PS_ID}  ·  {ORG}  ·  {CATEGORY}",
            va="center", ha="right", fontsize=11.5, color="#bcd3ea")
    ax.text(MARGIN, 0.30, "Smart India Hackathon 2026   ·   Thermal-Shelter — passive shelter "
                          "design tool", va="center", ha="left", fontsize=8.5, color=MUT)
    ax.text(SW - MARGIN, 0.30, f"{idx} / 6", va="center", ha="right", fontsize=8.5, color=MUT)
    return fig, ax


_STYLE = {
    "h":  dict(size=15.0, color=NAVY2, weight="bold", gap_before=0.14, gap_after=0.08, ls=1.05),
    "p":  dict(size=12.0, color=INK,   weight="normal", gap_before=0.0, gap_after=0.10, ls=1.18),
    "b":  dict(size=12.0, color=INK,   weight="normal", gap_before=0.0, gap_after=0.075, ls=1.16,
               prefix="•   ", hang="     "),
    "b1": dict(size=11.5, color=MUT,   weight="normal", gap_before=0.0, gap_after=0.09, ls=1.14,
               prefix="–   ", hang="      "),
}


def _draw(ax, x, y_top, width_in, blocks):
    """Draw a stack of (kind, text) blocks top-down; return the new y_top (inches from top)."""
    for kind, text in blocks:
        st = _STYLE[kind]
        size, ls = st["size"], st["ls"]
        prefix, hang = st.get("prefix", ""), st.get("hang", "")
        char_w = 0.505 * size / 72.0                     # ≈ DejaVu Sans advance
        ncols = max(10, int(width_in / char_w))
        wrapped = textwrap.fill(prefix + text, width=ncols, subsequent_indent=hang)
        nlines = wrapped.count("\n") + 1
        y_top += st["gap_before"]
        ax.text(x, SH - y_top, wrapped, va="top", ha="left", fontsize=size,
                color=st["color"], fontweight=st["weight"], linespacing=ls)
        y_top += nlines * (size * ls / 72.0) + st["gap_after"]
    return y_top


def _place_image(fig, path, x, y_top, width_in):
    img = imread(path)
    h_px, w_px = img.shape[0], img.shape[1]
    h_in = width_in * h_px / w_px
    bottom = SH - (y_top + h_in)
    iax = fig.add_axes([x / SW, bottom / SH, width_in / SW, h_in / SH])
    iax.imshow(img)
    iax.axis("off")
    return h_in


def _card(ax, x, y_top, w, h):
    ax.add_patch(FancyBboxPatch((x, SH - y_top - h), w, h,
                                boxstyle="round,pad=0.02,rounding_size=0.10",
                                fc=BG_SOFT, ec=CARD_EDGE, lw=1.2))


def slide1(fig, ax):
    ax.text(MARGIN, SH - (BODY_TOP + 0.02), "SMART INDIA HACKATHON 2026",
            va="top", ha="left", fontsize=11.5, color=MUT, fontweight="bold")
    ax.text(MARGIN, SH - (BODY_TOP + 0.34), f"Problem Statement {PS_ID}",
            va="top", ha="left", fontsize=25, color=NAVY, fontweight="bold")
    y = BODY_TOP + 1.05
    y = _draw(ax, MARGIN, y, COL_W, [
        ("h", PS_TITLE),
        ("p", f"Organisation      {ORG}"),
        ("p", f"Category           {CATEGORY}"),
        ("p", f"Theme              {THEME}"),
    ])
    y += 0.10
    ax.text(MARGIN, SH - y, "IDEA", va="top", ha="left", fontsize=11.5, color=MUT, fontweight="bold")
    _draw(ax, MARGIN, y + 0.28, COL_W, [("h", IDEA_TITLE)])

    # team card
    card_h = 4.95
    _card(ax, COL2_X, BODY_TOP, COL_W, card_h)
    cx = COL2_X + 0.35
    ax.text(cx, SH - (BODY_TOP + 0.32), "TEAM", va="top", ha="left",
            fontsize=11.5, color=MUT, fontweight="bold")
    ax.text(cx, SH - (BODY_TOP + 0.62), TEAM["team_name"], va="top", ha="left",
            fontsize=21, color=NAVY, fontweight="bold")
    yb = _draw(ax, cx, BODY_TOP + 1.30, COL_W - 0.7, [
        ("p", f"Team ID    {TEAM['team_id']}"),
        ("p", f"Institute   {TEAM['institute']}"),
    ])
    yb += 0.08
    ax.text(cx, SH - yb, "MEMBERS", va="top", ha="left", fontsize=11.5, color=MUT, fontweight="bold")
    members = [("p", f"{i}.   {m}") for i, m in enumerate(TEAM["members"], 1)]
    _draw(ax, cx, yb + 0.30, COL_W - 0.7, members)


def slide2(fig, ax):
    y = _draw(ax, MARGIN, BODY_TOP, COL_W, [("h", S2_LEAD), ("p", S2_BODY),
                                            ("h", "It outputs exactly what the problem asks")])
    y = _draw(ax, MARGIN, y, COL_W, [("b", t) for t in S2_OUTPUTS])
    y = _draw(ax, MARGIN, y + 0.05, COL_W, [("h", "What makes it different")])
    _draw(ax, MARGIN, y, COL_W, [("b", t) for t in S2_DIFF])
    h = _place_image(fig, HERO_PNG, COL2_X, BODY_TOP + 0.9, COL_W)
    _draw(ax, COL2_X, BODY_TOP + 0.9 + h + 0.12, COL_W,
          [("p", "Simulated Leh winter — the passive design climbs into the comfort band on "
                 "sunlight alone, while the baseline hut tracks the freezing outdoor air.")])


def slide3(fig, ax):
    h = _place_image(fig, FLOW_PNG, MARGIN, BODY_TOP, SW - 2 * MARGIN)
    y = BODY_TOP + h + 0.25
    _draw(ax, MARGIN, y, COL_W, [("h", "Methodology")] + [("b", t) for t in S3_METHOD])
    _draw(ax, COL2_X, y, COL_W, [("h", "Technology stack")] + [("b", t) for t in S3_STACK])


def slide4(fig, ax):
    y = _draw(ax, MARGIN, BODY_TOP, COL_W, [("h", "Why it's feasible")] + [("b", t) for t in S4_FEAS])
    y = _draw(ax, MARGIN, y + 0.10, COL_W, [("h", "Viability"), ("b", S4_VIA)])
    blocks = [("h", "Challenges & how we overcome them")]
    for ch, mit in S4_CHALL:
        blocks.append(("b", ch))
        blocks.append(("b1", mit))
    _draw(ax, COL2_X, BODY_TOP, COL_W, blocks)


def slide5(fig, ax):
    ax.text(MARGIN, SH - (BODY_TOP + 0.02), S5_HEAD, va="top", ha="left",
            fontsize=20, color=GREEN, fontweight="bold")
    y = _draw(ax, MARGIN, BODY_TOP + 0.62, COL_W, [
        ("p", S5_SUB),
        ("h", "Who it helps"), ("p", S5_WHO),
        ("h", "Benefits")])
    _draw(ax, MARGIN, y, COL_W, [("b", t) for t in S5_BEN])
    h = _place_image(fig, REGION_PNG, COL2_X, BODY_TOP + 1.05, COL_W)
    _draw(ax, COL2_X, BODY_TOP + 1.05 + h + 0.12, COL_W,
          [("p", "Auxiliary heat to hold 20 °C: passive design vs baseline hut, by region.")])


def slide6(fig, ax):
    y = _draw(ax, MARGIN, BODY_TOP, SW - 2 * MARGIN, [("b", t) for t in REFS])
    _draw(ax, MARGIN, y + 0.25, SW - 2 * MARGIN, [("p", S6_NOTE)])


SLIDE_FUNCS = [
    ("Problem Statement & Team Details", slide1),
    ("Proposed Solution  (the Idea)", slide2),
    ("Technical Approach", slide3),
    ("Feasibility & Viability", slide4),
    ("Impact & Benefits", slide5),
    ("Research & References", slide6),
]


def build_pdf(out_pdf: str):
    if not HAVE_MPL:
        raise SystemExit("Rendering the PDF needs matplotlib — run with ./.venv/bin/python.")
    make_figures()
    pdf = PdfPages(out_pdf)
    for i, (title, fn) in enumerate(SLIDE_FUNCS, 1):
        fig, ax = _new_slide(title, i)
        fn(fig, ax)
        pdf.savefig(fig, facecolor="white")
        fig.savefig(os.path.join(SLIDES_DIR, f"slide{i}.png"), dpi=150, facecolor="white")
        plt.close(fig)
    pdf.close()
    print(f"deck  → {out_pdf}")
    print(f"slides → {SLIDES_DIR}/slide1..6.png")


# --------------------------------------------------------------------------- #
#  Optional editable PowerPoint (needs python-pptx)
# --------------------------------------------------------------------------- #
def build_pptx(out_path: str):
    try:
        from PIL import Image
        from pptx import Presentation
        from pptx.dml.color import RGBColor
        from pptx.enum.shapes import MSO_SHAPE
        from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
        from pptx.util import Inches, Pt
    except ModuleNotFoundError as e:
        raise SystemExit(
            f"The .pptx build needs python-pptx (missing: {e.name}).\n"
            "Your system Python already has it — build the editable deck with:\n"
            "    python3 scripts/build_ppt.py --pptx\n"
            "(The PDF deck builds separately with ./.venv/bin/python scripts/build_ppt.py.)"
        )

    ensure_figures()

    FONT = "Arial"                    # clean, cross-platform — predictable metrics vs theme default
    BODY_H = SH - BODY_TOP - 0.55     # usable height from the body top down to the footer

    def rgb(h):
        h = h.lstrip("#")
        return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

    prs = Presentation()
    prs.slide_width = Inches(SW)
    prs.slide_height = Inches(SH)
    blank = prs.slide_layouts[6]

    def add_slide(title, idx):
        slide = prs.slides.add_slide(blank)
        for shp, y, h, col in ((0, 0, BAND_H, NAVY), (1, BAND_H, 0.06, ACCENT)):
            r = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, Inches(y), Inches(SW), Inches(h))
            r.fill.solid(); r.fill.fore_color.rgb = rgb(col)
            r.line.fill.background(); r.shadow.inherit = False
        tb = slide.shapes.add_textbox(Inches(MARGIN), 0, Inches(9.0), Inches(BAND_H))
        tb.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        rr = tb.text_frame.paragraphs[0].add_run(); rr.text = title
        rr.font.size = Pt(28); rr.font.bold = True; rr.font.color.rgb = rgb("#ffffff")
        tag = slide.shapes.add_textbox(Inches(SW - 4.4), 0, Inches(3.9), Inches(BAND_H))
        tag.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        pt = tag.text_frame.paragraphs[0]; pt.alignment = PP_ALIGN.RIGHT
        rt = pt.add_run(); rt.text = f"PS {PS_ID}  ·  {ORG}  ·  {CATEGORY}"
        rt.font.size = Pt(12); rt.font.color.rgb = rgb("#bcd3ea")
        ft = slide.shapes.add_textbox(Inches(MARGIN), Inches(SH - 0.42), Inches(9.5), Inches(0.32))
        rf = ft.text_frame.paragraphs[0].add_run()
        rf.text = "Smart India Hackathon 2026   ·   Thermal-Shelter — passive shelter design tool"
        rf.font.size = Pt(9); rf.font.color.rgb = rgb(MUT)
        nb = slide.shapes.add_textbox(Inches(SW - 1.4), Inches(SH - 0.42), Inches(0.9), Inches(0.32))
        pn = nb.text_frame.paragraphs[0]; pn.alignment = PP_ALIGN.RIGHT
        rn = pn.add_run(); rn.text = f"{idx} / 6"; rn.font.size = Pt(9); rn.font.color.rgb = rgb(MUT)
        return slide

    def box(slide, l, t, w, h):
        tf = slide.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h)).text_frame
        tf.word_wrap = True
        tf.auto_size = MSO_AUTO_SIZE.SHRINK_TEXT_ON_OVERFLOW   # viewer shrinks to fit — never spills
        tf.margin_left = tf.margin_right = Inches(0.04)
        tf.margin_top = tf.margin_bottom = Inches(0.02)
        return tf

    def write(tf, items):
        for i, it in enumerate(items):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            lvl = it.get("lvl", 0); bold = it.get("b", False)
            sz = it.get("sz", 16 if (bold and lvl == 0) else 12.5)
            text = it["t"]
            if it.get("bullet"):
                text = ("•  " if lvl == 0 else "–  ") + text
            r = p.add_run(); r.text = text
            r.font.size = Pt(sz); r.font.bold = bold; r.font.color.rgb = rgb(it.get("c", INK))
            r.font.name = FONT
            p.space_after = Pt(it.get("sa", 5)); p.line_spacing = it.get("ls", 1.05)
            if "space_before" in it:
                p.space_before = Pt(it["space_before"])

    def H(t, sb=6):
        return {"t": t, "b": True, "sz": 15, "c": NAVY2, "sa": 5, "space_before": sb, "ls": 1.0}

    def P(t, sz=12.5, c=INK, sa=5):
        return {"t": t, "sz": sz, "c": c, "sa": sa}

    def B(t, lvl=0, sz=12.5, c=INK, sa=4):
        return {"t": t, "lvl": lvl, "bullet": True, "sz": sz, "c": c, "sa": sa}

    def picture(slide, path, left, top, width):
        with Image.open(path) as im:
            w_px, h_px = im.size
        slide.shapes.add_picture(path, Inches(left), Inches(top), width=Inches(width))
        return width * h_px / w_px

    col2 = COL2_X

    # Slide 1
    s = add_slide("Problem Statement & Team Details", 1)
    write(box(s, MARGIN, BODY_TOP, COL_W + 0.5, 5.2), [
        {"t": "SMART INDIA HACKATHON 2026", "sz": 12, "c": MUT, "b": True, "sa": 4},
        {"t": f"Problem Statement {PS_ID}", "sz": 30, "c": NAVY, "b": True, "sa": 6},
        {"t": PS_TITLE, "sz": 15, "c": INK, "b": True, "sa": 12, "ls": 1.1},
        {"t": f"Organisation   {ORG}", "sz": 13, "c": INK, "sa": 3},
        {"t": f"Category        {CATEGORY}", "sz": 13, "c": INK, "sa": 3},
        {"t": f"Theme           {THEME}", "sz": 13, "c": INK, "sa": 12},
        {"t": "IDEA", "sz": 12, "c": MUT, "b": True, "sa": 3},
        {"t": IDEA_TITLE, "sz": 15, "c": ACCENT, "b": True, "ls": 1.1},
    ])
    card = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(col2), Inches(BODY_TOP),
                              Inches(COL_W), Inches(4.95))
    card.fill.solid(); card.fill.fore_color.rgb = rgb(BG_SOFT)
    card.line.color.rgb = rgb(CARD_EDGE); card.line.width = Pt(1); card.shadow.inherit = False
    team_items = [
        {"t": "TEAM", "sz": 12, "c": MUT, "b": True, "sa": 5},
        {"t": TEAM["team_name"], "sz": 22, "c": NAVY, "b": True, "sa": 4},
        {"t": f"Team ID   {TEAM['team_id']}", "sz": 13, "c": INK, "sa": 3},
        {"t": f"Institute  {TEAM['institute']}", "sz": 13, "c": INK, "sa": 10, "ls": 1.1},
        {"t": "MEMBERS", "sz": 12, "c": MUT, "b": True, "sa": 4},
    ] + [{"t": f"{i}.  {m}", "sz": 13, "c": INK, "sa": 3} for i, m in enumerate(TEAM["members"], 1)]
    write(box(s, col2 + 0.35, BODY_TOP + 0.3, COL_W - 0.7, 4.4), team_items)

    # Slide 2
    s = add_slide("Proposed Solution  (the Idea)", 2)
    items = [H(S2_LEAD, sb=0), P(S2_BODY, sa=10),
             H("It outputs exactly what the problem asks")] + [B(t) for t in S2_OUTPUTS]
    items += [H("What makes it different")] + [B(t) for t in S2_DIFF]
    write(box(s, MARGIN, BODY_TOP, COL_W, 5.4), items)
    ih = picture(s, HERO_PNG, col2, BODY_TOP + 0.9, COL_W)
    write(box(s, col2, BODY_TOP + 0.9 + ih + 0.05, COL_W, 1.0),
          [{"t": "Simulated Leh winter — the passive design climbs into the comfort band on "
                 "sunlight alone, while the baseline hut tracks the freezing outdoor air.",
            "sz": 10.5, "c": MUT, "sa": 0, "ls": 1.1}])

    # Slide 3
    s = add_slide("Technical Approach", 3)
    fh = picture(s, FLOW_PNG, MARGIN, BODY_TOP, SW - 2 * MARGIN)
    y2 = BODY_TOP + fh + 0.2
    write(box(s, MARGIN, y2, COL_W, SH - y2 - 0.5), [H("Methodology", sb=0)] + [B(t) for t in S3_METHOD])
    write(box(s, col2, y2, COL_W, SH - y2 - 0.5), [H("Technology stack", sb=0)] + [B(t) for t in S3_STACK])

    # Slide 4
    s = add_slide("Feasibility & Viability", 4)
    left = [H("Why it's feasible", sb=0)] + [B(t) for t in S4_FEAS] + [H("Viability"), B(S4_VIA)]
    write(box(s, MARGIN, BODY_TOP, COL_W, 5.4), left)
    right = [H("Challenges & how we overcome them", sb=0)]
    for ch, mit in S4_CHALL:
        right.append({"t": ch, "sz": 13, "b": True, "c": INK, "sa": 2})
        right.append(B(mit, lvl=1, c=MUT, sa=8))
    write(box(s, col2, BODY_TOP, COL_W, 5.4), right)

    # Slide 5
    s = add_slide("Impact & Benefits", 5)
    left = [{"t": S5_HEAD, "sz": 20, "b": True, "c": GREEN, "sa": 4, "ls": 1.0},
            P(S5_SUB, sz=12, c=MUT, sa=10), H("Who it helps", sb=0), P(S5_WHO, sz=13, sa=10),
            H("Benefits")] + [B(t) for t in S5_BEN]
    write(box(s, MARGIN, BODY_TOP, COL_W, 5.4), left)
    rh = picture(s, REGION_PNG, col2, BODY_TOP + 0.9, COL_W)
    write(box(s, col2, BODY_TOP + 0.9 + rh + 0.05, COL_W, 0.7),
          [{"t": "Auxiliary heat to hold 20 °C: passive design vs baseline hut, by region.",
            "sz": 10.5, "c": MUT, "sa": 0, "ls": 1.1}])

    # Slide 6
    s = add_slide("Research & References", 6)
    body = [B(t, sz=14, sa=7) for t in REFS]
    body.append({"t": S6_NOTE, "sz": 12.5, "c": MUT, "sa": 0, "ls": 1.15, "space_before": 6})
    write(box(s, MARGIN, BODY_TOP, SW - 2 * MARGIN, 5.4), body)

    prs.save(out_path)
    print(f"pptx  → {out_path}  ({len(prs.slides)} slides)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--figures-only", action="store_true", help="only regenerate the embedded figures (needs matplotlib)")
    ap.add_argument("--pptx", action="store_true", help="also emit an editable .pptx (needs python-pptx)")
    ap.add_argument("--pdf", default=os.path.join(DOCS, "Thermal-Shelter_SIH2026_PS26051.pdf"))
    ap.add_argument("--pptx-out", default=os.path.join(DOCS, "Thermal-Shelter_SIH2026_PS26051.pptx"))
    args = ap.parse_args()

    if args.figures_only:
        if not HAVE_MPL:
            raise SystemExit("Regenerating figures needs matplotlib — run with ./.venv/bin/python.")
        make_figures()
        print(f"figures → {FLOW_PNG}, {REGION_PNG}")
        return

    # The PDF half needs matplotlib (venv Python); the .pptx half needs python-pptx
    # (system Python). Build whichever this interpreter supports, so one script,
    # run under each, produces both deliverables.
    if HAVE_MPL:
        build_pdf(args.pdf)
    if args.pptx or not HAVE_MPL:
        build_pptx(args.pptx_out)


if __name__ == "__main__":
    main()
