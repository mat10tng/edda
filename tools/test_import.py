#!/usr/bin/env python3
"""The import contract (reference sections 9, 11 and 13, revisions 68
and 69).

    python3 tools/test_import.py

A project with no edda.yaml is read as before: spec folder specs, every
setting off. Each key of edda.yaml, valid and not; a pin older and newer
than the tools; a stack that disagrees with glossary.links; an edda.yaml
at the root and one in the spec folder; the old place still read. The
checker, the runner, approve (a dry run), the read view and trend take
the spec folder and the log from a project whose specs live elsewhere.
Every path the host gives (the spec folder, .edda, covers: and .links
paths), and every file a tool opens there (edda.yaml, .edda, .edda.vc,
.links, the default log), resolves inside the root or is refused
(outside_root); one linked inside is read; approve never writes outside;
covers: paths are relative to the root when the specs are nested; --root and a
named spec folder (or trend's --log) must name one root. The guide
regenerates to the same bytes and quotes decision X's sentence; the
pointer is one line, its guide path given for the host.
"""
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["EDDA_LOG"] = "off"     # the tools and their children never write the log (section 11)
import check                     # noqa: E402
import guide                     # noqa: E402
import settings                  # noqa: E402

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = check.ROOT
FIXTURE = os.path.join(ROOT, "fixtures", "blocks_approved")     # a story ready to approve
LINKED = os.path.join(ROOT, "fixtures", "approved")             # FIX-001 approved, its operation remove
REV = settings.REVISION
GLOSSARY = 'target: python\nrule: same_name\ncovers:\n  - "{}"\n'
MARKED = '# FIX-001@1\ndef remove(order):\n    order.status = "removed"\n'



class Host:
    """a host project in a temporary folder: root, its spec folder named
    specs, its files copied from FIXTURE"""

    def __init__(self, specs="specs", yaml=None, fixture=FIXTURE):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.join(self.tmp.name, "host")
        self.folder = os.path.join(self.root, specs)
        os.makedirs(self.folder)
        for name in os.listdir(fixture):
            shutil.copy(os.path.join(fixture, name), self.folder)
        if yaml is not None:
            self.write("edda.yaml", yaml)

    def write(self, name, text):
        os.makedirs(os.path.dirname(os.path.join(self.root, name)), exist_ok=True)
        with open(os.path.join(self.root, name), "w") as f:
            f.write(text)

    def away(self, name):
        """a folder outside the root, in the same temporary folder"""
        path = os.path.join(self.tmp.name, name)
        os.makedirs(path, exist_ok=True)
        return path

    def tool(self, name, *args, env=None):
        """(exit code, stdout, stderr) of a tool run in the host's root"""
        p = subprocess.run([sys.executable, os.path.join(TOOLS, name), *args], cwd=self.root,
                           capture_output=True, text=True, env=env or dict(os.environ, EDDA_LOG="off"))
        return p.returncode, p.stdout, p.stderr


