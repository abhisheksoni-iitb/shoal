#!/bin/bash
# Install the Shoal skill and its engine for Claude Code (and, with --all, other agents
# that read ~/.agents/skills or ~/.factory/skills). Re-run after changing anything here.
set -euo pipefail
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGETS=("$HOME/.claude/skills")
if [[ "${1:-}" == "--all" ]]; then
  for d in "$HOME/.agents/skills" "$HOME/.factory/skills"; do [[ -d "$d" ]] && TARGETS+=("$d"); done
fi
for base in "${TARGETS[@]}"; do
  dest="$base/shoal"
  mkdir -p "$dest/scripts" "$dest/references" "$dest/examples"
  cp "$SRC/skill/shoal/SKILL.md" "$dest/SKILL.md"
  cp "$SRC/skill/shoal/references/"*.md "$dest/references/"
  rm -rf "$dest/scripts/shoal"
  mkdir -p "$dest/scripts/shoal"
  cp "$SRC/shoal/"*.py "$SRC/shoal/template.json" "$dest/scripts/shoal/"
  cp "$SRC/examples/one-tap-reorder/feature.json" "$dest/examples/one-tap-reorder.feature.json"
  cp "$SRC/examples/one-tap-reorder/spec.md" "$dest/examples/one-tap-reorder.spec.md"
  cat > "$dest/scripts/shoal.sh" <<'LAUNCH'
#!/bin/bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$DIR${PYTHONPATH:+:$PYTHONPATH}" exec python3 -m shoal "$@"
LAUNCH
  chmod +x "$dest/scripts/shoal.sh"
  echo "Installed: $dest"
done
