"""Dashboard renderer for the Daily Brief project.

render_dashboard(...) returns the inner HTML (a <style> block + markup) that can
be embedded directly. build_page(...) wraps it into a full standalone HTML
document for GitHub Pages. Both draw from the dict returned by weather.fetch_weather_data().
"""
from datetime import datetime

BAD_WEATHER_CODES = {45, 48, 51, 61, 63, 65, 71, 73, 75, 80, 95}

# --- All CSS lives here as a plain string (never an f-string; CSS braces) ---
STYLE = """
<style>
  :root {
    --ground: #F1EFE9;
    --surface: #FBFAF6;
    --border: #E4DFD4;
    --ink: #232A31;
    --ink-soft: #6A737D;
    --accent: #E19A2B;
    --accent-soft: rgba(225,154,43,0.14);
    --go-fg: #3C8A5F;   --go-bg: #E4F0E8;
    --caution-fg: #B9772A; --caution-bg: #F6ECD8;
    --stay-fg: #57616D; --stay-bg: #E9EAEC;
    --shadow: 0 1px 2px rgba(35,42,49,0.05), 0 8px 24px rgba(35,42,49,0.06);
    --font-display: "Iowan Old Style", "Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif;
    --font-sans: system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --ground: #13161B; --surface: #1C212A; --border: #2C333D;
      --ink: #ECEAE3; --ink-soft: #98A2AD;
      --accent: #F0B24E; --accent-soft: rgba(240,178,78,0.16);
      --go-fg: #6ABE90; --go-bg: #1A3325;
      --caution-fg: #E0A659; --caution-bg: #352916;
      --stay-fg: #9AA4AF; --stay-bg: #262B33;
      --shadow: 0 1px 2px rgba(0,0,0,0.3), 0 10px 28px rgba(0,0,0,0.35);
    }
  }
  :root[data-theme="light"] {
    --ground: #F1EFE9; --surface: #FBFAF6; --border: #E4DFD4;
    --ink: #232A31; --ink-soft: #6A737D; --accent: #E19A2B; --accent-soft: rgba(225,154,43,0.14);
    --go-fg: #3C8A5F; --go-bg: #E4F0E8; --caution-fg: #B9772A; --caution-bg: #F6ECD8;
    --stay-fg: #57616D; --stay-bg: #E9EAEC;
    --shadow: 0 1px 2px rgba(35,42,49,0.05), 0 8px 24px rgba(35,42,49,0.06);
  }
  :root[data-theme="dark"] {
    --ground: #13161B; --surface: #1C212A; --border: #2C333D;
    --ink: #ECEAE3; --ink-soft: #98A2AD; --accent: #F0B24E; --accent-soft: rgba(240,178,78,0.16);
    --go-fg: #6ABE90; --go-bg: #1A3325; --caution-fg: #E0A659; --caution-bg: #352916;
    --stay-fg: #9AA4AF; --stay-bg: #262B33;
    --shadow: 0 1px 2px rgba(0,0,0,0.3), 0 10px 28px rgba(0,0,0,0.35);
  }

  * { box-sizing: border-box; }
  body { margin: 0; }
  .page {
    background: var(--ground);
    color: var(--ink);
    font-family: var(--font-sans);
    min-height: 100vh;
    display: flex;
    justify-content: center;
    padding: 28px 18px 40px;
    -webkit-font-smoothing: antialiased;
  }
  .board {
    width: 100%;
    max-width: 540px;
    display: flex;
    flex-direction: column;
    gap: 16px;
    animation: rise 0.5s ease both;
  }
  @keyframes rise { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
  @media (prefers-reduced-motion: reduce) { .board { animation: none; } }

  .eyebrow {
    margin: 0; font-size: 12px; letter-spacing: 0.14em; text-transform: uppercase;
    color: var(--ink-soft); font-weight: 600;
  }
  .greeting {
    margin: 4px 0 2px; font-family: var(--font-display); font-weight: 600;
    font-size: 34px; line-height: 1.1; text-wrap: balance; letter-spacing: -0.01em;
  }
  .place { margin: 0; color: var(--ink-soft); font-size: 14px; }

  .now {
    display: flex; align-items: center; gap: 14px; padding: 6px 2px 2px;
  }
  .now-emoji { font-size: 52px; line-height: 1; }
  .now-deg {
    font-family: var(--font-display); font-size: 76px; line-height: 0.9; font-weight: 600;
    font-variant-numeric: tabular-nums; letter-spacing: -0.02em;
  }
  .now-desc { margin: 6px 0 0; color: var(--ink-soft); font-size: 15px; }

  .verdict {
    border-radius: 16px; padding: 18px 20px; box-shadow: var(--shadow);
    border: 1px solid transparent;
  }
  .verdict--go { background: var(--go-bg); border-color: color-mix(in srgb, var(--go-fg) 22%, transparent); }
  .verdict--caution { background: var(--caution-bg); border-color: color-mix(in srgb, var(--caution-fg) 22%, transparent); }
  .verdict--stay { background: var(--stay-bg); border-color: color-mix(in srgb, var(--stay-fg) 22%, transparent); }
  .verdict-label {
    margin: 0 0 6px; font-size: 12px; letter-spacing: 0.12em; text-transform: uppercase; font-weight: 700;
  }
  .verdict--go .verdict-label { color: var(--go-fg); }
  .verdict--caution .verdict-label { color: var(--caution-fg); }
  .verdict--stay .verdict-label { color: var(--stay-fg); }
  .verdict-headline {
    margin: 0; font-family: var(--font-display); font-size: 23px; line-height: 1.2;
    text-wrap: balance; font-weight: 600;
  }
  .verdict-sub { margin: 8px 0 0; font-size: 14.5px; line-height: 1.5; color: var(--ink); opacity: 0.82; }

  .stats {
    display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px;
  }
  .stat {
    background: var(--surface); border: 1px solid var(--border); border-radius: 13px;
    padding: 12px 10px; text-align: center; box-shadow: var(--shadow);
  }
  .stat-k { display: block; font-size: 11px; letter-spacing: 0.04em; text-transform: uppercase; color: var(--ink-soft); font-weight: 600; }
  .stat-v { display: block; margin-top: 5px; font-size: 20px; font-weight: 600; font-variant-numeric: tabular-nums; }

  .card {
    background: var(--surface); border: 1px solid var(--border); border-radius: 16px;
    padding: 16px 18px; box-shadow: var(--shadow);
  }
  .card-head { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 6px; }
  .card-title { margin: 0; font-size: 14px; font-weight: 700; letter-spacing: 0.01em; }
  .card-note { font-size: 12.5px; color: var(--ink-soft); font-variant-numeric: tabular-nums; }
  .chart { display: block; width: 100%; height: auto; }

  .inbox { display: flex; align-items: center; justify-content: space-between; }
  .inbox-k { margin: 0; font-size: 15px; font-weight: 600; }
  .inbox-sub { margin: 3px 0 0; font-size: 12.5px; color: var(--ink-soft); }
  .inbox-v {
    margin: 0; font-family: var(--font-display); font-size: 46px; font-weight: 600;
    font-variant-numeric: tabular-nums; line-height: 1; color: var(--accent);
  }

  .foot { text-align: center; color: var(--ink-soft); font-size: 12px; margin-top: 4px; line-height: 1.5; }
  .foot b { color: var(--ink); font-weight: 600; }
</style>
"""


