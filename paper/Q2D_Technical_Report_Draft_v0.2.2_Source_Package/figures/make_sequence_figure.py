from __future__ import annotations

import matplotlib.pyplot as plt
from pathlib import Path
from matplotlib.patches import FancyBboxPatch, Rectangle, FancyArrowPatch, Circle

OUT = str(Path(__file__).with_name("query_sequence.png"))

fig, ax = plt.subplots(figsize=(16, 10), dpi=180)
ax.set_xlim(0, 16)
ax.set_ylim(0, 10)
ax.axis("off")

# Palette
ink = "#15233a"
blue = "#285b8f"
light_blue = "#eef4fa"
light_model = "#fff5ed"
light_transport = "#eef1f5"
light_data = "#eff7ef"
border = "#9aaabc"
muted = "#64748b"
warning = "#a84535"
green = "#2e6b49"

# Trust zones
zones = [
    (0.35, 0.35, 3.0, 9.2, light_model, "MODEL CONTEXT\n(untrusted)", ink, 18),
    (3.55, 0.35, 3.0, 9.2, light_blue, "TRUSTED\nREQUESTER\nRUNTIME", ink, 16),
    (6.75, 0.35, 1.65, 9.2, light_transport, "UNTRUSTED\nTRANSPORT", muted, 13.5),
    (8.6, 0.35, 3.0, 9.2, light_blue, "CUSTODIAN Q2D\nRUNTIME", ink, 16),
    (11.8, 0.35, 3.85, 9.2, light_data, "POLICY +\nPROTECTED DATA", ink, 18),
]
for x, y, w, h, fc, title, tc, title_size in zones:
    ax.add_patch(FancyBboxPatch((x, y), w, h,
                                boxstyle="round,pad=0.02,rounding_size=0.08",
                                linewidth=1.2, edgecolor=border, facecolor=fc, zorder=0))
    ax.text(x+w/2, 9.26, title, ha="center", va="top", fontsize=title_size,
            fontweight="bold", color=tc, linespacing=0.92)

# Model-context boundary
boundary_x = 3.45
ax.plot([boundary_x, boundary_x], [0.45, 9.4], color=warning, linewidth=2.4, zorder=1)
ax.text(boundary_x-0.08, 5.0, "MODEL-CONTEXT BOUNDARY", rotation=90,
        ha="right", va="center", fontsize=13.5, fontweight="bold", color=warning)

# Lifelines
lanes = {
    "agent": 1.85,
    "requester": 5.05,
    "custodian": 10.1,
    "data": 13.7,
}
for x in lanes.values():
    ax.plot([x, x], [1.0, 8.85], color=muted, linewidth=1.3,
            linestyle=(0, (4, 4)), zorder=1)

# Helper functions

def arrow(x1, y1, x2, y2, label, *, color=ink, above=0.12, fontsize=15.0, lw=1.8, style="-|>"):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style,
                                 mutation_scale=13, linewidth=lw, color=color,
                                 shrinkA=3, shrinkB=3, zorder=4))
    ax.text((x1+x2)/2, y1+above, label, ha="center", va="bottom",
            fontsize=fontsize, color=color, zorder=5)


def step_box(x, y, w, h, n, text, *, fc="#f8fafc", ec=border, text_color=ink, fontsize=15.0):
    ax.add_patch(FancyBboxPatch((x, y), w, h,
                                boxstyle="round,pad=0.02,rounding_size=0.08",
                                linewidth=1.2, edgecolor=ec, facecolor=fc, zorder=3))
    ax.add_patch(FancyBboxPatch((x+0.10, y+h-0.45), 0.34, 0.34,
                                boxstyle="round,pad=0.01,rounding_size=0.05",
                                linewidth=0, facecolor=blue, zorder=4))
    ax.text(x+0.27, y+h-0.28, str(n), ha="center", va="center",
            fontsize=13.5, fontweight="bold", color="white", zorder=5)
    ax.text(x+0.55, y+h/2, text, ha="left", va="center", fontsize=fontsize,
            color=text_color, linespacing=0.98, zorder=5)