class SettingsTest(unittest.TestCase):

    def setUp(self):
        self.host = Host()

    def tearDown(self):
        self.host.tmp.cleanup()

    def read(self, yaml, **kw):
        self.host.write("edda.yaml", yaml)
        return settings.read(self.host.root, **kw)

    def refused(self, yaml, code=1):
        with self.assertRaises(settings.Refused) as r:
            self.read(yaml)
        self.assertEqual(r.exception.code, code)
        return [re.sub(r"^.*?edda\.yaml:", "edda.yaml:", line) for line in r.exception.lines]

    def test_no_file_is_todays_behaviour(self):
        s = settings.read(self.host.root)
        self.assertEqual((s.folder, s.file, s.generated, s.pin, s.stack, s.flags),
                         (self.host.folder, None, settings.GENERATED_OFF, None, None, []))
        self.assertEqual(s.problem_log, "off")                                  # nothing is logged
        own = settings.read()       # Edda's own edda.yaml (revision 69) names no specs: specs/
        self.assertEqual((own.root, own.folder, own.file), (ROOT, os.path.join(ROOT, "specs"), os.path.join(ROOT, "edda.yaml")))

    def test_every_key_valid(self):
        os.rename(self.host.folder, os.path.join(self.host.root, "docs"))
        os.makedirs(os.path.join(self.host.root, "docs", "nested"))
        s = self.read(f"edda: {REV}\nspecs: \"docs/nested\"\nstack: python\n"
                      "generated_cases: {on: true, runs: 5}\n")
        self.assertEqual((s.folder, s.pin, s.stack, s.generated, s.flags),
                         (os.path.join(self.host.root, "docs", "nested"), REV, "python",
                          {"on": True, "runs": 5, "steps": 20}, []))
        self.assertEqual(self.read("specs: docs\n").folder, os.path.join(self.host.root, "docs"))

    def test_every_key_invalid(self):
        for value in ("0", "-1", "1.5", "true", '"68"'):
            self.assertEqual(self.refused(f"edda: {value}\n"),
                             ["edda.yaml:1: wrong_type: edda must be a whole number of at least 1"], value)
        for value in ('"/abs"', '"../up"', '"a/../b"', '""', ".."):
            self.assertEqual(len(self.refused(f"specs: {value}\n")), 1, value)
            self.assertIn("wrong_type: specs must be a folder inside the project, without ..",
                          self.refused(f"specs: {value}\n")[0], value)
        self.assertEqual(self.refused("specs: 5\n"), ["edda.yaml:1: wrong_type: specs must be a text"])
        self.assertEqual(self.refused("stack: java\n"), ["edda.yaml:1: wrong_type: stack must be python"])
        self.assertEqual(self.refused("packs: [a]\n"), ["edda.yaml:1: unknown_key: unknown key: packs"])
        self.assertEqual(self.refused("generated_cases: {runs: 2}\n"),
                         ["edda.yaml:1: missing_key: generated_cases needs on:"])
        self.assertEqual(self.refused("edda: 1\nedda: 2\n"), ["edda.yaml:2: declared_twice: declared twice: edda"])
        self.assertEqual(self.refused(""), ["edda.yaml:1: wrong_type: file must be a mapping"])   # still open

    def test_pin_older_and_newer(self):
        self.assertEqual(self.read(f"edda: {REV}\n").flags, [])
        s = self.read(f"edda: {REV - 1}\n")
        self.assertEqual([(rule, line, msg) for rule, _, line, msg in s.flags],
                         [("pinned_older", 1, f"edda.yaml pins revision {REV - 1}; these tools are revision {REV}")])
        line = [f"edda.yaml:2: pinned_newer: edda.yaml pins revision {REV + 1}; these tools are revision {REV}"]
        self.assertEqual(self.refused(f"stack: python\nedda: {REV + 1}\n", code=3), line)
        # a newer revision's keys are not read: the pin decides first
        self.assertEqual(self.refused(f"packs: [a]\nedda: {REV + 1}\n", code=3), line)

    def test_stack_and_glossary_links(self):
        links = os.path.join(self.host.folder, "glossary.links")
        with open(links, "w") as f:
            f.write("target: java\nrule: same_name\ncovers: []\n")
        found = self.refused("stack: python\n")
        self.assertEqual(len(found), 1)
        self.assertTrue(found[0].startswith("edda.yaml:1: stack_mismatch: stack is python but "), found)
        self.assertTrue(found[0].endswith("glossary.links names target java"), found)
        self.assertIsNone(self.read("edda: 68\n").stack)           # no stack named: nothing to agree
        with open(links, "w") as f:
            f.write("target: python\nrule: same_name\ncovers: []\n")
        self.assertEqual(self.read("stack: python\n").stack, "python")

    def test_both_files_and_the_old_place(self):
        old = os.path.join(self.host.folder, "edda.yaml")
        with open(old, "w") as f:
            f.write("generated_cases: {on: true, steps: 3}\n")
        s = settings.read(self.host.root)       # the old place alone is still read
        self.assertEqual((s.file, s.generated), (old, {"on": True, "runs": 100, "steps": 3}))
        self.assertEqual(settings.read(folder=self.host.folder).generated["steps"], 3)
        found = self.refused("edda: 68\n")
        self.assertEqual(len(found), 1)
        self.assertRegex(found[0], r"^edda\.yaml:1: two_settings: two edda\.yaml files; keep .*edda\.yaml "
                                   r"and move generated_cases: into it$")
        with self.assertRaises(settings.Refused) as r:      # at the second: the spec folder's
            settings.read(self.host.root)
        self.assertIn("specs/edda.yaml:1: two_settings:", r.exception.lines[0])
        os.remove(os.path.join(self.host.root, "edda.yaml"))
        with open(old, "w") as f:
            f.write("edda: 68\ngenerated_cases: {on: false}\n")
        with self.assertRaises(settings.Refused) as r:      # the old place holds generated_cases only
            settings.read(self.host.root)
        self.assertTrue(r.exception.lines[0].endswith("specs/edda.yaml:1: unknown_key: unknown key: edda"),
                        r.exception.lines)

    def test_specs_may_be_the_root_itself(self):
        s = self.read("specs: .\n")
        self.assertEqual((s.folder, s.file), (self.host.root, os.path.join(self.host.root, "edda.yaml")))

    def test_a_named_folder_takes_the_folder_above_as_root(self):
        os.makedirs(os.path.join(self.host.root, "other"))
        self.host.write("edda.yaml", f"edda: {REV - 1}\nspecs: other\n")
        s = settings.read(folder=self.host.folder)
        self.assertEqual((s.root, s.folder, s.pin), (self.host.root, self.host.folder, REV - 1))

    def test_the_revision_is_the_references(self):
        with open(os.path.join(ROOT, "language", "reference.md")) as f:
            self.assertEqual(int(re.search(r"^Revision (\d+)", f.read(), re.M).group(1)), REV)

    def test_every_new_rule_is_in_the_registry(self):
        import watch
        rules, _ = watch.registry()
        for rule in ("pinned_newer", "pinned_older", "stack_mismatch", "two_settings"):
            self.assertEqual(set(rules[rule]), set(watch.FIXED), rule)
        self.assertEqual((rules["pinned_older"]["level"], rules["pinned_newer"]["level"]), ("warns", "blocks"))


