#!/usr/bin/env python3
"""Client functions (reference sections 4, 8 to 12; decisions EE and FF).

    python3 tools/test_functions.py

A function declared with its meaning, types and rows checks, and is
called in expressions by position, typed by its returns. The checker
refuses a type phrase that is no scalar or choice, a row value of another
type or a time that is no time, a row that leaves out an input
(missing_key) or names one the function has not (unknown_key alone),
two rows with the same inputs and different results (contradicting_rows,
1 and 1.0 one number, a day and its 00:00 one time), a name that is also
a role, an entity, an operation, another function or one of Edda's own
words (declared_twice), a call with a keyword, the wrong count or the
wrong type, and a function asked for in a step; the analyser skips a
condition that calls one. In an example a call
answers from its rows only, a time by its moment, and a call no row
covers fails the example at its fact, in every phase: the frame rule's
tracking, a refuse condition, an ensure fact, a then fact.
A computed property is the code's value, never worked out from the
spec to compare: a fact that reads it catches wrong code (the client's
cost of 999), in an example, in a generated case and in that failure
pasted as an example, which checks against the schema; a code cost
that breaks an always fact throws every starting world away, and a
starting world met failing, by a read an always fact calls or a given
that cannot be made, pastes as one fact step.
Inputs named gives and given are inputs. edda run runs the rows against a correct, a broken
and a missing real function, each reported, a failing row a
failing_function with its dimensions, with STORY names those of every
function the stories reach (exit 1). A function is a block: approved
like an entity, named in story.blocks directly, through a computed
property, through a called operation and through an always fact, so a
story is refused until it is approved, pinned once it is, and its pins
stale after the function changes; a history without functions stays
valid. The read view gives its sentences, the model lists it, and
generated cases call a real function only once its rows pass; a
generated failure lists the rows its pasted example needs, or why they
are not known.
"""
import contextlib
import io
import json
import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["EDDA_LOG"] = "off"     # the tools and their children never write the log (section 11)
import approve                   # noqa: E402
import check                     # noqa: E402
import edda_binding as binding   # noqa: E402
import run                       # noqa: E402
import view                      # noqa: E402
import watch                     # noqa: E402

ROOT = check.ROOT

SPEC = """\
roles:
  clerk:
    is: "a person at the counter"

functions:
  shipping_cost:
    is: "what a parcel of that weight costs to ship"
    inputs: {weight: NUMBER}
    returns: NUMBER
    examples:
      - {given: {weight: 1}, gives: 5}
      - {given: {weight: 10}, gives: 12}
  is_holiday:
    is: "whether the shop is shut that day"
    inputs: {day: TIME}
    returns: YES_NO
    examples:
      - {given: {day: "2026-12-25"}, gives: True}
      - {given: {day: "2026-12-24 00:00"}, gives: False}

entities:
  parcel:
    is: "a thing a clerk sends"
    properties:
      weight: NUMBER
      paid: NUMBER, OPTIONAL
      cost: {computed: "shipping_cost(weight)"}
    may_read: [{role: clerk}]
    may_update: [{role: clerk}]

stories:
  PAR-001:
    story: "price a parcel"
    about: parcel
    as_a: clerk
    i_want: "to know what a parcel costs"
    so_that: "I can charge for it"
    operations:
      price:
        is: "gives what a parcel costs to ship"
        inputs: {parcel: parcel}
        who: [{role: clerk}]
        returns: "shipping_cost(parcel.weight)"
    examples:
      "a light parcel costs 5":
        given:
          - actor: ann
            with: {roles: [clerk]}
          - parcel: box
            with: {weight: 1}
        steps:
          - when: {actor: ann, call: "price(box)"}
            then: [DONE, "RESULT == shipping_cost(1)", "not is_holiday(TIME(\\"2026-12-24\\"))"]
      "an odd parcel has no row":
        given:
          - parcel: box
            with: {weight: 3}
        steps:
          - then: ["box.weight == 3", "shipping_cost(box.weight) > 0"]
  PAR-002:
    story: "charge for a parcel"
    about: parcel
    as_a: clerk
    i_want: "to charge what a parcel costs"
    so_that: "the shop is paid"
    operations:
      charge:
        is: "records what a parcel was charged"
        inputs: {parcel: parcel}
        who: [{role: clerk}]
        refuse:
          - when: "parcel.cost > 100"
            reason: "too dear to send"
        ensure:
          - "parcel.paid == parcel.cost"
    examples:
      "a light parcel is charged 5":
        given:
          - actor: ann
            with: {roles: [clerk]}
          - parcel: box
            with: {weight: 1}
        steps:
          - when: {actor: ann, call: "charge(box)"}
            then: [DONE, "box.paid == 5"]
  PAR-003:
    story: "see the price"
    about: parcel
    as_a: clerk
    i_want: "to see the price"
    so_that: "I can tell the customer"
    examples:
      "the price of a light parcel":
        given:
          - parcel: box
            with: {weight: 1}
        steps:
          - then: ["price(box) == 5"]
"""