def _twelve_hour(dt: datetime) -> str:
    h = dt.hour % 12 or 12
    return f"{h}:{dt.strftime('%M %p')}"


def _verdict(data: dict):
    """Return (kind, label, headline, sub) for the tonight banner."""
    t, precip, wind = data["evening_temp"], data["evening_precip"], data["evening_wind"]
    desc = data["evening_desc"]
    if data["outdoor_ok"]:
        wind_bit = "barely any wind" if wind <= 6 else f"a light {wind} mph breeze"
        rain_bit = "no rain in sight" if precip == 0 else f"only a {precip}% chance of rain"
        sub = f"{t}° and {desc} around sunset, {wind_bit}, {rain_bit}. A lovely night to get outside."
        return "go", "Tonight", "A great evening for a walk or tennis", sub
    reasons = []
    if data["evening_code"] in BAD_WEATHER_CODES:
        reasons.append(f"{desc} is expected")
    if precip > 30:
        reasons.append(f"there's a {precip}% chance of rain")
    if t > 90:
        reasons.append("it stays quite hot")
    if t < 45:
        reasons.append("it turns chilly")
    if wind > 20:
        reasons.append(f"it's breezy at {wind} mph")
    reason = reasons[0] if reasons else "conditions look rough"
    if len(reasons) > 1:
        reason = " and ".join([", ".join(reasons[:-1]), reasons[-1]]) if len(reasons) > 2 else " and ".join(reasons)
    kind = "caution" if (precip > 30 or data["evening_code"] in BAD_WEATHER_CODES) else "stay"
    sub = f"This evening {reason} — might be a night for the couch and some AC. Maybe tomorrow!"
    return kind, "Tonight", "Better to take it easy tonight", sub


