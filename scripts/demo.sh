#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
sh run.sh --vfs examples/deep.csv --prompt '{vfs}:{cwd}$ ' --script examples/stage4.txt --no-repl && exit 1
sh run.sh --vfs examples/deep.csv --prompt 'demo> ' --script examples/stage5.txt --no-repl && exit 1
exit 0
