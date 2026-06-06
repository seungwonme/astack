#!/usr/bin/env python3
"""oss-contrib :: render_html
stdin 으로 contributions.sh / stats.sh 의 JSON 을 받아 단일 HTML 리포트를 stdout 으로 출력.
의존성 0 (표준 라이브러리만), 다크/라이트 자동 대응, 인라인 CSS.
"""
import sys
import json
import html as _html


def esc(s):
    return _html.escape(str(s))


def bar_rows(items, label_key, value_key, unit=""):
    if not items:
        return "<p class='muted'>데이터 없음</p>"
    maxv = max((it[value_key] for it in items), default=0) or 1
    out = []
    for it in items:
        pct = round(it[value_key] / maxv * 100)
        out.append(
            f"<div class='bar-row'>"
            f"<span class='bar-label'>{esc(it[label_key])}</span>"
            f"<span class='bar-track'><span class='bar-fill' style='width:{pct}%'></span></span>"
            f"<span class='bar-val'>{esc(it[value_key])}{unit}</span>"
            f"</div>"
        )
    return "\n".join(out)


def render_contributions(d):
    s = d.get("summary", {})
    cards = f"""
    <div class='cards'>
      <div class='card'><div class='num'>{s.get('merged_prs', 0)}</div><div class='lbl'>머지된 PR</div></div>
      <div class='card'><div class='num'>{s.get('external_repos', 0)}</div><div class='lbl'>순수 외부 OSS</div></div>
      <div class='card'><div class='num'>{s.get('org_groups', 0)}</div><div class='lbl'>소속 조직</div></div>
    </div>"""

    ext = d.get("external", [])
    if ext:
        rows = "\n".join(
            f"<tr><td><a href='{esc(r['url'])}' target='_blank'>{esc(r['repo'])}</a></td>"
            f"<td class='c'>{r['prs']}</td>"
            f"<td class='c'><span class='star'>★ {r['stars']:,}</span></td>"
            f"<td class='desc'>{esc(r.get('description', ''))}</td></tr>"
            for r in ext
        )
        external = f"""
        <table>
          <thead><tr><th>레포</th><th>머지 PR</th><th>Stars</th><th>설명</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>"""
    else:
        external = "<p class='muted'>순수 외부 OSS 기여 없음</p>"

    orgs = d.get("orgs", [])
    if orgs:
        items = []
        for g in orgs:
            repos = ", ".join(
                f"{esc(r['repo'].split('/')[-1])}<span class='dim'>({r['prs']})</span>"
                for r in g["repos"]
            )
            items.append(
                f"<li><strong>{esc(g['org'])}</strong> "
                f"<span class='dim'>· {g['prs']} PR</span><br><span class='repos'>{repos}</span></li>"
            )
        org_html = f"<ul class='orglist'>{''.join(items)}</ul>"
    else:
        org_html = "<p class='muted'>소속 조직 기여 없음</p>"

    body = f"""
    {cards}
    <h2>순수 외부 OSS 기여 <span class='dim'>(star 순)</span></h2>
    {external}
    <h2>소속 조직 <span class='dim'>(팀/회사 프로젝트)</span></h2>
    {org_html}"""
    return f"{esc(d.get('user',''))} — 오픈소스 기여 내역", body


def render_stats(d):
    s = d.get("summary", {})
    cards = f"""
    <div class='cards'>
      <div class='card'><div class='num'>{s.get('total_prs', 0)}</div><div class='lbl'>전체 PR</div></div>
      <div class='card'><div class='num'>{s.get('merged_prs', 0)}</div><div class='lbl'>머지된 PR</div></div>
      <div class='card'><div class='num'>{s.get('merge_rate', 0)}%</div><div class='lbl'>머지율</div></div>
    </div>"""
    years = bar_rows(d.get("years", []), "year", "prs")
    months = bar_rows([{**m, "label": m["month"] + "월"} for m in d.get("months", [])], "label", "prs")
    weekdays = d.get("weekdays", [])
    langs = bar_rows(d.get("languages", []), "name", "repos")
    weekday_section = ""
    if weekdays:
        wd = bar_rows(weekdays, "day", "prs")
        weekday_section = f"<h2>요일별 <span class='dim'>(머지 PR)</span></h2>\n<div class='chart'>{wd}</div>"
    body = f"""
    {cards}
    <h2>연도별 <span class='dim'>(머지 PR)</span></h2>
    <div class='chart'>{years}</div>
    <h2>월별 <span class='dim'>(머지 PR)</span></h2>
    <div class='chart'>{months}</div>
    {weekday_section}
    <h2>언어별 <span class='dim'>(머지 PR이 닿은 레포 수)</span></h2>
    <div class='chart'>{langs}</div>"""
    return f"{esc(d.get('user',''))} — 기여 통계", body