class ToolsTest(unittest.TestCase):
    """the tools on a project whose spec folder is stories/, not specs/"""

    def setUp(self):
        self.host = Host("stories", f"edda: {REV}\nspecs: stories\nstack: python\n")

    def tearDown(self):
        self.host.tmp.cleanup()

    def test_check(self):
        code, out, _ = self.host.tool("check.py", "--root", ".")
        self.assertEqual(code, 0, out)
        self.assertEqual(out.splitlines()[0], "stories/order.edda OK")
        self.assertIn("stories/order.edda.vc OK", out.splitlines())
        self.assertNotIn("fixtures:", out)          # the fixtures are Edda's own
        code, out, err = self.host.tool("check.py", "--root", ".", "--model")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual([f["name"] for f in json.loads(out)["files"]], ["order.edda"])
        code, out, _ = self.host.tool("check.py", "--root", "nowhere")
        self.assertEqual((code, out), (2, "no such folder: nowhere\n"))

    def test_run(self):
        code, out, _ = self.host.tool("run.py", "--root", ".")
        self.assertEqual((code, out), (0, "FIX-001: not run: no binding for entity order\n"))
        self.assertEqual(self.host.tool("run.py", "--root", "nowhere")[:2], (2, "no such folder: nowhere\n"))

    def test_approve_dry_run(self):
        vc = os.path.join(self.host.folder, "order.edda.vc")
        with open(vc) as f:
            before = f.read()
        code, out, err = self.host.tool("approve.py", "FIX-001", "--by", "tuan", "--at", "2026-10-05 10:00",
                                        "--dry-run", "--root", ".")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out.splitlines()[:2], ["- story: FIX-001", "  number: 1"])
        with open(vc) as f:
            self.assertEqual(f.read(), before)

    def test_view(self):
        code, out, _ = self.host.tool("view.py", "--root", ".", "FIX-001")
        self.assertEqual(code, 0, out)
        self.assertTrue(out.startswith("  Remove an order. As a shop user,"), out)
        self.assertEqual(self.host.tool("view.py", "--root", ".", "NOPE-001")[:2], (2, "no such story: NOPE-001\n"))

    def test_a_pin_older_flags_once_and_runs(self):
        self.host.write("edda.yaml", f"edda: {REV - 1}\nspecs: stories\n")
        flag = f"edda.yaml:1: flagged: pinned_older: edda.yaml pins revision {REV - 1}; these tools are revision {REV}"
        code, out, _ = self.host.tool("check.py", "--root", ".")
        self.assertEqual((code, out.splitlines()[0], out.splitlines()[-1]), (0, flag, "1 out of date"))
        self.assertEqual(self.host.tool("run.py", "--root", ".")[:2],
                         (0, flag + "\nFIX-001: not run: no binding for entity order\n"))
        self.assertEqual(self.host.tool("view.py", "--root", ".")[1].splitlines()[0], flag)
        code, out, err = self.host.tool("check.py", "--root", ".", "--model")
        self.assertEqual((code, err), (0, flag + "\n"))
        json.loads(out)
        code, out, err = self.host.tool("approve.py", "FIX-001", "--by", "tuan", "--dry-run", "--root", ".")
        self.assertEqual((code, err, out.splitlines()[0]), (0, flag + "\n", "- story: FIX-001"))

    def test_a_pin_newer_refuses_with_one_line(self):
        self.host.write("edda.yaml", f"edda: {REV + 1}\nspecs: stories\n")
        line = f"edda.yaml:1: pinned_newer: edda.yaml pins revision {REV + 1}; these tools are revision {REV}\n"
        for tool, args in (("check.py", ()), ("run.py", ()), ("view.py", ())):
            self.assertEqual(self.host.tool(tool, "--root", ".", *args)[:2], (3, line), tool)
        self.assertEqual(self.host.tool("approve.py", "FIX-001", "--by", "tuan", "--dry-run", "--root", "."),
                         (3, "", line))

    def test_settings_that_do_not_check(self):
        self.host.write("edda.yaml", "stack: java\n")
        bad = "the settings do not check:\n    edda.yaml:1: wrong_type: stack must be python\n"
        for tool in ("check.py", "run.py", "view.py"):
            self.assertEqual(self.host.tool(tool, "--root", ".")[:2], (1, bad), tool)

    def test_the_log_goes_to_the_root(self):
        self.host.write("edda.yaml", f"edda: {REV - 1}\nspecs: stories\nproblem_log: local\n")
        env = {k: v for k, v in os.environ.items() if k != "EDDA_LOG"}
        self.host.tool("check.py", "--root", ".", env=env)
        log = os.path.join(self.host.root, ".edda", "checks.log")
        with open(log) as f:
            self.assertEqual([json.loads(x)["rule"] for x in f], ["pinned_older"])
        code, out, _ = self.host.tool("trend.py", "--root", ".", env=env)
        self.assertEqual(code, 0)
        self.assertIn("pinned_older", out)

    def test_no_file_reads_specs(self):
        plain = Host()
        try:
            code, out, _ = plain.tool("check.py", "--root", ".")
            self.assertEqual((code, out.splitlines()[0]), (0, "specs/order.edda OK"))
        finally:
            plain.tmp.cleanup()


