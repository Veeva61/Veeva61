"""Draws the contribution grid with a pearl snake crawling over every cell.

The snake winds through the whole year column by column, so it stays lively
even when the grid is almost empty. Days with contributions are real data from
GitHub: the snake eats them with a sparkle and they grow back while it returns.

Writes dist/github-snake.svg (light theme) and dist/github-snake-dark.svg.
Usage: python snake/snake.py <login> [calendar.json]
Without a calendar file it asks the GitHub GraphQL API, using GITHUB_TOKEN.
"""
import json
import os
import random
import sys
import urllib.request

PITCH = 16     # distance between cells, px
CELL = 12      # cell size, px
ROWS = 7
STEP_MS = 55   # time for the snake to move one cell
LENGTH = 9     # pearls in the snake, head included
TWINKLES = 14  # idle sparkles between cells

QUERY = """query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        weeks { contributionDays { date contributionCount contributionLevel weekday } }
      }
    }
  }
}"""

LEVELS = {"FIRST_QUARTILE": 0, "SECOND_QUARTILE": 1, "THIRD_QUARTILE": 2, "FOURTH_QUARTILE": 3}

THEMES = {
    "github-snake-dark.svg": {
        "empty": "#2b2838",
        "levels": ["#4a3f72", "#6a5aa8", "#a08ce0", "#d9ceff"],
        "head": "#f8f5ff",
        "tail": "#7a63c9",
        "spark": "#ffffff",
        "twinkle": "#c9b8ff",
        "glow": 2.4,
    },
    "github-snake.svg": {
        "empty": "#efeaff",
        "levels": ["#d9ceff", "#b9a6f0", "#8e7cc3", "#5f4b9e"],
        "head": "#4b3a8a",
        "tail": "#b9a6f0",
        "spark": "#8e7cc3",
        "twinkle": "#a690e8",
        "glow": 1.2,
    },
}

STAR = "M0,-1L.22,-.22L1,0L.22,.22L0,1L-.22,.22L-1,0L-.22,-.22Z"


