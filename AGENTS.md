# Invoice system

Markdown-based invoices rendered to styled HTML (print to PDF via browser).

## Commands

- `./invoice new "Client Name"` - scaffold `invoices/<YYYY>-<NNN>-<slug>.md` (auto-increments number)
- `./invoice build [file|number|slug ...]` - render to `dist/*.html` (all invoices if no args)
- `./invoice build --open` - render and open in browser
- `./invoice themes` - list color themes

## Files

- `invoices/*.md` - invoice source: YAML front matter (`invoice`, `date`, `due`, `client`, `items`, optional `theme`) + markdown body
- `themes/*.yaml` - color schemes (accent, accent_text, secondary, panel_bg, text, muted, border)
- `config.yaml` - business name/address/phone/email, `default_theme`, footer (gitignored, personal)
- `config.example.yaml` - sanitized config template; copy to `config.yaml` after cloning
- `templates/invoice.md` - scaffold for `new`
- `build.py` - renderer; run via `./invoice` (uses `.venv/`)

## Per-item fields

`description`, `qty` (default 1), `rate`, `amount` (default qty×rate), `note` (small line under description).