def tail(line):
    """a refusal line from its rule on, the resolved path left out"""
    return re.sub(r": /.*$", ": <path>", line[line.index(" outside_root: ") + 1:])


class InsideTheRootTest(unittest.TestCase):
    """every path the host gives resolves inside its root (section 9)"""

    def setUp(self):
        self.host = Host("docs/specs", f"edda: {REV}\nspecs: docs/specs\n", fixture=LINKED)
        self.host.write("shop/code.py", MARKED)
        self.host.write("docs/specs/glossary.links", GLOSSARY.format("shop/code.py"))

    def tearDown(self):
        self.host.tmp.cleanup()

    def refused(self, **kw):
        with self.assertRaises(settings.Refused) as r:
            settings.read(self.host.root, **kw)
        return r.exception.lines

    def test_nested_specs_read_covers_from_the_root(self):
        code, out, _ = self.host.tool("check.py", "--root", ".")
        self.assertEqual(code, 0, out)
        self.assertIn("docs/specs/glossary.links OK", out.splitlines())
        self.assertIn("shop/code.py OK", out.splitlines())
        self.assertIn("FIX-001: linked (remove -> shop/code.py::remove)", out)

    def test_no_file_keeps_the_folder_above(self):
        plain = Host(fixture=LINKED)
        try:
            plain.write("shop/code.py", MARKED)
            plain.write("specs/glossary.links", GLOSSARY.format("shop/code.py"))
            code, out, _ = plain.tool("check.py", "--root", ".")
            self.assertEqual(code, 0, out)
            self.assertIn("FIX-001: linked (remove -> shop/code.py::remove)", out)
        finally:
            plain.tmp.cleanup()

    def test_a_spec_folder_outside_is_refused(self):
        away = self.host.away("elsewhere")
        for name in os.listdir(self.host.folder):
            shutil.copy(os.path.join(self.host.folder, name), away)
        os.symlink(away, os.path.join(self.host.root, "out"))
        self.host.write("edda.yaml", f"edda: {REV}\nspecs: out\n")
        lines = self.refused()
        self.assertTrue(lines[0].endswith(".yaml:2: outside_root: the spec folder resolves outside the "
                                          f"project root: {os.path.realpath(away)}"), lines)
        self.assertEqual([tail(x) for x in lines],
                         ["outside_root: the spec folder resolves outside the project root: <path>"])
        code, out, _ = self.host.tool("check.py", "--root", ".")
        self.assertEqual((code, out.splitlines()[0]), (1, "the settings do not check:"))
        self.assertIn("edda.yaml:2: outside_root: the spec folder", out)
        # the default place, with no specs: line, is named by itself
        os.rename(self.host.folder, os.path.join(self.host.root, "docs", "kept"))
        os.symlink(away, os.path.join(self.host.root, "specs"))
        self.host.write("edda.yaml", f"edda: {REV}\n")
        self.assertRegex(self.refused()[0], r"^\S*specs: outside_root: the spec folder resolves outside")
        os.remove(os.path.join(self.host.root, "edda.yaml"))      # no file: the folder is still held
        self.assertRegex(self.refused()[0], r"^\S*specs: outside_root: ")
        self.assertRegex(self.refused(folder=os.path.join(self.host.root, "specs"))[0],
                         r"^\S*specs: outside_root: ")       # named: the folder above is the root

    def test_a_spec_folder_linked_inside_is_read(self):
        os.symlink(self.host.folder, os.path.join(self.host.root, "alias"))
        self.host.write("edda.yaml", f"edda: {REV}\nspecs: alias\n")
        self.assertEqual(settings.read(self.host.root).folder, os.path.join(self.host.root, "alias"))

    def test_a_log_folder_outside_is_refused(self):
        self.host.write("edda.yaml", f"edda: {REV}\nspecs: docs/specs\nproblem_log: local\n")    # off: not read
        os.symlink(self.host.away("logs"), os.path.join(self.host.root, ".edda"))
        self.assertEqual([tail(x) for x in self.refused()],
                         ["outside_root: the log folder .edda resolves outside the project root: <path>"])
        code, out, _ = self.host.tool("trend.py", "--root", ".")
        self.assertEqual(code, 1)
        self.assertTrue(out.startswith(".edda: outside_root: the log folder .edda resolves outside"), out)

    def test_a_covers_path_outside_is_refused(self):
        away = self.host.away("theirs")
        with open(os.path.join(away, "code.py"), "w") as f:
            f.write(MARKED)
        os.symlink(away, os.path.join(self.host.root, "vendor"))
        self.host.write("docs/specs/glossary.links", GLOSSARY.format("vendor/code.py"))
        code, out, _ = self.host.tool("check.py", "--root", ".")
        self.assertEqual(code, 1, out)
        found = [x.strip() for x in out.splitlines() if "outside_root" in x]
        self.assertEqual([re.sub(r": /.*$", ": <path>", x) for x in found],
                         ["4: outside_root: vendor/code.py resolves outside the project root: <path>"])
        # a file linked from inside the root is read
        os.remove(os.path.join(self.host.root, "vendor"))
        os.symlink(os.path.join(self.host.root, "shop"), os.path.join(self.host.root, "vendor"))
        code, out, _ = self.host.tool("check.py", "--root", ".")
        self.assertEqual(code, 0, out)
        self.assertIn("vendor/code.py OK", out.splitlines())

    def test_a_links_path_outside_is_refused(self):
        away = self.host.away("theirs")
        with open(os.path.join(away, "code.py"), "w") as f:
            f.write(MARKED.replace("def remove", "def take_off"))
        os.symlink(away, os.path.join(self.host.root, "vendor"))
        self.host.write("docs/specs/order.links", 'links:\n  remove: "vendor/code.py::take_off"\n')
        code, out, _ = self.host.tool("check.py", "--root", ".")     # not covered: never read
        self.assertEqual(code, 1, out)
        self.assertIn("unknown_link: not a covered file: vendor/code.py", out)
        self.host.write("docs/specs/glossary.links",
                        GLOSSARY.format("shop/code.py") + '  - "vendor/code.py"\n')
        code, out, _ = self.host.tool("check.py", "--root", ".")     # covered: refused at its covers: line
        self.assertEqual(code, 1, out)
        self.assertIn("5: outside_root: vendor/code.py resolves outside the project root: ", out)


