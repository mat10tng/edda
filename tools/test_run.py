#!/usr/bin/env python3
"""The runner catches a broken implementation (vision, decision EE).

    python3 tools/test_run.py

EDDA-001 runs through the binding against the real checker and its
examples pass; against a checker that moves one problem's line it is
failing, on the example and the then line that state the line. EDDA-003
passes too, and fails when notes come back out of order. A small
project of its own shows a known failure is kept when a later fact has no
binding, ACTOR and RESULT stay across a step without a call, and with:
values name a given only where an entity or actor is declared, and a bad
value or a crash in the code fails its example or fact, never the run.
It also holds the reference's rules for inputs (required by position,
optional by keyword, None when left out), the clock on a who-line (run
from the example's start) and left-out properties (DEFAULT, [] for MANY, None for OPTIONAL,
otherwise unset: failing when read, never "no binding", in the runner
or inside bound code, by every ordinary path to a thing's fields or a
maker's values, carried unread only by Thing(entity, values)), and the clock read through computed properties
and the operations they call (run from the example's start). A small account project holds
every call to its operation's rules: the refusal the spec gives, reason
for reason; ensure, with OLD, inside a comprehension too; always, with
a read it calls not judging it again; the frame rule, the actor
included, also_changes and a computed property naming only what it
reads on that entity; a read inside a fact that changes nothing; an
ensure on the clock, the binding told the call's time. A small item project leaves out a
DEFAULT of every kind, 01, a text with a backslash and a time
included: the runner gives each the value the checker's model gives,
a time as a time, and "2026-02-30" stays a text.
"""
import contextlib
import copy
import datetime
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["EDDA_LOG"] = "off"     # the tools and their children never write the log (section 11)
import edda_binding as binding   # noqa: E402
import run                       # noqa: E402

SPECS = os.path.join(binding.checker.ROOT, "specs")


def story(results, sid):
    return next(r for r in results if r[0] == sid)


ORDER = """\
roles:
  shop_user:
    is: "a person at a shop"
    properties:
      shop: TEXT
      locale: TEXT, OPTIONAL
      level: DEFAULT 1
  agent:
    is: "a person acting for a shop"

entities:
  order:
    is: "what a workshop buys"
    properties:
      status: DEFAULT incoming | removed
      units_sent: DEFAULT 0
      history: TEXT, OPTIONAL
      label: TEXT, OPTIONAL
      due: TIME, OPTIONAL
      parts: MANY order
      ref: TEXT
      overdue: {computed: "TODAY > TIME(\\"2020-01-01\\")"}
      late_flag: {computed: "overdue and units_sent > 0"}
      sent_late: {computed: "late_day(units_sent)"}
    may_change: {status: {incoming: [removed]}}
    may_read: [{role: shop_user}, {role: agent}]

stories:
  TST-001:
    story: "see a known failure"
    about: order
    as_a: shop_user
    i_want: "a failure kept when a later fact has no binding"
    so_that: "a false fact always fails"
    examples:
      "a known failure is kept":
        given:
          - order: bad
        steps:
          - then: ["bad.units_sent == 5", "bad.history is not None"]
  TST-002:
    story: "count an order"
    about: order
    as_a: shop_user
    i_want: "to count an order"
    so_that: "I know what was sent"
    operations:
      count:
        is: "the units sent of an order"
        inputs: {order: order}
        who: [{role: shop_user}, {role: agent}]
        returns: "order.units_sent"
    examples:
      "ACTOR and RESULT stay":
        given:
          - actor: erik
            with: {roles: [shop_user], shop: "north"}
          - order: purchase
            with: {units_sent: 2}
        steps:
          - when: {actor: erik, call: "count(purchase)"}
            then: [DONE, "RESULT == 2", "ACTOR.shop == \\"north\\""]
          - then: ["RESULT == 2", "ACTOR.name == \\"erik\\""]
  TST-003:
    story: "names stay as written"
    about: order
    as_a: shop_user
    i_want: "a role, choice or text that matches a given to stay as written"
    so_that: "only an entity or actor property names a given"
    examples:
      "names stay as written":
        given:
          - actor: agent
            with: {roles: [shop_user], shop: "north"}
          - actor: bob
            with: {roles: [agent]}
          - order: removed
          - order: purchase
            with: {status: removed, label: "removed"}
        steps:
          - when: {actor: bob, call: "count(purchase)"}
            then: [DONE, "ACTOR.roles == [\\"agent\\"]", "purchase.label == \\"removed\\""]
  TST-004:
    story: "a bad value fails the example"
    about: order
    as_a: shop_user
    i_want: "a bad value or a crash to fail its example, never the run"
    so_that: "every example is judged"
    operations:
      halve:
        is: "half a number"
        inputs: {n: NUMBER}
        who: [{role: shop_user}]
        returns: "n / 2"
    examples:
      "an argument divides by zero":
        given:
          - actor: erik
            with: {roles: [shop_user], shop: "north"}
        steps:
          - when: {actor: erik, call: "halve(1 / 0)"}
            then: [DONE]
      "the implementation returns a wrong value":
        given:
          - actor: erik
            with: {roles: [shop_user], shop: "north"}
          - order: purchase
            with: {units_sent: 2}
        steps:
          - when: {actor: erik, call: "count(purchase)"}
            then: [DONE, "sum(count(purchase) for x in [1]) == 2", "purchase.units_sent > 1", "purchase.units_sent == 2"]
      "the call crashes":
        given:
          - actor: erik
            with: {roles: [shop_user], shop: "north"}
        steps:
          - when: {actor: erik, call: "halve(4)"}
            then: [DONE]
      "a good example still runs":
        given:
          - actor: erik
            with: {roles: [shop_user], shop: "north"}
          - order: spare
        steps:
          - when: {actor: erik, call: "count(spare)"}
            then: [DONE]
  TST-005:
    story: "a crash in the binding fails its example"
    about: order
    as_a: shop_user
    i_want: "a given that cannot be made or a property that crashes to fail its example"
    so_that: "every example is judged"
    examples:
      "a given cannot be made":
        given:
          - actor: erik
            with: {roles: [shop_user], shop: "north"}
          - order: purchase
        steps:
          - when: {actor: erik, call: "count(purchase)"}
            then: [DONE]
      "a property crashes":
        given:
          - order: purchase
            with: {units_sent: 2}
        steps:
          - then: ["purchase.units_sent == 2", "purchase.label is None"]
      "a good example still runs":
        given:
          - actor: erik
            with: {roles: [shop_user], shop: "north"}
        steps:
          - when: {actor: erik, call: "halve(4)"}
            then: [DONE, "RESULT == 2"]
  TST-006:
    story: "inputs by position and keyword"
    about: order
    as_a: shop_user
    i_want: "required inputs by position, optional ones by keyword and None when left out"
    so_that: "a call means what the reference says"
    operations:
      tag:
        is: "the note an order is tagged with"
        inputs: {note: "TEXT, OPTIONAL", order: order}
        who: [{role: shop_user, when: "order.units_sent == 2 and note is None"}]
        returns: "note"
    examples:
      "an optional input left out is None":
        given:
          - actor: erik
            with: {roles: [shop_user], shop: "north"}
          - order: purchase
            with: {units_sent: 2}
        steps:
          - when: {actor: erik, call: "tag(purchase)"}
            then: [DONE, "RESULT is None", "tag(purchase, note=\\"x\\") == \\"x\\""]
  TST-007:
    story: "the clock on a who-line"
    about: order
    as_a: shop_user
    i_want: "a who-line that reads the clock to report the clock"
    so_that: "no story aborts the run"
    operations:
      late:
        is: "whether the day has come"
        inputs: {order: order}
        who: [{role: shop_user, when: "TODAY > TIME(\\"2020-01-01\\")"}]
        returns: "order.units_sent"
    examples:
      "a who-line reads TODAY":
        starts_at: "2026-10-05 09:00"
        given:
          - actor: erik
            with: {roles: [shop_user], shop: "north"}
          - order: purchase
        steps:
          - when: {actor: erik, call: "late(purchase)"}
            then: [DONE]
  TST-008:
    story: "left-out properties"
    about: order
    as_a: shop_user
    i_want: "a left-out property to take its DEFAULT, [] for MANY, None for OPTIONAL"
    so_that: "givens mean what the reference says"
    examples:
      "left out on an actor and an entity":
        given:
          - actor: erik
            with: {roles: [shop_user], shop: "north"}
          - order: purchase
          - order: dated
            with: {due: "2026-10-03 10:00"}
        steps:
          - when: {actor: erik, call: "count(purchase)"}
            then:
              - DONE
              - "ACTOR.locale is None"
              - "ACTOR.level == 1"
              - "purchase.status == incoming"
              - "purchase.units_sent == 0"
              - "purchase.label is None"
              - "purchase.parts == []"
              - "dated.due == TIME(\\"2026-10-03 10:00\\")"
  TST-009:
    story: "unset is not unbound"
    about: order
    as_a: shop_user
    i_want: "a left-out required value to fail its example only when read"
    so_that: "unset and no binding are told apart"
    examples:
      "a left-out value is read":
        given:
          - actor: erik
            with: {roles: [shop_user]}
          - order: purchase
        steps:
          - when: {actor: erik, call: "count(purchase)"}
            then: [DONE, "purchase.ref == \\"x\\"", "ACTOR.shop == \\"north\\""]
      "a left-out value is not read":
        given:
          - order: purchase
        steps:
          - then: ["purchase.units_sent == 0"]
  TST-010:
    story: "a computed property on the clock"
    about: order
    as_a: shop_user
    i_want: "a fact reading a computed property that reads the clock to report the clock"
    so_that: "no story runs on a clock that is not built"
    examples:
      "a fact reads a computed property through another":
        starts_at: "2026-10-05 09:00"
        given:
          - order: purchase
        steps:
          - then: ["purchase.late_flag == False"]
  TST-011:
    story: "unset inside bound code"
    about: order
    as_a: shop_user
    i_want: "an unset value used inside bound code to fail its example"
    so_that: "an unset value is never used silently"
    operations:
      has_ref:
        is: "whether an order has the ref x"
        inputs: {order: order}
        who: [{role: shop_user}]
        returns: "order.ref == \\"x\\""
    examples:
      "a bound operation compares an unset value":
        given:
          - order: purchase
        steps:
          - then: ["has_ref(purchase) == False"]
      "a bound operation tests an unset value for truth":
        given:
          - actor: erik
            with: {roles: [shop_user], shop: "north"}
          - order: purchase
        steps:
          - when: {actor: erik, call: "has_ref(purchase)"}
            then: [DONE]
  TST-012:
    story: "the clock through an operation"
    about: order
    as_a: shop_user
    i_want: "a computed property that calls an operation on the clock to report the clock"
    so_that: "no story runs on a clock that is not built"
    operations:
      late_day:
        is: "whether a day with sent units is late"
        inputs: {n: NUMBER}
        who: [{role: shop_user}]
        returns: "n > 0 and after_day()"
      after_day:
        is: "whether the day has come"
        who: [{role: shop_user}]
        returns: "TODAY > TIME(\\"2020-01-01\\")"
    examples:
      "a fact reads a computed property that calls a nested operation on the clock":
        starts_at: "2026-10-05 09:00"
        given:
          - order: purchase
        steps:
          - then: ["purchase.sent_late == False"]
"""