def line_of(text, needle, after=0):
    """the line of the first line of text holding needle, after line after"""
    return next(i for i, s in enumerate(text.splitlines(), 1) if i > after and needle in s)


class Folder:
    """a project folder of one parcel.edda, in a temporary folder"""

    def __init__(self, text=SPEC, files=()):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        self.write("parcel.edda", text)
        for name, t in files:
            self.write(name, t)

    def write(self, name, text):
        with open(os.path.join(self.dir, name), "w") as f:
            f.write(text)

    def read(self, name):
        with open(os.path.join(self.dir, name)) as f:
            return f.read()

    def problems(self, name="parcel.edda"):
        """every refusal and flag of a file, as (rule, line, message)"""
        P = check.project_of(self.dir, clock=(None, "UTC"))
        src, shape, meaning, history, flags = check.check(os.path.join(self.dir, name), P)
        return src + shape + meaning + history + flags

    def status(self):
        P = check.project_of(self.dir, clock=(None, "UTC"))
        source, data = check.load(os.path.join(self.dir, "parcel.edda"))
        return check.status_lines(data, P, source)

    def close(self):
        self.tmp.cleanup()


def changed(old, new, text=SPEC):
    assert text.count(old) == 1, old
    return text.replace(old, new)


ROWS = """\
      - {given: {weight: 1}, gives: 5}
      - {given: {weight: 10}, gives: 12}
"""