class FilesInsideTheRootTest(unittest.TestCase):
    """every file a tool opens under the root, not only every folder,
    resolves inside it as it is opened (section 9)"""

    def setUp(self):
        self.host = Host("docs/specs", f"edda: {REV}\nspecs: docs/specs\n", fixture=LINKED)
        self.host.write("shop/code.py", MARKED)
        self.host.write("docs/specs/glossary.links", GLOSSARY.format("shop/code.py"))

    def tearDown(self):
        self.host.tmp.cleanup()

    def move(self, name, to):
        """move the spec folder's file name to the folder to and link it back;
        the path it now resolves to"""
        here, there = os.path.join(self.host.folder, name), os.path.join(to, name)
        shutil.move(here, there)
        os.symlink(there, here)
        return os.path.realpath(there)

    def outside(self, out):
        return [re.sub(r": /.*$", ": <path>", x.strip()) for x in out.splitlines() if "outside_root" in x]

    def test_a_spec_file_linked_outside_is_refused(self):
        for name in ("order.edda", "order.edda.vc", "order.links"):
            with self.subTest(name=name):
                host = Host("docs/specs", f"edda: {REV}\nspecs: docs/specs\n", fixture=LINKED)
                self.host, saved = host, self.host
                try:
                    if name == "order.links":
                        host.write("shop/code.py", MARKED)
                        host.write("docs/specs/glossary.links", GLOSSARY.format("shop/code.py"))
                        host.write("docs/specs/order.links", 'links:\n  remove: "shop/code.py::remove"\n')
                    real = self.move(name, host.away("theirs"))
                    code, out, _ = host.tool("check.py", "--root", ".")
                    self.assertEqual(code, 1, out)
                    self.assertIn(f"1: outside_root: {name} resolves outside the project root: {real}", out)
                    if name == "order.links":
                        continue                # read by the checker alone
                    for tool in ("run.py", "view.py"):
                        code, out, _ = host.tool(tool, "--root", ".")
                        self.assertEqual(code, 1, (tool, out))
                        self.assertIn(f"outside_root: {name} resolves outside", out, tool)
                    code, out, err = host.tool("approve.py", "FIX-001", "--by", "tuan", "--dry-run", "--root", ".")
                    self.assertEqual((code, out), (1, ""))
                    self.assertIn(f"outside_root: {name} resolves outside the project root: {real}", err)
                finally:
                    self.host = saved
                    host.tmp.cleanup()

    def test_a_spec_file_linked_inside_is_read(self):
        kept = os.path.join(self.host.root, "kept")
        os.makedirs(kept)
        self.host.write("docs/specs/order.links", 'links:\n  remove: "shop/code.py::remove"\n')
        for name in ("order.edda", "order.edda.vc", "order.links"):
            self.move(name, kept)
        code, out, _ = self.host.tool("check.py", "--root", ".")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.outside(out), [])
        self.assertIn("FIX-001: linked (remove -> shop/code.py::remove)", out)
        self.assertEqual(self.host.tool("view.py", "--root", ".")[0], 0)

    def test_an_edda_yaml_linked_outside_is_refused(self):
        away = os.path.join(self.host.away("theirs"), "edda.yaml")
        os.rename(os.path.join(self.host.root, "edda.yaml"), away)
        os.symlink(away, os.path.join(self.host.root, "edda.yaml"))
        code, out, _ = self.host.tool("check.py", "--root", ".")
        self.assertEqual((code, out.splitlines()[0]), (1, "the settings do not check:"))
        self.assertEqual(self.outside(out), ["edda.yaml:1: outside_root: edda.yaml resolves outside the "
                                             "project root: <path>"])

    def test_no_file_and_no_root_reads_as_before(self):
        with mock.patch.object(settings.checker, "ROOT", self.host.away("bare")):     # an Edda with no edda.yaml
            self.assertIsNone(settings.read().guard)
        self.assertEqual(settings.read().guard, ROOT)       # Edda's own edda.yaml puts its root in play
        self.assertEqual(settings.read(self.host.root).guard, self.host.root)

    def test_a_log_linked_outside_is_not_written(self):
        self.host.write("edda.yaml", f"edda: {REV - 1}\nspecs: docs/specs\nproblem_log: local\n")     # one flag to log
        os.makedirs(os.path.join(self.host.root, ".edda"))
        away = os.path.join(self.host.away("logs"), "checks.log")
        with open(away, "w") as f:
            f.write("theirs\n")
        os.symlink(away, os.path.join(self.host.root, ".edda", "checks.log"))
        env = {k: v for k, v in os.environ.items() if k != "EDDA_LOG"}
        quiet = self.host.tool("check.py", "--root", ".")
        code, out, err = self.host.tool("check.py", "--root", ".", env=env)
        self.assertEqual((code, out), quiet[:2])            # output and exit code as with the log off
        self.assertEqual(re.sub(r": /\S*;", ": <path>;", err),
                         ".edda/checks.log: outside_root: the log resolves outside the project root: <path>; "
                         "nothing logged\n")
        with open(away) as f:
            self.assertEqual(f.read(), "theirs\n")
        code, out, _ = self.host.tool("trend.py", "--root", ".", env=env)
        self.assertEqual(code, 1)
        self.assertTrue(out.startswith(".edda/checks.log: outside_root: the log resolves outside"), out)
        # linked inside the root, it is written
        inside = os.path.join(self.host.root, "kept.log")
        os.remove(os.path.join(self.host.root, ".edda", "checks.log"))
        os.symlink(inside, os.path.join(self.host.root, ".edda", "checks.log"))
        code, out, err = self.host.tool("check.py", "--root", ".", env=env)
        self.assertEqual((code, out, err), quiet)
        with open(inside) as f:
            self.assertEqual([json.loads(x)["rule"] for x in f], ["pinned_older"])
        # one the operator names is theirs to choose
        mine = os.path.join(self.host.away("mine"), "my.log")
        self.assertEqual(self.host.tool("check.py", "--root", ".", env=dict(env, EDDA_LOG=mine)), quiet)
        self.assertTrue(os.path.exists(mine))

    def test_approve_never_writes_outside(self):
        host = Host("stories", f"edda: {REV}\nspecs: stories\n")
        try:
            vc = os.path.join(host.folder, "order.edda.vc")
            away = os.path.join(host.away("theirs"), "order.edda.vc")
            shutil.move(vc, away)
            os.symlink(away, vc)
            with open(away, "rb") as f:
                before = f.read()
            code, out, err = host.tool("approve.py", "FIX-001", "--by", "tuan", "--at", "2026-10-05 10:00", "--root", ".")
            self.assertEqual((code, out), (1, ""))
            self.assertIn("outside_root: order.edda.vc resolves outside the project root: ", err)
            with open(away, "rb") as f:
                self.assertEqual(f.read(), before)
            self.assertEqual(sorted(os.listdir(host.folder)), ["order.edda", "order.edda.vc"])
            # inside the root it is written, through the folder the lock holds
            os.remove(vc)
            shutil.move(away, vc)
            os.chmod(vc, 0o640)
            code, out, err = host.tool("approve.py", "FIX-001", "--by", "tuan", "--at", "2026-10-05 10:00", "--root", ".")
            self.assertEqual((code, err), (0, ""), out)
            with open(vc, "rb") as f:
                after = f.read()
            self.assertTrue(after.startswith(before))
            self.assertIn(b"- story: FIX-001\n  number: 1\n", after[len(before):])
            self.assertIn(b"  approved_by: tuan\n", after[len(before):])
            self.assertEqual(os.stat(vc).st_mode & 0o777, 0o640)
            self.assertEqual(sorted(os.listdir(host.folder)), ["order.edda", "order.edda.vc"])
        finally:
            host.tmp.cleanup()

    def test_open_inside_never_follows_a_link_put_in_place(self):
        top = os.path.realpath(self.host.root)
        code = os.path.join(top, "shop", "code.py")
        os.close(check.open_inside(top, code))
        with self.assertRaises(check.Outside):
            check.open_inside(top, os.path.join(top, "..", "elsewhere"))
        away = self.host.away("out")
        # the path resolved inside, then a folder of it or the file itself
        # swapped for a link out before the open: the open fails
        with mock.patch.object(check.os.path, "realpath", lambda p: p):
            shutil.move(os.path.join(top, "shop"), os.path.join(away, "shop"))
            os.symlink(os.path.join(away, "shop"), os.path.join(top, "shop"))
            with self.assertRaises(OSError):
                check.open_inside(top, code)
            os.remove(os.path.join(top, "shop"))
            os.makedirs(os.path.join(top, "shop"))
            os.symlink(os.path.join(away, "shop", "code.py"), code)
            with self.assertRaises(OSError):
                check.open_inside(top, code)

    def test_open_inside_never_follows_the_root_swapped_for_a_link(self):
        top = os.path.realpath(self.host.root)
        code = os.path.join(top, "shop", "code.py")
        os.close(check.open_inside(top, code))
        os.close(check.open_inside(top, top))
        os.close(check.open_inside(top, top, os.O_RDONLY | os.O_DIRECTORY))
        moved = os.path.join(self.host.away("moved"), "host")
        # the root resolved, then swapped for a link out before the open:
        # the open of a file under it, and of the root itself, fails
        with mock.patch.object(check.os.path, "realpath", lambda p: p):
            shutil.move(top, moved)
            os.symlink(moved, top)
            try:
                with self.assertRaises(OSError):
                    check.open_inside(top, code)
                for flags in (os.O_RDONLY, os.O_RDONLY | os.O_DIRECTORY):
                    with self.assertRaises(OSError):
                        check.open_inside(top, top, flags)
            finally:
                os.remove(top)
                shutil.move(moved, top)
        os.close(check.open_inside(top, code))


