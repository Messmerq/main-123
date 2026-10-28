"""Variant 17 command dispatch and UNIX-like command semantics."""

import getpass
import posixpath

from repl import parse

DEFAULT_LINES = 10
MIN_LINES = 0
MAX_SINGLE_ARGUMENT = 1


class Shell:
    """Execute commands against a VFS and keep the working directory."""

    def __init__(self, vfs, prompt="{vfs}:{cwd}$ "):
        """Bind a filesystem and validate the configurable prompt."""
        self.vfs = vfs
        self.cwd = "/"
        self.exited = False
        self.template = prompt
        self.prompt()

    def prompt(self):
        """Format the prompt, always including the VFS name."""
        try:
            text = self.template.format(vfs=self.vfs.name, cwd=self.cwd)
        except (KeyError, ValueError, IndexError, AttributeError) as error:
            message = "prompt: разрешены только {vfs} и {cwd}"
            raise ValueError(message) from error
        if self.vfs.name not in text:
            text = f"[{self.vfs.name}] {text}"
        return text

    def execute(self, line):
        """Parse whitespace-separated tokens after removing # comments."""
        parts = parse(line.split("#", 1)[0])
        if not parts:
            return ""
        command, *args = parts
        handlers = {
            "ls": self.ls, "cd": self.cd, "head": self.head,
            "whoami": self.whoami, "touch": self.touch,
            "exit": self.exit,
        }
        if command not in handlers:
            raise ValueError(f"{command}: неизвестная команда")
        return handlers[command](args)

    def ls(self, args):
        """List paths; -a includes hidden names and -l shows byte sizes."""
        options, paths = self.ls_arguments(args)
        lines = []
        for name in paths:
            if len(paths) > MAX_SINGLE_ARGUMENT:
                lines.append(f"{name}:")
            lines.extend(self.list_path(name, options))
        return "\n".join(lines)

    def ls_arguments(self, args):
        """Validate supported ls switches and separate operands."""
        flags = {"-a", "-l", "-al", "-la"}
        options = [arg for arg in args if arg.startswith("-")]
        if any(arg not in flags for arg in options):
            raise ValueError("ls: допустимы -a и -l")
        paths = [arg for arg in args if arg not in options] or [self.cwd]
        return "".join(options), paths

    def list_path(self, name, options):
        """Format one ls operand and apply hidden-file filtering."""
        path = self.vfs.resolve(name, self.cwd)
        node = self.vfs.get(path)
        items = self.vfs.children(path) if node.kind == "dir" else [path]
        lines = []
        for item in items:
            label = posixpath.basename(item) or "/"
            if "a" in options or not label.startswith("."):
                lines.append(self.list_entry(item, label, "l" in options))
        return lines

    def list_entry(self, path, label, long_view):
        """Render a directory entry; length is measured in bytes."""
        node = self.vfs.get(path)
        suffix = "/" if node.kind == "dir" else ""
        if long_view:
            return f"{node.kind:4} {len(node.data):6} {label}{suffix}"
        return label + suffix

    def cd(self, args):
        """Change directory; no argument returns to the VFS root."""
        if len(args) > MAX_SINGLE_ARGUMENT:
            raise ValueError("cd: ожидается не более одного пути")
        path = self.vfs.resolve(args[0] if args else "/", self.cwd)
        self.vfs.directory(path)
        self.cwd = path
        return ""

    def head(self, args):
        """Show first ten lines, or -n COUNT lines, from virtual files."""
        count, args = self.head_arguments(args)
        output = []
        for name in args:
            path = self.vfs.resolve(name, self.cwd)
            node = self.vfs.get(path)
            if node.kind != "file":
                raise ValueError(f"{name}: является каталогом")
            text = node.data.decode("utf-8", errors="replace")
            if len(args) > MAX_SINGLE_ARGUMENT:
                output.append(f"==> {name} <==\n")
            output.append("".join(text.splitlines(keepends=True)[:count]))
        return "".join(output).rstrip("\n")

    @staticmethod
    def head_arguments(args):
        """Validate the optional nonnegative line count and file operands."""
        count = DEFAULT_LINES
        if args and args[0] == "-n":
            try:
                count = int(args[1])
            except (IndexError, ValueError) as error:
                raise ValueError("head: после -n нужно целое число") from error
            args = args[2:]
        if count < MIN_LINES or not args:
            raise ValueError("head: ожидаются [-n N] FILE..., N >= 0")
        if any(arg.startswith("-") for arg in args):
            raise ValueError("head: неизвестная опция")
        return count, args

    def whoami(self, args):
        """Return the actual host OS username."""
        self.no_arguments("whoami", args)
        return getpass.getuser()

    def touch(self, args):
        """Create/update one or more virtual files, without disk writes."""
        if not args or any(arg.startswith("-") for arg in args):
            raise ValueError("touch: ожидается FILE... без опций")
        for name in args:
            self.vfs.touch(self.vfs.resolve(name, self.cwd))
        return ""

    def exit(self, args):
        """Request termination of both script execution and REPL."""
        self.no_arguments("exit", args)
        self.exited = True
        return ""

    @staticmethod
    def no_arguments(command, args):
        """Reject unexpected positional arguments."""
        if args:
            raise ValueError(f"{command}: аргументы не поддерживаются")