def make_order(name, values, workdir):     # binds every property but history
    return binding.Thing("order", status=values.get("status", "incoming"),
                         units_sent=values.get("units_sent", 0), label=values.get("label"))


# Every ordinary way bound code reaches a value in a mapping, each ending in
# an identity test that would pass silently on a leaked Unset (ref left out).
MAPPING_READS = {
    "[key]": lambda d: d["ref"] is None,
    "get": lambda d: d.get("ref") is None,
    "pop": lambda d: d.pop("ref") is None,
    "popitem": lambda d: dict(d.popitem() for _ in range(len(d))).get("ref") is None,
    "setdefault": lambda d: d.setdefault("ref") is None,
    "iteration": lambda d: {k: d[k] for k in d}["ref"] is None,
    "keys()": lambda d: {k: d[k] for k in d.keys()}["ref"] is None,
    "values()": lambda d: list(d.values())[list(d).index("ref")] is None,
    "items()": lambda d: dict(d.items())["ref"] is None,
    "copy()": lambda d: d.copy().get("ref") is None,
    "dict(x)": lambda d: dict(d)["ref"] is None,
    "{**x}": lambda d: {**d}.get("ref") is None,
    "f(**x)": lambda d: (lambda **kw: kw.get("ref"))(**d) is None,
    "x | y": lambda d: (d | {}).get("ref") is None,
    "y | x": lambda d: ({} | d).get("ref") is None,
    "update": lambda d: (lambda c: c.update(d) or c)({}).get("ref") is None,
    "==": lambda d: d == {k: None if k == "ref" else dict.get(d, k) for k in list(d)},
    "json.dumps": lambda d: '"ref": null' in json.dumps(d),
    "copy.copy": lambda d: copy.copy(d).get("ref") is None,
    "copy.deepcopy": lambda d: copy.deepcopy(d).get("ref") is None,
}
THING_READS = {
    "attribute": lambda o: o.ref is None,
    "getattr": lambda o: getattr(o, "ref") is None,
    "getattr with default": lambda o: getattr(o, "ref", None) is None,
    "hasattr": lambda o: hasattr(o, "ref") is False,
    "copy.copy": lambda o: copy.copy(o).__dict__.get("ref") is None,
    "copy.deepcopy": lambda o: copy.deepcopy(o).__dict__.get("ref") is None,
    **{f"{via} {k}": (lambda read, fields: lambda o: read(fields(o)))(read, fields)
       for via, fields in (("vars()", vars), ("__dict__", lambda o: o.__dict__))
       for k, read in MAPPING_READS.items()},
}
# Names alone hand out no value, so these leave no Unset in what they return.
MAPPING_NAMES = {
    "iteration": list, "keys()": lambda d: list(d.keys()), "reversed": lambda d: list(reversed(d)),
    "in": lambda d: "ref" in d, "len": len,
}


DEFAULTS = r"""roles:
  shop_user:
    is: "a person at a shop"

entities:
  item:
    is: "a thing with every kind of DEFAULT"
    properties:
      count: DEFAULT 01
      ratio: DEFAULT 01.50
      flag: DEFAULT True
      path: DEFAULT "C:\New"
      blank: DEFAULT ""
      kind: DEFAULT plain | boxed
      due: DEFAULT "2026-10-04 09:00"
      odd: DEFAULT "2026-02-30"
    may_read: [{role: shop_user}]

stories:
  TST-020:
    story: "left-out defaults"
    about: item
    as_a: shop_user
    i_want: "every DEFAULT left out in a given to take its value"
    so_that: "the runner reads a DEFAULT as the checker does"
    examples:
      "every kind left out":
        given:
          - item: box
        steps:
          - then:
              - "box.count == 1"
              - "box.ratio == 1.5"
              - "box.flag == True"
              - "box.path == \"C:\\\\New\""
              - "box.blank == \"\""
              - "box.kind == plain"
              - "box.due < TIME(\"2026-10-05\")"
              - "box.odd == \"2026-02-30\""
"""


