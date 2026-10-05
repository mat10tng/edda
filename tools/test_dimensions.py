#!/usr/bin/env python3
"""Problem dimensions and watching (reference section 11, revision 67).

    python3 tools/test_dimensions.py

Every rule of the registry has its four fixed dimensions with allowed
values, and every rule the checker raises on the fixtures is one of
them. Where in the spec is computed for problems in each place, and is
unknown where it cannot be told; a # edda: language comment re-tags a
problem. The count line, the log line's format, the log turned off, a
log that cannot be written (the output and exit code unchanged), a
runner failure counted and logged, and trend.py grouping by one
dimension and by two. No test writes into the repository: the log is
off or in a temporary folder.
"""
import contextlib
import glob
import io
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["EDDA_LOG"] = "off"     # the tools and their children never write the log (section 11)
import check                       # noqa: E402
import edda_binding as binding     # noqa: E402
import run                         # noqa: E402
import trend                       # noqa: E402
import watch                       # noqa: E402
from test_generate import BOX, put_one_more     # noqa: E402

ROOT = check.ROOT
CHECK = os.path.join(ROOT, "tools", "check.py")

SPEC = """\
roles:
  clerk:
    is: "a person at the counter"
epics:
  EP-001: "parts"
entities:
  box:
    is: "a box of parts"
    properties:
      count: INTEGER
      kind: DEFAULT small | large
    may_change:
      kind: {small: [large]}
    always:
      - "count >= 0"
    may_read: [{role: clerk}]
stories:
  BOX-001:
    story: "fill a box"
    about: box
    as_a: clerk
    i_want: "to put parts in a box"
    so_that: "the parts are kept"
    rules:
      - rule: "a put adds"
        shown_by:
          - "parts are put"
    operations:
      put:
        is: "puts parts in a box"
        inputs: {box: box, n: INTEGER}
        who: [{role: clerk}]
        refuse:
          - when: "n <= 0"
            reason: "nothing to put"
        ensure:
          - "box.count == OLD(box.count) + n"   # edda: language
      size:
        is: "the parts in a box"
        inputs: {box: box}
        who: [{role: clerk}]
        returns: "box.count"
    examples:
      "parts are put":
        given:
          - box: b
            with: {count: 1}
        steps:
          - when: {actor: ann, call: "put(b, 3)"}
            then: [DONE]
"""


BLOCK_ENTITY = """\
  box:
    is: "a box of parts"
    properties:
      count: INTEGER
      kind: DEFAULT small | large
    may_change:
      kind: {small: [large]}
    always:
      - "count >= 0"
    may_read: [{role: clerk}]
"""
FLOW_ENTITY = """\
  box: {is: "a box of parts", properties: {count: INTEGER, kind: DEFAULT small | large}, may_read: [{role: clerk}]}
"""
BLOCK_OPERATION = """\
      size:
        is: "the parts in a box"
        inputs: {box: box}
        who: [{role: clerk}]
        returns: "box.count"
"""
FLOW_OPERATION = """\
      size: {is: "the parts in a box", inputs: {box: box}, who: [{role: clerk}], returns: "box.count"}
"""


def line_of(text, needle):
    """the line of the first line of text holding needle"""
    return next(i for i, s in enumerate(text.splitlines(), 1) if needle in s)


class RegistryTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.rules, cls.allowed = watch.registry()

    def test_every_rule_has_four_allowed_dimensions(self):
        self.assertEqual(len(self.rules), 46)     # revision 68 adds the five of the settings
        names = {"category": "category", "fix": "fix", "acts": "acts", "level": "level"}
        for rule, dims in self.rules.items():
            self.assertEqual(set(dims), set(watch.FIXED), rule)
            for d, values in names.items():
                self.assertIn(dims[d], self.allowed[values], f"{rule} {d}")
            self.assertTrue(dims["sub"], rule)

    def test_the_allowed_values(self):
        self.assertEqual(self.allowed["category"], [
            "unreadable", "unknown word", "wrong kind", "misplaced", "contradiction", "weak check",
            "out of date", "code differs"])
        self.assertEqual(self.allowed["fix"], ["missing", "wrong", "extra"])
        self.assertEqual(self.allowed["acts"], ["agent", "person", "language"])
        self.assertEqual(self.allowed["level"], ["blocks", "warns", "note"])
        self.assertIn("unknown", self.allowed["where"])
        self.assertEqual(len(self.allowed["where"]), 16)
        self.assertEqual(self.allowed["found_by"], [
            "reading", "history", "analyser", "example run", "generated case", "person review"])

    def test_refusals_block_and_flags_warn(self):
        import yaml
        with open(os.path.join(ROOT, "language", "keywords.yaml")) as f:
            k = yaml.safe_load(f)
        self.assertEqual({r["level"] for r in k["refusals"]}, {"blocks"})
        self.assertEqual({r["level"] for r in k["flags"]}, {"warns"})
        self.assertEqual([(r["rule"], r["level"]) for r in k["failures"]],
                         [("failing_example", "blocks"), ("failing_case", "blocks")])

    def test_the_note_s_table(self):
        self.assertEqual(self.rules["dead_refusal"], {"category": "contradiction", "sub": "refusals",
                                                      "fix": "extra", "acts": "person", "level": "warns"})
        self.assertEqual(self.rules["missing_key"]["fix"], "missing")
        self.assertEqual(self.rules["no_story"]["category"], "code differs")

    def test_every_rule_the_fixtures_raise_is_in_the_registry(self):
        raised = set()
        for folder in sorted(glob.glob(os.path.join(ROOT, "fixtures", "*"))):
            P = check.project_of(folder)
            for path in sorted(glob.glob(f"{folder}/*.edda") + glob.glob(f"{folder}/*.edda.vc")):
                raised |= {r for layer in check.check(path, P) for r, _, _ in layer}
            L = None if any(any(check.check(p, P)[:4]) for p in glob.glob(f"{folder}/*.edda")) else check.links_of(folder, P)
            raised |= {r for _, refusals, flags in (L[0] if L else []) for r, _, _ in refusals + flags}
        self.assertTrue(raised)
        self.assertEqual(raised - set(self.rules), set())


class WhereTest(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "box.edda")
        with open(self.path, "w") as f:
            f.write(SPEC)

    def tearDown(self):
        self.dir.cleanup()

    def where(self, needle):
        return watch.where(self.path, line_of(SPEC, needle), check.load)

    def test_each_place(self):
        want = {
            "    is: \"a person": "role",
            "count: INTEGER": "entity property",
            "kind: {small": "status rules",
            "\"count >= 0\"": "always",
            "may_read:": "permissions",
            "  BOX-001:": "story",
            "i_want:": "story",
            "- rule: \"a put adds\"": "story rules",
            "who: [{role: clerk}]": "operation who",
            "when: \"n <= 0\"": "refuse",
            "OLD(box.count)": "ensure",
            "returns:": "returns",
            "- box: b": "example given",
            "call: \"put(b, 3)\"": "example step",
        }
        self.assertEqual({n: self.where(n) for n in want}, want)

    def test_unknown_where_it_cannot_be_told(self):
        for needle in ("EP-001", "  box:\n", "      put:", "inputs: {box", "\"parts are put\":"):
            needle = needle.rstrip("\n")
            self.assertEqual(self.where(needle), "unknown", needle)
        self.assertEqual(watch.where(self.path, None, check.load), "unknown")
        bad = os.path.join(self.dir.name, "bad.edda")
        with open(bad, "w") as f:
            f.write("roles: [\n")
        self.assertEqual(watch.where(bad, 1, check.load), "unknown")

    def test_a_block_in_flow_form_is_unknown(self):
        """a line that holds keys of several places, or of a place and of
        none, names no place; the same block one key per line still does"""
        flow = SPEC.replace(BLOCK_ENTITY, FLOW_ENTITY).replace(BLOCK_OPERATION, FLOW_OPERATION)
        path = os.path.join(self.dir.name, "flow.edda")
        with open(path, "w") as f:
            f.write(flow)
        (rule, line, _), = [p for layer in check.check(path, check.project_of(self.dir.name)) for p in layer
                            if p[0] == "yaml_feature" and p[1] == line_of(flow, "  box: {")]
        self.assertEqual(watch.where(path, line, check.load), "unknown")
        self.assertEqual(watch.where(path, line_of(flow, "      size: {"), check.load), "unknown")
        self.assertEqual([self.where(n) for n in ("count: INTEGER", "may_read:", "returns:")],
                         ["entity property", "permissions", "returns"])

    def test_history_and_code(self):
        self.assertEqual(watch.where("x/order.edda.vc", 3, check.load), "history")
        self.assertEqual(watch.where("x/order.links", 3, check.load), "code")
        self.assertEqual(watch.where("x/code.py", 3, check.load), "code")

    def test_fixture_problems(self):
        def at(folder, name):
            path = os.path.join(ROOT, "fixtures", folder, name)
            (rule, line, _), = [p for layer in check.check(path, check.project_of(os.path.dirname(path))) for p in layer]
            return rule, watch.where(path, line, check.load)
        self.assertEqual(at("wider_than_entity", "order.edda"), ("wider_than_entity", "operation who"))
        self.assertEqual(at("unreachable_choice", "order.edda"), ("unreachable_choice", "entity property"))
        self.assertEqual(at("derived_in_given", "order.edda"), ("derived_in_given", "example given"))
        self.assertEqual(at("not_ordered", "order.edda"), ("not_ordered", "example step"))
        self.assertEqual(at("bad_pin", "order.edda.vc"), ("bad_pin", "history"))
        self.assertEqual(at("no_example", "order.edda"), ("no_example", "story"))

    def test_a_person_re_tags_one_problem_as_language(self):
        tagged = watch.problem("conflicting_ensure", self.path, line_of(SPEC, "OLD(box.count)"), "analyser",
                               self.dir.name, check.load)
        plain = watch.problem("conflicting_ensure", self.path, line_of(SPEC, "\"count >= 0\""), "analyser",
                              self.dir.name, check.load)
        self.assertEqual((tagged["acts"], plain["acts"]), ("language", "person"))
        self.assertEqual(tagged["file"], "box.edda")

    def test_found_by(self):
        self.assertEqual([watch.found_by(r) for r in ("unknown_name", "bad_pin", "dead_refusal", "no_story")],
                         ["reading", "history", "analyser", "reading"])


