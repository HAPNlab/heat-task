# heat-task dev tasks. Run `just` to list recipes.
# Requires `just` (https://github.com/casey/just): `brew install just`.

# Show available recipes
default:
    @just --list

# Install/refresh the venv (--inexact keeps the manual psychtoolbox install)
sync:
    uv sync --inexact

# Run the task (locked PyPI core)
run *args:
    uv run heat-task {{args}}

# Talk to the thermode via the vendored medoc CLI
medoc *args:
    uv run medoc {{args}}

# Run the test suite
test *args:
    uv run pytest {{args}}

# --- Co-developing psyexp-core from ../psyexp-core ---------------------------
# Two overlays, two rules:
#   * psychtoolbox (NOT in the lock) -> kept by `uv sync --inexact`
#   * editable psyexp-core (IN the lock) -> only kept by skipping the sync;
#     `--inexact` does NOT save it.
# Co-development runs with --no-sync, which preserves both at once.

# Overlay an editable sibling checkout of ../psyexp-core
core-dev:
    uv pip install -e ../psyexp-core
    @echo "Editable psyexp-core overlaid. Use 'just core-run' / 'just core-test' so it isn't reverted."

# Run the task against the editable overlay (no sync; keeps core + psychtoolbox)
core-run *args:
    uv run --no-sync heat-task {{args}}

# Run the tests against the editable overlay
core-test *args:
    uv run --no-sync pytest {{args}}

# Drop the editable core, restore the locked PyPI version (keeps psychtoolbox)
core-release:
    uv sync --inexact

# Upgrade to the newest published psyexp-core and update the lock
core-upgrade:
    uv lock --upgrade-package psyexp-core
    uv sync --inexact
