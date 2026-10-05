#!/usr/bin/env python3
"""The edda command and the opt-in problem log (reference sections 9, 11
and 13, revision 69).

    python3 tools/test_command.py

The problem log: absent, off and local in edda.yaml; EDDA_LOG=off
overriding local; EDDA_LOG=<file> redirecting it but never turning it
on; no .edda/ made unless it is on; edda trend over a log written with
local, plain and --json. The command: each subcommand's exit codes 0, 1,
2 and 3 where they can be reached (guide has nothing to refuse, so no
1), the same plain output as the old script, and its --json document:
the envelope, the command's fields and messages.
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["EDDA_LOG"] = "off"     # the tools and their children never write the log (section 11)
import edda                      # noqa: E402
import settings                  # noqa: E402

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
EDDA = os.path.join(ROOT, "edda")
REV = settings.REVISION
READY = os.path.join(ROOT, "fixtures", "blocks_approved")     # checks; FIX-001 ready to approve
BROKEN = os.path.join(ROOT, "fixtures", "yaml_feature")       # refused by the source layer
ENVELOPE = ["format", "edda", "command", "exit"]


class Host:
    """a host project in a temporary folder: root, its spec folder specs
    copied from fixture, and edda.yaml when yaml is given"""

    def __init__(self, yaml=None, fixture=READY):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.join(self.tmp.name, "host")
        shutil.copytree(fixture, os.path.join(self.root, "specs"))
        if yaml is not None:
            with open(os.path.join(self.root, "edda.yaml"), "w") as f:
                f.write(yaml)

    def edda(self, *args, log="off"):
        """(exit code, stdout, stderr) of ./edda in the host's root; log, the
        EDDA_LOG to set, or None for none"""
        env = {k: v for k, v in os.environ.items() if k != "EDDA_LOG"}
        if log is not None:
            env["EDDA_LOG"] = log
        p = subprocess.run([EDDA, *args], cwd=self.root, capture_output=True, text=True, env=env)
        return p.returncode, p.stdout, p.stderr

    def script(self, name, *args):
        p = subprocess.run([sys.executable, os.path.join(TOOLS, name), *args], cwd=self.root,
                           capture_output=True, text=True, env=dict(os.environ, EDDA_LOG="off"))
        return p.returncode, p.stdout, p.stderr

    def json(self, *args, log="off"):
        code, out, _ = self.edda(*args, "--json", log=log)
        doc = json.loads(out)
        self_test.assertEqual(doc["exit"], code)
        return doc

    def has_log_folder(self):
        return os.path.lexists(os.path.join(self.root, ".edda"))

    def cleanup(self):
        self.tmp.cleanup()


self_test = unittest.TestCase()
FLAGGED = f"edda: {REV - 1}\n"      # one flag, pinned_older, so one problem to log
PINNED = f"edda.yaml:1: flagged: pinned_older: edda.yaml pins revision {REV - 1}; these tools are revision {REV}"


class ProblemLogTest(unittest.TestCase):
    """the log is opt-in: only problem_log: local writes it"""

    def run_both(self, host, log=None):
        for command in ("check", "run"):
            host.edda(command, "--root", ".", log=log)

    def test_absent_off_and_no_file_write_nothing(self):
        for yaml in (None, FLAGGED, FLAGGED + "problem_log: off\n"):
            host = Host(yaml)
            try:
                self.run_both(host)
                self.assertFalse(host.has_log_folder(), yaml)
            finally:
                host.cleanup()

    def test_local_writes_the_log_and_trend_reads_it(self):
        host = Host(FLAGGED + "problem_log: local\n")
        try:
            self.run_both(host)
            with open(os.path.join(host.root, ".edda", "checks.log")) as f:
                rules = [json.loads(x)["rule"] for x in f]
            self.assertEqual(rules, ["pinned_older"])     # the check's; the runner logs only its failures
            host.edda("check", "--root", ".", log=None)
            code, out, _ = host.edda("trend", "--root", ".", log=None)
            self.assertEqual(code, 0)
            self.assertIn("2 problems logged", out)
            doc = host.json("trend", "--root", ".", "--by", "category,acts", log=None)
            self.assertEqual((doc["total"], doc["skipped"], doc["log"], doc["by"]),
                             (2, 0, os.path.join(".edda", "checks.log"), ["category", "acts"]))
            self.assertEqual(doc["groups"], [{"count": 2, "values": ["out of date", "person"]}])
            self.assertEqual(doc["rules"], [{"count": 2, "rule": "pinned_older"}])
            self.assertEqual([(d["total"], d["counts"]) for d in doc["per_day"]], [(2, {"out of date": 2})])
        finally:
            host.cleanup()

    def test_edda_log_off_overrides_local(self):
        host = Host(FLAGGED + "problem_log: local\n")
        try:
            self.run_both(host, log="off")
            self.assertFalse(host.has_log_folder())
        finally:
            host.cleanup()

    def test_edda_log_redirects_but_never_turns_it_on(self):
        for setting, written in (("problem_log: local\n", True), ("problem_log: off\n", False), ("", False)):
            host = Host(FLAGGED + setting)
            try:
                mine = os.path.join(host.tmp.name, "mine.log")
                self.run_both(host, log=mine)
                self.assertEqual(os.path.exists(mine), written, setting)
                self.assertFalse(host.has_log_folder())
            finally:
                host.cleanup()

    def test_a_value_that_is_neither_is_refused(self):
        host = Host("problem_log: yes\n")
        try:
            self.assertEqual(host.edda("check", "--root", ".")[:2],
                             (1, "the settings do not check:\n"
                                 "    edda.yaml:1: wrong_type: problem_log must be local or off\n"))
        finally:
            host.cleanup()

    def test_a_log_folder_outside_matters_only_when_on(self):
        host = Host(f"edda: {REV}\n")
        try:
            os.symlink(host.tmp.name, os.path.join(host.root, ".edda"))
            self.assertEqual(host.edda("check", "--root", ".")[0], 0)      # off: nothing is written there
            with open(os.path.join(host.root, "edda.yaml"), "a") as f:
                f.write("problem_log: local\n")
            code, out, _ = host.edda("check", "--root", ".")
            self.assertEqual(code, 1)
            self.assertIn("outside_root: the log folder .edda resolves outside", out)
        finally:
            host.cleanup()

    def test_edda_itself_turns_it_on(self):
        own = settings.read()
        self.assertEqual((own.file, own.pin, own.stack, own.problem_log),
                         (os.path.join(ROOT, "edda.yaml"), REV, "python", "local"))


class ExitCodeTest(unittest.TestCase):
    """0 nothing refused or failed, 1 refused or failed, 2 usage, 3 Edda
    failed: the same for every subcommand"""

    def setUp(self):
        self.ok, self.broken = Host(f"edda: {REV}\n"), Host(f"edda: {REV}\n", BROKEN)
        self.newer = Host(f"edda: {REV + 1}\n")

    def tearDown(self):
        for h in (self.ok, self.broken, self.newer):
            h.cleanup()

    def codes(self, *args):
        """the exit codes of args on the host that checks, the refused one and
        the one pinned newer"""
        return tuple(h.edda(*args)[0] for h in (self.ok, self.broken, self.newer))

    def test_check(self):
        self.assertEqual(self.codes("check", "--root", "."), (0, 1, 3))
        self.assertEqual(self.ok.edda("check", "--root", ".", "--bogus")[0], 2)
        self.assertEqual(self.ok.edda("check", "--root", "nowhere")[:2], (2, "no such folder: nowhere\n"))
        self.assertEqual(self.ok.edda("check", "--root", ".", "--model", "nowhere")[0], 2)
        self.assertEqual(self.ok.edda("check", "--root", ".", "--graph", "order.nope")[:2],
                         (2, "no such property: order.nope\n"))

    def test_flags_alone_are_zero(self):
        host = Host(FLAGGED)
        try:
            code, out, _ = host.edda("check", "--root", ".")
            self.assertEqual((code, out.splitlines()[-1]), (0, "1 out of date"))
        finally:
            host.cleanup()

    def test_run(self):
        self.assertEqual(self.codes("run", "--root", "."), (0, 1, 3))
        self.assertEqual(self.ok.edda("run", "--root", ".", "NOPE-1")[:2], (2, "edda failed: unknown story: NOPE-1\n"))
        self.assertEqual(self.ok.edda("run", "--root", ".", "--seed", "x")[0], 2)
        self.assertEqual(self.ok.edda("run", "--root", "nowhere")[0], 2)

    def test_view(self):
        self.assertEqual(self.codes("view", "--root", "."), (0, 1, 3))
        self.assertEqual(self.ok.edda("view", "--root", ".", "NOPE-1")[:2], (2, "no such story: NOPE-1\n"))
        self.assertEqual(self.ok.edda("view", "nowhere")[:2], (2, "no such folder: nowhere\n"))

    def test_approve(self):
        dry = ("--by", "tuan", "--dry-run", "--root", ".")
        self.assertEqual(self.codes("approve", "FIX-001", *dry), (0, 1, 3))
        self.assertEqual(self.ok.edda("approve", "NOPE-1", *dry)[0], 1)
        self.assertEqual(self.ok.edda("approve", "FIX-001", *dry, "--at", "soon")[:3:2],
                         (2, 'not a time "YYYY-MM-DD HH:MM": soon\n'))
        self.assertEqual(self.ok.edda("approve", "FIX-001", "--by", "1x", "--root", ".")[:3:2],
                         (2, "not a name: 1x\n"))
        self.assertEqual(self.ok.edda("approve", "FIX-001", "--root", ".")[0], 2)       # no --by
        self.assertEqual(sorted(os.listdir(os.path.join(self.ok.root, "specs"))), ["order.edda", "order.edda.vc"])

    def test_guide(self):
        self.assertEqual(self.ok.edda("guide", "--pointer")[0], 0)
        self.assertEqual(self.ok.edda("guide", "--root", ".")[:2], (2, "--root goes with --pointer\n"))
        self.assertEqual(self.ok.edda("guide", "--pointer", "--root", "nowhere")[0], 2)
        out = io.StringIO()
        with mock.patch("guide.reference", return_value=""), redirect_stdout(out):
            self.assertEqual(edda.main(["guide"]), 3)       # a source missing: Edda failed, nothing written
        self.assertEqual(out.getvalue(), "guide not written: no revision line in the reference\n")

    def test_trend(self):
        self.assertEqual(self.ok.edda("trend", "--root", ".", log=None)[:2],
                         (0, "nothing logged yet: .edda/checks.log\n"))
        self.assertEqual(self.ok.edda("trend", "--root", ".", "--by", "colour", log=None)[0], 2)
        self.assertEqual(self.ok.edda("trend", "--root", ".")[0], 2)       # EDDA_LOG=off and no --log
        os.symlink(self.ok.tmp.name, os.path.join(self.ok.root, ".edda"))
        self.assertEqual(self.ok.edda("trend", "--root", ".", log=None)[0], 1)     # the log folder outside the root
        doc = self.ok.json("trend", "--root", ".", log=None)
        self.assertEqual((doc["log"], doc["messages"][0][:21]), (None, ".edda: outside_root: "))

    def test_edda_failing_is_three(self):
        out = io.StringIO()
        with mock.patch("trend.read", side_effect=RuntimeError("boom")), redirect_stdout(out):
            log = os.path.join(self.ok.tmp.name, "a.log")
            with open(log, "w") as f:
                f.write("\n")
            self.assertEqual(edda.main(["trend", "--log", log]), 3)
        self.assertEqual(out.getvalue(), "edda failed: RuntimeError: boom\n")

    def test_no_command_is_usage(self):
        self.assertEqual(self.ok.edda()[0], 2)
        self.assertEqual(self.ok.edda("lint")[:2], (2, edda.USAGE + "\n"))
        self.assertEqual(json.loads(self.ok.edda("lint", "--json")[1])["exit"], 2)


class MissingPathTest(unittest.TestCase):
    """every option that names a folder or file not there, or not of its
    kind, is a usage error: exit 2 and one line, nothing done; through the
    command and the old script alike"""

    CASES = (    # (command, args, the line); nowhere is not there, edda.yaml is a file, specs a folder
        ("check", ("--root", "nowhere"), "no such folder: nowhere"),
        ("check", ("--root", "edda.yaml"), "not a folder: edda.yaml"),
        ("check", ("--model", "nowhere"), "no such folder: nowhere"),
        ("check", ("--root", ".", "--model", "nowhere"), "no such folder: nowhere"),
        ("check", ("--root", ".", "--graph", "order.status", "nowhere"), "no such folder: nowhere"),
        ("run", ("--root", "nowhere"), "no such folder: nowhere"),
        ("run", ("--project", "/does-not-exist"), "no such folder: /does-not-exist"),
        ("run", ("--root", ".", "--project", "nowhere"), "no such folder: nowhere"),
        ("run", ("--project", "edda.yaml"), "not a folder: edda.yaml"),
        ("view", ("--root", "nowhere"), "no such folder: nowhere"),
        ("view", ("nowhere",), "no such folder: nowhere"),
        ("view", ("edda.yaml",), "not a folder: edda.yaml"),
        ("approve", ("FIX-001", "--by", "tuan", "--root", "nowhere"), "no such folder: nowhere"),
        ("approve", ("FIX-001", "--by", "tuan", "--folder", "nowhere"), "no such folder: nowhere"),
        ("approve", ("FIX-001", "--by", "tuan", "--root", ".", "--folder", "nowhere"), "no such folder: nowhere"),
        ("guide", ("--pointer", "--root", "nowhere"), "no such folder: nowhere"),
        ("guide", ("--pointer", "--root", "edda.yaml"), "not a folder: edda.yaml"),
        ("trend", ("--root", "nowhere"), "no such folder: nowhere"),
        ("trend", ("--root", "nowhere", "--log", "nowhere/.edda/checks.log"), "no such folder: nowhere"),
        ("trend", ("--log", "nowhere.log"), "no such file: nowhere.log"),
        ("trend", ("--log", "specs"), "not a file: specs"),
    )

    def test_each_option_of_each_command_and_script(self):
        host = Host(f"edda: {REV}\n")
        try:
            before = sorted(os.listdir(host.root)), sorted(os.listdir(os.path.join(host.root, "specs")))
            for command, args, line in self.CASES:
                for code, out, err in (host.edda(command, *args, log=None),
                                       host.script(f"{command}.py", *args)):
                    self.assertEqual((code, out + err), (2, line + "\n"), (command, args))
                doc = host.json(command, *args, log=None)
                self.assertEqual((doc["exit"], doc["messages"]), (2, [line]), (command, args))
            self.assertEqual((sorted(os.listdir(host.root)), sorted(os.listdir(os.path.join(host.root, "specs")))),
                             before)
        finally:
            host.cleanup()


class SameOutputTest(unittest.TestCase):
    """edda COMMAND prints what the old script prints, and exits alike"""

    def test_every_command(self):
        host = Host(FLAGGED)
        try:
            for name, args in (("check", ()), ("run", ()), ("view", ("--lines",)),
                               ("approve", ("FIX-001", "--by", "tuan", "--at", "2026-10-05 09:00", "--dry-run")),
                               ("trend", ())):
                self.assertEqual(host.edda(name, "--root", ".", *args), host.script(f"{name}.py", "--root", ".", *args),
                                 name)
            self.assertEqual(host.edda("guide", "--pointer", "--root", "."),
                             host.script("guide.py", "--pointer", "--root", "."))
        finally:
            host.cleanup()


class JsonTest(unittest.TestCase):
    """one JSON document on stdout: the envelope, the command's fields
    (edda.FIELDS) and messages"""

    @classmethod
    def setUpClass(cls):
        cls.host = Host(FLAGGED)

    @classmethod
    def tearDownClass(cls):
        cls.host.cleanup()

    def shape(self, doc, command):
        self.assertEqual(list(doc), ENVELOPE + list(edda.FIELDS[command]) + ["messages"])
        self.assertEqual((doc["format"], doc["edda"], doc["command"]), (edda.FORMAT, REV, command))

    def test_check(self):
        doc = self.host.json("check", "--root", ".")
        self.shape(doc, "check")
        self.assertEqual(doc["exit"], 0)
        (p,) = doc["problems"]
        self.assertEqual(p, {"rule": "pinned_older", "file": "edda.yaml", "line": 1, "category": "out of date",
                             "sub": "pin behind", "fix": "wrong", "acts": "person", "level": "warns",
                             "where": "unknown", "found_by": "reading",
                             "message": f"edda.yaml pins revision {REV - 1}; these tools are revision {REV}"})
        self.assertEqual(doc["counts"], {"out of date": 1})
        self.assertEqual([f["file"] for f in doc["files"]], ["specs/order.edda", "specs/order.edda.vc"])
        self.assertEqual(list(doc["files"][0]), ["file", "ok", "status", "problems", "flags"])
        self.assertTrue(doc["files"][0]["ok"])
        self.assertIn("story FIX-001: draft v0", doc["files"][0]["status"])
        self.assertEqual(doc["messages"], [PINNED])     # said in plain output, so said here too

    def test_a_flag_of_the_settings_is_in_messages(self):
        for args in (("check",), ("run",), ("view",),
                     ("approve", "FIX-001", "--by", "tuan", "--at", "2026-10-05 09:00", "--dry-run")):
            doc = self.host.json(args[0], "--root", ".", *args[1:])
            self.assertEqual((doc["exit"], doc["messages"]), (0, [PINNED]), args[0])

    def test_check_refused_names_each_problem(self):
        host = Host(f"edda: {REV}\n", BROKEN)
        try:
            doc = host.json("check", "--root", ".")
            self.assertEqual(doc["exit"], 1)
            self.assertEqual({(p["rule"], p["file"], p["level"]) for p in doc["problems"]},
                             {("yaml_feature", "specs/order.edda", "blocks")})
            self.assertEqual(doc["files"][0]["problems"][0]["rule"], "yaml_feature")
        finally:
            host.cleanup()

    def test_check_model_and_graph(self):
        doc = self.host.json("check", "--root", ".", "--model")
        self.assertEqual(doc["model"]["revision"], 70)
        doc = self.host.json("check", "--root", ".", "--graph", "order.status")
        self.assertTrue(doc["graph"] and all(isinstance(s, str) for s in doc["graph"]))

    def test_run(self):
        doc = self.host.json("run", "--root", ".")
        self.shape(doc, "run")
        self.assertEqual(list(doc["stories"][0]), ["id", "status", "detail", "examples_failed", "generated"])
        self.assertEqual(doc["failures"], [])

    def test_run_failure_has_its_dimensions(self):
        out = io.StringIO()
        result = {}
        with mock.patch("run.run", return_value=[("BOX-001", "failing", "1 of 1 examples failed",
                                                  [("puts one", [("specs/order.edda:3", "n == 1", "2")])])]), \
                redirect_stdout(out):
            import run
            self.assertEqual(run.main(["--root", self.host.root], result), 1)
        (f,) = result["failures"]
        self.assertEqual((f["rule"], f["found_by"], f["level"], f["message"]),
                         ("failing_example", "example run", "blocks", "then n == 1: found 2"))
        self.assertEqual(result["stories"][0]["examples_failed"],
                         [{"title": "puts one", "failures": [{"at": "specs/order.edda:3", "then": "n == 1",
                                                              "found": "2"}]}])

    def test_run_that_stops_says_why(self):
        host = Host(f"edda: {REV}\n", BROKEN)
        try:
            doc = host.json("run", "--root", ".")
            self.assertEqual((doc["exit"], doc["stories"], doc["messages"][0]),
                             (1, [], "the spec does not check; tools/check.py says:"))
        finally:
            host.cleanup()

    def test_view(self):
        doc = self.host.json("view", "--root", ".")
        self.shape(doc, "view")
        story = next(b for b in doc["blocks"] if b["kind"] == "story")
        self.assertEqual((story["file"], story["name"]), ("order.edda", "FIX-001"))
        self.assertEqual(list(story["sentences"][0]), ["line", "kind", "shade", "text"])

    def test_approve(self):
        doc = self.host.json("approve", "FIX-001", "--by", "tuan", "--at", "2026-10-05 09:00", "--dry-run",
                             "--root", ".")
        self.shape(doc, "approve")
        self.assertEqual((doc["kind"], doc["name"], doc["number"], doc["written"], doc["refused"]),
                         ("story", "FIX-001", 1, False, None))
        self.assertTrue(doc["version"].startswith("- story: FIX-001"))
        doc = self.host.json("approve", "NOPE-1", "--by", "tuan", "--dry-run", "--root", ".")
        self.assertEqual((doc["exit"], doc["refused"], doc["messages"][-1]), (1, "unknown name: NOPE-1", "unknown name: NOPE-1"))

    def test_guide(self):
        doc = self.host.json("guide", "--pointer", "--root", ".")
        self.shape(doc, "guide")
        self.assertIn(doc["guide"], doc["pointer"])
        self.assertFalse(doc["written"])

    def test_trend_with_nothing_logged(self):
        doc = self.host.json("trend", "--root", ".", log=None)
        self.shape(doc, "trend")
        self.assertEqual((doc["total"], doc["groups"]), (0, []))

    def test_a_usage_error_is_in_messages(self):
        doc = self.host.json("view", "--root", ".", "NOPE-1")
        self.assertEqual((doc["exit"], doc["blocks"], doc["messages"][-1]), (2, [], "no such story: NOPE-1"))
        doc = self.host.json("check", "--root", ".", "--bogus")
        self.assertEqual((doc["exit"], doc["messages"]),
                         (2, ["usage: check.py [--root DIR] [--model [DIR] | --graph ENTITY.PROPERTY [DIR]]"]))


def plain_of(command, doc, root):
    """the lines the plain output prints for what doc's fields hold, as the
    tool prints them; root, the host's root (approve's history)"""
    import run
    import trend
    import view
    out = []
    count = lambda counts: [", ".join(f"{n} {c}" for c, n in counts.items())] if counts else []     # noqa: E731
    if command == "check":
        for f in doc["files"]:
            out.append(f["file"] + " " + ("OK" if f["ok"] else ""))
            out += [f"    {p['line']}: {p['rule']}: {p['message']}" for p in f["problems"]]
            out += [f"    {p['line']}: flagged: {p['rule']}: {p['message']}" for p in f["flags"]]
            out += [f"    {s}" for s in f["status"]]
        out += count(doc["counts"])
        out += json.dumps(doc["model"], indent=2).splitlines() if doc["model"] is not None else []
        out += doc["graph"] or []
    elif command == "run":
        for st in doc["stories"]:
            out.append(f"{st['id']}: {st['status']}: {st['detail']}")
            for e in st["examples_failed"]:
                out.append(f"    example {run.show(e['title'])} failed")
                out += [f"        {f['at']}: " + (f"then {f['then']}: found {f['found']}" if f["then"] else f["found"])
                        for f in e["failures"]]
            out += st["generated"]
        out += count(doc["counts"])
    elif command == "view":
        out = [view.MARK[s["shade"]] + s["text"] for b in doc["blocks"] for s in b["sentences"]]
    elif command == "approve" and doc["version"] is not None:
        out = doc["version"].splitlines()
        if doc["written"]:
            vc = os.path.join(os.path.realpath(root), doc["history"])
            out.append(f"appended {doc['kind']} {doc['name']} v{doc['number']} to {vc}")
    elif command == "guide" and doc["pointer"] is not None:
        out = [doc["pointer"]]
    elif command == "trend" and doc["log"] is not None:
        if doc["skipped"]:
            out.append(f"{doc['skipped']} lines of the log skipped: not JSON or not a valid record")
        if not doc["total"]:
            return out + trend.wrap("nothing logged yet: ", doc["log"], "  ")
        out += [f"{doc['total']} problems logged, {doc['first']} to {doc['last']}", "per day:"]
        for d in doc["per_day"]:
            out += trend.wrap(f"  {d['date']}  {d['total']:>5}  ", count(d["counts"])[0])
        out.append("by " + " x ".join(doc["by"]) + ":")
        out += trend.lines([(g["count"], " x ".join(g["values"])) for g in doc["groups"]])
        out.append("rules that come up most:")
        out += trend.lines([(r["count"], r["rule"]) for r in doc["rules"]])
    return out


class NothingDroppedTest(unittest.TestCase):
    """every line the plain output prints is in the --json document: in
    the command's fields or in messages, for every command and outcome"""

    def same(self, host, *args, log="off"):
        code, out, err = host.edda(*args, log=log)
        doc = host.json(*args, log=log)
        plain = [line for line in (out + err).splitlines() if line]
        said = [line for line in plain_of(args[0], doc, host.root) + doc["messages"] if line]
        self.assertEqual((doc["exit"], sorted(said)), (code, sorted(plain)), args)
        return code

    def test_each_command_and_outcome(self):
        ok, broken, newer = Host(FLAGGED), Host(f"edda: {REV}\n", BROKEN), Host(f"edda: {REV + 1}\n")
        try:
            dry = ("FIX-001", "--by", "tuan", "--at", "2026-10-05 09:00", "--dry-run", "--root", ".")
            seen = set()
            for host, args in (
                    (ok, ("check", "--root", ".")), (ok, ("check", "--root", ".", "--model")),
                    (ok, ("check", "--root", ".", "--graph", "order.status")), (broken, ("check", "--root", ".")),
                    (ok, ("check", "--root", ".", "--bogus")), (newer, ("check", "--root", ".")),
                    (ok, ("run", "--root", ".")), (broken, ("run", "--root", ".")),
                    (ok, ("run", "--root", ".", "--seed", "x")), (newer, ("run", "--root", ".")),
                    (ok, ("view", "--root", ".")), (broken, ("view", "--root", ".")),
                    (ok, ("view", "--root", ".", "NOPE-1")), (newer, ("view", "--root", ".")),
                    (ok, ("approve", *dry)), (ok, ("approve", "NOPE-1", *dry[1:])), (broken, ("approve", *dry)),
                    (ok, ("approve", *dry, "--at", "soon")), (newer, ("approve", *dry)),
                    (ok, ("guide", "--pointer", "--root", ".")), (ok, ("guide", "--root", ".")),
                    (ok, ("trend", "--root", ".", "--by", "colour")), (ok, ("trend", "--root", "."))):
                seen.add((args[0], self.same(host, *args)))
            self.assertEqual({c for c, _ in seen}, set(edda.COMMANDS))
            self.assertTrue({0, 1, 2, 3} <= {code for _, code in seen})
        finally:
            for h in (ok, broken, newer):
                h.cleanup()

    def test_approve_written(self):
        hosts = Host(FLAGGED), Host(FLAGGED)        # one written plain, one with --json
        try:
            args = ("approve", "FIX-001", "--by", "tuan", "--at", "2026-10-05 09:00", "--root", ".")
            code, out, err = hosts[0].edda(*args)
            doc = hosts[1].json(*args)
            self.assertTrue(doc["written"])
            self.assertEqual(sorted(plain_of("approve", doc, hosts[1].root) + doc["messages"]),
                             sorted((out + err).replace(os.path.realpath(hosts[0].root),
                                                        os.path.realpath(hosts[1].root)).splitlines()))
        finally:
            for h in hosts:
                h.cleanup()

    def test_trend_over_a_log(self):
        host = Host(FLAGGED + "problem_log: local\n")
        try:
            host.edda("check", "--root", ".", log=None)
            with open(os.path.join(host.root, ".edda", "checks.log"), "a") as f:
                f.write("not json\n")
            for by in ("category", "where,fix"):
                self.assertEqual(self.same(host, "trend", "--root", ".", "--by", by, log=None), 0)
        finally:
            host.cleanup()


if __name__ == "__main__":
    unittest.main()
