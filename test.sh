#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)

cd "$SCRIPT_DIR"

rm -rf /tmp/something-??-??? /tmp/idk-??-??? /tmp/program-??-???

python3 -m cmakestrap --std 20 --git "/tmp/something-20-exe"
python3 -m cmakestrap --std 20 --git "/tmp/something-20-mod" --mod
python3 -m cmakestrap --std 20 --git "/tmp/something-20-lib" --lib
python3 -m cmakestrap --std 23 --git "/tmp/something-23-exe"
python3 -m cmakestrap --std 23 --git "/tmp/something-23-mod" --mod
python3 -m cmakestrap --std 23 --git "/tmp/something-23-lib" --lib

python3 -m cmakestrap --name idk --std 20 --git "/tmp/idk-20-exe"
python3 -m cmakestrap --name idk --std 20 --git "/tmp/idk-20-mod" --mod
python3 -m cmakestrap --name idk --std 20 --git "/tmp/idk-20-lib" --lib
python3 -m cmakestrap --name idk --std 23 --git "/tmp/idk-23-exe"
python3 -m cmakestrap --name idk --std 23 --git "/tmp/idk-23-mod" --mod
python3 -m cmakestrap --name idk --std 23 --git "/tmp/idk-23-lib" --lib

python3 -m cmakestrap --main --std 20 --git "/tmp/program-20-exe"
python3 -m cmakestrap --main --std 20 --git "/tmp/program-20-mod" --mod
python3 -m cmakestrap --main --std 20 --git "/tmp/program-20-lib" --lib
python3 -m cmakestrap --main --std 23 --git "/tmp/program-23-exe"
python3 -m cmakestrap --main --std 23 --git "/tmp/program-23-mod" --mod
python3 -m cmakestrap --main --std 23 --git "/tmp/program-23-lib" --lib

# rm -rf /tmp/something-??-??? /tmp/idk-??-??? /tmp/program-??-???