def _chart_svg(hourly, now_hour: int) -> str:
    temps = [h["temp"] for h in hourly]
    n = len(temps)
    lo, hi = min(temps) - 3, max(temps) + 3
    W, H = 700.0, 200.0
    x0, x1, ytop, ybot = 12.0, 688.0, 16.0, 150.0

    def xf(i):
        return x0 + (i / (n - 1)) * (x1 - x0)

    def yf(t):
        return ytop + (hi - t) / (hi - lo) * (ybot - ytop)

    pts = [(xf(i), yf(temps[i])) for i in range(n)]
    line_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area_d = line_d + f" L {pts[-1][0]:.1f},{ybot:.1f} L {pts[0][0]:.1f},{ybot:.1f} Z"

    band_x, band_w = xf(17), xf(20) - xf(17)  # evening 5-8 PM window
    nh = max(0, min(n - 1, now_hour))
    nx, ny = pts[nh]

    ticks = {0: "12a", 6: "6a", 12: "12p", 18: "6p", 23: "12a"}
    tick_svg = "".join(
        f'<text x="{xf(h):.1f}" y="188" text-anchor="middle" '
        f'font-size="12" fill="var(--ink-soft)" font-family="var(--font-sans)">{lbl}</text>'
        for h, lbl in ticks.items()
    )

    return f"""<svg class="chart" viewBox="0 0 700 200" role="img"
     aria-label="Hourly temperature for today, evening window highlighted">
  <rect x="{band_x:.1f}" y="{ytop:.1f}" width="{band_w:.1f}" height="{ybot - ytop:.1f}"
        fill="var(--accent-soft)" rx="6"></rect>
  <path d="{area_d}" fill="var(--accent-soft)"></path>
  <path d="{line_d}" fill="none" stroke="var(--accent)" stroke-width="2.5"
        stroke-linejoin="round" stroke-linecap="round"></path>
  <line x1="{nx:.1f}" y1="{ytop:.1f}" x2="{nx:.1f}" y2="{ybot:.1f}"
        stroke="var(--ink-soft)" stroke-width="1" stroke-dasharray="2 3" opacity="0.5"></line>
  <circle cx="{nx:.1f}" cy="{ny:.1f}" r="5" fill="var(--accent)"
          stroke="var(--surface)" stroke-width="2.5"></circle>
  {tick_svg}
</svg>"""


def render_dashboard(data: dict, email_count, generated_at: datetime = None) -> str:
    if generated_at is None:
        generated_at = datetime.now()
    kind, vlabel, vhead, vsub = _verdict(data)
    temps = [h["temp"] for h in data["hourly"]]
    high, low = max(temps), min(temps)
    # %-d isn't portable (Windows), so build the day number manually
    eyebrow = generated_at.strftime("%A · %B ") + str(generated_at.day)
    updated = _twelve_hour(generated_at)

    markup = f"""
<div class="page">
  <main class="board">
    <header>
      <p class="eyebrow">{eyebrow.upper()}</p>
      <h1 class="greeting">Good morning, Danish</h1>
      <p class="place">{data['location']}</p>
    </header>

    <section class="now">
      <span class="now-emoji">{data['current_emoji']}</span>
      <div>
        <div class="now-deg">{data['current_temp']}°</div>
        <p class="now-desc">{data['current_desc'].capitalize()} right now</p>
      </div>
    </section>

    <section class="verdict verdict--{kind}">
      <p class="verdict-label">{vlabel}</p>
      <p class="verdict-headline">{vhead}</p>
      <p class="verdict-sub">{vsub}</p>
    </section>

    <section class="stats">
      <div class="stat"><span class="stat-k">Evening</span><span class="stat-v">{data['evening_temp']}°</span></div>
      <div class="stat"><span class="stat-k">Rain</span><span class="stat-v">{data['evening_precip']}%</span></div>
      <div class="stat"><span class="stat-k">Wind</span><span class="stat-v">{data['evening_wind']} mph</span></div>
      <div class="stat"><span class="stat-k">Sunset</span><span class="stat-v">{data['sunset_time'].replace(' ', '')}</span></div>
    </section>

    <section class="card">
      <div class="card-head">
        <h2 class="card-title">Today's temperature</h2>
        <span class="card-note">High {high}° · Low {low}°</span>
      </div>
      {_chart_svg(data['hourly'], generated_at.hour)}
    </section>

    <section class="card inbox">
      <div>
        <p class="inbox-k">Inbox today</p>
        <p class="inbox-sub">emails since midnight</p>
      </div>
      <p class="inbox-v">{email_count}</p>
    </section>

    <p class="foot">Updated automatically at <b>{updated}</b><br>refreshes every morning · Monroe Township, NJ</p>
  </main>
</div>
"""
    return STYLE + markup


def build_page(data: dict, email_count, generated_at: datetime = None) -> str:
    """Full standalone HTML document for GitHub Pages."""
    inner = render_dashboard(data, email_count, generated_at)
    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>Danish's Daily Update</title>\n"
        "</head>\n<body>\n" + inner + "\n</body>\n</html>\n"
    )
