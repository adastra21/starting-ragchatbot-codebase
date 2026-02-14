#\!/bin/bash
set -e

cd "$(dirname "$0")/.."

TARGETS="backend/ main.py"

if [ "$1" = "--fix" ]; then
    echo "==> Running black (auto-format)..."
    uv run black $TARGETS
else
    echo "==> Checking formatting with black..."
    uv run black --check $TARGETS
fi

echo ""
echo "All quality checks passed."
