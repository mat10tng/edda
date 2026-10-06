#!/usr/bin/env python3
"""Generated cases (reference section 9), on a small box project of its
own.

    python3 tools/test_generate.py

Code that breaks the spec's refusal only for one edge value (the 10 of
"n > 10") is found, shrunk to one step from the smallest world, and
printed as an example ready to paste, with the broken rule and the
seed and what was skipped; the same seed prints the same thing again;
in a story with rules:, the printed example says where its title goes,
and pasted, it checks and fails at the same rule. Code that keeps the
spec passes every run and says how many calls of each operation ran.
Records reached through other records at any depth are inputs; a story
whose runs called nothing is not run, never passed; an optional
reference with nothing to point at is left out, an entity whose
required one has none is skipped and listed; a date-only time is a
time. What the binding cannot give (an unbound property, an unset
value) leaves the story not run when met in the starting world and
skips the operation when met in a step, never a crash, unless another
rule of that step fails: the failure is reported, the rule that could
not be judged listed beside it, whether it is an OLD value, a computed
property the frame rule reads, a refuse condition, or the code's own
unset read after a failure was found; a read whose returns or
ordered_by breaks a rule after its refuse did keeps both; a change that
computed property could name, directly or through another, is not
judged, one outside what it could name still fails, and examples judge
it as before; a later refuse condition that holds is still due, and a
reason no condition gives still fails; optional and
MANY inputs with nothing to point at do not block an operation; edge
values read a literal with its sign; a failure prints its full replay
command, which, run as printed or as ./edda run, gives the same run,
failed or passed, in another process under another PYTHONHASHSEED; a
shrink cut short by its time limit says so; whatever fails at a run's
setup, in it or at its cleanup, Hypothesis's source constants, the
clock and the runner's flags are left as they were. A run is its
seed's, spec's and code's alone: code loaded that no story runs leaves
it as it was, so the counts of calls below move only when the seed,
the spec or what the code does moves.
With the setting off, or no edda.yaml, the runner never imports
Hypothesis and runs without it; with the setting on and Hypothesis
missing it exits 3 with one line. A settings file that breaks its
shape, its root no mapping or a count no whole number of at least 1,
is refused at its line, in the checker's words.
"""
import contextlib
import datetime
import io
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["EDDA_LOG"] = "off"     # the tools and their children never write the log (section 11)
import edda_binding as binding   # noqa: E402
import run                       # noqa: E402
import generate                  # noqa: E402
from hypothesis import configuration                                 # noqa: E402
from hypothesis.internal.conjecture import engine, providers         # noqa: E402
from hypothesis.internal.constants_ast import Constants              # noqa: E402

TOOLS = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.relpath(os.path.join(TOOLS, "run.py"))    # as the replay command names it

BOX = """\
roles:
  clerk:
    is: "a person at the counter"
entities:
  box:
    is: "a box of parts"
    properties:
      count: INTEGER
      label: TEXT, OPTIONAL
      kind: DEFAULT small | large
    always:
      - "count >= 0"
    may_read: [{role: clerk}]
    may_update: [{role: clerk}]
stories:
  BOX-001:
    story: "fill a box"
    about: box
    as_a: clerk
    i_want: "to put parts in a box"
    so_that: "the parts are kept"
    operations:
      put:
        is: "puts parts in a box"
        inputs: {box: box, n: INTEGER}
        who: [{role: clerk}]
        refuse:
          - when: "n <= 0"
            reason: "nothing to put"
          - when: "n > 10"
            reason: "too many at once"
        ensure:
          - "box.count == OLD(box.count) + n"
      size:
        is: "the parts in a box"
        inputs: {box: box}
        who: [{role: clerk}]
        returns: "box.count"
      stamp:
        is: "stamps a box"
        inputs: {box: box}
        who: [{role: clerk}]
        ensure:
          - "box.label == \\"stamped\\""
    examples:
      "parts are put in a box":
        given:
          - actor: ann
            with: {roles: [clerk]}
          - box: b
            with: {count: 1}
        steps:
          - when: {actor: ann, call: "put(b, 3)"}
            then: [DONE, "b.count == 4"]
"""


HOLDER = """\
      holder:
        is: "the box that holds the parts"
        inputs: {box: box}
        who: [{role: clerk}]
        returns: "box"
"""


PICK = """\
      pick:
        is: "the box, when it has parts"
        inputs: {box: box}
        who: [{role: clerk}]
        refuse:
          - when: "size(box) < 0"
            reason: "no parts"
        returns: "holder(box)"
      line_up:
        is: "the box, in a list"
        inputs: {box: box}
        who: [{role: clerk}]
        refuse:
          - when: "size(box) < 0"
            reason: "no parts"
        returns: "[box]"
        ordered_by: ["holder(box).count"]
"""


def put(actor, box, n):         # keeps the spec
    if n <= 0:
        raise binding.Refused("nothing to put")
    if n > 10:
        raise binding.Refused("too many at once")
    box.count += n


def put_one_more(actor, box, n):     # keeps the refusals, adds one too many
    put(actor, box, n)
    box.count += 1


def size_closed(actor, box):      # refuses when read inside a fact, which its spec does not allow
    if actor is None:
        raise binding.Refused("closed")
    return box.count


def holder_closed(actor, box):    # the same
    if actor is None:
        raise binding.Refused("closed")
    return box


def put_off_by_one(actor, box, n):     # refuses 10, which the spec allows
    if n <= 0:
        raise binding.Refused("nothing to put")
    if n >= 10:
        raise binding.Refused("too many at once")
    box.count += n


ON = "generated_cases: {on: true, runs: 30, steps: 6}\n"

