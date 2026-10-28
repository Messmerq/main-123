"""Functional and failure-path checks for all five development stages."""

import base64
import csv
import getpass
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from main import arguments, main, repl, run_script
from repl import parse, prototype
from shell import Shell
from vfs import Vfs


class EmulatorTests(unittest.TestCase):
    """Exercise a fresh filesystem per test, including disk immutability."""

    def setUp(self):
        """Create isolated CSV and command script fixtures."""
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "test.csv"
        self.rows = [
            ("/", "dir", ""), ("/docs", "dir", ""),
            ("/docs/sub", "dir", ""), ("/docs/sub/deep", "dir", ""),
            ("/.hidden", "file", ""),
            ("/docs/text", "file", self.encode("one\ntwo\nthree\n")),
            ("/binary", "file", self.encode_bytes(b"\x00\xff\x01")),
        ]
        self.write_csv(self.rows)
        self.vfs = Vfs.load(self.path)
        self.shell = Shell(self.vfs)

    @staticmethod
    def encode_bytes(value):
        """Encode raw binary content in the documented CSV format."""
        return base64.b64encode(value).decode("ascii")

    def encode(self, value):
        """Encode fixture text as UTF-8 followed by base64."""
        return self.encode_bytes(value.encode("utf-8"))

    def write_csv(self, rows):
        """Write only the physical input fixture, never runtime VFS data."""
        with self.path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(["path", "type", "data"])
            writer.writerows(rows)

    def test_stage_one_parser(self):
        """The assigned parser splits whitespace without interpreting quotes."""
        self.assertEqual(parse('ls  "a b"'), ["ls", '"a', 'b"'])
        self.assertEqual(prototype("ls a b"), "ls: ['a', 'b']")
        self.assertEqual(prototype("cd /"), "cd: ['/']")
        self.assertEqual(prototype("  "), "")
        for line in ("bad", "cd a b", "exit extra"):
            with self.subTest(line=line), self.assertRaises(ValueError):
                prototype(line)
        with self.assertRaises(EOFError):
            prototype("exit")

    def test_configuration(self):
        """All CLI parameters are parsed and printed at startup."""
        args = arguments(["--vfs", str(self.path), "--prompt", "X> ",
                          "--script", "demo.txt", "--no-repl"])
        self.assertEqual(args.prompt, "X> ")
        self.assertEqual(args.script, Path("demo.txt"))
        self.assertTrue(args.no_repl)
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["--vfs", str(self.path), "--no-repl"]), 0)
        for key in ("vfs=", "prompt=", "script=", "no_repl="):
            self.assertIn(key, output.getvalue())

    def test_prompt(self):
        """Default and custom prompts retain the VFS name."""
        self.assertIn("test:/", self.shell.prompt())
        self.assertEqual(Shell(self.vfs, "hello> ").prompt(), "[test] hello> ")
        with self.assertRaises(ValueError):
            Shell(self.vfs, "{unknown}")

    def test_vfs_load_order_and_binary(self):
        """Parent rows may follow children; binary bytes survive decoding."""
        self.write_csv(list(reversed(self.rows)))
        loaded = Vfs.load(self.path)
        self.assertEqual(loaded.get("/binary").data, b"\x00\xff\x01")
        self.assertEqual(loaded.get("/docs/sub/deep").kind, "dir")

    def test_invalid_csv(self):
        """Reject malformed paths, types, base64, duplicates and parents."""
        bad_rows = [
            [("relative", "file", "")], [("/a/../b", "file", "")],
            [("//a", "file", "")], [("/a", "link", "")],
            [("/a", "dir", "eA==")], [("/", "file", "")],
            [("/a", "file", "@@")],
            [("/a", "file", ""), ("/a", "file", "")],
            [("/missing/child", "file", "")],
            [("/a", "file", ""), ("/a/child", "file", "")],
        ]
        for rows in bad_rows:
            with self.subTest(rows=rows):
                self.write_csv(rows)
                with self.assertRaises(ValueError):
                    Vfs.load(self.path)

    def test_bad_header_and_missing_file(self):
        """Loading failures are explicit and do not silently create a VFS."""
        self.path.write_text("wrong,header\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            Vfs.load(self.path)
        with self.assertRaises(FileNotFoundError):
            Vfs.load(self.path.with_name("absent.csv"))

    def test_ls(self):
        """Cover default, hidden, detailed, file and multiple path listings."""
        self.assertNotIn(".hidden", self.shell.execute("ls"))
        self.assertIn(".hidden", self.shell.execute("ls -a"))
        self.assertIn("file", self.shell.execute("ls -l /binary"))
        self.assertIn("docs/", self.shell.execute("ls -la"))
        self.assertIn("/docs:", self.shell.execute("ls /docs /binary"))
        for line in ("ls -z", "ls /missing"):
            with self.assertRaises(ValueError):
                self.shell.execute(line)

    def test_cd(self):
        """Relative/absolute navigation is confined to the virtual root."""
        self.shell.execute("cd /docs/sub/deep")
        self.shell.execute("cd ../..")
        self.assertEqual(self.shell.cwd, "/docs")
        self.shell.execute("cd ../../../../")
        self.assertEqual(self.shell.cwd, "/")
        self.shell.execute("cd /docs")
        self.shell.execute("cd")
        self.assertEqual(self.shell.cwd, "/")
        for line in ("cd a b", "cd /binary", "cd /missing"):
            with self.assertRaises(ValueError):
                self.shell.execute(line)

    def test_head(self):
        """Read whole/limited/zero lines, multiple files and binary input."""
        self.assertEqual(self.shell.execute("head /docs/text"),
                         "one\ntwo\nthree")
        self.assertEqual(self.shell.execute("head -n 1 /docs/text"), "one")
        self.assertEqual(self.shell.execute("head -n 0 /docs/text"), "")
        self.assertIn("==>", self.shell.execute("head /docs/text /binary"))
        self.assertIn("\ufffd", self.shell.execute("head /binary"))
        for line in ("head", "head -n", "head -n x /binary",
                     "head -n -1 /binary", "head /docs", "head -q /binary"):
            with self.subTest(line=line), self.assertRaises(ValueError):
                self.shell.execute(line)

    def test_whoami_and_errors(self):
        """Username comes from the host, with argument validation."""
        self.assertEqual(self.shell.execute("whoami"), getpass.getuser())
        self.assertEqual(self.shell.execute("# comment"), "")
        for line in ("whoami extra", "unknown", "exit extra"):
            with self.assertRaises(ValueError):
                self.shell.execute(line)

    def test_touch_memory_only(self):
        """Create/update files while physical CSV remains byte-identical."""
        before = self.path.read_bytes()
        self.shell.execute("touch /new /docs/second")
        self.assertEqual(self.vfs.get("/new").data, b"")
        self.vfs.get("/docs/text").modified = 0
        self.shell.execute("touch /docs/text")
        self.assertGreater(self.vfs.get("/docs/text").modified, 0)
        self.assertEqual(self.vfs.get("/docs/text").data, b"one\ntwo\nthree\n")
        self.assertEqual(self.path.read_bytes(), before)
        self.assertNotIn("/new", Vfs.load(self.path).nodes)
        for line in ("touch", "touch -a /new", "touch /absent/file"):
            with self.assertRaises(ValueError):
                self.shell.execute(line)

    def test_script_comments_errors_and_exit(self):
        """Echo input, continue after an error and stop immediately on exit."""
        path = Path(self.temp.name) / "start.txt"
        path.write_text("# hi\nunknown\ntouch /ok # inline\nexit\n"
                        "touch /never\n", encoding="utf-8")
        output = []
        self.assertTrue(run_script(self.shell, path, output.append))
        self.assertIn("/ok", self.vfs.nodes)
        self.assertNotIn("/never", self.vfs.nodes)
        self.assertTrue(self.shell.exited)
        self.assertTrue(any(":2:" in line for line in output))
        self.assertTrue(any("# hi" in line for line in output))

    def test_interactive_repl(self):
        """Simulate a real interactive session with recovery from errors."""
        output = io.StringIO()
        lines = ["unknown", "touch /interactive", "ls", "exit"]
        with patch("builtins.input", side_effect=lines):
            with redirect_stdout(output):
                repl(self.shell)
        self.assertIn("interactive", output.getvalue())
        self.assertIn("Ошибка", output.getvalue())
        self.assertTrue(self.shell.exited)


if __name__ == "__main__":
    unittest.main()
