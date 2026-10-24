"""Science catalogue pages (spec 3.2 item 5, acceptance 12).

Server rendered from the registry so the catalogue works before the WP8
frontend exists and never needs a network asset: inline CSS, system fonts,
no scripts. The WP8 Science screen reads the same data from /api/science.
"""
from __future__ import annotations

from html import escape
from typing import Any

from ..science import registry

CSS = """
:root{--bg:#fbfbfa;--fg:#1d1d1b;--muted:#5c5c57;--line:#dcdcd6;--panel:#f1f1ee;--accent:#1f5f8b}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--fg:#ececea;--muted:#a3a39d;--line:#34342f;--panel:#20201e;--accent:#7fb4dc}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.5 -apple-system,BlinkMacSystemFont,"Helvetica Neue",Helvetica,Arial,sans-serif}
main{max-width:920px;margin:0 auto;padding:24px 16px 64px}a{color:var(--accent)}
h1{font-size:24px;margin:0 0 4px}h2{font-size:17px;margin:28px 0 8px}.muted{color:var(--muted)}
table{width:100%;border-collapse:collapse}th,td{text-align:left;vertical-align:top;padding:8px;border-top:1px solid var(--line)}
th{width:28%;font-weight:600}pre{white-space:pre-wrap;background:var(--panel);padding:10px;border-radius:6px;margin:0;
font:13px/1.45 ui-monospace,Menlo,monospace}.tag{display:inline-block;padding:1px 8px;border:1px solid var(--line);
border-radius:10px;font-size:12px;margin-right:6px}ul{margin:0;padding-left:18px}
"""


def _page(title: str, body: str) -> str:
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{escape(title)}</title><style>{CSS}</style></head><body><main>{body}</main></body></html>")


def _value(v: Any) -> str:
    if isinstance(v, dict):
        return "<ul>" + "".join(f"<li><b>{escape(str(k))}</b>: {_value(x)}</li>" for k, x in v.items()) + "</ul>"
    if isinstance(v, list):
        return "<ul>" + "".join(f"<li>{_value(x)}</li>" for x in v) + "</ul>"
    text = escape(str(v))
    return f"<pre>{text}</pre>" if "\n" in str(v) else text


def index_page() -> str:
    rows = "".join(
        f"<tr><td><a href='/catalogue/{escape(e['metric_id'])}'>{escape(e['metric_id'])}</a></td>"
        f"<td>{escape(e['display_name'])}</td><td>{escape(e['classification'])}</td><td>{escape(e['units'])}</td>"
        f"<td>{escape(str(e['version']))}</td><td>{'complete' if not registry.problems(e) else 'incomplete'}</td></tr>"
        for e in registry.entries().values())
    st = registry.states()
    def defs(d): return "".join(f"<tr><th>{escape(k)}</th><td>{escape(v)}</td></tr>" for k, v in d.items())
    body = (
        "<h1>Science catalogue</h1><p class='muted'>Every metric the application can display, with its full "
        "register entry. Phase One approves M001 to M004 only.</p>"
        "<table><tr><th>ID</th><th>Metric</th><th>Class</th><th>Units</th><th>Version</th><th>Entry</th></tr>"
        f"{rows}</table>"
        f"<h2>Classes</h2><table>{defs(st['classes'])}</table>"
        f"<h2>Data validity</h2><table>{defs(st['validity'])}</table>"
        f"<h2>Value states</h2><table>{defs(st['value_states'])}</table>")
    return _page("Science catalogue", body)


def metric_page(metric_id: str) -> str:
    e = registry.with_sources(registry.entry(metric_id))
    probs = registry.problems(registry.entry(metric_id))
    shown = [f for f in registry.CONTRACT_FIELDS if f not in ("metric_id", "display_name")]
    refs = "".join(
        f"<li>{escape(r['role'])}: {escape(r.get('citation', ''))}"
        + (f" DOI <a href='https://doi.org/{escape(r['doi'])}'>{escape(r['doi'])}</a>" if r.get("doi") else "")
        + f" <span class='tag'>{escape(str(r.get('status')))}</span></li>" for r in e["source_refs"])
    rows = []
    for f in shown:
        cell = f"<ul>{refs}</ul>" if f == "source_refs" else _value(e[f])
        rows.append(f"<tr><th>{escape(f.replace('_', ' '))}</th><td>{cell}</td></tr>")
    rows.insert(3, f"<tr><th>evidence label</th><td>{escape(e['evidence_label'])}</td></tr>")
    rows.insert(5, f"<tr><th>outputs</th><td>{_value(e.get('outputs', {}))}</td></tr>")
    warn = ("<p><b>Entry incomplete, metric not displayable:</b> " + escape("; ".join(probs)) + "</p>") if probs else ""
    body = (f"<p><a href='/catalogue'>Science catalogue</a></p><h1>{escape(e['metric_id'])} {escape(e['display_name'])}</h1>"
            f"<p><span class='tag'>{escape(e['classification'])}</span><span class='tag'>v{escape(str(e['version']))}</span>"
            f"<span class='tag'>{escape(e['units'])}</span></p>{warn}<table>{''.join(rows)}</table>"
            f"<p class='muted'>Source: {escape(e['documentation_path'])}. Status codes: V confirmed, P from the starter "
            "pack and not rechecked, M DOI not confirmed.</p>")
    return _page(f"{e['metric_id']} {e['display_name']}", body)