class Declaration(unittest.TestCase):

    def problems(self, text):
        f = Folder(text)
        try:
            return f.problems()
        finally:
            f.close()

    def test_a_declared_function_checks(self):
        f = Folder()
        try:
            self.assertEqual(f.problems(), [])
            self.assertEqual(f.status()[:4], ["role clerk: draft v0", "entity parcel: draft v0",
                                              "function shipping_cost: draft v0", "function is_holiday: draft v0"])
        finally:
            f.close()

    def test_a_type_phrase_that_is_no_scalar_or_choice(self):
        for phrase in ("parcel", "MANY parcel", "NUMBER, OPTIONAL", "DEFAULT 1"):
            text = changed("inputs: {weight: NUMBER}", f'inputs: {{weight: "{phrase}"}}'
                           if "," in phrase else f"inputs: {{weight: {phrase}}}")
            self.assertEqual(self.problems(text), [(
                "bad_type_phrase", line_of(SPEC, "inputs: {weight: NUMBER}"),
                "not a type phrase (a function takes and gives TEXT, NUMBER, INTEGER, TIME, YES_NO or a choice): "
                + phrase)], phrase)
        text = changed("    returns: YES_NO\n", "    returns: shut | open\n")
        text = text.replace("gives: True}", "gives: shut}").replace("gives: False}", "gives: open}")
        text = text.replace('"not is_holiday(TIME(\\"2026-12-24\\"))"', '"is_holiday(TIME(\\"2026-12-24\\")) == open"')
        self.assertEqual(self.problems(text), [], "a choice result")
        text = text.replace("gives: open}", "gives: closed}")
        self.assertEqual(self.problems(text), [("unknown_choice", line_of(SPEC, '"2026-12-24 00:00"'),
                                                "not one of gives's values: closed")])

    def test_a_row_value_of_another_type(self):
        rows = line_of(SPEC, "{given: {weight: 1}, gives: 5}")
        self.assertEqual(self.problems(changed("{given: {weight: 1}, gives: 5}", '{given: {weight: "1"}, gives: 5}')),
                         [("type_mismatch", rows, 'weight expects a NUMBER: "1"')])
        self.assertEqual(self.problems(changed("{given: {weight: 1}, gives: 5}", "{given: {weight: 1}, gives: True}")),
                         [("type_mismatch", rows, "gives expects a NUMBER: True")])
        holiday = line_of(SPEC, '{given: {day: "2026-12-25"}')
        self.assertEqual(self.problems(changed('{given: {day: "2026-12-25"}', '{given: {day: "2026-02-30"}')),
                         [("type_mismatch", holiday, 'day expects a TIME, "YYYY-MM-DD HH:MM" or "YYYY-MM-DD": 2026-02-30')])
        self.assertEqual(self.problems(changed('{given: {day: "2026-12-25"}', "{given: {day: 2026}")),
                         [("type_mismatch", holiday, "day expects a TIME: 2026")])

    def test_a_row_that_leaves_out_or_misnames_an_input(self):
        rows = line_of(SPEC, "{given: {weight: 1}, gives: 5}")
        self.assertEqual(self.problems(changed("{given: {weight: 1}, gives: 5}", "{given: {}, gives: 5}")),
                         [("missing_key", rows, "row 1 needs weight:")])
        self.assertEqual(self.problems(changed("{given: {weight: 1}, gives: 5}", "{given: {wieght: 1}, gives: 5}")),
                         [("unknown_key", rows, "unknown key: wieght")])
        self.assertEqual(self.problems(changed("{given: {weight: 1}, gives: 5}", "{given: {weight: 1}}")),
                         [("missing_key", rows, "row 1 needs gives:")])

    def test_contradicting_rows(self):
        third = ROWS + "      - {given: {weight: 1.0}, gives: 6}\n"
        self.assertEqual(self.problems(changed(ROWS, third)), [(
            "contradicting_rows", line_of(SPEC, "{given: {weight: 10}, gives: 12}") + 1,
            "shipping_cost: rows 1 and 3 give different results for the same inputs")])
        self.assertEqual(self.problems(changed(ROWS, ROWS + "      - {given: {weight: 1}, gives: 5}\n")), [],
                         "a row twice says one thing")
        day = changed('{given: {day: "2026-12-24 00:00"}, gives: False}', '{given: {day: "2026-12-25 00:00"}, gives: False}')
        self.assertEqual(self.problems(day), [(
            "contradicting_rows", line_of(SPEC, '"2026-12-24 00:00"'),
            "is_holiday: rows 1 and 2 give different results for the same inputs")], "a day is its 00:00")

    def test_the_fixture_raises_only_contradicting_rows(self):
        folder = os.path.join(ROOT, "fixtures", "contradicting_rows")
        P = check.project_of(folder)
        found = check.check(os.path.join(folder, "order.edda"), P)
        self.assertEqual(found, ([], [], [("contradicting_rows", 16, "shipping_cost: rows 1 and 3 give different "
                                                                      "results for the same inputs")], [], []))
        self.assertEqual(watch.registry()[0]["contradicting_rows"], {
            "category": "contradiction", "sub": "function rows", "fix": "wrong", "acts": "person", "level": "blocks"})

    def test_a_name_from_two_sources(self):
        at = line_of(SPEC, "  shipping_cost:")
        for other in ("price", "parcel", "clerk", "is_holiday"):
            text = changed("  shipping_cost:\n    is:", f"  {other}:\n    is:")
            text = text.replace("shipping_cost(", f"{other}(")
            found = [p for p in self.problems(text) if p[0] == "declared_twice"]
            self.assertTrue(found, other)
        text = changed("  shipping_cost:\n    is:", "  len:\n    is:").replace("shipping_cost(", "len(")
        self.assertEqual(self.problems(text), [("declared_twice", at, "declared twice: len (a word of Edda's own)")])
        before = changed("functions:\n  shipping_cost:", "functions:\n  price:").replace("shipping_cost(", "price(")
        self.assertIn(("declared_twice", line_of(SPEC, "      price:"), "declared twice: price"), self.problems(before),
                      "an operation after the function is the second")

    def test_a_call_with_the_wrong_inputs(self):
        fact = line_of(SPEC, '"box.weight == 3"')
        for call, msg in (("shipping_cost(box.weight, 2)", "shipping_cost expects 1 input by position"),
                          ("shipping_cost(weight=box.weight)", "shipping_cost expects 1 input by position"),
                          ('shipping_cost(\\"3\\")', "shipping_cost input weight expects a NUMBER")):
            text = changed('"shipping_cost(box.weight) > 0"', f'"{call} > 0"')
            shown = call.replace('\\"', '"')
            self.assertEqual(self.problems(text), [("type_mismatch", fact, f"{msg}: {shown} > 0")], call)
        text = changed('"shipping_cost(box.weight) > 0"', '"shipping_cost(box.weight) == \\"5\\""')
        self.assertEqual(self.problems(text), [("type_mismatch", fact, '== expects two values of one kind: '
                                                                      'shipping_cost(box.weight) == "5"')])

    def test_the_analyser_skips_a_condition_calling_a_function(self):
        text = changed('''          - when: "parcel.cost > 100"
            reason: "too dear to send"
''', '''          - when: "shipping_cost(parcel.weight) > 100"
            reason: "too dear to send"
          - when: "shipping_cost(parcel.weight) > 200"
            reason: "far too dear to send"
''')
        self.assertEqual(self.problems(text), [], "no dead_refusal: a call is never read as cases")

    def test_a_function_is_never_asked_for_in_a_step(self):
        text = changed('call: "price(box)"', 'call: "shipping_cost(1)"')
        self.assertEqual(self.problems(text), [(
            "not_an_expression", line_of(SPEC, 'call: "price(box)"'),
            "not an expression (a call of an operation was expected): shipping_cost(1)")])


def price(actor, parcel):
    return 5 if parcel.weight <= 1 else 12


def make_parcel(name, values, workdir):     # its computed cost from the code, as an example reads one
    return binding.Thing("parcel", values, cost=5 if values["weight"] <= 1 else 12)


def charge(actor, parcel):
    if price(actor, parcel) > 100:
        raise binding.Refused("too dear to send")
    parcel.paid = price(actor, parcel)


