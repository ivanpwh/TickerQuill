#!/bin/sh
# TickerQuill for Linux: run ./tickerquill.sh (or double-click it and choose "Run").
# The first time, it also installs TickerQuill into .venv and adds it to the app menu.
# Needs Python 3.10 or newer with Tk and venv (Debian/Ubuntu: sudo apt install python3-tk python3-venv), or uv.
cd "$(dirname "$0")" || exit 1

fail() {
    echo "$1"
    exit 1
}

if [ ! -x .venv/bin/tickerquill ]; then
    echo "Setting up TickerQuill for the first time. This can take a few minutes."
    if python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; then
        python3 -m venv .venv && .venv/bin/python -m pip install --upgrade pip \
            && .venv/bin/python -m pip install -r requirements.txt \
            || fail "Installing the dependencies failed; see the messages above. Delete .venv to start over."
    elif command -v uv >/dev/null 2>&1; then
        uv venv --python ">=3.10" .venv && uv pip install --python .venv/bin/python -r requirements.txt \
            || fail "Installing the dependencies failed; see the messages above. Delete .venv to start over."
    else
        fail "Python 3.10 or newer was not found (Debian/Ubuntu: sudo apt install python3 python3-venv python3-tk)."
    fi
    .venv/bin/python -m tickerquill --shortcut
    echo "Done. Next time you can also start TickerQuill from the app menu."
fi

exec .venv/bin/python -m tickerquill "$@"