CSS = """
:root { --bg:#fff; --fg:#1a1a1a; --muted:#666; --card:#f5f5f7; --border:#e2e2e6;
        --accent:#2563eb; --star:#d97706; --fill:#2563eb; --track:#e2e2e6; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#0d1117; --fg:#e6edf3; --muted:#8b949e; --card:#161b22; --border:#30363d;
          --accent:#58a6ff; --star:#e3b341; --fill:#388bfd; --track:#21262d; } }
* { box-sizing:border-box; }
body { margin:0; padding:2.5rem 1.5rem; background:var(--bg); color:var(--fg);
       font:15px/1.6 -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; }
.wrap { max-width:860px; margin:0 auto; }
h1 { font-size:1.6rem; margin:0 0 .25rem; }
h2 { font-size:1.15rem; margin:2rem 0 .75rem; }
.gen { color:var(--muted); font-size:.85rem; margin-bottom:1.5rem; }
.dim { color:var(--muted); font-weight:400; font-size:.85em; }
.muted { color:var(--muted); }
.cards { display:flex; gap:1rem; flex-wrap:wrap; }
.card { flex:1; min-width:140px; background:var(--card); border:1px solid var(--border);
        border-radius:12px; padding:1.1rem 1.2rem; }
.card .num { font-size:2rem; font-weight:700; color:var(--accent); }
.card .lbl { color:var(--muted); font-size:.85rem; }
table { width:100%; border-collapse:collapse; font-size:.9rem; }
th,td { text-align:left; padding:.55rem .6rem; border-bottom:1px solid var(--border); }
th { color:var(--muted); font-weight:600; }
td.c { text-align:center; white-space:nowrap; }
td.desc { color:var(--muted); }
a { color:var(--accent); text-decoration:none; }
a:hover { text-decoration:underline; }
.star { color:var(--star); white-space:nowrap; }
.orglist { list-style:none; padding:0; margin:0; }
.orglist li { padding:.6rem 0; border-bottom:1px solid var(--border); }
.repos { color:var(--muted); font-size:.88rem; }
.chart { display:flex; flex-direction:column; gap:.4rem; }
.bar-row { display:flex; align-items:center; gap:.6rem; }
.bar-label { width:130px; text-align:right; font-size:.85rem; color:var(--muted);
             overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.bar-track { flex:1; height:14px; background:var(--track); border-radius:7px; overflow:hidden; }
.bar-fill { display:block; height:100%; background:var(--fill); border-radius:7px; }
.bar-val { width:48px; font-size:.85rem; }
footer { margin-top:2.5rem; color:var(--muted); font-size:.8rem;
         border-top:1px solid var(--border); padding-top:1rem; }
"""


def main():
    raw = sys.stdin.read()
    d = json.loads(raw)
    t = d.get("type")
    if t == "stats":
        title, body = render_stats(d)
    else:
        title, body = render_contributions(d)
    html_out = f"""<!doctype html>
<html lang='ko'><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>{title}</title><style>{CSS}</style></head>
<body><div class='wrap'>
<h1>{title}</h1>
<div class='gen'>생성: {esc(d.get('generated', ''))} · gh CLI 기준</div>
{body}
<footer>oss-contrib · GitHub CLI 기반 · 머지된 PR 기준 집계</footer>
</div></body></html>"""
    sys.stdout.write(html_out)


if __name__ == "__main__":
    main()
