"""Stage 2: configurable prototype independent of the VFS implementation."""

import argparse
import sys
from pathlib import Path

from repl import prototype


def arguments(argv=None):
    """Read the physical VFS path, custom prompt and startup script."""
    parser = argparse.ArgumentParser(description="Эмулятор UNIX, вариант 17")
    parser.add_argument("--vfs", default="examples/deep.csv")
    parser.add_argument("--prompt", default="{vfs}:{cwd}$ ")
    parser.add_argument("--script", type=Path)
    parser.add_argument("--no-repl", action="store_true")
    return parser.parse_args(argv)


def run_script(shell, path, output=print):
    """Echo every line, support # comments and continue after errors."""
    failed = False
    lines = path.read_text(encoding="utf-8").splitlines()
    for number, line in enumerate(lines, 1):
        output(shell.prompt() + line)
        try:
            result = shell.execute(line)
            if result:
                output(result)
        except (ValueError, OSError) as error:
            output(f"{path}:{number}: Ошибка: {error}")
            failed = True
        if shell.exited:
            break
    return failed


class PrototypeShell:
    """Keep stage 1 stubs runnable with the stage 2 configuration."""

    def __init__(self, options):
        """Retain the user-specified prompt and VFS display name."""
        self.name = Path(options.vfs).stem
        self.template = options.prompt
        self.exited = False

    def prompt(self):
        """Include the VFS name in the configured prompt."""
        value = self.template.format(vfs=self.name, cwd="/")
        return value if self.name in value else f"[{self.name}] {value}"

    def execute(self, line):
        """Run a stub command, ignoring Python-style comments."""
        try:
            return prototype(line.split("#", 1)[0])
        except EOFError:
            self.exited = True
            return ""


def main(argv=None):
    """Demonstrate configuration before attaching a real VFS."""
    options = arguments(argv)
    print(vars(options))
    shell = PrototypeShell(options)
    try:
        failed = run_script(shell, options.script) if options.script else False
        while not options.no_repl and not shell.exited:
            try:
                print(shell.execute(input(shell.prompt())))
            except ValueError as error:
                print(f"Ошибка: {error}")
        return int(failed)
    except (EOFError, KeyboardInterrupt):
        return 0
    except (ValueError, OSError, UnicodeError) as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
