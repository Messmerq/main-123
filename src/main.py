"""CLI configuration, startup script execution and interactive REPL."""

import sys

from config import arguments, run_script
from shell import Shell
from vfs import Vfs


def repl(shell):
    """Read interactive commands without invoking the real OS shell."""
    while not shell.exited:
        try:
            result = shell.execute(input(shell.prompt()))
            if result:
                print(result)
        except (EOFError, KeyboardInterrupt):
            print()
            break
        except (ValueError, OSError) as error:
            print(f"Ошибка: {error}")


def main(argv=None):
    """Load VFS, print configuration, run startup script, then REPL."""
    options = arguments(argv)
    print(f"vfs={options.vfs!r}; prompt={options.prompt!r}; "
          f"script={str(options.script)!r}; no_repl={options.no_repl}")
    try:
        shell = Shell(Vfs.load(options.vfs), options.prompt)
        failed = run_script(shell, options.script) if options.script else False
        if not options.no_repl and not shell.exited:
            repl(shell)
        return int(failed)
    except (ValueError, OSError, UnicodeError) as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