class Runner(unittest.TestCase):

    def setUp(self):
        self.f = Folder()
        binding.ENTITIES["parcel"] = make_parcel
        binding.OPERATIONS.update({"price": price, "charge": charge})
        self.saved = dict(binding.FUNCTIONS)

    def tearDown(self):
        del binding.ENTITIES["parcel"]
        for name in ("price", "charge"):
            del binding.OPERATIONS[name]
        binding.FUNCTIONS.clear()
        binding.FUNCTIONS.update(self.saved)
        self.f.close()

    def test_a_call_answers_from_its_rows_and_fails_where_none_covers(self):
        binding.FUNCTIONS["shipping_cost"] = lambda w: 999     # never called inside an example
        (sid, status, detail, failed), = run.run(self.f.dir, ["PAR-001"], clock=(None, "UTC"))
        self.assertEqual((status, detail), ("failing", "1 of 2 examples failed"))
        path = os.path.relpath(os.path.join(self.f.dir, "parcel.edda"))
        self.assertEqual(failed, [("an odd parcel has no row", [(
            f"{path}:{line_of(SPEC, 'shipping_cost(box.weight) > 0')}", "shipping_cost(box.weight) > 0",
            "no row for shipping_cost(3)")])])

    def test_stories_reaching_a_function_through_a_computed_property_or_a_read_run(self):
        results = run.run(self.f.dir, ["PAR-002", "PAR-003"], clock=(None, "UTC"))
        self.assertEqual([r[1] for r in results], ["examples passed", "examples passed"])

    def test_a_call_no_row_covers_fails_in_every_phase(self):
        refuse = '''        refuse:
          - when: "parcel.cost > 100"
            reason: "too dear to send"
'''
        direct = '''        refuse:
          - when: "shipping_cost(parcel.weight) > 100"
            reason: "too dear to send"
'''
        heavy = changed('''            with: {weight: 1}
        steps:
          - when: {actor: ann, call: "charge(box)"}
            then: [DONE, "box.paid == 5"]''', '''            with: {weight: 3}
        steps:
          - when: {actor: ann, call: "charge(box)"}
            then: [DONE, "box.paid == 12"]''')
        path = os.path.relpath(os.path.join(self.f.dir, "parcel.edda"))

        def failed(text):
            self.f.write("parcel.edda", text)
            (_, status, _, out), = run.run(self.f.dir, ["PAR-002"], clock=(None, "UTC"))
            return out

        def no_row(text, needle='then: [DONE, "box.paid == 12"]', then="DONE", found="no row for shipping_cost(3)"):
            return [("a light parcel is charged 5", [(f"{path}:{line_of(text, needle)}", then, found)])]
        frame = changed(refuse, "", heavy).replace('"parcel.paid == parcel.cost"', '"parcel.cost == parcel.paid"')
        self.assertEqual(failed(frame), no_row(frame), "the frame rule's dependency tracking of parcel.cost")
        self.assertEqual(failed(heavy), [], "a refuse condition reading the code's cost calls no function")
        when = changed(refuse, direct, heavy)
        self.assertEqual(failed(when), no_row(when), "a refuse condition")
        bare = changed(refuse, "", heavy).replace('"parcel.paid == parcel.cost"',
                                                  '"parcel.paid == shipping_cost(parcel.weight)"')
        ensure = "charge: ensure parcel.paid == shipping_cost(parcel.weight): found no row for shipping_cost(3)"
        self.assertEqual(failed(bare), no_row(bare, '"parcel.paid == shipping_cost(parcel.weight)"', None, ensure),
                         "an ensure fact")
        odd = changed('"shipping_cost(box.weight) > 0"', '"box.cost == 12"')
        self.f.write("parcel.edda", odd)        # the code's cost is 12: no row is needed to read it
        self.assertEqual(run.run(self.f.dir, ["PAR-001"], clock=(None, "UTC"))[0][1], "examples passed",
                         "a computed property read in a fact is the code's value")

    def test_a_fact_that_reads_the_computed_property_catches_wrong_code(self):
        binding.ENTITIES["parcel"] = lambda name, values, workdir: binding.Thing("parcel", values, cost=999)
        path = os.path.relpath(os.path.join(self.f.dir, "parcel.edda"))
        text = changed('"price(box) == 5"', '"price(box) == 5", "box.cost == 5"')
        self.f.write("parcel.edda", text)
        (_, status, _, failed), = run.run(self.f.dir, ["PAR-003"], clock=(None, "UTC"))
        self.assertEqual((status, failed), ("failing", [("the price of a light parcel", [(
            f"{path}:{line_of(text, 'box.cost == 5')}", "box.cost == 5", "box.cost is 999")])]))
        binding.ENTITIES["parcel"] = make_parcel
        self.assertEqual(run.run(self.f.dir, ["PAR-003"], clock=(None, "UTC"))[0][1], "examples passed",
                         "the code's cost, 5")

    def test_inputs_named_gives_and_given(self):
        text = changed("functions:\n", '''functions:
  tagged:
    is: "whether a weight carries a tag"
    inputs: {gives: NUMBER, given: TEXT}
    returns: YES_NO
    examples:
      - {given: {gives: 1, given: "red"}, gives: True}
''').replace('"price(box) == 5"', '"price(box) == 5", "tagged(box.weight, \\"red\\")"')
        self.f.write("parcel.edda", text)
        self.assertEqual(self.f.problems(), [])
        self.assertEqual(run.run(self.f.dir, ["PAR-003"], clock=(None, "UTC"))[0][1], "examples passed")
        self.f.write("parcel.edda", text.replace("{gives: 1, given:", "{gives: True, given:"))
        self.assertEqual(self.f.problems(), [("type_mismatch", line_of(text, "{gives: 1, given:"),
                                              "gives expects a NUMBER: True")], "the input, not the result")

    def main(self, *args):
        out, result = io.StringIO(), {}
        with contextlib.redirect_stdout(out):
            code = run.main(["--project", self.f.dir, *args])
        with contextlib.redirect_stdout(io.StringIO()):
            run.main(["--project", self.f.dir, *args], result)
        return code, out.getvalue().splitlines(), result

    def test_the_rows_against_a_correct_a_broken_and_a_missing_function(self):
        path = os.path.relpath(os.path.join(self.f.dir, "parcel.edda"))
        binding.FUNCTIONS["shipping_cost"] = lambda w: 5 if w <= 1 else 12
        code, out, result = self.main()
        self.assertEqual(out[:2], ["function shipping_cost: rows passed: all 2",
                                   "function is_holiday: not run: no binding for function is_holiday"])
        self.assertEqual(result["functions"][1], {"name": "is_holiday", "status": "not run",
                                                  "detail": "no binding for function is_holiday", "failures": []})
        self.assertEqual(out[2], "PAR-001: failing: 1 of 2 examples failed")
        binding.FUNCTIONS["is_holiday"] = lambda day: (day.month, day.day) == (12, 25)
        binding.FUNCTIONS["shipping_cost"] = lambda w: w + 4      # right for 1, wrong for 10
        row = line_of(SPEC, "{given: {weight: 10}, gives: 12}")
        code, out, result = self.main("PAR-002")       # a story named: the rows of every function it reaches
        self.assertEqual((code, out[:3]), (1, ["function shipping_cost: failing: 1 of 2 rows failed",
                                               f"    {path}:{row}: shipping_cost(10) gives 12, but the code gave 14",
                                               "PAR-002: examples passed: all 1"]))
        self.assertEqual([f["name"] for f in result["functions"]], ["shipping_cost"], "is_holiday is not reached")
        self.assertEqual([p["line"] for p in result["failures"] if p["rule"] == "failing_function"], [row])
        code, out, result = self.main()
        self.assertEqual(code, 1)
        self.assertEqual(out[:3], ["function shipping_cost: failing: 1 of 2 rows failed",
                                   f"    {path}:{row}: shipping_cost(10) gives 12, but the code gave 14",
                                   "function is_holiday: rows passed: all 2"])
        (f,) = [p for p in result["failures"] if p["rule"] == "failing_function"]
        self.assertEqual({k: f[k] for k in ("category", "sub", "fix", "acts", "level", "where", "found_by", "line")},
                         {"category": "code differs", "sub": "behaviour", "fix": "wrong", "acts": "agent",
                          "level": "blocks", "where": "function", "found_by": "example run", "line": row})
        binding.FUNCTIONS["shipping_cost"] = lambda w: 1 / 0
        code, out, _ = self.main()
        self.assertIn(f"    {path}:{row - 1}: shipping_cost(1) raised ZeroDivisionError: division by zero", out)