class OneRootTest(unittest.TestCase):
    """--root and a spec folder named by an option name one root, or the
    tool refuses with one line and exits 2"""

    def setUp(self):
        self.host = Host()
        self.other = Host()

    def tearDown(self):
        self.host.tmp.cleanup()
        self.other.tmp.cleanup()

    def test_each_tool_and_option(self):
        theirs = self.other.folder
        two = f"--root . and the spec folder {theirs} name two roots; give one\n"
        for tool, args, stream in (
                ("check.py", ("--model", theirs), 2),
                ("check.py", ("--graph", "order.status", theirs), 2),
                ("run.py", ("--project", theirs), 1),
                ("approve.py", ("FIX-001", "--by", "tuan", "--dry-run", "--folder", theirs), 2)):
            got = self.host.tool(tool, "--root", ".", *args)
            self.assertEqual((got[0], got[stream]), (2, two), (tool, args))
        for tool, args in (
                ("check.py", ("--model", "specs")),
                ("check.py", ("--graph", "order.status", "specs")),
                ("run.py", ("--project", "specs")),
                ("approve.py", ("FIX-001", "--by", "tuan", "--dry-run", "--folder", "specs"))):
            self.assertEqual(self.host.tool(tool, "--root", ".", *args)[0], 0, (tool, args))

    def test_trend_root_and_log(self):
        log = os.path.join(self.other.root, ".edda", "checks.log")
        for root in (self.other.root, self.host.root):      # an empty log in each
            os.makedirs(os.path.join(root, ".edda"), exist_ok=True)
            open(os.path.join(root, ".edda", "checks.log"), "w").close()
        code, out, _ = self.host.tool("trend.py", "--root", ".", "--log", log)
        self.assertEqual((code, out), (2, f"--root . and --log {log} name two logs; give one\n"))
        code, out, _ = self.host.tool("trend.py", "--root", ".", "--log", ".edda/checks.log")
        self.assertEqual((code, out), (0, "nothing logged yet: .edda/checks.log\n"))


