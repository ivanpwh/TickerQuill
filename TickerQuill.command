#!/bin/bash
# TickerQuill for macOS: double-click this file in Finder to start the app.
# The first time, it also installs TickerQuill into .venv and makes ~/Applications/TickerQuill.app.
# Needs Python 3.10 or newer with Tk (python.org installer, or Homebrew python + python-tk), or uv.
cd "$(dirname "$0")" || exit 1

fail() {
    echo "$1"
    read -r -p "Press Return to close."
    exit 1
}

if [ ! -x .venv/bin/tickerquill ]; then
    echo "Setting up TickerQuill for the first time. This can take a few minutes; keep this window open."
    if python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; then
        python3 -m venv .venv && .venv/bin/python -m pip install --upgrade pip \
            && .venv/bin/python -m pip install -r requirements.txt \
            || fail "Installing the dependencies failed; see the messages above. Delete .venv to start over."
    elif command -v uv >/dev/null 2>&1; then
        uv venv --python ">=3.10" .venv && uv pip install --python .venv/bin/python -r requirements.txt \
            || fail "Installing the dependencies failed; see the messages above. Delete .venv to start over."
    else
        fail "Python 3.10 or newer was not found. Install it from https://www.python.org/downloads/ and open this file again."
    fi
    .venv/bin/python -m tickerquill --shortcut
    echo "Done. Next time you can also open TickerQuill from Applications, Launchpad or Spotlight."
fi

# Start the app on its own so this Terminal window can be closed.
nohup .venv/bin/python -m tickerquill >/dev/null 2>&1 &
exit 0
