#!/usr/bin/env python3
"""The analyser (reference section 11, revision 66): dead_refusal,
conflicting_ensure, empty_ensure and forbidden_change, found from the
spec alone.

    python3 tools/test_analyse.py

For each flag: a spec that should raise it does, a near miss does not,
and a condition too complex for the simple rules is skipped, with no flag
and no crash. The design note's four examples, an always rule clash, an
integer edge (`q < 1` against `q <= 0`), a decimal one, and a refusal
with `or`. forbidden_change runs only in the one shape where it is
provably right, and each of its six conditions has a test that flags
and one that skips; Astra's round 82, 83 and 84 cases give no flag. dead_refusal and
conflicting_ensure, under the same two cases, can only miss a flag.
Each spec is one order.edda in a temporary folder.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check  # noqa: E402

SPEC = """roles:
  shop_user:
    is: "a person at a shop"

entities:
  order:
    is: "what a workshop buys"
    properties:
      status: {status}
      quantity: INTEGER
      price: NUMBER
      paid: YES_NO
      note: TEXT, OPTIONAL
      lines: MANY line
{order_props}
    may_change: {{status: {{draft: [pending, cancelled], pending: [shipped, cancelled]}}}}
    always:
{always}
    may_update: [{{role: shop_user}}]
  line:
    is: "one article"
    part_of: order
    properties:
      units: INTEGER
  shop:
    is: "a place that sells"
    properties:
      name: TEXT
      open: YES_NO
      order: order
{shop_always}
{entities}
stories:
  FIX-001:
    story: "work on an order"
    about: order
    as_a: shop_user
    i_want: "to work on an order"
    so_that: "it moves on"
    operations:
      submit:
        is: "does something to an order"
        inputs: {inputs}
        who: [{who}]
{refuse}
        ensure:
{ensure}
"""

TWO = "{f: order, g: order}"
INV = "status != draft or quantity == 0"
ANALYSER = {"dead_refusal", "conflicting_ensure", "empty_ensure", "forbidden_change"}


def flags(refuse=(), ensure=("f.paid",), always=("quantity >= 0",), who="{role: shop_user}", inputs="{f: order}",
          shop_always=(), status="DEFAULT draft | pending | shipped | cancelled", order_props="", entities=""):
    """the analyser's flags of a spec: [(rule, line, message)]"""
    text = SPEC.format(
        always="\n".join(f'      - "{a}"' for a in always),
        shop_always="\n".join(["    always:"] * bool(shop_always) + [f'      - "{a}"' for a in shop_always]),
        refuse="\n".join(["        refuse:"] * bool(refuse)
                          + [f'          - when: "{w}"\n            reason: "r{i}"' for i, w in enumerate(refuse)]),
        ensure="\n".join(f'          - "{e}"' for e in ensure),
        who=who, inputs=inputs, status=status, order_props=order_props, entities=entities)
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "order.edda")
        with open(path, "w") as f:
            f.write(text)
        src, shape, meaning, history, found = check.check(path, check.project_of(d))
        assert not (src or shape or meaning or history), (src, shape, meaning, text)
    return [p for p in found if p[0] in ANALYSER]


def conflicts(**kw):
    """the conflicting_ensure flags alone: a status ensure also meets may_change"""
    return [p for p in flags(**kw) if p[0] == "conflicting_ensure"]


def rules(found):
    return [rule for rule, _, _ in found]


