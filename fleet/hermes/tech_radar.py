#!/usr/bin/env python3
"""기술 레이더 — 지난 7일의 GitHub(검색·Trending·릴리스)·스킬 모음·Hacker News 에서 우리 작업(Claude Code·Codex·Herdr·Hermes·
에이전트 운용·PicDock/KDP 자동화)과 닿는 후보를 긁어 에이전트가 읽기 좋은 다이제스트로 출력한다.
hermes cron --script 모드: 이 stdout 이 에이전트 프롬프트에 주입된다. 한 번 보여 준 항목은 ~/.hermes/state/tech_radar_seen.json 에 적어 다시 안 보여 준다.
GitHub 토큰은 ~/.hermes/.env 의 GITHUB_TOKEN(있으면 한도가 넉넉해진다)."""
import json, os, re, sys, datetime as dt, urllib.request, urllib.parse, html
from pathlib import Path

HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
STATE = HOME / "state" / "tech_radar_seen.json"
KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime.now(KST)
SINCE = (NOW - dt.timedelta(days=7))
SINCE_D = SINCE.strftime("%Y-%m-%d")
KEYS = ["claude", "codex", "agent", "mcp", "llm", "cli", "terminal", "skill", "hermes", "automation", "copilot", "cursor", "openai", "anthropic", "prompt", "workflow"]


