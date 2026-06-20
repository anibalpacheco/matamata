#!/usr/bin/env bash
#
# Regenerate the committed doc assets (docs/*.png + the apply_results fixtures).
# Driven by the Makefile (`make png`, `png-hosts`, `png-tables`, `png-apply`, `assets`)
# but runnable directly: scripts/regen-docs.sh {cli|hosts|tables|apply|all}
#
# These recipes are transcribed from CLAUDE.md's "Maintaining examples and README images"
# section and carry its gotchas, so keep the two in sync:
#   - host renders that embed RELATIVE crest/flag paths must run from inside examples/,
#     or rsvg-convert silently drops the images;
#   - each firefox screenshot needs a FRESH profile, or the second one silently no-ops
#     and you get a stale PNG with no git diff.

set -euo pipefail

cd "$(dirname "$0")/.."                       # repo root, wherever we were invoked from

# Local machine config (VENV) lives in .env, shared with the Makefile. When invoked via
# make, the venv is already on PATH; sourcing here keeps a direct run working too.
[ -f .env ] && . ./.env
[ -n "${VENV:-}" ] && export PATH="$VENV:$PATH"

# Base-loader examples rendered straight through the CLI (no host, no images).
cli() {
  for n in knockout-8 symmetric-8 third-place facup-drawn facup-pending-draw; do
    PYTHONPATH=src python -m matamata "examples/$n.json" -o "/tmp/$n.svg"
    rsvg-convert -z 2 "/tmp/$n.svg" -o "docs/$n.png"
  done
}

# Host-rendered SVG previews. libertadores embeds no images, so it renders from root;
# world-cup/copa-rio embed relative flags/crests paths, so they render from examples/.
hosts() {
  PYTHONPATH=src python examples/libertadores_host.py > /tmp/libertadores.svg
  rsvg-convert -z 2 /tmp/libertadores.svg -o docs/libertadores-2026.png
  (
    cd examples
    PYTHONPATH=../src python world_cup_2022_host.py > _w.svg
    PYTHONPATH=../src python copa_rio_host.py        > _c.svg
    rsvg-convert -z 2 _w.svg -o ../docs/world-cup-2022.png
    rsvg-convert -z 2 _c.svg -o ../docs/copa-rio-de-la-plata.png
    rm -f _w.svg _c.svg
  )
}

# HTML-table screenshots (firefox headless). A fresh profile per shot is mandatory.
tables() {
  (
    cd examples
    shot() {  # shot OUT WxH SRC  — fresh profile, fixed window (not trimmed)
      local p; p=$(mktemp -d)
      firefox --headless --no-remote --profile "$p" \
        --window-size "$2" --screenshot "$PWD/$1" "file://$PWD/$3" >/dev/null 2>&1
      rm -rf "$p"
    }

    PYTHONPATH=../src python copa_rio_host.py html > _c.html
    shot ../docs/copa-rio-de-la-plata-table.png 480,320 _c.html
    rm -f _c.html

    # knockout-8 table, light + forced-dark (rsvg can't honor the @media query).
    PYTHONPATH=../src python - <<'PY'
from matamata import load_stage, render_html
frag = render_html(load_stage("knockout-8.json"))
dark = frag.replace("@media (prefers-color-scheme: dark)", "@media all")
wrap = lambda bg, body: f"<!doctype html><html><head><meta charset='utf-8'><style>html,body{{margin:0;padding:0;background:{bg};}}</style></head><body>{body}</body></html>"
open("_light.html", "w").write(wrap("#ffffff", frag))
open("_dark.html", "w").write(wrap("#0f172a", dark))
PY
    shot /tmp/light.png 480,800 _light.html
    shot /tmp/dark.png  480,800 _dark.html
    # trim, then re-add a symmetric border in each scheme's background color.
    magick /tmp/light.png -bordercolor '#ffffff' -border 2 -fuzz 1% -trim +repage \
      -bordercolor '#ffffff' -border 20 ../docs/knockout-8-table.png
    magick /tmp/dark.png  -bordercolor '#0f172a' -border 2 -fuzz 1% -trim +repage \
      -bordercolor '#0f172a' -border 20 ../docs/knockout-8-table-dark.png
    rm -f _light.html _dark.html
  )
}

# The apply_results walkthrough: regenerate docs/apply-after.json from -before.json
# (never hand-edited), then render both previews.
apply() {
  PYTHONPATH=src python - <<'PY'
import json
from matamata import KnockoutStage

with open("docs/apply-before.json", encoding="utf-8") as fh:
    doc = json.load(fh)
out = KnockoutStage(doc).apply_results(
    {"id": "sf1", "leg": 2, "goals1": 0, "goals2": 1, "pen1": 4, "pen2": 2}
)
with open("docs/apply-after.json", "w", encoding="utf-8") as fh:
    json.dump(out, fh, indent=2, ensure_ascii=False)
    fh.write("\n")
PY
  PYTHONPATH=src python -m matamata docs/apply-before.json -o /tmp/apply-before.svg
  PYTHONPATH=src python -m matamata docs/apply-after.json  -o /tmp/apply-after.svg
  rsvg-convert -z 2 /tmp/apply-before.svg -o docs/apply-before.png
  rsvg-convert -z 2 /tmp/apply-after.svg  -o docs/apply-after.png
}

case "${1:-all}" in
  cli)    cli ;;
  hosts)  hosts ;;
  tables) tables ;;
  apply)  apply ;;
  all)    cli; hosts; tables; apply ;;
  *) echo "usage: $0 {cli|hosts|tables|apply|all}" >&2; exit 1 ;;
esac