class DeadRefusal(unittest.TestCase):
    def test_note_example(self):
        found = flags(refuse=("f.quantity <= 0", "f.quantity < 0"))
        self.assertEqual([(r, m) for r, _, m in found],
                         [("dead_refusal", "submit: refusal 2 can never be given; refusal 1 covers it")])

    def test_line_is_the_refusal(self):
        (_, line, _), = flags(refuse=("f.quantity <= 0", "f.quantity < 0"))
        self.assertEqual(SPEC.splitlines().index("{refuse}") + 4, line)     # refuse:, when, reason, when

    def test_near_miss(self):
        self.assertEqual(flags(refuse=("f.quantity < 0", "f.quantity <= 0")), [])

    def test_integer_edge(self):
        self.assertEqual(rules(flags(refuse=("f.quantity < 1", "f.quantity <= 0"))), ["dead_refusal"])

    def test_decimal_edge(self):
        self.assertEqual(rules(flags(refuse=("f.price < 1", "f.price <= 0.5"))), ["dead_refusal"])
        self.assertEqual(flags(refuse=("f.price < 1", "f.price <= 1")), [])

    def test_whole_numbers_between_bounds(self):
        # no whole number between 0 and 1: the second refusal adds nothing
        self.assertEqual(rules(flags(refuse=("f.quantity <= 0 or f.quantity >= 1", "f.quantity == 5"))),
                         ["dead_refusal"])

    def test_or_refusal(self):
        found = flags(refuse=("f.status == shipped or f.status == cancelled", "f.status in [cancelled]"))
        self.assertEqual(rules(found), ["dead_refusal"])
        self.assertEqual(flags(refuse=("f.status == shipped or f.status == cancelled", "f.status != draft")), [])

    def test_covered_by_two(self):
        found = flags(refuse=("f.status == shipped", "f.quantity < 0", "f.status == cancelled",
                              "f.status not in [draft, pending]"))
        self.assertEqual([m for _, _, m in found],
                         ["submit: refusal 4 can never be given; refusals 1 and 3 cover it"])

    def test_not_and_yes_no(self):
        self.assertEqual(rules(flags(refuse=("not f.paid", "f.paid == False and f.quantity > 3"))), ["dead_refusal"])
        self.assertEqual(flags(refuse=("not f.paid", "f.paid and f.quantity > 3")), [])

    def test_optional_has_no_value_too(self):
        self.assertEqual(flags(refuse=("f.note is not None", "f.note is None")), [])
        self.assertEqual(rules(flags(refuse=("f.note is not None", "f.note is not None and f.quantity > 0"))),
                         ["dead_refusal"])

    def test_too_complex_is_skipped(self):
        self.assertEqual(flags(refuse=("len(f.lines) == 0", "len(f.lines) == 0")), [])
        self.assertEqual(flags(refuse=("f.quantity < 0", "f.quantity < f.price")), [])
        self.assertEqual(flags(refuse=("sum(l.units for l in f.lines) < 0", "f.quantity < 0")), [])

    def test_two_inputs_only_miss(self):
        # g may be another order, so its refusal does not cover f's
        self.assertEqual(flags(refuse=("f.status == draft", "g.status == draft"), inputs=TWO), [])
        # only one order gets past refusals 1 and 2, pending, so 3 is dead; missed, not invented
        self.assertEqual(flags(refuse=("f != g", "g.status != pending", "f.status == draft"), inputs=TWO), [])

    def test_always_only_misses(self):
        # a draft has no units, so refusal 2 is dead; missed, not invented
        self.assertEqual(flags(refuse=("f.quantity == 0", "f.status == draft"), always=(INV,)), [])


class ConflictingEnsure(unittest.TestCase):
    def test_note_example(self):
        found = conflicts(ensure=("f.status == pending", "f.status == shipped"))
        self.assertEqual([(r, m) for r, _, m in found],
                         [("conflicting_ensure", "submit: ensure 1 and ensure 2 cannot both hold")])

    def test_near_miss(self):
        self.assertEqual(conflicts(ensure=("f.status == pending", "f.status != shipped")), [])
        self.assertEqual(conflicts(ensure=("f.status == pending", "f.quantity == 0")), [])

    def test_always_clash(self):
        found = conflicts(ensure=("f.quantity == 0",), always=("quantity > 0",))
        self.assertEqual([m for _, _, m in found],
                         ["submit: ensure 1 cannot hold with always 1 of order: quantity > 0"])

    def test_always_near_miss(self):
        self.assertEqual(conflicts(ensure=("f.quantity == 1",), always=("quantity > 0",)), [])

    def test_integer_edge(self):
        self.assertEqual(rules(conflicts(ensure=("f.quantity < 1", "f.quantity > 0"))), ["conflicting_ensure"])
        self.assertEqual(conflicts(ensure=("f.price < 1", "f.price > 0")), [])

    def test_too_complex_is_skipped(self):
        self.assertEqual(conflicts(ensure=("f.quantity == OLD(f.quantity) + 1", "f.quantity == 0")), [])
        self.assertEqual(conflicts(ensure=("f.quantity == 0",), always=("quantity > len(lines)",)), [])

    def test_two_inputs_only_miss(self):
        # g may be another order, so the two can both hold
        self.assertEqual(conflicts(ensure=("f.status == shipped", "g.status == pending"), inputs=TWO), [])

    def test_always_only_misses(self):
        # the always fact rules out both together, each one alone it allows: missed, not invented
        self.assertEqual(conflicts(ensure=("f.status == draft", "f.quantity == 1"), always=(INV,)), [])