class Approval(unittest.TestCase):

    def setUp(self):
        self.f = Folder()

    def tearDown(self):
        self.f.close()

    def approve(self, name, at="2026-10-05 09:00"):
        return approve.approve(self.f.dir, name, at, "tuan", None, False, clock=(None, "UTC"))

    def blocks(self, sid):
        P = check.project_of(self.f.dir, clock=(None, "UTC"))
        return approve.story_blocks(sid, P, approve.Files(self.f.dir))

    def test_story_blocks_name_the_functions_called(self):
        clerk, cost, holiday, parcel = ("role", "clerk"), ("function", "shipping_cost"), ("function", "is_holiday"), \
            ("entity", "parcel")       # by file name, then file order
        self.assertEqual(self.blocks("PAR-001"), [clerk, cost, holiday, parcel])
        self.assertEqual(self.blocks("PAR-002"), [clerk, cost, parcel], "through a computed property")
        self.assertEqual(self.blocks("PAR-003"), [clerk, cost, parcel], "through a called operation")

    def test_a_function_is_approved_pinned_and_its_pins_go_stale(self):
        with self.assertRaises(approve.Refused) as r:
            self.approve("PAR-002")
        self.assertEqual(str(r.exception), "approve its blocks first")
        for name in ("clerk", "parcel"):
            self.approve(name)
        with self.assertRaises(approve.Refused) as r:
            self.approve("PAR-002")
        self.assertEqual(str(r.exception), "approve its blocks first", "the function is not approved")
        new, kind, number, vc = self.approve("shipping_cost")
        self.assertEqual((kind, number), ("function", 1))
        self.assertTrue(new.startswith("- function: shipping_cost\n  number: 1\n"))
        new, *_ = self.approve("PAR-002")
        self.assertIn("  pins: [{role: clerk, number: 1}, {function: shipping_cost, number: 1}, "
                      "{entity: parcel, number: 1}]\n", new)
        self.assertEqual(self.f.problems("parcel.edda.vc"), [])
        self.assertIn("function shipping_cost: approved v1", self.f.status())
        self.assertIn("story PAR-002: approved v1", self.f.status())
        self.f.write("parcel.edda", changed(ROWS, ROWS + "      - {given: {weight: 20}, gives: 15}\n"))
        self.assertIn("function shipping_cost: draft v1", self.f.status())
        self.approve("shipping_cost")
        self.assertIn("story PAR-002: approved v1, pins stale", self.f.status())
        with self.assertRaises(approve.Refused) as r:
            self.approve("shipping_cost")
        self.assertEqual(str(r.exception), "nothing to approve: the block matches its newest version")
        model = check.model_of(self.f.dir)
        story = next(s for s in model["stories"] if s["id"] == "PAR-002")
        self.assertEqual(story["pins"][1], {"kind": "function", "name": "shipping_cost", "version": 1})
        (fn,) = story["versions"][0]["functions"]
        self.assertEqual((fn["name"], [r["gives"]["value"] for r in fn["examples"]]), ("shipping_cost", [5, 12]))
        self.assertEqual(model["files"][0]["blocks"][2], {"kind": "function", "name": "shipping_cost", "line": 6,
                                                          "status": "approved", "version": 2, "pins_stale": False})

    def test_a_function_reached_only_through_an_always_fact(self):
        text = changed("    may_read: [{role: clerk}]\n",
                       '    always: ["not is_holiday(TIME(\\"2026-12-24\\"))"]\n    may_read: [{role: clerk}]\n')
        self.f.write("parcel.edda", text)
        self.assertEqual(self.f.problems(), [])
        self.assertEqual(self.blocks("PAR-002"), [("role", "clerk"), ("function", "shipping_cost"),
                                                  ("function", "is_holiday"), ("entity", "parcel")])
        for name in ("clerk", "parcel", "shipping_cost"):
            self.approve(name)
        with self.assertRaises(approve.Refused) as r:
            self.approve("PAR-002")
        self.assertEqual(str(r.exception), "approve its blocks first", "is_holiday is not approved")
        self.approve("is_holiday")
        new, *_ = self.approve("PAR-002")
        self.assertIn("{function: is_holiday, number: 1}", new)
        self.f.write("parcel.edda", text.replace('"2026-12-24 00:00"}, gives: False}',
                                                 '"2026-12-24 00:00"}, gives: False}\n      - {given: {day: "2026-01-01"}, gives: True}'))
        self.approve("is_holiday")
        self.assertIn("story PAR-002: approved v1, pins stale", self.f.status())

    def test_a_history_without_functions_stays_valid(self):
        for folder in ("blocks_approved", "approved"):
            path = os.path.join(ROOT, "fixtures", folder)
            P = check.project_of(path)
            for name in os.listdir(path):
                if name.endswith(".edda.vc"):
                    self.assertEqual(check.check(os.path.join(path, name), P)[:4], ([], [], [], []), folder)

    def test_a_pin_to_no_such_function(self):
        self.approve("clerk")
        self.approve("parcel")
        vc = self.f.read("parcel.edda.vc") + (
            "- story: PAR-003\n  number: 1\n  approved_at: \"2026-10-05 09:00\"\n  approved_by: tuan\n"
            "  pins: [{entity: parcel, number: 1}, {function: nope, number: 1}]\n  text: |\n"
            + "".join("    " + line + "\n" for line in check.block_text(SPEC, line_of(SPEC, "  PAR-003:")).splitlines()))
        self.f.write("parcel.edda.vc", vc)
        self.assertEqual(self.f.problems("parcel.edda.vc"), [
            ("bad_pin", line_of(vc, "{function: nope"), "pin function nope v1: no such function")])