class GuideTest(unittest.TestCase):

    def test_the_guide_regenerates_to_the_same_bytes(self):
        with open(guide.GUIDE) as f:
            self.assertEqual(guide.guide(), f.read(), "language/guide.md differs; run python3 tools/guide.py")

    def test_the_guide_is_short_lines_of_ascii(self):
        text = guide.guide()
        self.assertTrue(text.isascii())
        self.assertEqual([line for line in text.splitlines() if len(line) >= 80], [])

    def test_the_guide_says_what_an_agent_must_do(self):
        text = " ".join(" ".join(re.sub(r"^> ?", "", line) for line in guide.guide().splitlines()).split())
        for said in ("An agent writes level 1 from the customer's words.",
                     "only the operator's approve command, `tools/approve.py`, writes it;",
                     "`acts`: `agent`, the agent fixes it alone;",
                     "<edda>/edda check --root .",
                     "An agent runs the check after each change and acts on each problem's `acts`, "
                     "who must act (decision X, operator decision, 3 Oct 2026); with `--json`",
                     "the exit code says whether anything was refused or failed.",
                     "The code carries `# <STORY-ID>@<n>`",
                     "**Done.** A story is done when",
                     "## For people",
                     "Where it goes is the host's choice"):
            self.assertIn(said, text)
        self.assertLess(text.index("## For agents"), text.index("## For people"))

    def test_a_missing_source_stops_the_guide(self):
        with self.assertRaises(guide.Missing):
            guide.paragraph("## 1. The idea\n\nNothing here.\n", 1, "**Who writes, who reads.**")
        with self.assertRaises(guide.Missing):
            guide.section("## 1. The idea\n", 13)

    def test_the_pointer_is_one_line(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(guide.main(["--pointer"]), 0)
        self.assertEqual(out.getvalue(), "This project uses Edda; load the Edda guide (language/guide.md) "
                                         "before working on specs or linked code.\n")

    def test_the_pointer_gives_the_path_the_host_reads(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = os.path.realpath(tmp)
            edda, guide_md = os.path.join(tmp, "work", "edda"), os.path.join("language", "guide.md")
            os.makedirs(os.path.join(edda, "language"))
            for name in ("host", "far/away"):
                os.makedirs(os.path.join(tmp, "work", name) if name == "host" else os.path.join(tmp, name))
            saved = guide.ROOT, guide.GUIDE
            guide.ROOT, guide.GUIDE = edda, os.path.join(edda, guide_md)
            try:
                self.assertEqual(guide.guide_path(os.path.join(tmp, "work")), os.path.join("edda", guide_md))
                self.assertEqual(guide.guide_path(edda), guide_md)                      # Edda itself
                self.assertEqual(guide.guide_path(os.path.join(tmp, "work", "host")),
                                 os.path.join("..", "edda", guide_md))                  # beside it
                self.assertEqual(guide.guide_path(os.path.join(tmp, "far", "away")),
                                 os.path.join(edda, guide_md))                          # elsewhere
                here = os.getcwd()
                os.chdir(os.path.join(tmp, "far"))
                try:
                    self.assertEqual(guide.guide_path(), os.path.join("..", "work", "edda", guide_md))
                finally:
                    os.chdir(here)
            finally:
                guide.ROOT, guide.GUIDE = saved
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(guide.main(["--pointer", "--root", os.path.dirname(ROOT)]), 0)
        self.assertIn(f"({os.path.basename(ROOT)}/language/guide.md)", out.getvalue())


if __name__ == "__main__":
    unittest.main()