def problem(rule, category):
    return {"rule": rule, "category": category}


class CountTest(unittest.TestCase):

    def test_one_count_per_category_in_the_registry_s_order(self):
        problems = [problem("empty_ensure", "weak check")] + [problem("dead_refusal", "contradiction")] * 3
        self.assertEqual(watch.count_line(problems), "3 contradiction, 1 weak check")

    def test_nothing_when_there_are_none(self):
        self.assertIsNone(watch.count_line([]))


class LogTest(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.spec = os.path.join(self.dir.name, "box.edda")
        with open(self.spec, "w") as f:
            f.write(SPEC)
        self.problems = [watch.problem("dead_refusal", self.spec, line_of(SPEC, "when: \"n <= 0\""), "analyser",
                                       self.dir.name, check.load)]

    def tearDown(self):
        os.environ["EDDA_LOG"] = "off"
        self.dir.cleanup()

    def test_one_json_line_per_problem(self):
        to = os.path.join(self.dir.name, "logs", "checks.log")
        os.environ["EDDA_LOG"] = to
        watch.log(self.problems * 2, self.dir.name)
        with open(to) as f:
            lines = [json.loads(s) for s in f]
        self.assertEqual(len(lines), 2)
        self.assertEqual(list(lines[0]), list(watch.FIELDS))
        self.assertRegex(lines[0]["date"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d$")
        del lines[0]["date"]
        self.assertEqual(lines[0], {
            "rule": "dead_refusal", "file": "box.edda", "line": line_of(SPEC, "when: \"n <= 0\""),
            "category": "contradiction", "sub": "refusals", "fix": "extra", "acts": "person", "level": "warns",
            "where": "refuse", "found_by": "analyser", "commit": "none"})

    def test_the_default_place_and_the_commit_in_git(self):
        os.environ.pop("EDDA_LOG")
        self.assertEqual(watch.log_file("/p"), os.path.join("/p", ".edda", "checks.log"))
        self.assertRegex(watch.commit(ROOT), r"^[0-9a-f]{4,}$")
        self.assertEqual(watch.commit(self.dir.name), "none")

    def test_off_or_no_problems_writes_nothing(self):
        os.environ["EDDA_LOG"] = "off"
        watch.log(self.problems, self.dir.name)
        os.environ.pop("EDDA_LOG")
        watch.log([], self.dir.name)
        self.assertEqual(os.listdir(self.dir.name), ["box.edda"])

    def test_a_log_that_cannot_be_written_changes_nothing(self):
        def plain(log):
            env = dict(os.environ, EDDA_LOG=log)
            p = subprocess.run([sys.executable, CHECK], cwd=ROOT, capture_output=True, text=True, env=env)
            return p.returncode, p.stdout, p.stderr
        locked = os.path.join(self.dir.name, "locked")
        os.mkdir(locked)
        os.chmod(locked, stat.S_IRUSR | stat.S_IXUSR)
        try:
            off, blocked = plain("off"), plain(os.path.join(locked, "sub", "checks.log"))
        finally:
            os.chmod(locked, stat.S_IRWXU)
        self.assertEqual(blocked, off)
        self.assertEqual(off[0], 0)
        self.assertEqual(off[1].splitlines()[-1], "6 out of date, 18 code differs")
        self.assertEqual(os.listdir(locked), [])


class RunnerTest(unittest.TestCase):
    """a runner failure is counted and logged, with where and found by"""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.specs = os.path.join(self.dir.name, "specs")
        os.mkdir(self.specs)
        with open(os.path.join(self.specs, "box.edda"), "w") as f:
            f.write(BOX)
        binding.ENTITIES["box"] = lambda name, values, workdir: binding.Thing("box", values)
        binding.OPERATIONS.update({"put": put_one_more, "size": lambda actor, box: box.count})

    def tearDown(self):
        del binding.ENTITIES["box"]
        for name in ("put", "size"):
            del binding.OPERATIONS[name]
        os.environ["EDDA_LOG"] = "off"
        self.dir.cleanup()

    def main(self, log):
        os.environ["EDDA_LOG"] = log
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = run.main(["--project", self.specs, "BOX-001"])
        return code, out.getvalue()

    def test_failure_counted_and_logged(self):
        to = os.path.join(self.dir.name, "checks.log")
        code, out = self.main(to)
        self.assertEqual((code, out.splitlines()[-1]), (1, "1 code differs"))
        with open(to) as f:
            (p,), = [[json.loads(s) for s in f]]
        self.assertEqual((p["rule"], p["file"], p["where"], p["found_by"], p["level"]),
                         ("failing_example", os.path.join("specs", "box.edda"), "ensure", "example run", "blocks"))
        self.assertEqual(p["line"], line_of(BOX, "OLD(box.count) + n"))
        self.assertEqual(self.main(os.path.join(self.dir.name, "box.edda", "no")), (code, out))   # unwritable

    def test_a_failing_generated_case_is_logged(self):
        with open(os.path.join(self.specs, "edda.yaml"), "w") as f:
            f.write("generated_cases: {on: true, runs: 30, steps: 6}\n")
        to = os.path.join(self.dir.name, "checks.log")
        os.environ["EDDA_LOG"] = to
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = run.main(["--project", self.specs, "--seed", "3", "BOX-001"])
        with open(to) as f:
            rules = [(p["rule"], p["found_by"], p["where"]) for p in map(json.loads, f)]
        self.assertEqual(code, 1)
        self.assertIn(("failing_case", "generated case", "ensure"), rules)
        self.assertEqual(out.getvalue().splitlines()[-1], f"{len(rules)} code differs")


VALID = {"date": "2026-10-01T09:00:00+02:00", "rule": "dead_refusal", "file": "specs/box.edda", "line": 3,
         "category": "contradiction", "sub": "refusals", "fix": "extra", "acts": "person", "level": "warns",
         "where": "refuse", "found_by": "analyser", "commit": "6aeeefd"}
LOG = [
    VALID,
    dict(VALID, rule="no_example", category="weak check", sub="no example", fix="missing", acts="agent",
         where="story", line=None),
    dict(VALID, date="2026-10-02T09:00:00+02:00"),
]
BAD = [
    dict(VALID, date=None), dict(VALID, category=[]), dict(VALID, line="3"), dict(VALID, line=True),
    dict(VALID, line=0), dict(VALID, rule=7), dict(VALID, commit=None), dict(VALID, category="typo"),
    dict(VALID, where="nowhere"), dict(VALID, found_by="guess"), dict(VALID, sub="nothing"),
    dict(VALID, level={"x": 1}), dict(VALID, date="2026-10-01"), dict(VALID, date="2026-13-01T09:00:00+02:00"),
    {k: v for k, v in VALID.items() if k != "acts"}, [VALID], "a text", 3, None,
]


class TrendTest(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.log = os.path.join(self.dir.name, "checks.log")
        with open(self.log, "w") as f:
            for p in LOG:
                f.write(json.dumps(p) + "\n")
            f.write("not json\n")

    def tearDown(self):
        self.dir.cleanup()

    def trend(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = trend.main(["--log", self.log, *args])
        return code, out.getvalue().splitlines()

    def test_by_one_dimension(self):
        code, out = self.trend()
        self.assertEqual(code, 0)
        self.assertEqual(out, [
            "1 lines of the log skipped: not JSON or not a valid record",
            "3 problems logged, 2026-10-01 to 2026-10-02",
            "",
            "per day:",
            "  2026-10-01      2  1 contradiction, 1 weak check",
            "  2026-10-02      1  1 contradiction",
            "",
            "by category:",
            "  2  contradiction",
            "  1  weak check",
            "",
            "rules that come up most:",
            "  2  dead_refusal",
            "  1  no_example"])

    def test_by_a_pair(self):
        code, out = self.trend("--by", "where,fix", "--top", "1")
        i = out.index("by where x fix:")
        self.assertEqual(out[i + 1:i + 3], ["  2  refuse x extra", "  1  story x missing"])
        self.assertEqual(out[-2:], ["rules that come up most:", "  2  dead_refusal"])
        self.assertTrue(all(len(s) < 80 for s in out))

    def test_bad_records_are_skipped_and_counted(self):
        """null, list, wrong-type and out-of-set values: each such record is
        skipped and counted, and the valid records still report"""
        with open(self.log, "a") as f:
            for p in BAD:
                f.write(json.dumps(p) + "\n")
        code, out = self.trend()
        self.assertEqual(code, 0)
        self.assertEqual(out[:2], [f"{len(BAD) + 1} lines of the log skipped: not JSON or not a valid record",
                                   "3 problems logged, 2026-10-01 to 2026-10-02"])
        self.assertEqual([trend.valid(p) for p in LOG], [True] * 3)

    def test_no_line_is_cut(self):
        """all eight categories on one day, and two long rule names (one in
        words, one with no space): every category and every character
        reaches the output, over indented lines, none past 79 characters"""
        categories = watch.registry()[1]["category"]
        in_words = " ".join(["a rule in words"] * 8)
        one_word = "a_rule_" + "x" * 100
        with open(self.log, "a") as f:
            for c in categories:
                f.write(json.dumps(dict(VALID, date="2026-10-03T09:00:00+02:00", category=c)) + "\n")
            for rule in (in_words, one_word):
                f.write(json.dumps(dict(VALID, rule=rule)) + "\n")
        code, out = self.trend("--by", "where,found_by")
        self.assertEqual(code, 0)
        self.assertEqual([s for s in out if len(s) > 79], [])
        i = out.index("  2026-10-03      8  1 unreadable, 1 unknown word, 1 wrong kind, 1 misplaced,")
        self.assertEqual(out[i + 1:i + 3], ["                     1 contradiction, 1 weak check, 1 out of date,",
                                            "                     1 code differs"])
        self.assertEqual(" ".join(s[21:] for s in out[i:i + 3]),
                         ", ".join(f"1 {c}" for c in categories))
        i = out.index("rules that come up most:")
        self.assertEqual(out[i + 2:i + 6], [
            "   1  a rule in words a rule in words a rule in words a rule in words a rule in",
            "      words a rule in words a rule in words a rule in words",
            "   1  " + one_word[:73],
            "      " + one_word[73:]])

    def test_a_wrong_dimension(self):
        self.assertEqual(self.trend("--by", "colour")[0], 2)
        self.assertEqual(self.trend("--by", "where,fix,acts")[0], 2)


if __name__ == "__main__":
    unittest.main()
