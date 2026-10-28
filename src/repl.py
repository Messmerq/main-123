"""Stage 1: minimal command loop and whitespace parser."""


MAX_CD_ARGUMENTS = 1


def parse(line):
    """Split input by whitespace; quoting is intentionally unsupported."""
    return line.split()


def prototype(line):
    """Return a stub command result or raise a user-facing error."""
    parts = parse(line)
    if not parts:
        return ""
    command, *args = parts
    if command not in {"ls", "cd", "exit"}:
        raise ValueError(f"{command}: неизвестная команда")
    if command == "exit":
        if args:
            raise ValueError("exit: аргументы не поддерживаются")
        raise EOFError
    if command == "cd" and len(args) > MAX_CD_ARGUMENTS:
        raise ValueError("cd: ожидается не более одного пути")
    return f"{command}: {args}"


def main():
    """Run the initial interactive prototype until exit or EOF."""
    while True:
        try:
            print(prototype(input("prototype-vfs:/$ ")))
        except (EOFError, KeyboardInterrupt):
            print()
            return
        except ValueError as error:
            print(f"Ошибка: {error}")


if __name__ == "__main__":
    main()