# 1
arrow(lanes["agent"], 8.42, lanes["requester"], 8.42,
      "1  Emit typed intent", fontsize=15.5)

# 2
step_box(3.68, 7.45, 2.73, 0.92, 2,
         "Bind identity and contract;\nadd purpose & sinks; sign", fontsize=14.0)

# 3
arrow(lanes["requester"], 7.22, lanes["custodian"], 7.22,
      "3  Deliver signed query", above=0.08, fontsize=15.5)

# 4
step_box(8.66, 6.22, 2.88, 0.94, 4,
         "Validate identity & nonce;\nregistry and policy", fontsize=14.0)

# 5 request and return
arrow(lanes["custodian"], 5.92, lanes["data"], 5.92,
      "5  Evaluate predicate locally", above=0.10, fontsize=15.0)
arrow(lanes["data"], 5.52, lanes["custodian"], 5.52,
      "Bounded result", color=green, above=0.08, fontsize=14.0)

# 6
step_box(8.66, 4.43, 2.88, 0.94, 6,
         "Validate domain; debit budget;\nissue disclosure receipt", fontsize=14.0)

# 7
arrow(lanes["custodian"], 4.14, lanes["requester"], 4.14,
      "7  Authenticated answer / deny / escalate\n    + evidence and receipt",
      above=0.10, fontsize=14.0)

# 8
step_box(3.68, 3.05, 2.73, 0.92, 8,
         "Verify evidence & response\noutside model context", fontsize=14.0)

# Evidence termination callout
ax.add_patch(FancyArrowPatch((3.96, 3.55), (3.54, 3.55), arrowstyle="-|>",
                             mutation_scale=13, linewidth=1.5, color=warning, zorder=5))
ax.add_patch(Circle((3.40, 3.55), 0.11, facecolor="white", edgecolor=warning,
                    linewidth=1.8, zorder=6))
ax.plot([3.34, 3.46], [3.49, 3.61], color=warning, linewidth=1.6, zorder=7)
ax.text(3.23, 3.55, "EVIDENCE STOPS HERE",
        ha="right", va="center", fontsize=12.5, color=warning, fontweight="bold")

# 9
arrow(lanes["requester"], 2.65, lanes["agent"], 2.65,
      "9  Semantic answer only", above=0.10, fontsize=15.0)

# 10 contained flow
ax.text(0.62, 1.62, "10", ha="center", va="center", fontsize=13.5,
        fontweight="bold", color="white",
        bbox=dict(boxstyle="round,pad=0.28", facecolor=blue, edgecolor="none"))
ax.text(0.98, 1.62, "Contained runtime mediates answer-derived flows.",
        ha="left", va="center", fontsize=14.0, color=ink)
arrow(lanes["agent"], 1.18, lanes["requester"], 1.18,
      "derived output", above=0.08, fontsize=13.0)
arrow(lanes["requester"], 1.18, 13.15, 1.18,
      "permitted flow", color=green, above=0.08, fontsize=13.0)
ax.add_patch(FancyBboxPatch((13.05, 0.87), 1.82, 0.62,
                            boxstyle="round,pad=0.02,rounding_size=0.08",
                            linewidth=1.2, edgecolor=green, facecolor="white", zorder=4))
ax.text(13.96, 1.18, "Permitted sinks", ha="center", va="center",
        fontsize=12.5, color=green, fontweight="bold", zorder=5)
# blocked sink illustration
ax.add_patch(FancyArrowPatch((lanes["requester"], 0.72), (15.05, 0.72), arrowstyle="-|>",
                             mutation_scale=13, linewidth=1.3, color=warning,
                             linestyle=(0, (4, 3)), zorder=4))
ax.text(9.7, 0.77, "undeclared flow blocked", ha="center", va="bottom",
        fontsize=12.5, color=warning)
ax.text(15.20, 0.72, "×", ha="center", va="center", fontsize=20,
        color=warning, fontweight="bold")

# Small legend


plt.subplots_adjust(left=0.015, right=0.995, top=0.985, bottom=0.02)
fig.savefig(OUT, bbox_inches="tight", facecolor="white")
plt.close(fig)
print(OUT)