class EmptyEnsure(unittest.TestCase):
    def test_note_examples(self):
        found = flags(ensure=("f.status == f.status", "f.quantity >= f.quantity"))
        self.assertEqual([(r, m) for r, _, m in found], [
            ("empty_ensure", "submit: ensure 1 cannot fail; both sides are the same: f.status == f.status"),
            ("empty_ensure", "submit: ensure 2 cannot fail; both sides are the same: f.quantity >= f.quantity")])

    def test_near_miss(self):
        self.assertEqual(flags(ensure=("f.quantity == OLD(f.quantity)", "f.quantity > f.quantity")), [])

    def test_complex_sides_still_compared(self):
        self.assertEqual(rules(flags(ensure=("len(f.lines) <= len(f.lines)",))), ["empty_ensure"])


class ForbiddenChange(unittest.TestCase):
    def test_note_example(self):
        found = flags(refuse=("f.status == cancelled",), ensure=("f.status == shipped",))
        self.assertEqual([(r, m) for r, _, m in found],
                         [("forbidden_change", "submit sets status to shipped from draft, which may_change does not allow")])

    def test_near_miss(self):
        self.assertEqual(flags(refuse=("f.status != pending",), ensure=("f.status == shipped",)), [])
        self.assertEqual(flags(refuse=("f.status in [draft, cancelled]",), ensure=("f.status == shipped",)), [])

    def test_refusal_with_or(self):
        self.assertEqual(flags(refuse=("f.status == draft or f.status == cancelled",), ensure=("f.status == shipped",)), [])
        self.assertEqual(rules(flags(refuse=("f.status == draft and f.quantity > 0",), ensure=("f.status == shipped",))),
                         ["forbidden_change"])

    def test_who_limits_the_start(self):
        self.assertEqual(flags(refuse=("f.status == cancelled",), ensure=("f.status == shipped",),
                               who='{role: shop_user, when: "f.status == pending"}'), [])

    def test_too_complex_is_skipped(self):
        self.assertEqual(flags(refuse=("f.status == cancelled or len(f.lines) == 0 and f.status == draft",),
                               ensure=("f.status == shipped",)), [])
        self.assertEqual(flags(refuse=("any(l.units > 0 for l in f.lines) or f.status == draft",
                                       "f.status == cancelled"), ensure=("f.status == shipped",)), [])

    def test_unreached_start_is_left_to_unreachable_choice(self):
        folder = os.path.join(check.ROOT, "fixtures", "unreachable_choice")
        found = check.check(os.path.join(folder, "order.edda"), check.project_of(folder))[4]
        self.assertEqual([p[0] for p in found], ["unreachable_choice"])

    # the six conditions (section 11), the sixth under round 84,, each with a case that flags and one that skips

    def test_1_an_input_s_own_status(self):
        self.assertEqual(rules(flags(refuse=("f.status == cancelled",), ensure=("f.status == shipped",),
                                     inputs="{f: order, h: shop}")), ["forbidden_change"])
        # the same change through a reference is skipped
        self.assertEqual(flags(refuse=("h.order.status == cancelled",), ensure=("h.order.status == shipped",),
                               inputs="{h: shop}"), [])

    def test_2_every_refusal_and_who_line_read(self):
        self.assertEqual(rules(flags(refuse=("h.open == False", "f.status == cancelled"), ensure=("f.status == shipped",),
                                     inputs="{f: order, h: shop}")), ["forbidden_change"])
        # a skipped refusal ends the check, even on another entity (no more "stands apart")
        self.assertEqual(flags(refuse=("len(h.name) == 0", "f.status == cancelled"), ensure=("f.status == shipped",),
                               inputs="{f: order, h: shop}"), [])
        self.assertEqual(flags(refuse=("len(f.lines) == 0", "f.status == cancelled"), ensure=("f.status == shipped",)), [])
        self.assertEqual(flags(refuse=("len(g.lines) == 0", "f.status == cancelled"), ensure=("f.status == shipped",),
                               inputs=TWO), [])

    def test_3_every_always_fact_of_the_target_read(self):
        found = flags(refuse=("f.status == cancelled",), ensure=("f.status == shipped",), always=(INV,))
        self.assertEqual(rules(found), ["forbidden_change"])
        self.assertEqual(flags(refuse=("f.status == cancelled",), ensure=("f.status == shipped",),
                               always=("quantity >= len(lines)",)), [])

    def test_4_no_always_fact_elsewhere_reaches_the_target(self):
        self.assertEqual(rules(flags(refuse=("f.status == cancelled",), ensure=("f.status == shipped",),
                                     shop_always=("open == True", "len(name) > 0"))), ["forbidden_change"])
        self.assertEqual(flags(refuse=("f.status == cancelled",), ensure=("f.status == shipped",),
                               shop_always=("order.quantity >= 0",)), [])

    def test_5_two_inputs_of_the_target_s_entity(self):
        found = flags(refuse=("g.status != pending",), ensure=("f.status == shipped",), inputs=TWO)
        self.assertEqual([m for _, _, m in found],
                         ["submit sets status to shipped from draft or cancelled, which may_change does not allow"])
        self.assertEqual(flags(refuse=("f != g", "g.status != pending"), ensure=("f.status == shipped",),
                               inputs=TWO), [])

    # Astra round 83 (kb:9380669)

    def test_round_83_related_skipped_conditions(self):
        # only a pending order gets past the who-line and the refusal together
        self.assertEqual(flags(refuse=("len(h.name) == 0",), ensure=("f.status == shipped",),
                               who='{role: shop_user, when: "f.status == pending or len(h.name) == 0"}',
                               inputs="{f: order, h: shop}"), [])

    def test_round_83_invariant_of_another_entity(self):
        self.assertEqual(flags(ensure=("h.order.status == shipped",), inputs="{h: shop}",
                               shop_always=("order.status in [pending, shipped]",)), [])

    def test_round_83_reference_replaced(self):
        self.assertEqual(flags(refuse=("f.status != shipped",), ensure=("h.order == f", "h.order.status == shipped"),
                               inputs="{f: order, h: shop}"), [])

    def test_too_many_cases_is_skipped(self):
        # each refusal leaves two boxes open; ten of them are more than the limit
        many = tuple(f"f.quantity == {k} and f.price == {k}" for k in range(10))
        self.assertEqual(flags(refuse=many + ("f.status == cancelled",), ensure=("f.status == shipped",)), [])

    # Astra round 84 (kb:9380671): the gate covers what is set, not only what is read

    def test_round_84_computed_target(self):
        # status follows the shipment's; a draft or cancelled start cannot happen
        shipment = ("  shipment:\n    is: \"what carries an order\"\n    properties:\n"
                    "      status: draft | pending | shipped | cancelled\n")
        self.assertEqual(flags(refuse=("f.shipment.status != pending",), ensure=("f.status == shipped",),
                               status='{computed: "shipment.status"}', order_props="      shipment: shipment",
                               entities=shipment), [])

    def test_round_84_derived_target(self):
        # no condition reads the DERIVED status, so only the target stops the check
        self.assertEqual(rules(flags(refuse=("f.quantity < 0",), ensure=("f.status == shipped",))), ["forbidden_change"])
        self.assertEqual(flags(refuse=("f.quantity < 0",), ensure=("f.status == shipped",),
                               status="DEFAULT draft | pending | shipped | cancelled, DERIVED"), [])


class OwnSpecs(unittest.TestCase):
    def test_no_analyser_flag_on_specs(self):
        folder = os.path.join(check.ROOT, "specs")
        P = check.project_of(folder)
        for name in sorted(os.listdir(folder)):
            if name.endswith(".edda"):
                found = check.check(os.path.join(folder, name), P)[4]
                self.assertEqual([p for p in found if p[0] in ANALYSER], [], name)


if __name__ == "__main__":
    unittest.main()
