#!/usr/bin/env python3
"""Markdown-based invoice renderer.

Usage:
  ./invoice new "Client Name"     Scaffold a new invoice in invoices/
  ./invoice build [files...]      Render invoice(s) to dist/ (all, if none given)
  ./invoice build --open          Render all and open each in the browser
  ./invoice themes                List available color themes

Invoice files are Markdown with YAML front matter. See templates/invoice.md.
Colors come from themes/<name>.yaml; pick one per invoice with `theme:` in the
front matter, or set default_theme in config.yaml.
"""

import re
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from string import Template

import markdown
import yaml

ROOT = Path(__file__).resolve().parent
INVOICES_DIR = ROOT / "invoices"
THEMES_DIR = ROOT / "themes"
DIST_DIR = ROOT / "dist"
TEMPLATE_FILE = ROOT / "templates" / "invoice.md"
CONFIG_FILE = ROOT / "config.yaml"

HTML = Template("""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Invoice $invoice_number - $client_name</title>
<style>
  :root {
    --accent: $accent; --on-accent: $accent_text; --secondary: $secondary;
    --panel: $panel_bg; --text: $text; --muted: $muted; --border: $border;
  }
  * { box-sizing: border-box; margin: 0; }
  body {
    font-family: Georgia, 'Times New Roman', serif; color: var(--text);
    max-width: 8in; margin: 0 auto; padding: 0.5in;
    background: #fff; font-size: 11pt; line-height: 1.45;
    -webkit-print-color-adjust: exact; print-color-adjust: exact;
  }
  header {
    display: flex; justify-content: space-between; align-items: flex-start;
    gap: 2em; padding-bottom: .7em;
    border-bottom: 4px solid var(--accent);
    box-shadow: 0 5px 0 -3px var(--secondary);
  }
  .biz h1 { color: var(--accent); font-size: 1.8em; letter-spacing: .02em; }
  .contact { color: var(--muted); font-size: .85em; margin-top: .45em; }
  .meta { text-align: right; white-space: nowrap; }
  .inv-title { font-size: 1.55em; font-weight: bold; letter-spacing: .14em;
               color: var(--secondary); }
  .inv-no { font-size: 1.05em; color: var(--accent); font-weight: bold;
            margin-top: .1em; }
  .dates { margin: .55em 0 0 auto; border-collapse: collapse; font-size: .9em; }
  .dates td { padding: .1em .35em; }
  .dates td:first-child { color: var(--muted); text-align: right; }
  .billto {
    margin: 1.3em 0 0; background: var(--panel);
    border-left: 4px solid var(--secondary); padding: .8em 1em;
    display: inline-block; min-width: 55%;
  }
  .billto h2 { font-size: .78em; text-transform: uppercase;
               letter-spacing: .16em; color: var(--muted); margin-bottom: .35em; }
  .client-name { font-weight: bold; font-size: 1.05em; }
  table.items { width: 100%; border-collapse: collapse; margin-top: 1.5em; }
  table.items th {
    background: var(--accent); color: var(--on-accent); text-align: left;
    padding: .55em .7em; font-size: .8em; letter-spacing: .08em;
    text-transform: uppercase;
  }
  table.items td { padding: .55em .7em; border-bottom: 1px solid var(--border);
                   vertical-align: top; }
  .num { text-align: right; white-space: nowrap; }
  .qty { text-align: center; }
  .item-note { color: var(--muted); font-size: .88em; margin-top: .15em; }
  tfoot td { border-bottom: none; }
  tr.total td {
    font-weight: bold; font-size: 1.2em; color: var(--accent);
    border-top: 2.5px solid var(--secondary); padding-top: .45em;
  }
  .body { margin-top: 1.7em; }
  .body h2 {
    color: var(--accent); font-size: 1em; text-transform: uppercase;
    letter-spacing: .1em; border-bottom: 1px solid var(--border);
    padding-bottom: .2em; margin: 1.1em 0 .5em;
  }
  .body h3 { color: var(--accent); font-size: .95em; margin: .9em 0 .4em; }
  .body p { margin: .5em 0; }
  .body ul, .body ol { padding-left: 1.4em; margin: .5em 0; }
  .body table { border-collapse: collapse; margin: .6em 0; }
  .body th, .body td { border: 1px solid var(--border); padding: .3em .6em; }
  .body th { background: var(--panel); }
  .body blockquote { border-left: 3px solid var(--secondary);
                     padding-left: .8em; color: var(--muted); margin: .6em 0; }
  footer {
    margin-top: 2.6em; padding-top: .8em; border-top: 1px solid var(--border);
    color: var(--muted); font-size: .82em; text-align: center;
  }
  @page { margin: 0.5in; }
  @media print { body { padding: 0; max-width: none; } }
</style>
</head>
<body>
<header>
  <div class="biz">
    <h1>$business_name</h1>
    <div class="contact">$business_contact</div>
  </div>
  <div class="meta">
    <div class="inv-title">INVOICE</div>
    <div class="inv-no">$invoice_number</div>
    <table class="dates">
      <tr><td>Date</td><td>$date</td></tr>
      <tr><td>Due</td><td>$due</td></tr>
    </table>
  </div>
</header>

<section class="billto">
  <h2>Bill To</h2>
  <div class="client-name">$client_name</div>
  <div>$client_details</div>
</section>

<table class="items">
  <thead>
    <tr><th>Description</th><th class="qty">Qty</th>
        <th class="num">Rate</th><th class="num">Amount</th></tr>
  </thead>
  <tbody>
$rows
  </tbody>
  <tfoot>
    <tr class="total"><td colspan="3">Total Due</td><td class="num">$total</td></tr>
  </tfoot>
</table>

<div class="body">
$body
</div>

<footer>$footer</footer>
</body>
</html>
""")