class DefaultTest(unittest.TestCase):
    """section 4: a DEFAULT means one value in the checker's model and in
    the runner, DEFAULT 01 and a backslash in a text included"""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        with open(os.path.join(self.dir.name, "item.edda"), "w") as f:
            f.write(DEFAULTS)
        binding.ENTITIES["item"] = lambda name, values, workdir: binding.Thing("item", values)

    def tearDown(self):
        del binding.ENTITIES["item"]
        self.dir.cleanup()

    def test_left_out_defaults_in_a_given(self):
        sid, status, detail, failed = story(run.run(self.dir.name, ["TST-020"]), "TST-020")
        self.assertEqual((status, detail, failed), ("examples passed", "all 1", []))

    def test_model_and_runner_agree(self):
        p = subprocess.run([sys.executable, os.path.join(os.path.dirname(run.__file__), "check.py"),
                            "--model", self.dir.name], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout)
        props = json.loads(p.stdout)["entities"][0]["properties"]
        model = {x["name"]: x["default"] for x in props}
        runner = run.left_out({x["name"]: x["phrase"] for x in props}, {}, "box")
        self.assertEqual(model, {"count": 1, "ratio": 1.5, "flag": True, "path": "C:\\New",
                                 "blank": "", "kind": "plain", "due": "2026-10-04 09:00",
                                 "odd": "2026-02-30"})
        # a time reads as the runner reads a time in with: (section 7.2)
        model = {n: run.as_time(v, next(x["type"] for x in props if x["name"] == n)) for n, v in model.items()}
        self.assertEqual(runner, model)
        self.assertEqual([type(v) for v in runner.values()], [type(v) for v in model.values()])


class OwnProjectTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        with open(os.path.join(self.dir.name, "order.edda"), "w") as f:
            f.write(ORDER)
        binding.ENTITIES["order"] = make_order
        binding.OPERATIONS["count"] = lambda actor, order: order.units_sent

    def tearDown(self):
        del binding.ENTITIES["order"], binding.OPERATIONS["count"]
        for name in ("halve", "tag", "late", "has_ref", "late_day", "after_day"):
            binding.OPERATIONS.pop(name, None)
        self.dir.cleanup()

    def main(self, *stories):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = run.main(["--project", self.dir.name, *stories])
        return code, out.getvalue()

    def test_known_failure_is_kept_when_a_later_fact_has_no_binding(self):
        sid, status, detail, failed = story(run.run(self.dir.name, ["TST-001"]), "TST-001")
        self.assertEqual((status, detail), ("failing", "1 of 1 examples failed; no binding for order.history"))
        self.assertEqual(failed[0][1][0][1:], ("bad.units_sent == 5", "bad.units_sent is 0"))
        self.assertEqual(self.main("TST-001")[0], 1)

    def test_passing_story_reports_examples_passed_not_done(self):
        code, out = self.main("TST-002")
        self.assertEqual((code, out), (0, "TST-002: examples passed: all 1\n"))

    def test_actor_and_result_stay_across_a_step_without_a_call(self):
        sid, status, detail, failed = story(run.run(self.dir.name, ["TST-002"]), "TST-002")
        self.assertEqual((status, failed), ("examples passed", []), (detail, failed))

    def test_with_names_a_given_only_for_an_entity_or_actor(self):
        sid, status, detail, failed = story(run.run(self.dir.name, ["TST-003"]), "TST-003")
        self.assertEqual((status, failed), ("examples passed", []), (detail, failed))
        given = run.load_project(self.dir.name)[2][2][1]["examples"]["names stay as written"]["given"]
        made = run.make_givens(given, self.dir.name)
        self.assertEqual((made["purchase"].status, made["purchase"].label), ("removed", "removed"))

    def tst_004(self):
        """TST-004's failures by example title"""
        sid, status, detail, failed = story(run.run(self.dir.name, ["TST-004"]), "TST-004")
        return status, detail, {title: [f[1:] for f in fs] for title, fs in failed}

    def test_an_argument_that_fails_fails_its_example_not_the_run(self):
        binding.OPERATIONS["halve"] = lambda actor, n: n / 2
        status, detail, failed = self.tst_004()
        self.assertEqual(failed["an argument divides by zero"], [("DONE", "1 / 0: division by zero")])
        self.assertEqual(self.main("TST-004")[0], 1)

    def test_a_wrong_value_from_the_implementation_fails_the_fact_not_the_run(self):
        binding.OPERATIONS["halve"] = lambda actor, n: n / 2
        binding.OPERATIONS["count"] = lambda actor, order: None
        binding.ENTITIES["order"] = lambda name, values, workdir: binding.Thing("order", units_sent="two")
        status, detail, failed = self.tst_004()
        self.assertEqual(failed["the implementation returns a wrong value"], [
            ("sum(count(purchase) for x in [1]) == 2", "sum over None"),
            ("purchase.units_sent > 1", 'a comparison of "two" with 1'),
            ("purchase.units_sent == 2", 'purchase.units_sent is "two"')])
        self.assertEqual(self.main("TST-004")[0], 1)

    def test_a_call_that_crashes_in_the_binding_fails_its_example_not_the_run(self):
        def halve(actor, n):
            raise RuntimeError("boom")
        binding.OPERATIONS["halve"] = halve
        status, detail, failed = self.tst_004()
        self.assertEqual((status, detail), ("failing", "2 of 4 examples failed"))
        self.assertEqual(failed["the call crashes"], [("DONE", "raised RuntimeError: boom")])
        self.assertEqual(self.main("TST-004")[0], 1)

    def tst_005(self):
        """TST-005's status, detail and failures by example title"""
        binding.OPERATIONS["halve"] = lambda actor, n: n / 2
        sid, status, detail, failed = story(run.run(self.dir.name, ["TST-005"]), "TST-005")
        return status, detail, {title: [f[1:] for f in fs] for title, fs in failed}

    def test_a_fixture_folder_that_does_not_exist_fails_its_example_not_the_run(self):
        binding.ENTITIES["order"] = lambda name, values, workdir: binding.make_spec_file(
            name, {"fixture": "no_such_fixture"}, workdir)
        status, detail, failed = self.tst_005()
        self.assertEqual((status, detail), ("failing", "2 of 3 examples failed"))
        [(text, found)] = failed["a given cannot be made"]
        self.assertIsNone(text)
        self.assertTrue(found.startswith("given purchase could not be made: FileNotFoundError: "), found)
        code, out = self.main("TST-005")
        self.assertEqual(code, 1)
        self.assertIn(": given purchase could not be made: FileNotFoundError: ", out)

    def test_a_maker_that_raises_fails_its_example_not_the_run(self):
        def boom(*a):
            raise RuntimeError("boom")
        binding.ENTITIES["order"] = boom
        status, detail, failed = self.tst_005()
        self.assertEqual((status, detail), ("failing", "2 of 3 examples failed"))
        self.assertEqual(failed["a given cannot be made"], [(None, "given purchase could not be made: RuntimeError: boom")])
        real = binding.make_actor
        binding.make_actor = boom
        try:
            status, detail, failed = self.tst_005()
        finally:
            binding.make_actor = real
        self.assertEqual(failed["a good example still runs"], [(None, "given erik could not be made: RuntimeError: boom")])

    def test_a_property_that_raises_fails_its_fact_not_the_run(self):
        class Broken(binding.Thing):
            @property
            def units_sent(self):
                return 1 / 0
        binding.ENTITIES["order"] = lambda name, values, workdir: Broken("order", label=None)
        status, detail, failed = self.tst_005()
        self.assertEqual((status, detail), ("failing", "2 of 3 examples failed"))
        self.assertEqual(failed["a given cannot be made"], [("DONE", "raised ZeroDivisionError: division by zero")])
        self.assertEqual(failed["a property crashes"], [
            ("purchase.units_sent == 2", "purchase.units_sent raised ZeroDivisionError: division by zero")])
        self.assertEqual(self.main("TST-005")[0], 1)


    def test_a_false_fact_on_a_cyclic_entity_shows_its_kind_and_given_name(self):
        run.load_project(self.dir.name)
        binding.ENTITIES["order"] = lambda name, values, workdir: binding.Thing("order")
        made = run.make_givens([{"order": "purchase"}, {"order": "spare"}], self.dir.name)
        purchase, spare = made["purchase"], made["spare"]
        purchase.customer = binding.Thing("customer", latest_order=purchase)
        env = {"RESULT": purchase, "spare": spare, "found": [purchase, binding.Thing("problem")]}
        self.assertEqual(run.judge("RESULT == spare", env), "RESULT is order purchase")
        self.assertEqual(run.judge("found == []", env), "found is [order purchase, problem]")


    # section 6 inputs, section 3 who-lines and the clock, section 8 left-out properties

    def test_required_inputs_by_position_optional_by_keyword_and_none_when_left_out(self):
        binding.OPERATIONS["tag"] = lambda actor, order, note: note
        sid, status, detail, failed = story(run.run(self.dir.name, ["TST-006"]), "TST-006")
        self.assertEqual((status, detail, failed), ("examples passed", "all 1", []))

    def test_the_clock_on_a_who_line_runs_from_the_examples_start(self):
        binding.OPERATIONS["late"] = lambda actor, order: 0
        try:
            sid, status, detail, failed = story(run.run(self.dir.name, ["TST-007"]), "TST-007")
        finally:
            del binding.OPERATIONS["late"]
        self.assertEqual((status, detail, failed), ("examples passed", "all 1", []))

    def test_left_out_properties_take_default_empty_list_or_none(self):
        binding.ENTITIES["order"] = lambda name, values, workdir: binding.Thing("order", values)
        sid, status, detail, failed = story(run.run(self.dir.name, ["TST-008"]), "TST-008")
        self.assertEqual((status, detail, failed), ("examples passed", "all 1", []))

    def test_a_left_out_required_value_fails_only_when_read(self):
        binding.ENTITIES["order"] = lambda name, values, workdir: binding.Thing("order", values)
        sid, status, detail, failed = story(run.run(self.dir.name, ["TST-009"]), "TST-009")
        self.assertEqual((status, detail), ("failing", "1 of 2 examples failed"))
        self.assertEqual([f[1:] for f in failed[0][1]], [
            ('purchase.ref == "x"', "purchase.ref is unset"),
            ('ACTOR.shop == "north"', "ACTOR.shop is unset")])

    def test_a_property_the_binding_does_not_make_is_not_bound_not_unset(self):
        sid, status, detail, failed = story(run.run(self.dir.name, ["TST-009"]), "TST-009")
        self.assertEqual((status, detail), ("not run", "no binding for order.ref"))

    def test_a_computed_property_on_the_clock_runs_from_the_examples_start(self):
        binding.ENTITIES["order"] = lambda name, values, workdir: binding.Thing("order", values, late_flag=False)
        sid, status, detail, failed = story(run.run(self.dir.name, ["TST-010"]), "TST-010")
        self.assertEqual((status, detail, failed), ("examples passed", "all 1", []))

    def test_an_unset_value_compared_inside_bound_code_fails_the_example(self):
        binding.ENTITIES["order"] = lambda name, values, workdir: binding.Thing("order", values)
        binding.OPERATIONS["has_ref"] = lambda actor, order: order.ref == "x"
        sid, status, detail, failed = story(run.run(self.dir.name, ["TST-011"]), "TST-011")
        self.assertEqual((status, detail), ("failing", "2 of 2 examples failed"))
        self.assertEqual([f[1:] for f in dict(failed)["a bound operation compares an unset value"]],
                         [("has_ref(purchase) == False", "purchase.ref is unset")])

    def test_an_unset_value_tested_for_truth_inside_bound_code_fails_the_example(self):
        def has_ref(actor, order):
            try:
                return True if order.ref else False
            except Exception:       # bound code cannot swallow an unset read
                return False
        binding.ENTITIES["order"] = lambda name, values, workdir: binding.Thing("order", values)
        binding.OPERATIONS["has_ref"] = has_ref
        sid, status, detail, failed = story(run.run(self.dir.name, ["TST-011"]), "TST-011")
        self.assertEqual((status, detail), ("failing", "2 of 2 examples failed"))
        self.assertEqual([f[1:] for f in dict(failed)["a bound operation tests an unset value for truth"]],
                         [("DONE", "purchase.ref is unset")])
        self.assertEqual(self.main("TST-011")[0], 1)

    def test_an_identity_test_on_an_unset_value_inside_bound_code_fails_the_example(self):
        binding.ENTITIES["order"] = lambda name, values, workdir: binding.Thing("order", values)
        for read in (lambda o: o.ref, lambda o: getattr(o, "ref"),
                     lambda o: vars(o)["ref"], lambda o: o.__dict__.get("ref")):
            binding.OPERATIONS["has_ref"] = lambda actor, order: read(order) is None
            sid, status, detail, failed = story(run.run(self.dir.name, ["TST-011"]), "TST-011")
            self.assertEqual((status, detail), ("failing", "2 of 2 examples failed"))
            self.assertEqual([f[1:] for f in dict(failed)["a bound operation compares an unset value"]],
                             [("has_ref(purchase) == False", "purchase.ref is unset")])

        def maker(name, values, workdir):
            return binding.Thing("order", ref="x" if values.get("ref") is None else "y")
        binding.ENTITIES["order"] = maker
        sid, status, detail, failed = story(run.run(self.dir.name, ["TST-009"]), "TST-009")
        self.assertEqual([f[1:] for f in dict(failed)["a left-out value is not read"]],
                         [(None, "given purchase could not be made: purchase.ref is unset")])

    def test_a_dict_copy_of_a_things_fields_does_not_hide_an_unset_value(self):
        # Astra round 55: dict(vars(order))["ref"] is None gave False, and passed
        binding.ENTITIES["order"] = lambda name, values, workdir: binding.Thing("order", values)
        binding.OPERATIONS["has_ref"] = lambda actor, order: dict(vars(order))["ref"] is None
        sid, status, detail, failed = story(run.run(self.dir.name, ["TST-011"]), "TST-011")
        self.assertEqual([f[1:] for f in dict(failed)["a bound operation compares an unset value"]],
                         [("has_ref(purchase) == False", "purchase.ref is unset")])

    def test_every_ordinary_path_to_an_unset_field_fails_the_example(self):
        binding.ENTITIES["order"] = lambda name, values, workdir: binding.Thing("order", values)
        for path, read in THING_READS.items():
            with self.subTest(thing=path):
                binding.OPERATIONS["has_ref"] = lambda actor, order: read(order)
                sid, status, detail, failed = story(run.run(self.dir.name, ["TST-011"]), "TST-011")
                self.assertEqual([f[1:] for f in dict(failed)["a bound operation compares an unset value"]],
                                 [("has_ref(purchase) == False", "purchase.ref is unset")])
        for path, read in MAPPING_READS.items():
            with self.subTest(values=path):
                binding.ENTITIES["order"] = lambda name, values, workdir: binding.Thing(
                    "order", units_sent=0, ref="x" if read(values) else "y")
                sid, status, detail, failed = story(run.run(self.dir.name, ["TST-009"]), "TST-009")
                self.assertEqual([f[1:] for f in dict(failed)["a left-out value is not read"]],
                                 [(None, "given purchase could not be made: purchase.ref is unset")])

    def test_names_alone_hand_out_no_unset_value(self):
        def holds_unset(x):
            return type(x) is binding.Unset or isinstance(x, list) and any(map(holds_unset, x))
        for path, names in MAPPING_NAMES.items():
            with self.subTest(path=path):
                values = binding.Values(ref=binding.Unset("purchase.ref"), units_sent=0)
                thing = binding.Thing("order", values)
                for d in (values, vars(thing), thing.__dict__):
                    self.assertFalse(holds_unset(names(d)))

    def test_a_maker_carries_an_unset_value_onto_the_thing_unread(self):
        values = binding.Values(ref=binding.Unset("purchase.ref"), units_sent=0)
        thing = binding.Thing("order", values, label="a")
        self.assertIs(type(dict.get(vars(thing), "ref")), binding.Unset)
        self.assertEqual((thing.units_sent, thing.label), (0, "a"))
        with self.assertRaises(binding.UnsetRead):
            binding.Thing("order", **values)

    def test_an_unset_value_used_inside_a_bound_property_or_maker_fails_the_example(self):
        class Computed(binding.Thing):
            @property
            def units_sent(self):
                return self.ref + "!"
        binding.ENTITIES["order"] = lambda name, values, workdir: Computed("order", values)
        sid, status, detail, failed = story(run.run(self.dir.name, ["TST-009"]), "TST-009")
        self.assertEqual([f[1:] for f in dict(failed)["a left-out value is not read"]],
                         [("purchase.units_sent == 0", "purchase.ref is unset")])

        def maker(name, values, workdir):
            return binding.Thing("order", ref=values["ref"].upper())
        binding.ENTITIES["order"] = maker
        sid, status, detail, failed = story(run.run(self.dir.name, ["TST-009"]), "TST-009")
        self.assertEqual([f[1:] for f in dict(failed)["a left-out value is not read"]],
                         [(None, "given purchase could not be made: purchase.ref is unset")])

    def test_a_computed_property_calling_an_operation_on_the_clock_runs_from_the_examples_start(self):
        binding.OPERATIONS["late_day"] = lambda actor, n: False
        binding.OPERATIONS["after_day"] = lambda actor: True
        binding.ENTITIES["order"] = lambda name, values, workdir: binding.Thing("order", values, sent_late=False)
        try:
            sid, status, detail, failed = story(run.run(self.dir.name, ["TST-012"]), "TST-012")
        finally:
            del binding.OPERATIONS["late_day"], binding.OPERATIONS["after_day"]
        self.assertEqual((status, detail, failed), ("examples passed", "all 1", []))


