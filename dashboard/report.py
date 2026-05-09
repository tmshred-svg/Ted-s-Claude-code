import json
from datetime import date, datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .config import CFG


def render(context: dict) -> str:
    env = Environment(
        loader=FileSystemLoader(str(Path(__file__).parent / "templates")),
        autoescape=select_autoescape(["html"]),
    )
    env.tests["number"] = lambda v: isinstance(v, (int, float))
    tpl = env.get_template("dashboard.html.j2")
    return tpl.render(**context)


def write(html: str) -> Path:
    out_dir = Path(CFG.report_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    dated = out_dir / f"{today}.html"
    dated.write_text(html, encoding="utf-8")
    latest = out_dir / "latest.html"
    latest.write_text(html, encoding="utf-8")
    return dated


def fmt_log(*sections) -> str:
    merged = {}
    for name, log in sections:
        merged[name] = log
    return json.dumps(merged, indent=2, default=str)