def fetch(login):
    body = json.dumps({"query": QUERY, "variables": {"login": login}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": "bearer " + os.environ["GITHUB_TOKEN"],
            "Content-Type": "application/json",
            "User-Agent": "profile-snake",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    if data.get("errors"):
        raise SystemExit(data["errors"])
    return data


def grid(data):
    """Returns (columns, {(col, row): level or -1})."""
    weeks = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    cells = {}
    for col, week in enumerate(weeks):
        for day in week["contributionDays"]:
            level = LEVELS.get(day["contributionLevel"], -1)
            if day["contributionCount"] == 0:
                level = -1
            cells[(col, day["weekday"])] = level
    return len(weeks), cells


def route(cols):
    """Closed loop: snake down and up each column, then back along a lane outside the grid."""
    pts = []
    for c in range(cols):
        rows = range(ROWS) if c % 2 == 0 else range(ROWS - 1, -1, -1)
        pts += [(c, r) for r in rows]
    last = cols - 1
    if cols % 2:  # ends at the bottom right: return below the grid and up the left side
        pts += [(c, ROWS) for c in range(last, -2, -1)]
        pts += [(-1, r) for r in range(ROWS - 1, -1, -1)]
    else:  # ends at the top right: return above the grid
        pts += [(c, -1) for c in range(last, -1, -1)]
    return pts


def centre(p):
    return p[0] * PITCH + CELL / 2, p[1] * PITCH + CELL / 2


def pct(x):
    return f"{x:.3f}".rstrip("0").rstrip(".") + "%"


def mix(a, b, t):
    a, b = int(a[1:], 16), int(b[1:], 16)
    out = 0
    for shift in (16, 8, 0):
        ca, cb = (a >> shift) & 255, (b >> shift) & 255
        out |= round(ca + (cb - ca) * t) << shift
    return f"#{out:06x}"


def svg(cols, cells, theme):
    pts = route(cols)
    n = len(pts)
    period = n * STEP_MS
    ncells = cols * ROWS
    refill_from = (ncells + LENGTH + 2) / n * 100
    refill_to = refill_from + (100 - refill_from) * 0.6

    xs = [centre(p)[0] for p in pts]
    ys = [centre(p)[1] for p in pts]
    pad = 12
    x0, y0 = min(xs) - pad, min(ys) - pad
    w, h = max(xs) - min(xs) + 2 * pad, max(ys) - min(ys) + 2 * pad

    css = [
        f".c{{fill:{theme['empty']}}}",
        *(f".l{i}{{fill:{col}}}" for i, col in enumerate(theme["levels"])),
        f".s{{animation:m {period}ms linear infinite}}",
        f".k{{fill:{theme['spark']};opacity:0;animation:none {period}ms linear infinite}}",
        f".t{{fill:{theme['twinkle']};opacity:0;animation:tw 3.6s ease-in-out infinite}}",
        "@keyframes tw{0%,100%{opacity:0}50%{opacity:.85}}",
    ]

    # Snake movement: keyframes only where the direction changes, speed stays constant.
    frames = []
    for k, p in enumerate(pts):
        prev, nxt = pts[k - 1], pts[(k + 1) % n]
        turn = (p[0] - prev[0], p[1] - prev[1]) != (nxt[0] - p[0], nxt[1] - p[1])
        if k == 0 or turn:
            x, y = centre(p)
            frames.append(f"{pct(k / n * 100)}{{transform:translate({x:g}px,{y:g}px)}}")
    x, y = centre(pts[0])
    frames.append(f"100%{{transform:translate({x:g}px,{y:g}px)}}")
    css.append("@keyframes m{" + "".join(frames) + "}")

    body = []
    index = {p: k for k, p in enumerate(pts)}
    sparks = []
    for (c, r), level in sorted(cells.items()):
        x, y = c * PITCH, r * PITCH
        cls = "c" if level < 0 else f"c l{level}"
        if level < 0:
            body.append(f'<rect class="{cls}" x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="3"/>')
            continue
        k = index[(c, r)]
        at = k / n * 100
        name = f"e{c}_{r}"
        full, empty = theme["levels"][level], theme["empty"]
        css.append(
            f"@keyframes {name}{{0%,{pct(at)}{{fill:{full}}}{pct(at + 0.05)},{pct(refill_from)}"
            f"{{fill:{empty}}}{pct(refill_to)},100%{{fill:{full}}}}}"
            f".{name}{{animation:{name} {period}ms linear infinite}}"
        )
        body.append(f'<rect class="{cls} {name}" x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="3"/>')
        cx, cy = centre((c, r))
        tr = f"translate({cx:g}px,{cy:g}px)"
        css.append(
            f"@keyframes p{name}{{0%,{pct(at)}{{opacity:0;transform:{tr} scale(2) rotate(0)}}"
            f"{pct(at + 0.9)}{{opacity:1;transform:{tr} scale(9) rotate(25deg)}}"
            f"{pct(min(at + 3.2, 99.9))},100%{{opacity:0;transform:{tr} scale(4) rotate(60deg)}}}}"
            f".p{name}{{animation-name:p{name}}}"
        )
        sparks.append(f'<path class="k p{name}" d="{STAR}"/>')

    # Idle twinkles in the gaps between cells.
    rnd = random.Random(61)
    twinkles = []
    for i in range(TWINKLES):
        c, r = rnd.randrange(1, cols), rnd.randrange(1, ROWS)
        x, y = c * PITCH - 2, r * PITCH - 2
        s = rnd.uniform(3, 4.5)
        delay = rnd.uniform(0, 3.6)
        twinkles.append(
            f'<path class="t" d="{STAR}" transform="translate({x} {y}) scale({s:.2f})" '
            f'style="animation-delay:-{delay:.2f}s"/>'
        )

    pearls = []
    for i in range(LENGTH):
        t = i / (LENGTH - 1)
        radius = 6.6 - 3.0 * t
        colour = mix(theme["head"], theme["tail"], t)
        opacity = 1 - 0.45 * t
        delay = 0 if i == 0 else -(period - i * STEP_MS)
        pearls.append(
            f'<circle class="s" r="{radius:.2f}" fill="{colour}" fill-opacity="{opacity:.2f}" '
            f'style="animation-delay:{delay}ms"/>'
        )
    # Head on top: draw the tail first.
    pearls.reverse()

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0:g} {y0:g} {w:g} {h:g}" '
        f'width="{w:g}" height="{h:g}">'
        "<desc>Contribution grid with a pearl snake, generated by snake/snake.py</desc>"
        "<defs>"
        f'<filter id="g" filterUnits="userSpaceOnUse" x="{x0:g}" y="{y0:g}" width="{w:g}" height="{h:g}">'
        f'<feGaussianBlur stdDeviation="{theme["glow"]}" result="b"/>'
        '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
        "</defs>"
        f"<style>{''.join(css)}</style>"
        + "".join(body)
        + "".join(twinkles)
        + '<g filter="url(#g)">'
        + "".join(sparks)
        + "".join(pearls)
        + "</g></svg>"
    )


def main():
    login = sys.argv[1]
    if len(sys.argv) > 2:
        with open(sys.argv[2], encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = fetch(login)
    cols, cells = grid(data)
    os.makedirs("dist", exist_ok=True)
    for name, theme in THEMES.items():
        with open(os.path.join("dist", name), "w", encoding="utf-8") as f:
            f.write(svg(cols, cells, theme))
        print("wrote dist/" + name)


if __name__ == "__main__":
    main()