ACCOUNT = """\
roles:
  clerk:
    is: "a person at the desk"
    properties:
      tries: DEFAULT 0

entities:
  account:
    is: "money kept for a customer"
    properties:
      balance: DEFAULT 0
      status: DEFAULT open | closed
      note: TEXT, OPTIONAL
      history: TEXT, OPTIONAL
      stamped: TIME, OPTIONAL
      entries: MANY entry
      total: {computed: "sum(e.amount for e in entries)"}
      leader: {computed: "ranked(entries)[0].label"}
    may_change: {status: {open: [closed]}}
    always:
      - "balance >= 0"
    may_read: [{role: clerk}]
    may_update: [{role: clerk}]

  entry:
    is: "one sum noted on an account"
    part_of: account
    properties:
      amount: DEFAULT 0
      label: TEXT, OPTIONAL
    may_read: [{role: clerk}]

  purse:
    is: "coins kept for a customer"
    properties:
      coins: DEFAULT 0
    always:
      - "nonnegative(coins)"
    may_read: [{role: clerk}]
    may_update: [{role: clerk}]

stories:
  RUL-001:
    story: "keep money on an account"
    about: account
    as_a: clerk
    i_want: "to put money on an account, note sums and close it"
    so_that: "the money is kept"
    operations:
      deposit:
        is: "puts money on an open account"
        inputs: {account: account, n: INTEGER}
        who: [{role: clerk}]
        refuse:
          - when: "account.status == closed"
            reason: "the account is closed"
          - when: "n <= 0"
            reason: "nothing to put"
        ensure:
          - "account.balance == OLD(account.balance) + n"
        also_changes: ["account.history"]
      add_entry:
        is: "notes a sum on an account"
        inputs: {account: account, n: INTEGER}
        who: [{role: clerk}]
        ensure:
          - "account.total == OLD(account.total) + n"
      close:
        is: "closes an account"
        inputs: {account: account}
        who: [{role: clerk}]
        refuse:
          - when: "account.status == closed"
            reason: "the account is already closed"
        ensure:
          - "account.status == closed"
      balance_of:
        is: "the money on an account"
        inputs: {account: account}
        who: [{role: clerk}]
        returns: "account.balance"
    examples:
      "money is put on an account":
        given:
          - actor: ann
            with: {roles: [clerk]}
          - account: savings
            with: {balance: 5}
        steps:
          - when: {actor: ann, call: "deposit(savings, 3)"}
            then: [DONE, "savings.balance == 8", "balance_of(savings) == 8"]
      "a closed account takes no money":
        given:
          - actor: ann
            with: {roles: [clerk]}
          - account: old
            with: {status: closed}
        steps:
          - when: {actor: ann, call: "deposit(old, 3)"}
            then:
              - refused: "the account is closed"
      "a sum is noted":
        given:
          - actor: ann
            with: {roles: [clerk]}
          - account: savings
        steps:
          - when: {actor: ann, call: "add_entry(savings, 4)"}
            then: [DONE, "savings.total == 4"]
      "an account is closed":
        given:
          - actor: ann
            with: {roles: [clerk]}
          - account: savings
        steps:
          - when: {actor: ann, call: "close(savings)"}
            then: [DONE, "savings.status == closed"]
  RUL-002:
    story: "take money from an account"
    about: account
    as_a: clerk
    i_want: "to take money from an account"
    so_that: "the customer gets it"
    operations:
      withdraw:
        is: "takes money from an account"
        inputs: {account: account, n: INTEGER}
        who: [{role: clerk}]
        ensure:
          - "account.balance == OLD(account.balance) - n"
    examples:
      "more than the balance is taken":
        given:
          - actor: ann
            with: {roles: [clerk]}
          - account: savings
            with: {balance: 5}
        steps:
          - when: {actor: ann, call: "withdraw(savings, 7)"}
            then: [DONE]
  RUL-003:
    story: "stamp an account"
    about: account
    as_a: clerk
    i_want: "to stamp an account with the time"
    so_that: "I know when it was seen"
    operations:
      stamp:
        is: "stamps an account with the time"
        inputs: {account: account}
        who: [{role: clerk}]
        ensure:
          - "account.stamped == NOW"
    examples:
      "an account is stamped":
        starts_at: "2026-10-05 09:00"
        given:
          - actor: ann
            with: {roles: [clerk]}
          - account: savings
        steps:
          - when: {actor: ann, call: "stamp(savings)"}
            then: [DONE]
  RUL-004:
    story: "fill a purse"
    about: account
    as_a: clerk
    i_want: "to put coins in a purse"
    so_that: "the coins are kept"
    operations:
      nonnegative:
        is: "whether a number is not below zero"
        inputs: {n: INTEGER}
        who: [{role: clerk}]
        returns: "n >= 0"
      fill:
        is: "puts coins in a purse"
        inputs: {purse: purse, n: INTEGER}
        who: [{role: clerk}]
        ensure:
          - "purse.coins == OLD(purse.coins) + n"
    examples:
      "a purse is filled":
        given:
          - actor: ann
            with: {roles: [clerk]}
          - purse: small
            with: {coins: 1}
        steps:
          - when: {actor: ann, call: "fill(small, 2)"}
            then: [DONE, "small.coins == 3"]
  RUL-005:
    story: "note a sum on one account of two"
    about: account
    as_a: clerk
    i_want: "a sum noted on one account to leave the other alone"
    so_that: "each account keeps its own sums"
    examples:
      "a sum is noted on one account of two":
        given:
          - actor: ann
            with: {roles: [clerk]}
          - entry: old_sum
            with: {amount: 7}
          - account: savings
          - account: other
            with: {entries: [old_sum]}
        steps:
          - when: {actor: ann, call: "add_entry(savings, 4)"}
            then: [DONE, "savings.total == 4", "other.total == 7"]
  RUL-006:
    story: "settle an account"
    about: account
    as_a: clerk
    i_want: "the balance set to the sum of its entries"
    so_that: "the balance matches the sums noted"
    operations:
      settle:
        is: "sets the balance to the sum of the entries"
        inputs: {account: account}
        who: [{role: clerk}]
        ensure:
          - "account.balance == sum(OLD(e.amount) for e in account.entries)"
    examples:
      "an account is settled":
        given:
          - actor: ann
            with: {roles: [clerk]}
          - entry: first
            with: {amount: 7}
          - entry: second
            with: {amount: 4}
          - account: savings
            with: {entries: [first, second]}
        steps:
          - when: {actor: ann, call: "settle(savings)"}
            then: [DONE, "savings.balance == 11"]
  RUL-007:
    story: "append an entry"
    about: account
    as_a: clerk
    i_want: "an entry added to the end of a list of entries"
    so_that: "the entries keep their order"
    operations:
      append_entry:
        is: "adds an entry to the end of an account's entries"
        inputs: {account: account, entries: MANY entry, fresh: entry}
        who: [{role: clerk}]
        ensure:
          - "account.entries == OLD(entries) + [fresh]"
    examples:
      "an entry is appended":
        given:
          - actor: ann
            with: {roles: [clerk]}
          - entry: first
            with: {amount: 7}
          - entry: extra
            with: {amount: 2}
          - account: savings
            with: {entries: [first]}
        steps:
          - when: {actor: ann, call: "append_entry(savings, savings.entries, extra)"}
            then: [DONE, "len(savings.entries) == 2"]
  RUL-008:
    story: "put an entry first"
    about: account
    as_a: clerk
    i_want: "an entry ranked first on its account"
    so_that: "it leads the account"
    operations:
      ranked:
        is: "entries, smallest amount first"
        inputs: {entries: MANY entry}
        who: [{role: clerk}]
        returns: "entries"
        ordered_by: ["entry.amount"]
      promote:
        is: "makes an entry the smallest on its account"
        inputs: {account: account, entry: entry}
        who: [{role: clerk}]
        ensure:
          - "account.leader == entry.label"
    examples:
      "an entry is put first":
        given:
          - actor: ann
            with: {roles: [clerk]}
          - entry: first
            with: {amount: 7, label: "a"}
          - entry: second
            with: {amount: 4, label: "b"}
          - entry: loose
            with: {amount: 1}
          - account: savings
            with: {entries: [first, second]}
        steps:
          - when: {actor: ann, call: "promote(savings, first)"}
            then: [DONE, "savings.leader == \\"a\\""]
"""


