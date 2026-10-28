#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
for file in minimal files deep; do
    printf 'ls -al /\nexit\n' | sh run.sh --vfs "examples/$file.csv" --prompt '{vfs}:{cwd}> '
done
sh run.sh --vfs examples/deep.csv --script examples/stage3.txt --no-repl && exit 1
exit 0
