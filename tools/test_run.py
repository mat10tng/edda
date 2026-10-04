#!/usr/bin/env python3
"""The runner catches a broken implementation (vision, decision EE).

    python3 tools/test_run.py

EDDA-001 runs through the binding against the real checker and its
examples pass; against a checker that moves one problem's line it is
failing, on the example and the then line that state the line. A small
project of its own shows a known failure is kept when a later fact has no
binding, ACTOR and RESULT stay across a step without a call, and with:
values name a given only where an entity or actor is declared, and a bad
value or a crash in the code fails its example or fact, never the run.
It also holds the reference's rules for inputs (required by position,
optional by keyword, None when left out), the clock on a who-line (not
run) and left-out properties (DEFAULT, [] for MANY, None for OPTIONAL,
otherwise unset: failing when read, never "no binding", in the runner
or inside bound code, by every ordinary path to a thing's fields or a
maker's values, carried unread only by Thing(entity, values)), and the clock read through computed properties
and the operations they call (not run).
"""
import contextlib
import copy
import io
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
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

    def test_the_clock_on_a_who_line_is_not_run(self):
        binding.OPERATIONS["late"] = lambda actor, order: 0
        sid, status, detail, failed = story(run.run(self.dir.name, ["TST-007"]), "TST-007")
        self.assertEqual((status, detail), ("not run", "TODAY needs the clock, not built yet"))

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

    def test_a_computed_property_on_the_clock_is_not_run(self):
        sid, status, detail, failed = story(run.run(self.dir.name, ["TST-010"]), "TST-010")
        self.assertEqual((status, detail), ("not run", "order.late_flag needs the clock, not built yet"))

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

    def test_a_computed_property_calling_an_operation_on_the_clock_is_not_run(self):
        binding.OPERATIONS["late_day"] = lambda actor, n: False
        binding.OPERATIONS["after_day"] = lambda actor: False
        binding.ENTITIES["order"] = lambda name, values, workdir: binding.Thing("order", values, sent_late=False)
        sid, status, detail, failed = story(run.run(self.dir.name, ["TST-012"]), "TST-012")
        self.assertEqual((status, detail), ("not run", "order.sent_late needs the clock, not built yet"))


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

    def test_actor_without_an_allowed_role_is_refused(self):
        run.run(SPECS, ["EDDA-001"])            # loads the operations as written
        stranger = binding.make_actor("eve", ["shop_user"], {})
        with self.assertRaises(binding.Refused) as r:
            run.run_operation("check", stranger, [None], {})
        self.assertEqual(r.exception.reason, "check is not allowed for shop_user")


if __name__ == "__main__":
    unittest.main(verbosity=2, warnings=False)    # Python's own filters: check.py leaves files to the collector