class Account(binding.Thing):
    @property
    def total(self):
        return sum(e.amount for e in self.entries)

    @property
    def leader(self):
        return ranked(None, self.entries)[0].label


def deposit(actor, account, n):            # obeys the spec
    if account.status == "closed":
        raise binding.Refused("the account is closed")
    if n <= 0:
        raise binding.Refused("nothing to put")
    account.balance += n
    account.history = f"put {n}"           # allowed by also_changes


def close(actor, account):
    if account.status == "closed":
        raise binding.Refused("the account is already closed")
    account.status = "closed"


def add_entry(actor, account, n):
    account.entries.append(binding.Thing("entry", amount=n))


def withdraw(actor, account, n):
    account.balance -= n


def fill(actor, purse, n):
    purse.coins += n


def settle(actor, account):
    account.balance = sum(e.amount for e in account.entries)


def append_entry(actor, account, entries, fresh):
    entries.append(fresh)                   # entries is account.entries


def ranked(actor, entries):
    return sorted(entries, key=lambda e: e.amount)


def promote(actor, account, entry):
    entry.amount = min(e.amount for e in account.entries) - 1


GOOD = {"deposit": deposit, "close": close, "add_entry": add_entry, "withdraw": withdraw,
        "balance_of": lambda actor, account: account.balance,
        "stamp": lambda actor, account: None,
        "nonnegative": lambda actor, n: n >= 0, "fill": fill, "settle": settle,
        "append_entry": append_entry, "ranked": ranked, "promote": promote}


