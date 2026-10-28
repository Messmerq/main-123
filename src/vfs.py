"""CSV-backed virtual filesystem; all runtime modifications stay in RAM."""

import base64
import binascii
import csv
import io
import posixpath
import time
from dataclasses import dataclass, field
from pathlib import Path

FIELDS = ["path", "type", "data"]
ROOT = "/"


@dataclass
class Node:
    """A directory or a byte-oriented file with a modification timestamp."""

    kind: str
    data: bytes = b""
    modified: float = field(default_factory=time.time)


class Vfs:
    """Store canonical absolute POSIX paths independently of the host OS."""

    def __init__(self, name="memory"):
        """Create the implicit root directory."""
        self.name = name
        self.nodes = {ROOT: Node("dir")}

    @classmethod
    def load(cls, filename):
        """Load and validate a UTF-8 CSV without extracting any files."""
        path = Path(filename)
        text = path.read_text(encoding="utf-8-sig")
        vfs = cls(path.stem)
        seen = set()
        try:
            reader = csv.DictReader(io.StringIO(text), strict=True)
            if reader.fieldnames != FIELDS:
                raise ValueError("CSV: ожидаются столбцы path,type,data")
            for row in reader:
                vfs.add_row(row, seen)
            vfs.validate_parents()
        except (csv.Error, binascii.Error, TypeError) as error:
            raise ValueError(f"CSV: неверный формат: {error}") from error
        return vfs

    def add_row(self, row, seen):
        """Validate one CSV row and decode file contents from base64."""
        if set(row) != set(FIELDS) or None in row.values():
            raise ValueError("CSV: неверное количество полей")
        path, kind, data = (row[key] for key in FIELDS)
        if not path.startswith(ROOT) or "\x00" in path:
            raise ValueError("CSV: путь должен быть абсолютным")
        if self.resolve(path) != path or path.startswith("//"):
            raise ValueError(f"CSV: неканонический путь {path}")
        if path in seen:
            raise ValueError(f"CSV: дубликат пути {path}")
        if kind not in {"file", "dir"}:
            raise ValueError(f"CSV: неизвестный тип {kind}")
        if kind == "dir" and data:
            raise ValueError("CSV: каталог не может содержать данные")
        if path == ROOT and kind != "dir":
            raise ValueError("CSV: корень должен быть каталогом")
        self.nodes[path] = Node(kind, base64.b64decode(data, validate=True))
        seen.add(path)

    def validate_parents(self):
        """Require an explicit directory parent, regardless of row order."""
        for path in self.nodes:
            if path != ROOT:
                self.directory(posixpath.dirname(path))

    def resolve(self, path, cwd=ROOT):
        """Resolve absolute/relative paths and clamp .. at virtual root."""
        return ROOT + posixpath.normpath(
            posixpath.join(cwd, path)
        ).lstrip(ROOT)

    def get(self, path):
        """Return a node or report a missing virtual path."""
        if path not in self.nodes:
            raise ValueError(f"{path}: путь не найден")
        return self.nodes[path]

    def directory(self, path):
        """Return a directory node or report a type error."""
        node = self.get(path)
        if node.kind != "dir":
            raise ValueError(f"{path}: не является каталогом")
        return node

    def children(self, path):
        """List direct children in deterministic name order."""
        self.directory(path)
        return sorted(
            item for item in self.nodes
            if item != ROOT and posixpath.dirname(item) == path
        )

    def touch(self, path):
        """Create an empty file or refresh a timestamp, only in memory."""
        if path in self.nodes:
            self.nodes[path].modified = time.time()
        else:
            self.directory(posixpath.dirname(path))
            self.nodes[path] = Node("file")
