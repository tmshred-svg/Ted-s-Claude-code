"""Server-rendered SVG line panels.

Inline SVG renders in any browser without JavaScript or an external CDN, so
the charts always show up — even if jsdelivr is blocked or Chart.js fails.
"""
from datetime import datetime
from html import escape
from typing import Mapping, Sequence


PALETTE = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#17becf", "#bcbd22",
    "#0a7d2c", "#b00020",
]


def _parse_date(s):
    try:
        return datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def panel_svg(
    series: Sequence[Mapping],
    title: str = "",
    width: int = 1100,
    height: int = 320,
) -> str:
    """Render multiple series as overlaid lines into a single inline SVG."""
    parsed = []
    for s in series:
        pts = []
        for row in s.get("data", []):
            if len(row) < 2:
                continue
            d = _parse_date(row[0])
            if d is None:
                continue
            try:
                v = float(row[1])
            except (TypeError, ValueError):
                continue
            pts.append((d, v))
        if pts:
            parsed.append({"label": s.get("label", ""), "points": pts})

    if not parsed:
        return '<div class="meta">no chart data</div>'

    all_x = [d for s in parsed for (d, _) in s["points"]]
    all_y = [v for s in parsed for (_, v) in s["points"]]
    xmin, xmax = min(all_x), max(all_x)
    ymin, ymax = min(all_y), max(all_y)
    yspan = (ymax - ymin) or abs(ymax) or 1.0
    if ymax == ymin:
        ymax = ymin + yspan
    xspan = (xmax - xmin).total_seconds() or 1.0

    pad_l, pad_r, pad_top, pad_x_axis, pad_legend = 60, 18, 30, 22, 28
    plot_top = pad_top
    plot_bottom = height - pad_x_axis - pad_legend
    plot_h = max(1, plot_bottom - plot_top)
    plot_w = max(1, width - pad_l - pad_r)

    def x_px(d):
        return pad_l + (d - xmin).total_seconds() / xspan * plot_w

    def y_px(v):
        return plot_top + plot_h - (v - ymin) / (ymax - ymin) * plot_h

    parts = [
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
        f'preserveAspectRatio="none" style="width:100%;height:100%;display:block;" '
        f'role="img" aria-label="{escape(title)}">'
    ]
    if title:
        parts.append(
            f'<text x="{width // 2}" y="18" text-anchor="middle" '
            f'font-size="13" font-weight="600" fill="#222">{escape(title)}</text>'
        )

    parts.append(
        f'<rect x="{pad_l}" y="{plot_top}" width="{plot_w}" height="{plot_h}" '
        f'fill="#fff" stroke="#ddd"/>'
    )
    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        v = ymin + (ymax - ymin) * (1 - frac)
        y = plot_top + plot_h * frac
        parts.append(
            f'<line x1="{pad_l}" x2="{pad_l + plot_w}" y1="{y:.1f}" y2="{y:.1f}" '
            f'stroke="#eee" stroke-dasharray="2,3"/>'
        )
        parts.append(
            f'<text x="{pad_l - 6}" y="{y + 3:.1f}" text-anchor="end" '
            f'font-size="10" fill="#666">{v:.4g}</text>'
        )

    for i, s in enumerate(parsed):
        color = PALETTE[i % len(PALETTE)]
        coords = " ".join(f"{x_px(d):.1f},{y_px(v):.1f}" for d, v in s["points"])
        parts.append(
            f'<polyline fill="none" stroke="{color}" stroke-width="1.4" '
            f'stroke-linejoin="round" stroke-linecap="round" points="{coords}"/>'
        )

    x_label_y = plot_bottom + 14
    parts.append(
        f'<text x="{pad_l}" y="{x_label_y}" font-size="10" fill="#666">'
        f"{xmin.date().isoformat()}</text>"
    )
    parts.append(
        f'<text x="{pad_l + plot_w}" y="{x_label_y}" text-anchor="end" '
        f'font-size="10" fill="#666">{xmax.date().isoformat()}</text>'
    )

    legend_y = height - 10
    legend_x = pad_l
    legend_max_x = pad_l + plot_w
    parts.append('<g font-size="11" fill="#333">')
    for i, s in enumerate(parsed):
        color = PALETTE[i % len(PALETTE)]
        last_v = s["points"][-1][1]
        text = f'{s["label"]} — last {last_v:.4g}'
        approx_w = 18 + len(text) * 6.4
        if legend_x + approx_w > legend_max_x and legend_x != pad_l:
            legend_x = pad_l
            legend_y += 14
        parts.append(
            f'<rect x="{legend_x}" y="{legend_y - 8}" width="10" height="3" fill="{color}"/>'
        )
        parts.append(
            f'<text x="{legend_x + 14}" y="{legend_y}">{escape(text)}</text>'
        )
        legend_x += approx_w
    parts.append("</g>")
    parts.append("</svg>")
    return "".join(parts)