class RulesTest(unittest.TestCase):
    """every call is held to its operation's rules (reference section 6)"""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "account.edda")
        with open(self.path, "w") as f:
            f.write(ACCOUNT)
        self.made = {}      # the given things by name, so a test's code can reach them
        for kind, cls in (("account", Account), ("entry", binding.Thing), ("purse", binding.Thing)):
            binding.ENTITIES[kind] = lambda name, values, workdir, kind=kind, cls=cls: \
                self.made.setdefault(name, cls(kind, values))
        binding.OPERATIONS.update(GOOD)

    def tearDown(self):
        for kind in ("account", "entry", "purse"):
            del binding.ENTITIES[kind]
        for name in GOOD:
            del binding.OPERATIONS[name]
        self.dir.cleanup()

    def line(self, text, after=None):
        """file:line of the first line holding text, after the line holding after"""
        lines = ACCOUNT.splitlines()
        start = lines.index(next(x for x in lines if after in x)) if after else 0
        n = next(i for i in range(start, len(lines)) if text in lines[i]) + 1
        return f"{os.path.relpath(self.path)}:{n}"

    def failed(self, sid):
        sid, status, detail, failed = story(run.run(self.dir.name, [sid]), sid)
        return status, {title: fs for title, fs in failed}

    def test_an_operation_that_obeys_every_rule_passes(self):
        sid, status, detail, failed = story(run.run(self.dir.name, ["RUL-001"]), "RUL-001")
        self.assertEqual((status, detail, failed), ("examples passed", "all 4", []))

    def test_also_changes_allows_a_change_the_frame_rule_would_refuse(self):
        def deposit_noted(actor, account, n):
            deposit(actor, account, n)
            account.note = "put"            # named nowhere; history, also_changes, was fine
        binding.OPERATIONS["deposit"] = deposit_noted
        status, failed = self.failed("RUL-001")
        self.assertEqual(failed["money is put on an account"], [
            (self.line("deposit:"), None, "deposit changed savings.note, which the spec does not name")])

    def test_a_change_the_spec_does_not_name_fails(self):
        def close_and_empty(actor, account):
            close(actor, account)
            account.balance = 7
        binding.OPERATIONS["close"] = close_and_empty
        status, failed = self.failed("RUL-001")
        self.assertEqual(failed, {"an account is closed": [
            (self.line("close:"), None, "close changed savings.balance, which the spec does not name")]})

    def test_a_broken_ensure_fails(self):
        binding.OPERATIONS["close"] = lambda actor, account: None
        status, failed = self.failed("RUL-001")
        self.assertEqual(failed, {"an account is closed": [
            (self.line('- "account.status == closed"', "close:"), None,
             'close: ensure account.status == closed: found account.status is "open"')]})

    def test_a_broken_ensure_with_old_fails(self):
        def deposit_forgets(actor, account, n):
            account.balance = n
        binding.OPERATIONS["deposit"] = deposit_forgets
        status, failed = self.failed("RUL-001")
        self.assertEqual(failed["money is put on an account"], [
            (self.line("OLD(account.balance) + n"), None,
             "deposit: ensure account.balance == OLD(account.balance) + n: found account.balance is 3")])

    def test_a_broken_always_rule_fails(self):
        status, failed = self.failed("RUL-002")
        self.assertEqual((status, failed), ("failing", {"more than the balance is taken": [
            (self.line('"balance >= 0"'), None, "withdraw: always balance >= 0, on account savings: found balance is -2")]}))

    def test_a_refusal_with_the_wrong_reason_fails(self):
        def deposit_wrong(actor, account, n):
            if account.status == "closed":
                raise binding.Refused("no such account")
            deposit(actor, account, n)
        binding.OPERATIONS["deposit"] = deposit_wrong
        status, failed = self.failed("RUL-001")
        self.assertEqual(failed, {"a closed account takes no money": [
            (self.line('"account.status == closed"', "deposit:"), None,
             'deposit should refuse: "the account is closed", but it refused: "no such account"')]})

    def test_a_refusal_the_spec_does_not_give_fails(self):
        def deposit_never(actor, account, n):
            raise binding.Refused("the account is closed")
        binding.OPERATIONS["deposit"] = deposit_never
        status, failed = self.failed("RUL-001")
        self.assertEqual(failed, {"money is put on an account": [
            (self.line("deposit:"), None, 'deposit refused: "the account is closed", but the spec does not refuse')]})

    def test_a_call_not_refused_where_the_spec_refuses_fails(self):
        def deposit_always(actor, account, n):
            account.balance += n
        binding.OPERATIONS["deposit"] = deposit_always
        status, failed = self.failed("RUL-001")
        self.assertEqual(failed, {"a closed account takes no money": [
            (self.line('"account.status == closed"', "deposit:"), None,
             'deposit should refuse: "the account is closed", but it did not refuse')]})

    def test_a_refused_call_that_changed_something_fails(self):
        def deposit_marks(actor, account, n):
            account.note = "tried"
            deposit(actor, account, n)
        binding.OPERATIONS["deposit"] = deposit_marks
        status, failed = self.failed("RUL-001")
        self.assertEqual(failed["a closed account takes no money"], [
            (self.line("deposit:"), None, "deposit changed old.note, which the spec does not name")])

    def test_a_read_inside_a_fact_that_changes_something_fails(self):
        def balance_of(actor, account):
            account.note = "seen"
            return account.balance
        binding.OPERATIONS["balance_of"] = balance_of
        status, failed = self.failed("RUL-001")
        self.assertEqual(failed, {"money is put on an account": [
            (self.line("balance_of:"), None, "balance_of changed savings.note, which the spec does not name")]})

    def test_an_always_rule_that_calls_a_read_does_not_check_itself_again(self):
        status, failed = self.failed("RUL-004")
        self.assertEqual((status, failed), ("examples passed", {}))

    def test_an_always_rule_that_calls_a_read_still_fails_once_when_broken(self):
        binding.OPERATIONS["fill"] = lambda actor, purse, n: setattr(purse, "coins", -n)
        status, failed = self.failed("RUL-004")
        self.assertEqual(failed, {"a purse is filled": [
            (self.line("purse.coins == OLD(purse.coins) + n"), None,
             "fill: ensure purse.coins == OLD(purse.coins) + n: found purse.coins is -2"),
            (self.line('"nonnegative(coins)"'), None,
             "fill: always nonnegative(coins), on purse small: found it is false")]})

    def test_naming_a_computed_property_names_only_what_it_reads_on_that_entity(self):
        def add_entry_and_spoil(actor, account, n):
            add_entry(actor, account, n)
            self.made["old_sum"].amount = 999      # another account's entry
        binding.OPERATIONS["add_entry"] = add_entry_and_spoil
        status, failed = self.failed("RUL-005")
        self.assertEqual(failed, {"a sum is noted on one account of two": [
            (self.line("add_entry:"), None, "add_entry changed old_sum.amount, which the spec does not name")]})

    def test_naming_a_computed_property_allows_what_it_reads(self):
        status, failed = self.failed("RUL-005")
        self.assertEqual((status, failed), ("examples passed", {}))

    def test_old_inside_a_comprehension_keeps_its_loop_variable(self):
        status, failed = self.failed("RUL-006")
        self.assertEqual((status, failed), ("examples passed", {}))

    def test_old_inside_a_comprehension_fails_a_wrong_value(self):
        def settle_wrong(actor, account):
            account.balance = sum(e.amount for e in account.entries) + 1
        binding.OPERATIONS["settle"] = settle_wrong
        status, failed = self.failed("RUL-006")
        self.assertEqual(failed, {"an account is settled": [
            (self.line("sum(OLD(e.amount)"), None,
             "settle: ensure account.balance == sum(OLD(e.amount) for e in account.entries): "
             "found account.balance is 12")]})

    def test_old_of_an_input_list_the_call_appends_to_keeps_its_value(self):
        status, failed = self.failed("RUL-007")
        self.assertEqual((status, failed), ("examples passed", {}))

    def test_old_of_an_input_list_fails_a_wrong_append(self):
        def append_twice(actor, account, entries, fresh):
            entries.extend([fresh, fresh])
        binding.OPERATIONS["append_entry"] = append_twice
        status, failed = self.failed("RUL-007")
        self.assertEqual(failed, {"an entry is appended": [
            (self.line("OLD(entries) + [fresh]"), None,
             "append_entry: ensure account.entries == OLD(entries) + [fresh]: "
             "found account.entries is [entry first, entry extra, entry extra]")]})

    def test_naming_a_computed_property_allows_what_its_reads_ordered_by_reads(self):
        status, failed = self.failed("RUL-008")
        self.assertEqual((status, failed), ("examples passed", {}))

    def test_ordered_by_names_only_the_items_of_the_ranked_list(self):
        def promote_and_spoil(actor, account, entry):
            promote(actor, account, entry)
            self.made["loose"].amount = 0        # on no account's ranked list
        binding.OPERATIONS["promote"] = promote_and_spoil
        status, failed = self.failed("RUL-008")
        self.assertEqual(failed, {"an entry is put first": [
            (self.line("promote:"), None, "promote changed loose.amount, which the spec does not name")]})

    def test_a_refused_call_that_changed_the_actor_fails(self):
        def deposit_counts(actor, account, n):
            actor.tries += 1
            deposit(actor, account, n)
        binding.OPERATIONS["deposit"] = deposit_counts
        status, failed = self.failed("RUL-001")
        self.assertEqual(failed, {
            "money is put on an account": [
                (self.line("deposit:"), None, "deposit changed ann.tries, which the spec does not name")],
            "a closed account takes no money": [
                (self.line("deposit:"), None, "deposit changed ann.tries, which the spec does not name")]})

    def test_an_ensure_that_reads_now_is_held_to_the_examples_start(self):
        seen = []
        binding.clock = seen.append      # the binding is told each call's time (section 9)

        def stamp(actor, account):
            account.stamped = seen[-1]
        binding.OPERATIONS["stamp"] = stamp
        try:
            sid, status, detail, failed = story(run.run(self.dir.name, ["RUL-003"]), "RUL-003")
        finally:
            del binding.clock        # tearDown restores stamp with the rest of GOOD
        self.assertEqual((status, detail, failed), ("examples passed", "all 1", []))
        self.assertEqual([str(t) for t in seen], ["2026-10-05 09:00:00"])

    def test_a_broken_rule_is_printed_at_its_line(self):
        binding.OPERATIONS["close"] = lambda actor, account: None
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = run.main(["--project", self.dir.name, "RUL-001"])
        self.assertEqual(code, 1)
        at = self.line('- "account.status == closed"', "close:")
        self.assertIn(f"        {at}: close: ensure account.status == closed: "
                      'found account.status is "open"\n', out.getvalue())


class ShowTest(unittest.TestCase):
    def test_a_failed_fact_on_returned_problems_shows_their_fields(self):
        found = [binding.Thing("problem", kind="refused", rule="unknown_key",
                               file_name="order.edda", line=33,
                               message="unknown key: ensures",
                               about=binding.Thing("entity", _given="spare"))]
        msg = run.judge("RESULT == []", {"RESULT": found})
        self.assertEqual(msg, 'RESULT is [problem{kind: "refused", rule: "unknown_key", '
                              'file_name: "order.edda", line: 33, '
                              'message: "unknown key: ensures", about: entity spare}]')
        print("example:", msg)

    def test_a_value_whose_repr_raises_is_shown_unprintable(self):
        class Odd:
            def __repr__(self):
                raise ValueError("no")
        self.assertEqual(run.judge("RESULT == 1", {"RESULT": Odd()}), "RESULT is <unprintable: ValueError>")


