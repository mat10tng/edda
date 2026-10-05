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
property the frame rule reads, or a refuse condition; a change that
computed property could name, directly or through another, is not
judged, one outside what it could name still fails, and examples judge
it as before; a later refuse condition that holds is still due, and a
reason no condition gives still fails; optional and
MANY inputs with nothing to point at do not block an operation; edge
values read a literal with its sign; a failure prints its full replay
command. With the setting off, or no edda.yaml, the runner never imports
Hypothesis and runs without it; with the setting on and Hypothesis
missing it exits 3 with one line. A settings file that breaks its
shape, its root no mapping or a count no whole number of at least 1,
is refused at its line, in the checker's words.
"""
import contextlib
import datetime
import io
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import edda_binding as binding   # noqa: E402
import run                       # noqa: E402

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


def put(actor, box, n):         # keeps the spec
    if n <= 0:
        raise binding.Refused("nothing to put")
    if n > 10:
        raise binding.Refused("too many at once")
    box.count += n


def put_one_more(actor, box, n):     # keeps the refusals, adds one too many
    put(actor, box, n)
    box.count += 1


def put_off_by_one(actor, box, n):     # refuses 10, which the spec allows
    if n <= 0:
        raise binding.Refused("nothing to put")
    if n >= 10:
        raise binding.Refused("too many at once")
    box.count += n


ON = "generated_cases: {on: true, runs: 30, steps: 6}\n"

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
        for name in ("put", "size"):
            del binding.OPERATIONS[name]
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
            "BOX-001: generated cases: 30 runs passed; calls: put 101, size 77; skipped stamp: no binding for stamp"])

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
            "            then: [DONE]"])

    def test_the_seed_replays_the_same_run(self):
        binding.OPERATIONS["put"] = put_off_by_one
        self.assertEqual(self.main("--seed", "11"), self.main("--seed", "11"))

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
        self.assertEqual(lines[-2:], [
            '    and under the shown_by: of the rule "a put adds the parts it is given":',
            '          - "generated: put breaks a rule"'])
        example = lines[lines.index("    as an example:") + 1:-2]
        pasted = BOX.replace("    operations:\n", RULES + lines[-1] + "\n" + "    operations:\n", 1)
        pasted = pasted.replace("    examples:\n", "    examples:\n" + "\n".join(example) + "\n", 1)
        self.write("box.edda", pasted)
        self.write("edda.yaml", "generated_cases: {on: false}\n")
        code, again = self.main()
        put_line = pasted.splitlines().index("      put:") + 1     # one lower: the shown_by line above it
        self.assertEqual((code, again.splitlines()), (1, [
            "BOX-001: failing: 1 of 2 examples failed",
            '    example "generated: put breaks a rule" failed',
            "        " + lines[3].strip().replace(f"box.edda:{put_line - 1}:", f"box.edda:{put_line}:")]))

    def test_skips_are_listed_when_no_world_keeps_the_always_rules(self):
        self.write("box.edda", BOX.replace('"count >= 0"', '"count > count"'))
        self.assertEqual(self.main("--seed", "3")[1].splitlines()[-1],
                         "BOX-001: generated cases: not run: no starting world keeps every always-rule; "
                         "skipped stamp: no binding for stamp")

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
            self.assertEqual(self.main("--seed", "3")[1].splitlines()[-1],
                             "BOX-001: generated cases: not run: box_1.label is unset; "
                             "skipped stamp: no binding for stamp")
        finally:
            del binding.VALUES["box"]

    def test_an_unset_value_read_in_a_step_skips_the_operation(self):
        binding.VALUES["box"] = {"count": [1, 2]}
        binding.OPERATIONS["size"] = lambda actor, box: box.label
        try:
            self.write("box.edda", BOX.replace("label: TEXT, OPTIONAL", "label: TEXT"))
            self.assertEqual(self.main("--seed", "3"), (0, "BOX-001: examples passed: all 1\n"
                             "BOX-001: generated cases: 30 runs passed; calls: put 43; "
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
                             "BOX-001: generated cases: 30 runs passed; calls: put 62, size 64; "
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
            "BOX-001: generated cases: 30 runs passed; calls: size 6; "
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
                                       "put changed b.tax, which the spec does not name\n"))

    def test_optional_and_many_inputs_with_nothing_to_point_at_do_not_block(self):
        self.write("box.edda", BOX.replace("stories:\n", NOTE + "stories:\n", 1)
                   .replace("    examples:\n", TAG + "    examples:\n", 1))
        binding.OPERATIONS["tag"] = lambda actor, box, notes, note=None: None
        try:
            self.assertEqual(self.main("--seed", "3"), (0, "BOX-001: examples passed: all 1\n"
                             "BOX-001: generated cases: 30 runs passed; calls: put 85, size 34, tag 41; "
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
            "SHELF-001: generated cases: 30 runs passed; calls: weigh 157"]))

    def test_runs_that_called_nothing_are_not_run(self):
        self.bind(binding.ENTITIES, shelf=shelf_with(0))
        self.bind(binding.VALUES, shelf={"code": ["s1"]})
        self.bind(binding.OPERATIONS, weigh=lambda actor, part: part.weight)
        self.assertEqual(self.project("shelf.edda", SHELF)[1][-1],
                         "SHELF-001: generated cases: not run: no call ran in 30 runs; "
                         "weigh never had a record for each input")

    def test_a_reference_with_nothing_to_point_at(self):
        self.bind(binding.ENTITIES, node=lambda name, values, workdir: binding.Thing("node", values),
                  ring=lambda name, values, workdir: binding.Thing("ring", values))
        self.bind(binding.OPERATIONS, label_of=lambda actor, node: node.label)
        self.assertEqual(self.project("node.edda", NODE), (0, [
            "NODE-001: examples passed: all 1",
            "NODE-001: generated cases: 30 runs passed; calls: label_of 170; "
            "skipped entity ring: nothing to fill its required next"]))

    def test_a_date_only_time_is_a_time(self):
        self.bind(binding.ENTITIES, task=lambda name, values, workdir: binding.Thing("task", values))
        self.bind(binding.OPERATIONS, move=move)
        self.assertEqual(self.project("task.edda", TASK), (0, [
            "TASK-001: examples passed: all 1",
            "TASK-001: generated cases: 30 runs passed; calls: move 166"]))


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