BOUND = """\
import sys
sys.path.insert(0, {tools!r})
import edda_binding as binding


def put(actor, box, n):
    if n <= 0:
        raise binding.Refused("nothing to put")
    if n {over} 10:
        raise binding.Refused("too many at once")
    box.count += n


binding.ENTITIES["box"] = lambda name, values, workdir: binding.Thing("box", values)
binding.OPERATIONS.update({{"put": put, "size": lambda actor, box: box.count}})
"""     # sitecustomize.py for a child process: the box binding, put kept (>) or off by one (>=)

RULES = """\
    rules:
      - rule: "a put adds the parts it is given"
        shown_by:
          - "parts are put in a box"
"""


class GeneratedTest(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.write("box.edda", BOX)
        self.write("edda.yaml", ON)
        binding.ENTITIES["box"] = lambda name, values, workdir: binding.Thing("box", values)
        binding.OPERATIONS.update({"put": put, "size": lambda actor, box: box.count})

    def tearDown(self):
        del binding.ENTITIES["box"]
        for name in ("put", "size", "holder"):
            binding.OPERATIONS.pop(name, None)
        self.dir.cleanup()

    def write(self, name, text):
        with open(os.path.join(self.dir.name, name), "w") as f:
            f.write(text)

    def main(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = run.main(["--project", self.dir.name, *args])
        return code, out.getvalue()

    def test_code_that_keeps_the_spec_passes_every_run(self):
        code, out = self.main("--seed", "3")
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines(), [
            "BOX-001: examples passed: all 1",
            "BOX-001: generated cases: 30 runs passed; calls: put 101, size 76; skipped stamp: no binding for stamp"])

    def test_an_edge_value_that_breaks_a_refusal_is_found_and_shrunk(self):
        binding.OPERATIONS["put"] = put_off_by_one
        code, out = self.main("--seed", "3")
        put_line = BOX.splitlines().index("      put:") + 1
        self.assertEqual(code, 1)
        self.assertEqual(out.splitlines(), [
            "BOX-001: examples passed: all 1",
            "BOX-001: generated cases: failed (seed 3); skipped stamp: no binding for stamp",
            f"    replay: python3 {RUN} --project {self.dir.name} --seed 3",
            f'    {os.path.relpath(self.dir.name)}/box.edda:{put_line}: put refused: "too many at once", '
            "but the spec does not refuse",
            "    as an example:",
            '      "generated: put breaks a rule":',
            "        given:",
            "          - actor: clerk_1",
            "            with: {roles: [clerk]}",
            "          - box: box_1",
            "            with: {count: 0, kind: small}",
            "        steps:",
            '          - when: {actor: clerk_1, call: "put(box_1, 10)"}',
            "            then: [DONE]",
            "1 code differs"])

    def test_the_seed_replays_the_same_run(self):
        binding.OPERATIONS["put"] = put_off_by_one
        self.assertEqual(self.main("--seed", "11"), self.main("--seed", "11"))

    def runs(self):
        """a failed run, as printed, and passed ones, with their counts;
        seed 5's moved with the code loaded before revision 76"""
        binding.OPERATIONS["put"] = put_off_by_one
        failed = self.main("--seed", "11")
        binding.OPERATIONS["put"] = put
        return failed, self.main("--seed", "3"), self.main("--seed", "5")

    def test_an_unrelated_edit_leaves_the_run_as_it_was(self):
        before = self.runs()
        with tempfile.TemporaryDirectory() as d:     # code no story runs, full of literals, loaded with the binding
            with open(os.path.join(d, "unrelated_code.py"), "w") as f:
                f.write("".join(f"def unused_{i}(n):\n"
                                f"    return n * {i * 37 % 2001 - 1000} + len({'abc '[i % 4] * (i % 4)!r})\n"
                                for i in range(60)))
            sys.path.insert(0, d)
            try:
                import unrelated_code
                binding.unused = unrelated_code
                after = self.runs()
            finally:
                sys.path.remove(d)
                del sys.modules["unrelated_code"], binding.unused
        self.assertIn("generated cases: failed (seed 11)", before[0][1])
        self.assertEqual(before, after)

    def child(self, argv, over, hash_seed):
        """(exit code, output) of the real command argv in a fresh process
        under hash_seed, with the box binding loaded first, put kept (>)
        or off by one (>=)"""
        with tempfile.TemporaryDirectory() as site:
            with open(os.path.join(site, "sitecustomize.py"), "w") as f:
                f.write(BOUND.format(tools=TOOLS, over=over))
            p = subprocess.run([sys.executable, *argv], capture_output=True, text=True,
                               env=dict(os.environ, PYTHONPATH=site, PYTHONHASHSEED=hash_seed))
        self.assertEqual(p.stderr, "")
        return p.returncode, p.stdout

    def test_the_printed_replay_gives_the_same_run_in_another_process(self):
        binding.OPERATIONS["put"] = put_off_by_one
        failed = self.main("--seed", "11")
        binding.OPERATIONS["put"] = put
        passed = self.main("--seed", "3")
        replay = next(line for line in failed[1].splitlines() if line.startswith("    replay: "))
        printed = shlex.split(replay[len("    replay: "):])
        self.assertEqual(printed[0], "python3")
        edda = [os.path.join(os.path.dirname(TOOLS), "edda"), "run", "--project", self.dir.name]
        for hash_seed in ("0", "4242"):
            self.assertEqual(self.child(printed[1:], ">=", hash_seed), failed)
            self.assertEqual(self.child(edda + ["--seed", "11"], ">=", hash_seed), failed)
            self.assertEqual(self.child(edda + ["--seed", "3"], ">", hash_seed), passed)

    def state(self):
        """what a generated run changes for the whole process"""
        return (providers._get_local_constants, run.NOW[0], run.UNSET_ENDS[0], run.REAL_FUNCTIONS[0],
                list(run.GIVENS), list(run.REAL_CALLS), getattr(configuration, "__hypothesis_home_directory"))

    def test_what_a_run_changes_is_undone_whatever_fails(self):
        seen, home = [], []

        def watched(*args):
            before = self.state()
            try:
                return cases(*args)
            finally:
                seen.append((before, self.state()))
        cases = generate.cases

        def clock_at(when):     # the clock hook, failing at the setup (call 1) or the reset (2) of a generated run
            calls = []

            def hook(now):
                if run.UNSET_ENDS[0]:
                    calls.append(now)
                    if len(calls) == when:
                        raise RuntimeError(f"clock call {when}")
            return hook

        class Folder(tempfile.TemporaryDirectory):   # the first made is Hypothesis's home
            def __init__(self):
                super().__init__()
                home.append(self)

            def cleanup(self):
                super().cleanup()
                if self is home[0]:
                    raise OSError("cleanup")

        def crash(actor, box, n):     # in a generated run only: the example keeps passing
            if run.UNSET_ENDS[0]:
                raise run.EddaError("body")
            put(actor, box, n)
        faults = {"clock setup": (RuntimeError, mock.patch.object(binding, "clock", clock_at(1))),
                  "body": (None, mock.patch.dict(binding.OPERATIONS, put=crash)),
                  "clock reset": (RuntimeError, mock.patch.object(binding, "clock", clock_at(2))),
                  "folder cleanup": (OSError, mock.patch.object(generate, "tempfile",
                                                                mock.Mock(TemporaryDirectory=Folder)))}
        for name, (raised, fault) in faults.items():
            with self.subTest(name), mock.patch.object(generate, "cases", watched), fault:
                seen.clear()
                home.clear()
                if raised:
                    self.assertRaises(raised, self.main, "--seed", "3")
                else:
                    self.assertEqual(self.main("--seed", "3")[0], 3)
                self.assertEqual(len(seen), 1)
                self.assertEqual(seen[0][1], seen[0][0])
        self.assertIsNot(providers._get_local_constants, Constants)

    def test_a_shrink_cut_short_by_its_time_limit_says_so(self):
        binding.OPERATIONS["put"] = put_off_by_one
        with mock.patch.object(engine, "MAX_SHRINKING_SECONDS", 0):
            code, out = self.main("--seed", "3")
        self.assertEqual(code, 1)
        self.assertEqual(out.splitlines()[3],
                         "    shrinking stopped on its time limit; replay may end on a different example")

    def test_a_world_that_breaks_an_always_rule_is_thrown_away(self):
        seen = []

        def put_seen(actor, box, n):
            seen.append(box.count)
            put(actor, box, n)
        binding.OPERATIONS["put"] = put_seen
        self.assertEqual(self.main("--seed", "5")[0], 0)
        self.assertTrue(seen)
        self.assertGreaterEqual(min(seen), 0)

    def test_a_pasted_failure_in_a_story_with_rules_checks_and_fails_at_the_same_rule(self):
        self.write("box.edda", BOX.replace("    operations:\n", RULES + "    operations:\n", 1))
        binding.OPERATIONS["put"] = put_off_by_one
        code, out = self.main("--seed", "3")
        lines = out.splitlines()
        self.assertEqual(code, 1)
        self.assertEqual(lines[-3:], [
            '    and under the shown_by: of the rule "a put adds the parts it is given":',
            '          - "generated: put breaks a rule"',
            "1 code differs"])
        example = lines[lines.index("    as an example:") + 1:-3]
        pasted = BOX.replace("    operations:\n", RULES + lines[-2] + "\n" + "    operations:\n", 1)
        pasted = pasted.replace("    examples:\n", "    examples:\n" + "\n".join(example) + "\n", 1)
        self.write("box.edda", pasted)
        self.write("edda.yaml", "generated_cases: {on: false}\n")
        code, again = self.main()
        put_line = pasted.splitlines().index("      put:") + 1     # one lower: the shown_by line above it
        self.assertEqual((code, again.splitlines()), (1, [
            "BOX-001: failing: 1 of 2 examples failed",
            '    example "generated: put breaks a rule" failed',
            "        " + lines[3].strip().replace(f"box.edda:{put_line - 1}:", f"box.edda:{put_line}:"),
            "1 code differs"]))

    def test_skips_are_listed_when_no_world_keeps_the_always_rules(self):
        self.write("box.edda", BOX.replace('"count >= 0"', '"count > count"'))
        self.assertEqual(self.main("--seed", "3")[1].splitlines()[-2:],
                         ["BOX-001: generated cases: not run: no starting world keeps every always-rule; "
                          "skipped stamp: no binding for stamp", "1 code differs"])

    def test_malformed_settings_are_refused(self):
        self.write("edda.yaml", "generated_cases:\n  on: yes\n  runs: 0\n  wobble: 1\n")
        code, out = self.main()
        path = os.path.relpath(os.path.join(self.dir.name, "edda.yaml"))
        self.assertEqual((code, out.splitlines()), (1, [
            "the settings do not check:",
            f"    {path}:2: wrong_type: on must be a yes/no",
            f"    {path}:4: unknown_key: unknown key: wobble"]))
        for runs in ("0", "-1", "1.0", "true"):
            self.write("edda.yaml", f"generated_cases: {{on: true, runs: {runs}}}\n")
            self.assertEqual(self.main(), (1, "the settings do not check:\n"
                                           f"    {path}:1: wrong_type: runs must be a whole number of at least 1\n"))
        self.write("edda.yaml", "generated_cases:\n  on: true\n  steps: 2.5\n")
        self.assertEqual(self.main()[1].splitlines()[1], f"    {path}:3: wrong_type: steps must be a whole number of at least 1")
        for root in ("false", "0", "[]", "[generated_cases]", ""):
            self.write("edda.yaml", root + "\n")
            self.assertEqual(self.main(), (1, f"the settings do not check:\n    {path}:1: wrong_type: file must be a mapping\n"),
                             root)

    def test_what_the_binding_cannot_give_in_the_starting_world_is_not_run(self):
        self.write("box.edda", BOX.replace("      kind: DEFAULT small | large\n",
                                           "      kind: DEFAULT small | large\n      weight: INTEGER, DERIVED\n")
                   .replace('"count >= 0"', '"weight >= 0"'))
        self.assertEqual(self.main("--seed", "3")[1].splitlines()[-1],
                         "BOX-001: generated cases: not run: no binding for box.weight; "
                         "skipped stamp: no binding for stamp")
        binding.VALUES["box"] = {"count": [1, 2]}       # label left unset: no value space gives it
        try:
            self.write("box.edda", BOX.replace("label: TEXT, OPTIONAL", "label: TEXT")
                       .replace('"count >= 0"', '"label != \\"\\""'))
            self.assertEqual(self.main("--seed", "3")[1].splitlines()[-2:],
                             ["BOX-001: generated cases: not run: box_1.label is unset; "
                              "skipped stamp: no binding for stamp", "1 code differs"])
        finally:
            del binding.VALUES["box"]

    def test_an_unset_value_read_in_a_step_skips_the_operation(self):
        binding.VALUES["box"] = {"count": [1, 2]}
        binding.OPERATIONS["size"] = lambda actor, box: box.label
        try:
            self.write("box.edda", BOX.replace("label: TEXT, OPTIONAL", "label: TEXT"))
            self.assertEqual(self.main("--seed", "3"), (0, "BOX-001: examples passed: all 1\n"
                             "BOX-001: generated cases: 30 runs passed; calls: put 34; "
                             "skipped stamp: no binding for stamp; skipped size: box_1.label is unset\n"))
        finally:
            del binding.VALUES["box"]

    def test_a_failed_rule_wins_over_one_that_cannot_be_judged(self):
        binding.VALUES["box"] = {"count": [1, 2]}       # label left unset: no value space gives it
        binding.OPERATIONS["put"] = put_one_more
        try:
            self.write("box.edda", LABELLED)
            code, out = self.main("--seed", "3")
            lines = out.splitlines()
            ensure = BOX.splitlines().index('          - "box.count == OLD(box.count) + n"') + 1
            where = f"{os.path.relpath(self.dir.name)}/box.edda"
            self.assertEqual(code, 1)
            at = lines.index("BOX-001: generated cases: failed (seed 3); skipped stamp: no binding for stamp")
            self.assertEqual(lines[at + 2:at + 4], [
                f"    {where}:{ensure}: put: ensure box.count == OLD(box.count) + n: found box.count is 3",
                f'    {where}:{ensure + 1}: not judged: put: ensure box.label != "": box.label is unset'])
        finally:
            del binding.VALUES["box"]

    def test_a_step_whose_only_unkept_rule_cannot_be_judged_skips_the_operation(self):
        binding.VALUES["box"] = {"count": [1, 2]}
        try:
            self.write("box.edda", LABELLED)
            self.assertEqual(self.main("--seed", "3"), (0, "BOX-001: examples passed: all 1\n"
                             "BOX-001: generated cases: 30 runs passed; calls: put 61, size 48; "
                             "skipped stamp: no binding for stamp; skipped put: box.label is unset\n"))
        finally:
            del binding.VALUES["box"]

    def weighed(self, put_code, refuse="", ensure="", also=""):
        """the box project with an unbound weight, a computed heft read
        through it, and put given put_code: its seed 3 run, as lines"""
        text = BOX.replace("      kind: DEFAULT small | large\n", "      kind: DEFAULT small | large\n"
                           "      weight: INTEGER, DERIVED\n      heft: {computed: \"count + weight\"}\n")
        text = text.replace("        refuse:\n          - when: \"n <= 0\"",
                            "        refuse:\n" + refuse + "          - when: \"n <= 0\"")
        text = text.replace('          - "box.count == OLD(box.count) + n"\n',
                            '          - "box.count == OLD(box.count) + n"\n' + ensure + also, 1)
        self.write("box.edda", text)
        binding.OPERATIONS["put"] = put_code
        code, out = self.main("--seed", "3")
        return code, out.splitlines(), text.splitlines(), f"{os.path.relpath(self.dir.name)}/box.edda"

    def test_a_computed_property_the_frame_rule_cannot_read_keeps_other_failures(self):
        code, lines, text, where = self.weighed(put_one_more, also='        also_changes: ["box.heft"]\n')
        ensure = text.index('          - "box.count == OLD(box.count) + n"') + 1
        self.assertEqual(code, 1)
        at = lines.index("BOX-001: generated cases: failed (seed 3); skipped stamp: no binding for stamp")
        self.assertEqual(lines[at + 2:at + 4], [
            f"    {where}:{ensure}: put: ensure box.count == OLD(box.count) + n: found box.count is 2",
            f"    {where}:{text.index('      put:') + 1}: not judged: put: frame rule, box.heft: no binding for box.weight"])

    def test_an_old_value_that_cannot_be_read_keeps_other_failures(self):
        code, lines, text, where = self.weighed(put_one_more, ensure='          - "box.count > OLD(box.weight)"\n')
        ensure = text.index('          - "box.count == OLD(box.count) + n"') + 1
        self.assertEqual(code, 1)
        at = lines.index("BOX-001: generated cases: failed (seed 3); skipped stamp: no binding for stamp")
        self.assertEqual(lines[at + 2:at + 4], [
            f"    {where}:{ensure}: put: ensure box.count == OLD(box.count) + n: found box.count is 2",
            f"    {where}:{ensure + 1}: not judged: put: ensure box.count > OLD(box.weight): no binding for box.weight"])

    def test_a_refusal_after_one_that_cannot_be_judged_is_still_due(self):
        def put_unchecked(actor, box, n):      # never refuses nothing to put
            if n > 10:
                raise binding.Refused("too many at once")
            box.count += n
        code, lines, text, where = self.weighed(put_unchecked, refuse=HEAVY)
        when = text.index('          - when: "n <= 0"') + 1
        self.assertEqual(code, 1)
        at = lines.index("BOX-001: generated cases: failed (seed 3); skipped stamp: no binding for stamp")
        self.assertEqual(lines[at + 2:at + 4], [
            f'    {where}:{when}: put should refuse: "nothing to put", but it did not refuse',
            f"    {where}:{when - 2}: not judged: put: refuse when box.weight > 100: no binding for box.weight"])

    def test_a_refusal_no_rule_gives_fails_when_one_cannot_be_judged(self):
        def put_closed(actor, box, n):
            raise binding.Refused("closed")
        code, lines, text, where = self.weighed(put_closed, refuse=HEAVY)
        heavy = text.index('          - when: "box.weight > 100"') + 1
        self.assertEqual(code, 1)
        at = lines.index("BOX-001: generated cases: failed (seed 3); skipped stamp: no binding for stamp")
        self.assertEqual(lines[at + 2:at + 4], [
            f'    {where}:{heavy + 2}: put should refuse: "too heavy" or "nothing to put", but it refused: "closed"',
            f"    {where}:{heavy}: not judged: put: refuse when box.weight > 100: no binding for box.weight"])

    def test_a_refusal_only_a_rule_that_cannot_be_judged_gives_is_not_failed(self):
        def put_heavy(actor, box, n):
            raise binding.Refused("too heavy")
        self.assertEqual(self.weighed(put_heavy, refuse=HEAVY)[:2], (0, [
            "BOX-001: not run: no binding for box.weight",
            "BOX-001: generated cases: 30 runs passed; calls: size 19; "
            "skipped stamp: no binding for stamp; skipped put: no binding for box.weight"]))

    def taxed(self, put_code, total="subtotal + tax"):
        """the box project with a computed total, which put may change, a
        subtotal no value space gives, so unset in every run, and put
        given put_code: its seed 3 run, as (code, lines, where)"""
        binding.VALUES["box"] = {"count": [1, 2], "tax": [1, 2]}
        binding.OPERATIONS["put"] = put_code
        try:
            self.write("box.edda", TAXED.replace("TOTAL", total))
            code, out = self.main("--seed", "3")
        finally:
            del binding.VALUES["box"]
        return code, out.splitlines(), f"{os.path.relpath(self.dir.name)}/box.edda"

    def test_a_change_an_unread_frame_path_could_name_is_not_judged(self):
        def put_taxed(actor, box, n):
            put(actor, box, n)
            box.tax += 1
        for total in ("subtotal + tax", "subtotal + levy"):     # levy, computed, reads tax
            self.assertEqual(self.taxed(put_taxed, total)[:2], (0, [
                "BOX-001: examples passed: all 1",     # subtotal given there: tax is named
                "BOX-001: generated cases: 30 runs passed; calls: put 39, size 52; "
                "skipped stamp: no binding for stamp; skipped put: box_3.subtotal is unset"]), total)

    def test_a_change_no_unread_frame_path_could_name_still_fails(self):
        def put_restyled(actor, box, n):
            put(actor, box, n)
            box.tax += 1
            box.label = "restyled"
        code, lines, where = self.taxed(put_restyled)
        put_line = TAXED.splitlines().index("      put:") + 1
        self.assertEqual(code, 1)
        at = lines.index("BOX-001: generated cases: failed (seed 3); skipped stamp: no binding for stamp")
        self.assertEqual(lines[at + 2:at + 4], [
            f"    {where}:{put_line}: put changed box_1.label, which the spec does not name",
            f"    {where}:{put_line}: not judged: put: frame rule, box.total: box_1.subtotal is unset"])

    def test_examples_judge_an_unread_frame_path_as_before(self):
        def put_taxed(actor, box, n):
            put(actor, box, n)
            box.tax += 1
        binding.OPERATIONS["put"] = put_taxed
        self.write("box.edda", TAXED.replace("TOTAL", "subtotal + tax").replace("subtotal: 2, ", ""))
        self.write("edda.yaml", "generated_cases: {on: false}\n")
        put_line = TAXED.splitlines().index("      put:") + 1
        self.assertEqual(self.main(), (1, "BOX-001: failing: 1 of 1 examples failed\n"
                                       '    example "parts are put in a box" failed\n'
                                       f"        {os.path.relpath(self.dir.name)}/box.edda:{put_line}: "
                                       "put changed b.tax, which the spec does not name\n"
                                       "1 code differs\n"))

    def peeked(self, ensure, holder=False, code=put_one_more, unset=False):
        """the box project with put also ensuring ensure, which reads size,
        bound to refuse when read inside a fact, which its spec does not
        allow, and put adding one too many, or bound to code: its seed 3
        run, as (code, lines, text, where). With holder, a read
        holder(box) giving the box, bound to refuse the same way; with
        unset, box.label required and given by no run"""
        text = BOX.replace('          - "box.count == OLD(box.count) + n"\n',
                           f'          - "box.count == OLD(box.count) + n"\n          - "{ensure}"\n', 1)
        if holder:
            text = text.replace("      stamp:\n", HOLDER + "      stamp:\n", 1)
            binding.OPERATIONS["holder"] = holder_closed
        if unset:
            text = text.replace("label: TEXT, OPTIONAL", "label: TEXT", 1)
            binding.VALUES["box"] = {"count": [1, 2]}
        self.write("box.edda", text)
        binding.OPERATIONS.update({"put": code, "size": size_closed})
        try:
            code, out = self.main("--seed", "3")
        finally:
            binding.VALUES.pop("box", None)
        return code, out.splitlines(), text, f"{os.path.relpath(self.dir.name)}/box.edda"

    def test_a_rule_a_read_inside_an_ensure_breaks_keeps_the_steps_other_failures(self):
        code, lines, text, where = self.peeked("size(box) >= 0")
        ensure = text.splitlines().index('          - "box.count == OLD(box.count) + n"') + 1
        size = text.splitlines().index("      size:") + 1
        self.assertEqual(code, 1)
        at = lines.index("BOX-001: generated cases: failed (seed 3); skipped stamp: no binding for stamp")
        self.assertEqual(lines[at + 2:at + 5], [
            f"    {where}:{ensure}: put: ensure box.count == OLD(box.count) + n: found box.count is 2",
            f'    {where}:{size}: size (read inside put: ensure size(box) >= 0) refused: "closed", '
            "but the spec does not refuse",
            "    as an example:"])
        example = lines[at + 5:-1]
        pasted = text.replace("    examples:\n", "    examples:\n" + "\n".join(example) + "\n", 1)
        self.write("box.edda", pasted)
        self.write("edda.yaml", "generated_cases: {on: false}\n")
        code, again = self.main()      # an example's call ends at the broken rule, as before
        again = again.splitlines()
        self.assertEqual(code, 1)
        self.assertIn(f'        {where}:{size}: size refused: "closed", but the spec does not refuse',
                      again[again.index('    example "generated: put breaks a rule" failed') + 1:])

    def old_read(self, ensure, read="size", holder=False):
        """the step's lines of peeked(ensure): the read's failure, met
        before the call, then the step's own"""
        code, lines, text, where = self.peeked(ensure, holder)
        own = text.splitlines().index('          - "box.count == OLD(box.count) + n"') + 1
        line = text.splitlines().index(f"      {read}:") + 1
        self.assertEqual(code, 1)
        at = lines.index("BOX-001: generated cases: failed (seed 3); skipped stamp: no binding for stamp")
        return lines[at + 2:at + 5], where, own, line

    def test_a_rule_a_read_inside_an_old_value_breaks_keeps_the_steps_other_failures(self):
        lines, where, ensure, size = self.old_read("box.count > OLD(size(box))")
        self.assertEqual(lines, [
            f'    {where}:{size}: size (read inside put: ensure box.count > OLD(size(box))) refused: "closed", '
            "but the spec does not refuse",
            f"    {where}:{ensure}: put: ensure box.count == OLD(box.count) + n: found box.count is 2",
            "    as an example:"])

    def test_an_old_value_the_ensure_does_not_read_after_the_call_still_reports_its_read(self):
        lines, where, ensure, size = self.old_read("box.count > 0 or OLD(size(box)) >= 0")
        self.assertEqual(lines, [
            f'    {where}:{size}: size (read inside put: ensure box.count > 0 or OLD(size(box)) >= 0) '
            'refused: "closed", but the spec does not refuse',
            f"    {where}:{ensure}: put: ensure box.count == OLD(box.count) + n: found box.count is 2",
            "    as an example:"])

    def test_a_comprehension_source_the_ensure_does_not_read_again_still_reports_its_read(self):
        fact = "box.count > 0 or all(OLD(x) >= 0 for x in [size(box)])"
        lines, where, ensure, size = self.old_read(fact)
        self.assertEqual(lines, [
            f'    {where}:{size}: size (read inside put: ensure {fact}) refused: "closed", '
            "but the spec does not refuse",
            f"    {where}:{ensure}: put: ensure box.count == OLD(box.count) + n: found box.count is 2",
            "    as an example:"])

    def test_a_read_on_a_frame_path_is_reported_once_beside_the_steps_other_failure(self):
        # the ensure reads holder too, after the call: the failure keeps the first place met
        lines, where, ensure, holder = self.old_read("holder(box).count >= 0", "holder", holder=True)
        self.assertEqual(lines, [
            f'    {where}:{holder}: holder (read inside put: frame rule, holder(box).count) refused: "closed", '
            "but the spec does not refuse",
            f"    {where}:{ensure}: put: ensure box.count == OLD(box.count) + n: found box.count is 2",
            "    as an example:"])

    def test_an_unset_value_the_code_reads_after_a_failure_keeps_the_failure(self):
        def put_unlabelled(actor, box, n):      # keeps the spec, but reads the label no run gives
            put(actor, box, n)
            return box.label
        fact = "box.count > OLD(size(box))"
        code, lines, text, where = self.peeked(fact, code=put_unlabelled, unset=True)
        size = text.splitlines().index("      size:") + 1
        put_line = text.splitlines().index("      put:") + 1
        self.assertEqual(code, 1)
        at = lines.index("BOX-001: generated cases: failed (seed 3); skipped stamp: no binding for stamp")
        self.assertEqual(lines[at + 2:at + 5], [
            f'    {where}:{size}: size (read inside put: ensure {fact}) refused: "closed", '
            "but the spec does not refuse",
            f"    {where}:{put_line}: not judged: put: box_1.label is unset",
            "    as an example:"])

    def held(self, read):
        """the RuleBroken of a read, read, held to its rules where the
        frame rule reads what it gives back: on the box project with
        holder and the reads pick, refusing on size, giving holder, and
        line_up, ordered by holder, size and holder bound to refuse when
        read inside a fact, while generated cases run; with (where, the
        lines of size and holder)"""
        text = BOX.replace("      stamp:\n", HOLDER + PICK + "      stamp:\n", 1)
        self.write("box.edda", text)
        self.write("edda.yaml", "generated_cases: {on: false}\n")
        binding.OPERATIONS.update({"size": size_closed, "holder": holder_closed, "pick": lambda actor, box: box,
                                   "line_up": lambda actor, box: [box]})
        self.main()     # loads the project
        run.UNSET_ENDS[0], run.RECORD[0] = True, set()
        try:
            with self.assertRaises(run.RuleBroken) as e:
                run.run_operation(read, None, [binding.Thing("box", count=1, kind="small")], {})
        finally:
            run.UNSET_ENDS[0], run.RECORD[0] = False, None
            for name in ("pick", "line_up"):
                del binding.OPERATIONS[name]
        lines = text.splitlines()
        where = f"{os.path.relpath(self.dir.name)}/box.edda"
        return e.exception.failures, where, lines.index("      size:") + 1, lines.index("      holder:") + 1

    def test_a_read_whose_returns_breaks_a_rule_after_its_refuse_did_keeps_both(self):
        failures, where, size, holder = self.held("pick")
        self.assertEqual([f"{at}: {m}" for at, _, m in failures], [
            f'{where}:{size}: size (read inside pick: refuse when size(box) < 0) refused: "closed", '
            "but the spec does not refuse",
            f'{where}:{holder}: holder (read inside pick: returns) refused: "closed", but the spec does not refuse'])

    def test_a_read_whose_ordered_by_breaks_a_rule_after_its_refuse_did_keeps_both(self):
        failures, where, size, holder = self.held("line_up")
        self.assertEqual([f"{at}: {m}" for at, _, m in failures], [
            f'{where}:{size}: size (read inside line_up: refuse when size(box) < 0) refused: "closed", '
            "but the spec does not refuse",
            f'{where}:{holder}: holder (read inside line_up: ordered_by holder(box).count) refused: "closed", '
            "but the spec does not refuse"])

    def test_optional_and_many_inputs_with_nothing_to_point_at_do_not_block(self):
        self.write("box.edda", BOX.replace("stories:\n", NOTE + "stories:\n", 1)
                   .replace("    examples:\n", TAG + "    examples:\n", 1))
        binding.OPERATIONS["tag"] = lambda actor, box, notes, note=None: None
        try:
            self.assertEqual(self.main("--seed", "3"), (0, "BOX-001: examples passed: all 1\n"
                             "BOX-001: generated cases: 30 runs passed; calls: put 84, size 39, tag 33; "
                             "skipped stamp: no binding for stamp\n"))
        finally:
            del binding.OPERATIONS["tag"]

    def test_edge_values_read_signed_literals(self):
        import generate
        self.write("box.edda", BOX.replace('"count >= 0"', '"count >= -10"'))
        self.write("edda.yaml", "generated_cases: {on: false}\n")
        self.main()
        generate.R = run
        nums = generate.edges(run.PROJECT[0])[0]
        self.assertTrue({-11, -10, -9, 10} <= set(nums), nums)

    def test_setting_off_runs_as_before(self):
        self.write("edda.yaml", "generated_cases: {on: false}\n")
        self.assertEqual(self.main(), (0, "BOX-001: examples passed: all 1\n"))


LABELLED = (BOX.replace("label: TEXT, OPTIONAL", "label: TEXT")     # put also ensures a label, never generated
            .replace('          - "box.count == OLD(box.count) + n"\n',
                     '          - "box.count == OLD(box.count) + n"\n          - "box.label != \\"\\""\n')
            .replace("with: {count: 1}", 'with: {count: 1, label: "x"}'))


TAXED = (BOX.replace("      kind: DEFAULT small | large\n", "      kind: DEFAULT small | large\n"
                     "      subtotal: INTEGER\n      tax: INTEGER\n      total: {computed: \"TOTAL\"}\n"
                     "      levy: {computed: \"tax * 2\"}\n")
         .replace('          - "box.count == OLD(box.count) + n"\n',
                  '          - "box.count == OLD(box.count) + n"\n        also_changes: ["box.total"]\n', 1)
         .replace("with: {count: 1}", "with: {count: 1, subtotal: 2, tax: 1}"))

HEAVY = """\
          - when: "box.weight > 100"
            reason: "too heavy"
"""


NOTE = """\
  note:
    is: "a note no binding makes"
    properties:
      text: TEXT
    may_read: [{role: clerk}]
"""

TAG = """\
      tag:
        is: "tags a box with notes"
        inputs: {box: box, notes: MANY note, note: "note, OPTIONAL"}
        who: [{role: clerk}]
"""


SHELF = """\
roles:
  clerk:
    is: "a person at the counter"
entities:
  shelf:
    is: "a shelf"
    properties:
      code: TEXT
      bin: bin
    may_read: [{role: clerk}]
  bin:
    is: "a bin on a shelf"
    properties:
      parts: MANY part
    may_read: [{role: clerk}]
  part:
    is: "a part in a bin"
    properties:
      weight: INTEGER
    may_read: [{role: clerk}]
stories:
  SHELF-001:
    story: "weigh a part"
    about: shelf
    as_a: clerk
    i_want: "to weigh a part on a shelf"
    so_that: "its weight is known"
    operations:
      weigh:
        is: "the weight of a part"
        inputs: {part: part}
        who: [{role: clerk}]
        returns: "part.weight"
    examples:
      "a part is weighed":
        given:
          - actor: ann
            with: {roles: [clerk]}
          - shelf: s
            with: {code: "s1"}
        steps:
          - when: {actor: ann, call: "weigh(s.bin.parts[0])"}
            then: [DONE, "RESULT == 3"]
"""

NODE = """\
roles:
  clerk:
    is: "a person at the counter"
entities:
  node:
    is: "a node of a tree"
    properties:
      label: TEXT
      parent: node, OPTIONAL
    may_read: [{role: clerk}]
  ring:
    is: "a ring of links"
    properties:
      next: ring
    may_read: [{role: clerk}]
stories:
  NODE-001:
    story: "name a node"
    about: node
    as_a: clerk
    i_want: "to read a node's label"
    so_that: "the node is known"
    operations:
      label_of:
        is: "the label of a node"
        inputs: {node: node}
        who: [{role: clerk}]
        returns: "node.label"
    examples:
      "a node is named":
        given:
          - actor: ann
            with: {roles: [clerk]}
          - node: n
            with: {label: "top"}
        steps:
          - when: {actor: ann, call: "label_of(n)"}
            then: [DONE, "RESULT == \\"top\\""]
"""

TASK = """\
roles:
  clerk:
    is: "a person at the counter"
entities:
  task:
    is: "a task with a due time"
    properties:
      due: TIME
    may_read: [{role: clerk}]
    may_update: [{role: clerk}]
stories:
  TASK-001:
    story: "move a task"
    about: task
    as_a: clerk
    i_want: "to move a task's due time"
    so_that: "the plan fits"
    operations:
      move:
        is: "moves a task to a new time"
        inputs: {task: task, to: TIME}
        who: [{role: clerk}]
        refuse:
          - when: "to < TIME(\\"2026-10-03\\")"
            reason: "too early"
        ensure:
          - "task.due == to"
    examples:
      "a task is moved":
        given:
          - actor: ann
            with: {roles: [clerk]}
          - task: t
            with: {due: "2026-10-05 09:00"}
        steps:
          - when: {actor: ann, call: "move(t, TIME(\\"2026-10-04\\"))"}
            then: [DONE, "t.due == TIME(\\"2026-10-04\\")"]
"""


def shelf_with(parts):
    """a shelf maker: its bin holds parts parts of weight 3"""
    return lambda name, values, workdir: binding.Thing(
        "shelf", values, bin=binding.Thing("bin", parts=[binding.Thing("part", weight=3) for _ in range(parts)]))


def move(actor, task, to):
    if to < datetime.datetime(2026, 10, 3):
        raise binding.Refused("too early")
    task.due = to


class WorldTest(unittest.TestCase):
    """what a run finds to call with, each on a project of its own"""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.bound = {}     # id of a binding table to (the table, the names this test put there)

    def tearDown(self):
        for table, names in self.bound.values():
            for name in names:
                del table[name]
        self.dir.cleanup()

    def bind(self, table, **made):
        table.update(made)
        self.bound.setdefault(id(table), (table, []))
        self.bound[id(table)][1].extend(made)

    def project(self, name, text):
        for f, t in ((name, text), ("edda.yaml", ON)):
            with open(os.path.join(self.dir.name, f), "w") as out:
                out.write(t)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = run.main(["--project", self.dir.name, "--seed", "3"])
        return code, out.getvalue().splitlines()

    def test_a_record_reached_through_another_is_an_input(self):
        self.bind(binding.ENTITIES, shelf=shelf_with(1))
        self.bind(binding.VALUES, shelf={"code": ["s1"]})
        self.bind(binding.OPERATIONS, weigh=lambda actor, part: part.weight)
        self.assertEqual(self.project("shelf.edda", SHELF), (0, [
            "SHELF-001: examples passed: all 1",
            "SHELF-001: generated cases: 30 runs passed; calls: weigh 162"]))

    def test_runs_that_called_nothing_are_not_run(self):
        self.bind(binding.ENTITIES, shelf=shelf_with(0))
        self.bind(binding.VALUES, shelf={"code": ["s1"]})
        self.bind(binding.OPERATIONS, weigh=lambda actor, part: part.weight)
        self.assertEqual(self.project("shelf.edda", SHELF)[1][-2:],
                         ["SHELF-001: generated cases: not run: no call ran in 30 runs; "
                          "weigh never had a record for each input", "1 code differs"])

    def test_a_reference_with_nothing_to_point_at(self):
        self.bind(binding.ENTITIES, node=lambda name, values, workdir: binding.Thing("node", values),
                  ring=lambda name, values, workdir: binding.Thing("ring", values))
        self.bind(binding.OPERATIONS, label_of=lambda actor, node: node.label)
        self.assertEqual(self.project("node.edda", NODE), (0, [
            "NODE-001: examples passed: all 1",
            "NODE-001: generated cases: 30 runs passed; calls: label_of 169; "
            "skipped entity ring: nothing to fill its required next"]))

    def test_a_date_only_time_is_a_time(self):
        self.bind(binding.ENTITIES, task=lambda name, values, workdir: binding.Thing("task", values))
        self.bind(binding.OPERATIONS, move=move)
        self.assertEqual(self.project("task.edda", TASK), (0, [
            "TASK-001: examples passed: all 1",
            "TASK-001: generated cases: 30 runs passed; calls: move 168"]))


HIDDEN = """\
import sys
sys.modules["hypothesis"] = None        # an import of it raises ImportError
sys.path.insert(0, {tools!r})
import run
code = run.main({argv!r})
print("imported generate:", "generate" in sys.modules)
sys.exit(code)
"""


class WithoutHypothesisTest(unittest.TestCase):
    """the runner with Hypothesis hidden, in a fresh process"""

    def hidden(self, argv):
        p = subprocess.run([sys.executable, "-c", HIDDEN.format(tools=TOOLS, argv=argv)],
                           capture_output=True, text=True)
        return p.returncode, p.stdout

    def test_setting_off_never_imports_hypothesis(self):
        code, out = self.hidden([])
        plain = subprocess.run([sys.executable, os.path.join(TOOLS, "run.py")], capture_output=True, text=True)
        self.assertEqual((code, out), (plain.returncode, plain.stdout + "imported generate: False\n"))

    def test_setting_on_without_hypothesis_exits_3(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "box.edda"), "w") as f:
                f.write(BOX)
            with open(os.path.join(d, "edda.yaml"), "w") as f:
                f.write(ON)
            code, out = self.hidden(["--project", d])
        self.assertEqual(code, 3)
        self.assertEqual(out.splitlines(), [
            "edda failed: generated cases need Hypothesis (import of hypothesis halted; None in sys.modules); "
            "install it with python3 -m pip install -r tools/requirements.txt",
            "imported generate: False"])


if __name__ == "__main__":
    unittest.main()