class RunTest(unittest.TestCase):
    def test_real_checker_passes_edda_001(self):
        sid, status, detail, failed = story(run.run(SPECS, ["EDDA-001"]), "EDDA-001")
        self.assertEqual((status, failed), ("examples passed", []), detail)

    def test_broken_checker_fails_edda_001_where_it_breaks(self):
        real = binding.problems_of

        def broken(path):       # unknown_key one line too low
            found = real(path)
            for p in found:
                if p.rule == "unknown_key":
                    p.line += 1
            return found

        binding.problems_of = broken
        try:
            sid, status, detail, failed = story(run.run(SPECS, ["EDDA-001"]), "EDDA-001")
        finally:
            binding.problems_of = real
        self.assertEqual(status, "failing")
        self.assertEqual(detail, "1 of 26 examples failed")
        self.assertEqual(failed, [("an unknown key is refused",
                                   [(os.path.relpath(os.path.join(SPECS, "spec_file.edda")) + ":152", "RESULT[0].line == 33", "RESULT[0].line is 34")])])

    def test_real_checker_passes_edda_003(self):
        sid, status, detail, failed = story(run.run(SPECS, ["EDDA-003"]), "EDDA-003")
        self.assertEqual((status, detail, failed), ("examples passed", "all 2", []))

    def test_notes_that_do_not_refuse_a_file_that_does_not_check_fail_edda_003(self):
        real = binding.notes_of
        binding.notes_of = lambda files: real([f for f in files if "ensures:" not in f.text])  # the bad file left out
        try:
            sid, status, detail, failed = story(run.run(SPECS, ["EDDA-003"]), "EDDA-003")
        finally:
            binding.notes_of = real
        self.assertEqual((status, detail), ("failing", "1 of 2 examples failed"))
        self.assertEqual(failed[0][0], "a file that does not check is refused and no notes are listed")

    def test_notes_out_of_order_fail_edda_003(self):
        real = binding.checker.notes
        binding.checker.notes = lambda paths: sorted(real(paths), key=lambda n: n["line"])
        try:
            sid, status, detail, failed = story(run.run(SPECS, ["EDDA-003"]), "EDDA-003")
        finally:
            binding.checker.notes = real
        self.assertEqual((status, detail), ("failing", "1 of 2 examples failed"))

    def test_actor_without_an_allowed_role_is_refused(self):
        run.run(SPECS, ["EDDA-001"])            # loads the operations as written
        stranger = binding.make_actor("eve", ["shop_user"], {})
        with self.assertRaises(binding.Refused) as r:
            run.run_operation("check", stranger, [None], {})
        self.assertEqual(r.exception.reason, "check is not allowed for shop_user")


def tree(folder):
    """every file under folder with its bytes"""
    out = {}
    for d, _, names in os.walk(folder):
        for n in names:
            with open(os.path.join(d, n), "rb") as f:
                out[os.path.join(d, n)] = f.read()
    return out


class ApprovalTest(unittest.TestCase):
    """approve, approve_block and diff run through the binding against
    approve.py and check.py, on the fixture copy, never on specs/ or
    fixtures/; notes refuses a file that does not check"""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.tuan = binding.make_actor("tuan", ["operator"], {})
        binding.clock(datetime.datetime(2026, 10, 2, 9, 0))

    def tearDown(self):
        binding.clock(None)
        self.dir.cleanup()

    def file(self, fixture, name="f"):
        return binding.make_spec_file(name, {"fixture": fixture}, self.dir.name)

    def test_the_real_code_passes_edda_004_to_008(self):
        found = run.run(SPECS, ["EDDA-004", "EDDA-005", "EDDA-006", "EDDA-008"])
        self.assertEqual([(sid, status, detail) for sid, status, detail, _ in found],
                         [("EDDA-008", "examples passed", "all 8"), ("EDDA-004", "examples passed", "all 9"),
                          ("EDDA-005", "examples passed", "all 6"), ("EDDA-006", "examples passed", "all 6")])

    def test_running_every_story_writes_nothing_under_specs_or_fixtures(self):
        before = tree(SPECS), tree(binding.FIXTURES)
        run.run(SPECS)
        self.assertEqual((tree(SPECS), tree(binding.FIXTURES)), before)

    def test_approve_appends_a_version_to_the_copy(self):
        f = self.file("blocks_approved")
        fixture = tree(os.path.join(binding.FIXTURES, "blocks_approved"))
        st, old = f.stories[0], f.history.versions
        binding.OPERATIONS["approve"](self.tuan, st, because="the shop asked for it")
        self.assertIs(f.stories[0], st)
        self.assertEqual(f.history.versions[:-1], old)
        self.assertIs(f.history.versions[-1], st.versions[-1])
        v = st.versions[-1]
        self.assertEqual((v.number, v.approved_by, v.approved_at, v.because), (1, "tuan",
                         datetime.datetime(2026, 10, 2, 9, 0), "the shop asked for it"))
        self.assertEqual([(p.kind, p.name, p.number) for p in v.pins], [("role", "shop_user", 1), ("entity", "order", 1)])
        self.assertEqual([p.block for p in v.pins], st.blocks)
        self.assertTrue(st.approved)
        self.assertFalse(st.pins_stale)
        with open(f._path + ".vc") as vc:
            self.assertEqual(f.history.text, vc.read())
        self.assertEqual(tree(os.path.join(binding.FIXTURES, "blocks_approved")), fixture)

    def test_approve_refuses_with_approve_py_s_reason_and_writes_nothing(self):
        for fixture, reason, version in (("approved", "nothing to approve: the story matches its newest version "
                                                      "and its pins are current", 1),
                                         ("order", "approve its blocks first", 0),
                                         ("unknown_key", "the file does not check", 0)):
            f = self.file(fixture, fixture)
            text = f.history.text
            with self.assertRaises(binding.Refused) as r:
                binding.OPERATIONS["approve"](self.tuan, f.stories[0])
            self.assertEqual(r.exception.reason, reason)
            self.assertEqual((f.history.text, f.stories[0].version), (text, version))

    def test_approve_needs_the_clock(self):
        binding.clock(None)
        with self.assertRaises(ValueError):
            binding.OPERATIONS["approve"](self.tuan, self.file("blocks_approved").stories[0])

    def test_approve_block_appends_a_block_version(self):
        f = self.file("order")
        order = f.blocks[1]
        binding.OPERATIONS["approve_block"](self.tuan, order)
        self.assertEqual((order.kind, order.name, order.version, order.approved), ("entity", "order", 1, True))
        self.assertEqual((order.versions[0].because, order.versions[0].pins, f.blocks[0].version), (None, [], 0))

    def test_approve_block_refuses_an_approved_block(self):
        f = self.file("approved")
        with self.assertRaises(binding.Refused) as r:
            binding.OPERATIONS["approve_block"](self.tuan, f.blocks[1])
        self.assertEqual(r.exception.reason, "nothing to approve: the block matches its newest version")
        self.assertEqual(f.blocks[1].version, 1)

    def test_diff_gives_the_checker_s_changes(self):
        changes = binding.OPERATIONS["diff"](self.tuan, self.file("reason_changed").stories[0])
        self.assertEqual([(c.kind, c.line) for c in changes], [("removed", 16), ("added", 16), ("removed", 37), ("added", 37)])
        fresh = binding.OPERATIONS["diff"](self.tuan, self.file("order", "fresh").stories[0])
        self.assertEqual((len(fresh), {c.kind for c in fresh}), (48, {"added"}))

    def test_changes_out_of_order_fail_edda_006(self):
        real = binding.checker.changes
        binding.checker.changes = lambda old, new: real(old, new)[::-1]
        try:
            sid, status, detail, failed = story(run.run(SPECS, ["EDDA-006"]), "EDDA-006")
        finally:
            binding.checker.changes = real
        self.assertEqual((status, detail), ("failing", "5 of 6 examples failed"))

    def test_an_approval_that_writes_nothing_fails_edda_005(self):
        real = binding.approver.approve
        binding.approver.approve = lambda folder, name, at, by, because, dry_run: real(folder, name, at, by, because, True)
        try:
            sid, status, detail, failed = story(run.run(SPECS, ["EDDA-005"]), "EDDA-005")
        finally:
            binding.approver.approve = real
        self.assertEqual((status, detail), ("failing", "2 of 6 examples failed"))

    def test_notes_refuses_a_file_that_does_not_check(self):
        a, bad = self.file("notes_a", "a"), self.file("notes_bad", "bad")
        with self.assertRaises(binding.Refused) as r:
            binding.OPERATIONS["notes"](self.tuan, [a, bad])
        self.assertEqual(r.exception.reason, "a file does not check")
        self.assertEqual(len(binding.OPERATIONS["notes"](self.tuan, [a])), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2, warnings=False)    # Python's own filters: check.py leaves files to the collector
