#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
sh run.sh --vfs examples/minimal.csv --prompt 'demo> ' --no-repl
sh run.sh --vfs examples/deep.csv --prompt '{vfs}:{cwd}> ' --script examples/stage2.txt --no-repl && exit 1
sh run.sh --vfs examples/missing.csv --no-repl && exit 1
exit 0