def env_token():
    try:
        for line in open(HOME / ".env"):
            if line.startswith("GITHUB_TOKEN="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return ""


TOKEN = env_token()


def get(url, accept="application/vnd.github+json", timeout=25):
    req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": "tech-radar/1.0", **({"Authorization": "Bearer " + TOKEN} if TOKEN and "github.com" in url else {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def gh_json(url):
    try:
        return json.loads(get(url))
    except Exception as e:
        return {"_error": f"{type(e).__name__}: {str(e)[:120]}"}


items = []   # dict(url, title, desc, score, source)
errors = []


def add(url, title, desc, score, source):
    if not url or any(x["url"] == url for x in items):
        return
    items.append({"url": url, "title": title.strip()[:120], "desc": re.sub(r"\s+", " ", (desc or "")).strip()[:220], "score": score, "source": source})


# 1) GitHub 검색 — 새로 생긴 저장소(7일) + 활발한 기존 저장소
NEW_Q = ['"claude code"', 'claude-code', 'codex cli', 'agent skills SKILL.md', 'hermes-agent', '"mcp server"', 'coding agent terminal', 'claude plugin hooks']
for q in NEW_Q:
    d = gh_json("https://api.github.com/search/repositories?" + urllib.parse.urlencode({"q": f"{q} created:>={SINCE_D}", "sort": "stars", "order": "desc", "per_page": 6}))
    if "_error" in d:
        errors.append(f"github search {q}: {d['_error']}"); continue
    for r in d.get("items", []):
        if r.get("stargazers_count", 0) >= 15:
            add(r["html_url"], r["full_name"], r.get("description"), r["stargazers_count"], "github 신규(7일) ★")
for q in ['"claude code"', 'codex', 'claude skills', 'agent harness multi-machine']:
    d = gh_json("https://api.github.com/search/repositories?" + urllib.parse.urlencode({"q": f"{q} pushed:>={SINCE_D} stars:>=300", "sort": "stars", "order": "desc", "per_page": 6}))
    if "_error" in d:
        errors.append(f"github active {q}: {d['_error']}"); continue
    for r in d.get("items", []):
        add(r["html_url"], r["full_name"], r.get("description"), r["stargazers_count"], "github 활발(7일 push) ★")

# 2) GitHub Trending (주간) — 키워드가 닿는 것만
try:
    page = get("https://github.com/trending?since=weekly", accept="text/html")
    for m in re.finditer(r'<h2 class="h3 lh-condensed">.*?href="/([^"]+)".*?</h2>(.*?)(?=<h2 class="h3 lh-condensed">|<footer|$)', page, re.S):
        name, rest = m.group(1).strip(), m.group(2)
        dm = re.search(r'<p class="col-9[^"]*">(.*?)</p>', rest, re.S)
        desc = html.unescape(re.sub(r"<[^>]+>", "", dm.group(1))).strip() if dm else ""
        sm = re.search(r'([\d,]+) stars this week', rest)
        stars = int(sm.group(1).replace(",", "")) if sm else 0
        blob = (name + " " + desc).lower()
        if any(k in blob for k in KEYS):
            add("https://github.com/" + name, name, desc, stars, "github trending(주간) ★this week")
except Exception as e:
    errors.append(f"trending: {type(e).__name__}")

# 3) 릴리스 — 우리가 쓰는 도구의 지난 7일 릴리스
for repo in ["anthropics/claude-code", "openai/codex", "NousResearch/hermes-agent", "anthropics/skills", "anthropics/claude-agent-sdk-python", "modelcontextprotocol/servers"]:
    d = gh_json(f"https://api.github.com/repos/{repo}/releases?per_page=5")
    if isinstance(d, dict) and "_error" in d:
        errors.append(f"releases {repo}: {d['_error']}"); continue
    for r in d if isinstance(d, list) else []:
        pub = r.get("published_at") or ""
        if pub[:10] >= SINCE_D and not r.get("draft"):
            body = (r.get("body") or "")[:500]
            add(r["html_url"], f"{repo} {r.get('tag_name','')}", f"릴리스 {pub[:10]} — {body}", 0, "릴리스")

# 4) Hacker News (Algolia) — 지난 7일, 80점 이상
for q in ["Claude Code", "Codex CLI", "coding agent", "MCP", "agent skills", "Hermes agent"]:
    try:
        d = json.loads(get("https://hn.algolia.com/api/v1/search?" + urllib.parse.urlencode({"query": q, "tags": "story", "numericFilters": f"points>=80,created_at_i>{int(SINCE.timestamp())}", "hitsPerPage": 8}), accept="application/json"))
        for h in d.get("hits", []):
            add(h.get("url") or f"https://news.ycombinator.com/item?id={h['objectID']}", h.get("title", ""), f"HN {h.get('points')}점 · 댓글 {h.get('num_comments')} · https://news.ycombinator.com/item?id={h['objectID']}", h.get("points", 0), "hacker news")
    except Exception as e:
        errors.append(f"hn {q}: {type(e).__name__}")

# 본 것 제외 + 정렬 + 상한
try:
    seen = json.load(open(STATE))
except Exception:
    seen = {}
fresh = [x for x in items if x["url"] not in seen]
ORDER = ["릴리스", "github trending(주간) ★this week", "github 신규(7일) ★", "github 활발(7일 push) ★", "hacker news"]
fresh.sort(key=lambda x: (ORDER.index(x["source"]) if x["source"] in ORDER else 9, -x["score"]))
fresh = fresh[:45]

print(f"# 기술 레이더 다이제스트 ({NOW.strftime('%Y-%m-%d %H:%M')} KST, 지난 7일, 새 후보 {len(fresh)}개 / 전체 {len(items)}개, 이미 본 것 {len(items)-len([x for x in items if x['url'] not in seen])}개 제외)\n")
if not fresh:
    print("새 후보 없음.")
cur = None
for x in fresh:
    if x["source"] != cur:
        cur = x["source"]; print(f"\n## {cur}")
    sc = f" [{x['score']}]" if x["score"] else ""
    print(f"- {x['title']}{sc} — {x['desc']}\n  {x['url']}")
if errors:
    print("\n## 수집 경고\n" + "\n".join("- " + e for e in errors))

STATE.parent.mkdir(parents=True, exist_ok=True)
for x in fresh:
    seen[x["url"]] = NOW.strftime("%Y-%m-%d")
# 90일 지난 기록은 버린다
cut = (NOW - dt.timedelta(days=90)).strftime("%Y-%m-%d")
seen = {k: v for k, v in seen.items() if v >= cut}
json.dump(seen, open(STATE, "w"), ensure_ascii=False, indent=0)