def load_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f)


def split_front_matter(text):
    """Return (front_matter_str, body_str)."""
    if text.lstrip().startswith("---"):
        parts = text.lstrip().split("---", 2)
        return parts[1], parts[2]
    return "", text


def md_inline(s):
    """Render markdown without the wrapping <p> tag."""
    html = markdown.markdown(str(s or "").strip()).strip()
    if html.startswith("<p>") and html.endswith("</p>"):
        html = html[3:-4].strip()
    return html


def md_block(s):
    return markdown.markdown(str(s or "").strip(), extensions=["tables"])


def money(x):
    return f"${x:,.2f}"


def fmt_qty(q):
    return str(int(q)) if float(q) == int(q) else str(q)


def fmt_date(value):
    if isinstance(value, (date, datetime)):
        d = value
    else:
        try:
            d = datetime.strptime(str(value), "%Y-%m-%d")
        except ValueError:
            return str(value)
    return d.strftime("%B %-d, %Y")


def load_theme(name, config):
    theme_file = THEMES_DIR / f"{name}.yaml"
    if not theme_file.exists():
        available = ", ".join(sorted(p.stem for p in THEMES_DIR.glob("*.yaml")))
        sys.exit(f"error: theme '{name}' not found. Available: {available}")
    return load_yaml(theme_file)


def render_invoice(path, config):
    text = path.read_text()
    front, body_src = split_front_matter(text)
    meta = yaml.safe_load(front) or {}
    if not meta.get("client", {}).get("name"):
        sys.exit(f"error: {path.name}: front matter needs client.name")
    if not meta.get("items"):
        sys.exit(f"error: {path.name}: front matter needs at least one item")

    theme = load_theme(meta.get("theme") or config["default_theme"], config)
    biz = config["business"]

    rows, total = [], 0.0
    for item in meta["items"]:
        qty = float(item.get("qty", 1))
        rate = float(item.get("rate", 0))
        amount = float(item.get("amount", qty * rate))
        total += amount
        desc = md_inline(item.get("description", ""))
        if item.get("note"):
            desc += f'<div class="item-note">{md_inline(item["note"])}</div>'
        rows.append(
            f'    <tr><td>{desc}</td><td class="qty">{fmt_qty(qty)}</td>'
            f'<td class="num">{money(rate)}</td>'
            f'<td class="num">{money(amount)}</td></tr>'
        )

    client = meta["client"]
    client_bits = []
    if client.get("attn"):
        client_bits.append(f"Attn: {md_inline(client['attn'])}")
    if client.get("address"):
        client_bits.append(md_inline(client["address"]).replace("\n", "<br>\n"))
    contact = "<br>\n".join(
        line for line in [
            md_inline(biz.get("address", "")).replace("\n", "<br>\n"),
            md_inline(biz.get("phone", "")),
            md_inline(biz.get("email", "")),
        ] if line
    )

    html = HTML.substitute(
        **theme,
        business_name=md_inline(biz.get("name", "")),
        business_contact=contact,
        invoice_number=meta.get("invoice", path.stem),
        date=fmt_date(meta.get("date", "")),
        due=fmt_date(meta.get("due", "")),
        client_name=md_inline(client["name"]),
        client_details="<br>\n".join(client_bits),
        rows="\n".join(rows),
        total=money(total),
        body=md_block(body_src),
        footer=md_inline(config.get("footer", "")),
    )

    DIST_DIR.mkdir(exist_ok=True)
    out = DIST_DIR / f"{path.stem}.html"
    out.write_text(html)
    return out