class ViewAndModel(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.f = Folder()
        cls.model = check.model_of(cls.f.dir)

    @classmethod
    def tearDownClass(cls):
        cls.f.close()

    def test_the_model_lists_functions(self):
        self.assertEqual((self.model["edda_model"], self.model["revision"]), (2, 71))
        fn = self.model["functions"][0]
        self.assertEqual([k for k in fn], ["name", "is", "inputs", "returns", "examples", "file", "line"])
        self.assertEqual((fn["name"], fn["file"], fn["line"]), ("shipping_cost", "parcel.edda", 6))
        self.assertEqual([(i["name"], i["type"]) for i in fn["inputs"]], [("weight", "NUMBER")])
        self.assertEqual((fn["returns"]["type"], fn["returns"]["line"]), ("NUMBER", 9))
        self.assertEqual(fn["examples"][0], {"given": {"weight": {"kind": "number", "value": 1}},
                                             "gives": {"kind": "number", "value": 5}, "line": 11})
        day = self.model["functions"][1]["examples"][0]
        self.assertEqual((day["given"]["day"], day["gives"]), ({"kind": "time", "value": "2026-12-25"},
                                                               {"kind": "yes_no", "value": True}))

    def test_the_read_view_gives_its_sentences(self):
        self.assertEqual([(s["kind"], s["text"], s["line"]) for s in view.function_sentences(self.model["functions"][0])], [
            ("function", "Shipping cost is what a parcel of that weight costs to ship.", 6),
            ("signature", "Shipping cost takes weight, a number, and gives a number.", 9),
            ("row", "For example, the shipping cost of 1 gives 5.", 11),
            ("row", "For example, the shipping cost of 10 gives 12.", 12)])
        self.assertEqual([s["text"] for s in view.function_sentences(self.model["functions"][1])][1:3], [
            "Is holiday takes day, a time, and gives a yes or no.",
            "For example, the is holiday of the time 2026-12-25 gives yes."])

    def test_a_call_reads_as_a_call_and_its_returns_proves_yes_or_no(self):
        st = self.model["stories"][0]
        texts = [s["text"] for s in view.story_sentences(st, self.model["operations"], self.model["entities"],
                                                         self.model["roles"], self.model["functions"])]
        self.assertIn("Price gives the shipping cost of the parcel's weight.", texts)
        self.assertIn("Then it is done and the result is the shipping cost of 1 and the is holiday of the time "
                      "2026-12-24 is no.", texts)

    def test_edda_view_prints_functions_before_the_stories(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(view.main([self.f.dir]), 0)
        lines = out.getvalue().splitlines()
        self.assertEqual(lines[:2], ["  Shipping cost is what a parcel of that weight costs to ship.",
                                     "  Shipping cost takes weight, a number, and gives a number."])
        self.assertEqual(lines.index("  Price a parcel. As a clerk, I want to know what a parcel costs, so that I "
                                     "can charge for it."), 10)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            view.main([self.f.dir, "PAR-001"])
        self.assertNotIn("Shipping cost is", out.getvalue())


ON = "generated_cases: {on: true, runs: 10, steps: 3}\n"
DIRECT = changed('"parcel.paid == parcel.cost"', '"parcel.paid == shipping_cost(parcel.weight)"')   # charge runs the function


class Generated(unittest.TestCase):

    def setUp(self):
        self.f = Folder(files=[("edda.yaml", ON)])
        binding.ENTITIES["parcel"] = make_parcel
        binding.OPERATIONS.update({"price": price, "charge": charge})
        self.saved = dict(binding.FUNCTIONS)

    def tearDown(self):
        del binding.ENTITIES["parcel"]
        for name in ("price", "charge"):
            del binding.OPERATIONS[name]
        binding.FUNCTIONS.clear()
        binding.FUNCTIONS.update(self.saved)
        self.f.close()

    def generated(self, sid):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            run.main(["--project", self.f.dir, "--seed", "3", sid])
        return [line for line in out.getvalue().splitlines() if "generated cases" in line]

    def test_a_verified_function_is_the_real_one(self):
        binding.FUNCTIONS["shipping_cost"] = lambda w: 5 if w <= 1 else 12
        self.f.write("parcel.edda", DIRECT)
        (line,) = self.generated("PAR-002")
        self.assertTrue(line.startswith("PAR-002: generated cases: 10 runs passed; calls: charge "), line)

    def test_a_failure_lists_the_rows_its_example_needs(self):
        binding.FUNCTIONS["shipping_cost"] = lambda w: 5 if w <= 1 else 12

        def careless(actor, parcel):    # right only where a row covers the weight
            parcel.paid = price(actor, parcel) + (0 if parcel.weight in (1, 10) else 1)
        binding.OPERATIONS["charge"] = careless
        self.f.write("parcel.edda", DIRECT)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = run.main(["--project", self.f.dir, "--seed", "3", "PAR-002"])
        lines = out.getvalue().splitlines()
        self.assertEqual(code, 1)
        at = lines.index("    and under the examples: of the function shipping_cost, the rows the example needs, "
                         "from the real function, to add only once a person approves them:")
        row = re.fullmatch(r"      - \{given: \{weight: (\S+)\}, gives: (\d+)\}    # shipping_cost\(\1\) gives \2",
                           lines[at + 1])
        self.assertTrue(row, lines[at + 1])
        self.assertNotIn(float(row.group(1)), (1, 10))
        import generate     # Hypothesis only now, as run.main imports it
        del binding.FUNCTIONS["shipping_cost"]      # missing: the rows are not known
        run.FUNCTION_RESULTS.clear()
        self.assertEqual(generate.rows_needed([("shipping_cost", [3], 12)]), [
            "    the function shipping_cost has no binding, so the rows the example needs are not known: "
            "shipping_cost(3)"])
        run.FUNCTION_RESULTS.clear()
        binding.FUNCTIONS["shipping_cost"] = lambda w: w + 4
        self.assertEqual(generate.rows_needed([("shipping_cost", [3], 7), ("shipping_cost", [1], 5)]), [
            "    the function shipping_cost is not verified: its rows do not all pass, so the rows the example "
            "needs are not known: shipping_cost(3)"])

    def failed_and_pasted(self, spec=SPEC):
        """generated cases of PAR-002 on spec: (the lines printed, the spec
        with the printed example pasted under PAR-002's examples and the
        rows it needs under shipping_cost's, its title, how it fails
        there); the pasted spec must check, schema and all"""
        self.f.write("parcel.edda", spec)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = run.main(["--project", self.f.dir, "--seed", "3", "PAR-002"])
        lines = out.getvalue().splitlines()
        self.assertEqual(code, 1)
        start = lines.index("    as an example:") + 1
        end = next(i for i, x in enumerate(lines) if i > start and not x.startswith("      "))
        example, rows = lines[start:end], [x for x in lines[end + 1:] if x.startswith("      - {")]
        then = '            then: [DONE, "box.paid == 5"]\n'
        pasted = changed(ROWS, ROWS + "".join(r + "\n" for r in rows), spec)
        pasted = changed(then, then + "".join(x + "\n" for x in example), pasted)
        self.f.write("parcel.edda", pasted)     # pasted as an example, the rows it needs added
        self.f.write("edda.yaml", "")
        self.assertEqual(self.f.problems(), [])
        title = example[0].strip()[1:-2]
        (_, status, _, failed), = run.run(self.f.dir, ["PAR-002"], clock=(None, "UTC"))
        return lines, pasted, title, [f for t, f in failed if t == title]

    def test_a_rule_that_reads_the_computed_property_catches_wrong_code_and_its_pasted_failure_reproduces(self):
        binding.FUNCTIONS["shipping_cost"] = lambda w: 5 if w <= 1 else 12
        binding.ENTITIES["parcel"] = lambda name, values, workdir: binding.Thing("parcel", values, cost=999)
        lines, pasted, title, failed = self.failed_and_pasted()
        found = 'charge should refuse: "too dear to send", but it did not refuse'    # the refuse condition reads 999
        path = os.path.relpath(os.path.join(self.f.dir, "parcel.edda"))
        at = f"{path}:{line_of(pasted, 'when: ' + json.dumps('parcel.cost > 100'))}"
        self.assertIn(f"    {at}: {found}", lines)
        self.assertEqual(failed, [[(at, None, found)]])

    def test_a_failure_in_the_starting_world_pastes_as_one_fact_step(self):
        binding.FUNCTIONS["shipping_cost"] = lambda w: 5 if w <= 1 else 12
        binding.ENTITIES["parcel"] = lambda name, values, workdir: binding.Thing("parcel", values, cost=-1)
        always = changed("    may_read: [{role: clerk}]\n", '    always:\n      - "cost > 0"\n    may_read: [{role: clerk}]\n')
        self.f.write("parcel.edda", always)
        self.assertEqual(self.generated("PAR-002"), [
            "PAR-002: generated cases: not run: no starting world keeps every always-rule"],
            "a code cost that breaks an always fact throws every world away")
        cheap = '''      cheap:
        is: "whether a cost is below a hundred"
        inputs: {n: NUMBER}
        who: [{role: clerk}]
        refuse:
          - when: "n < 0"
            reason: "no such cost"
        returns: "n < 100"
'''
        spec = changed('"cost > 0"', '"cheap(cost)"', always).replace(
            "    operations:\n      charge:", "    operations:\n" + cheap + "      charge:")
        binding.OPERATIONS["cheap"] = lambda actor, n: n < 100     # the read the always fact calls, on the code's -1
        try:
            lines, pasted, title, failed = self.failed_and_pasted(spec)
        finally:
            del binding.OPERATIONS["cheap"]
        self.assertEqual(title, "generated: the starting world breaks a rule")
        self.assertIn('          - then: ["cheap(parcel_1.cost)"]', lines)
        path = os.path.relpath(os.path.join(self.f.dir, "parcel.edda"))
        found = 'cheap should refuse: "no such cost", but it did not refuse'
        at = f"{path}:{line_of(pasted, 'when: ' + json.dumps('n < 0'))}"
        self.assertIn(f"    {at}: {found}", lines)
        self.assertEqual(failed, [[(at, None, found)]])

    def test_a_given_that_cannot_be_made_pastes_and_fails_at_its_given(self):
        def broken(name, values, workdir):
            raise ValueError("no scales")
        binding.ENTITIES["parcel"] = broken
        binding.FUNCTIONS["shipping_cost"] = lambda w: 5 if w <= 1 else 12
        lines, pasted, title, failed = self.failed_and_pasted()
        self.assertIn("    given parcel_1 could not be made: ValueError: no scales", lines)
        path = os.path.relpath(os.path.join(self.f.dir, "parcel.edda"))
        self.assertEqual(failed, [[(f"{path}:{line_of(pasted, 'given:', line_of(pasted, title))}", None,
                                    "given parcel_1 could not be made: ValueError: no scales")]])

    def test_an_unverified_function_skips_the_operation(self):
        binding.FUNCTIONS["shipping_cost"] = lambda w: w + 4
        self.assertEqual(self.generated("PAR-002"), [
            "PAR-002: generated cases: not run: skipped charge: function shipping_cost not verified"])
        del binding.FUNCTIONS["shipping_cost"]
        self.assertEqual(self.generated("PAR-002"), [
            "PAR-002: generated cases: not run: skipped charge: function shipping_cost not verified"])


if __name__ == "__main__":
    unittest.main()