def cmd_new(client):
    """Scaffold invoices/<YYYY>-<NNN>-<client-slug>.md with the next number."""
    year, highest = date.today().year, 0
    for p in INVOICES_DIR.glob("*.md"):
        try:
            meta = yaml.safe_load(split_front_matter(p.read_text())[0]) or {}
        except yaml.YAMLError:
            continue
        m = re.match(rf"^{year}-(\d+)$", str(meta.get("invoice", "")))
        if m:
            highest = max(highest, int(m.group(1)))
    number = f"{year}-{highest + 1:03d}"
    slug = re.sub(r"[^a-z0-9]+", "-", client.lower()).strip("-") or "client"

    config = load_yaml(CONFIG_FILE)
    text = (TEMPLATE_FILE.read_text()
            .replace("{{NUMBER}}", number)
            .replace("{{DATE}}", str(date.today()))
            .replace("{{DUE}}", str(date.today() + timedelta(days=14)))
            .replace("{{CLIENT}}", client)
            .replace("{{BUSINESS}}", config["business"]["name"]))

    INVOICES_DIR.mkdir(exist_ok=True)
    path = INVOICES_DIR / f"{number}-{slug}.md"
    path.write_text(text)
    print(f"created {path.relative_to(ROOT)}")
    return path


def resolve(arg):
    """Turn a CLI arg into an invoice path (accepts number, slug, or filename)."""
    p = Path(arg)
    if p.exists():
        return p
    for candidate in [INVOICES_DIR / arg, INVOICES_DIR / f"{arg}.md"]:
        if candidate.exists():
            return candidate
    matches = list(INVOICES_DIR.glob(f"*{arg}*.md"))
    if len(matches) == 1:
        return matches[0]
    sys.exit(f"error: no invoice matching '{arg}'"
             + (f" (ambiguous: {', '.join(m.name for m in matches)})"
                if matches else ""))


def main():
    args = sys.argv[1:]
    open_after = "--open" in args
    args = [a for a in args if a != "--open"]

    if not args or args[0] in ("-h", "--help", "help"):
        print(__doc__)
        return

    cmd, rest = args[0], args[1:]
    if cmd == "new":
        if not rest:
            sys.exit('usage: ./invoice new "Client Name"')
        cmd_new(" ".join(rest))
    elif cmd == "themes":
        for p in sorted(THEMES_DIR.glob("*.yaml")):
            t = load_yaml(p)
            print(f"  {p.stem:<16} {t['name']:<24} accent {t['accent']}  "
                  f"secondary {t['secondary']}")
    elif cmd == "build":
        config = load_yaml(CONFIG_FILE)
        files = [resolve(a) for a in rest] if rest else sorted(
            INVOICES_DIR.glob("*.md"))
        if not files:
            sys.exit("no invoices found - create one with ./invoice new")
        for f in files:
            out = render_invoice(f, config)
            print(f"built {out.relative_to(ROOT)}")
            if open_after:
                subprocess.run(["open", str(out)])
    else:
        # allow `./invoice 2026-001` as shorthand for build
        config = load_yaml(CONFIG_FILE)
        out = render_invoice(resolve(cmd), config)
        print(f"built {out.relative_to(ROOT)}")
        if open_after:
            subprocess.run(["open", str(out)])


if __name__ == "__main__":
    main()
