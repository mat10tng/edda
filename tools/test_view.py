#!/usr/bin/env python3
"""The read view (reference section 12).

    python3 tools/test_view.py

Every example of EDDA-007 passes through the runner, and a renderer
broken on purpose makes EDDA-007 fail. A small spec of its own shows
every sentence kind, with its template, anchor and shade: the story, a
note and a question, the operation, a permission split into "whose"
and "while", a refusal with its input dropped and one without, an
outcome by its fact and by its means, a read with its order, an
invariant, rules heading their examples, a given, a when with a keyword
and the forms of then. Every expression form of 7.1 reads in words. A
drifted refusal is a warning; an older version renders from its
snapshot, its lines counted from its key line. Astra round 65's cases
read as they mean: `or` as a value, `and` and a non-yes/no value where
they have no reading, an actor condition after ", if", an article by
sound and a list inside a list. Astra round 66's too: "is yes" only for
a value proven yes or no, in the current text and in a version read
against its pins; a list literal in brackets inside a larger
expression; grouping from the tree, a quote in a text escaped; "a
user", "an hour". Astra round 67's too: an OPTIONAL yes/no under not
"is no or has no value", a comprehension's names only inside it, the
version fields in section 9, "an unable". Astra round 68's too: a
reading with an "or" or "and" the view puts in is in brackets inside a
larger condition or value, after "is asked and" and "it is done and"
too. view.py over specs/
prints a story sentence for each of EDDA-001 to EDDA-008 and no story id
outside a note or quoted text; a project that does not check exits 1
with its problems.
"""
import ast
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["EDDA_LOG"] = "off"     # the tools and their children never write the log (section 11)
import check                     # noqa: E402
import edda_binding as binding   # noqa: E402
import run                       # noqa: E402
import view                      # noqa: E402

ROOT = check.ROOT
SPECS = os.path.join(ROOT, "specs")


def cli(*args):
    p = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "view.py"), *args],
                       cwd=ROOT, capture_output=True, text=True)
    return p.returncode, p.stdout


SMALL = """\
roles:
  shop_user:
    is: "a person at a shop"
    properties:
      shop: shop

entities:
  shop:
    is: "a place that sells"
    properties:
      orders: MANY order
    may_read: [{role: shop_user}]
  order:
    is: "what a workshop buys"
    properties:
      shop: shop
      status: DEFAULT incoming | removed
      units_sent: DEFAULT 0
      label: TEXT, OPTIONAL
    may_change: {status: {incoming: [removed]}}
    may_read: [{role: shop_user}]
    may_update: [{role: shop_user}]
    always:
      - "units_sent >= 0"

stories:
  FIX-001:
    story: "remove an order"
    about: order
    as_a: shop_user
    i_want: "to remove an order"
    so_that: "the list is clean"
    notes: ["the shop asked for this"]
    questions: ["may a sent order be removed?"]
    rules:
      - rule: "an unsent order can be removed"
        shown_by: ["a fresh order is removed"]
      - rule: "a removed order stays removed"
        shown_by: ["a removed order is not removed again"]
    operations:
      remove:
        is: "takes an unsent order off the list"
        inputs: {order: order, because: "TEXT, OPTIONAL"}
        who: [{role: shop_user, when: "ACTOR.shop == order.shop and order.units_sent == 0"}]
        refuse:
          - when: "order.status == removed or order.label is None"
            reason: "already removed"
          - when: "because == \\"no\\""
            reason: "not wanted"
        ensure:
          - "order.status == removed"
          - fact: "order.units_sent == OLD(order.units_sent)"
            means: "nothing more is sent"
        notes: ["a removed order keeps its history"]
      open_orders:
        is: "lists the orders a shop still waits for"
        inputs: {shop: shop}
        who: [{role: shop_user}]
        returns: "[order for order in shop.orders if order.status == incoming]"
        ordered_by: ["order.units_sent"]
    examples:
      "a removed order is not removed again":
        given:
          - actor: erik
            with: {roles: [shop_user], shop: butik}
          - shop: butik
          - order: purchase
            with: {shop: butik, status: removed, label: "red"}
        steps:
          - when: {actor: erik, call: "remove(purchase, because=\\"moved\\")"}
            then: [{refused: "already removed"}]
          - then: ["purchase.status == removed", "len(butik.orders) == 0"]
      "a fresh order is removed":
        given:
          - actor: erik
            with: {roles: [shop_user], shop: butik}
          - shop: butik
          - order: purchase
            with: {shop: butik, label: "red"}
        steps:
          - when: {actor: erik, call: "remove(purchase)"}
            then:
              - DONE
              - "purchase.status == removed"
        notes: ["erik is the buyer"]
"""

# (kind, shade, line, text) of every sentence of SMALL, in order
EXPECTED = [
    ("story", "plain", 27, "Remove an order. As a shop user, I want to remove an order, so that the list is clean."),
    ("note", "grey", 33, "the shop asked for this"),
    ("question", "warning", 34, "may a sent order be removed?"),
    ("operation", "plain", 41, "Remove takes an unsent order off the list."),
    ("permission", "plain", 44, "A shop user whose shop is the order's shop may remove an order, and because, "
                                "an optional text, while the order's units sent is 0."),
    ("refusal", "plain", 46, "If remove is asked for an order whose status is removed or label has no value, "
                             "then the system shall refuse it: already removed."),
    ("refusal", "plain", 48, "If remove is asked and because is \"no\", then the system shall refuse it: not wanted."),
    ("outcome", "plain", 51, "When remove succeeds, the order's status is removed."),
    ("outcome", "plain", 52, "When remove succeeds, nothing more is sent."),
    ("note", "grey", 54, "a removed order keeps its history"),
    ("operation", "plain", 55, "Open orders lists the orders a shop still waits for."),
    ("permission", "plain", 58, "A shop user may open orders a shop."),
    ("read", "plain", 59, "Open orders gives every order in the shop's orders where order's status is incoming, "
                          "ordered by the order's units sent."),
    ("rule", "plain", 36, "Rule: an unsent order can be removed."),
    ("example", "plain", 73, "Example: a fresh order is removed."),
    ("given", "plain", 74, "Given erik, a shop user with shop butik, butik, a shop, and purchase, an order with "
                           "shop butik and label \"red\"."),
    ("when", "plain", 81, "When erik asks to remove purchase."),
    ("then", "plain", 82, "Then it is done and purchase's status is removed."),
    ("note", "grey", 85, "erik is the buyer"),
    ("rule", "plain", 38, "Rule: a removed order stays removed."),
    ("example", "plain", 62, "Example: a removed order is not removed again."),
    ("given", "plain", 63, "Given erik, a shop user with shop butik, butik, a shop, and purchase, an order with "
                           "shop butik and status removed and label \"red\"."),
    ("when", "plain", 70, "When erik asks to remove purchase, because \"moved\"."),
    ("then", "plain", 71, "Then it is refused: already removed."),
    ("then", "plain", 72, "Then purchase's status is removed and the number of butik's orders is 0."),
]


class Templates(unittest.TestCase):
    """one small spec holds every sentence kind"""

    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.mkdtemp()
        with open(os.path.join(cls.folder, "order.edda"), "w") as f:
            f.write(SMALL)
        cls.model = json.loads(subprocess.run([sys.executable, os.path.join(ROOT, "tools", "check.py"), "--model",
                                               cls.folder], capture_output=True, text=True, check=True).stdout)
        cls.found = view.story_sentences(cls.model["stories"][0], cls.model["operations"], cls.model["entities"],
                                         cls.model["roles"])

    def test_every_kind_in_order(self):
        self.assertEqual([(s["kind"], s["shade"], s["line"], s["text"]) for s in self.found], EXPECTED)

    def test_invariant(self):
        order = next(e for e in self.model["entities"] if e["name"] == "order")
        self.assertEqual(view.invariant_sentences(order),
                         [{"kind": "invariant", "text": "Always, units sent is at least 0.", "line": 24, "shade": "plain"}])

    def test_every_sentence_kind_of_the_spec(self):
        kinds = {s["kind"] for s in self.found} | {"invariant"}
        declared = next(e for e in check.model_of(SPECS)["entities"] if e["name"] == "sentence")
        self.assertEqual(kinds, set(next(p for p in declared["properties"] if p["name"] == "kind")["values"]))

    def test_command_marks_shades_and_lines(self):
        code, out = cli("--lines", self.folder)
        self.assertEqual(code, 0)
        lines = out.splitlines()
        self.assertEqual(lines[:2], ["  order.edda:24: Always, units sent is at least 0.", ""])
        self.assertIn("~ order.edda:33: the shop asked for this", lines)
        self.assertIn("? order.edda:34: may a sent order be removed?", lines)


def thing(name, yes_no=(), text=(), maybe=(), **refs):
    """an entity as the model holds it, its properties typed: yes_no and
    text name properties of those types, maybe OPTIONAL YES_NO ones,
    refs one to an entity"""
    props = ([{"name": p, "type": "YES_NO"} for p in yes_no] + [{"name": p, "type": "TEXT"} for p in text]
             + [{"name": p, "type": "YES_NO", "optional": True} for p in maybe]
             + [{"name": p, "type": "entity", "entity": e} for p, e in refs.items()])
    return {"name": name, "properties": props}


# the types the expression tests read against: order, story and block are
# entities, l a list of items, n not known
ORDER = thing("order", yes_no=("ok", "a", "b", "big"), text=("label",))
TYPES = view.Types([ORDER, thing("item", yes_no=("ok", "big")), thing("block", yes_no=("approved",)), thing("story")])
SCOPE = {"order": ("entity", "order"), "story": ("entity", "story"), "block": ("entity", "block"),
         "l": ("list", ("entity", "item"))}


def typed(kept=(), the=()):
    return view.Words(kept, the, types=TYPES, scope=SCOPE)


class Expressions(unittest.TestCase):
    """section 12: every form of 7.1 in words, composed inside out"""

    def said(self, text, kept=("order", "l", "story", "n"), the=(), condition=False):
        W = typed(kept, the)
        n = ast.parse(text, mode="eval").body
        return W.c(n) if condition else W.w(n)

    def test_forms(self):
        for text, words in [
            ("order.units_sent > 0", "order's units sent is more than 0"),
            ("order.status != removed", "order's status is not removed"),
            ("order.label is None", "order's label has no value"),
            ("order.label is not None", "order's label has a value"),
            ("\"x\" in order.label", "\"x\" is in order's label"),
            ("order.status not in [removed, sent]", "order's status is not in (the list of removed and sent)"),
            ("len(l) == 0", "the number of l is 0"),
            ("sum(x.amount for x in l)", "the sum of x's amount over every x in l"),
            ("any(x.ok for x in l)", "there is an x in l where x's ok is yes"),
            ("any(x.a == 1 for x in l if x.big)", "there is an x in l where x's big is yes and x's a is 1"),
            ("all(x.ok for x in l if x.big)", "for every x in l where x's big is yes, x's ok is yes"),
            ("[x.name for x in l if x.ok]", "x's name for every x in l where x's ok is yes"),
            ("[x for x in l if x.ok]", "every x in l where x's ok is yes"),
            ("[y for x in l for y in x.ys]", "y for every x in l, and every y in x's ys"),
            ("l[0]", "the first of l"),
            ("l[-1]", "the last of l"),
            ("l[n - 1]", "item n minus 1 of l"),
            ("l[2]", "item 2 of l"),
            ("order.at > TIME(\"2026-10-03 10:00\")", "order's at is more than the time 2026-10-03 10:00"),
            ("order.a * 2 / 3 + 1", "order's a times 2 divided by 3 plus 1"),
            ("OLD(order.units)", "order's units before"),
            ("ACTOR.name == RESULT", "the asker's name is the result"),
            ("order.day == TODAY", "order's day is today"),
            ("order.lines == []", "order's lines is empty"),
            ("order.a == -2", "order's a is -2"),
            ("check(story.file)", "the check of story's file"),
            ("any(p.kind == refused for p in check(story.file))",
             "there is a p in the check of story's file where p's kind is refused"),
        ]:
            self.assertEqual(self.said(text), words, text)

    def test_conditions(self):
        for text, words in [
            ("order.a < 1 and order.b >= 2 or order.c <= 3", "order's a is less than 1 and order's b is at least 2 "
                                                             "or order's c is at most 3"),
            ("(order.a == 1 or order.b == 2) and order.c == 3", "(either order's a is 1 or order's b is 2) "
                                                                "and order's c is 3"),
            ("order.c == 3 and (order.a == 1 or order.b == 2)", "order's c is 3 and either order's a is 1 "
                                                                "or order's b is 2"),
            ("not (order.a == 1 or order.b == 2)", "not (order's a is 1 or order's b is 2)"),
            ("not any(x.ok for x in l)", "not (there is an x in l where x's ok is yes)"),
            ("order.ok == True or order.ok == False or order.x == None", "order's ok is yes or order's ok is no "
                                                                          "or order's x is no value"),
        ]:
            self.assertEqual(self.said(text, condition=True), words, text)

    def test_grouping_kept(self):
        """two expressions that differ in their tree never read the same"""
        for one, two, said_one, said_two in [
            ("(n + 1) * 2", "n + 1 * 2", "(n plus 1) times 2", "n plus 1 times 2"),
            ("n - (l - 1)", "n - l - 1", "n minus (l minus 1)", "n minus l minus 1"),
            ("-(n + 1)", "-n + 1", "minus (n plus 1)", "minus n plus 1"),
            ("len(l + l)", "len(l) + l", "the number of (l plus l)", "the number of l plus l"),
            ("not (order.a == 1 and order.b == 2)", "(not order.a == 1) and order.b == 2",
             "not (order's a is 1 and order's b is 2)", "not order's a is 1 and order's b is 2"),
            ("not (order.a and order.b)", "not order.a and order.b",
             "not (order's a is yes and order's b is yes)", "order's a is no and order's b is yes"),
            ("(order.a == 1 or order.b == 2) and order.c == 3", "order.a == 1 or order.b == 2 and order.c == 3",
             "(either order's a is 1 or order's b is 2) and order's c is 3",
             "order's a is 1 or order's b is 2 and order's c is 3"),
            ("all(x.ok for x in l) and n == 1", "all(x.ok and n == 1 for x in l)",
             "(for every x in l, x's ok is yes) and n is 1", "for every x in l, x's ok is yes and n is 1"),
            ("any(x.ok for x in l) or n == 1", "any(x.ok or n == 1 for x in l)",
             "(there is an x in l where x's ok is yes) or n is 1",
             "there is an x in l where either x's ok is yes or n is 1"),
            ("len([x for x in l if x.ok]) == n", "[x for x in l if x.ok == n]",
             "the number of (every x in l where x's ok is yes) is n", "every x in l where x's ok is n"),
        ]:
            self.assertEqual((self.said(one, condition=logic(one)), self.said(two, condition=logic(two))),
                             (said_one, said_two), (one, two))

    def test_paths(self):
        """a property read straight on a name keeps the possessive; a longer
        path reads from its end with "of" """
        for text, words, the in [
            ("order.status", "the order's status", {"order"}),
            ("purchase.status", "purchase's status", ()),
            ("block.versions[-1].number", "the number of the last of the block's versions", {"block"}),
            ("order.b.c", "the c of order's b", ()),
            ("ACTOR.shop.name", "the name of the asker's shop", ()),
            ("RESULT[0].kind", "the kind of the first of the result", ()),
        ]:
            self.assertEqual(self.said(text, the=the), words, text)

    def test_yes_no_condition(self):
        W = typed(the={"block"})
        for text, words in [("block.approved", "the block's approved is yes"),
                            ("not block.approved", "the block's approved is no"),
                            ("block.approved and block.version == 1",
                             "the block's approved is yes and the block's version is 1")]:
            self.assertEqual(W.of(expr(text), condition=True), words, text)
        self.assertEqual(W.of(expr("block.approved")), "the block's approved")     # a value stays a value

    def test_dropped_root(self):
        c = ast.parse('order.shop.name == "x" and order.lines[0].status == removed', mode="eval").body
        self.assertEqual(view.Words().condition(c, "order"),
                         "shop's name is \"x\" and the status of the first of lines is removed")

    def test_unknown_form_as_written(self):
        """a form the view has no reading for is shown as written, flagged"""
        for text in ["order.status.startswith('in')", "min(order.a, 2) > 1", "l[1:2]", "1 if order.ok else 2",
                     "order.a <= n <= 3", "order.a is order.b"]:
            W = view.Words(kept=("order", "l", "n"))
            self.assertEqual(W.of(expr(text), condition=True), f'"{text}"', text)
            self.assertTrue(W.unread, text)

    def test_an_entity_type_reads_the(self):
        self.assertEqual(self.said("order.status == removed", kept=(), the={"order"}), "the order's status is removed")


def logic(text):
    """is text's top and, or or not: read as a condition, where it stands"""
    n = ast.parse(text, mode="eval").body
    return isinstance(n, ast.BoolOp) or (isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not))


def expr(text):
    """an expression as the model holds it"""
    return {"text": text, "line": 1, "ast": check.ast_json(ast.parse(text, mode="eval").body)}


ROUND_65 = (SMALL
            .replace('when: "ACTOR.shop == order.shop and order.units_sent == 0"',
                     'when: "ACTOR.shop == order.shop and order.units_sent == 0 '
                     'and any(o.status == incoming for o in ACTOR.shop.orders)"')
            .replace('who: [{role: shop_user}]\n        returns: "[order for order in shop.orders '
                     'if order.status == incoming]"',
                     'who: [{role: shop_user, when: "not ACTOR.shop == shop"}]\n        returns: '
                     '"[order for order in shop.orders if order.status == incoming] or shop.orders"'))


class Round65(unittest.TestCase):
    """Astra round 65 (kb:9380533): no reading changes what an expression
    means"""

    @classmethod
    def setUpClass(cls):
        assert ROUND_65.count("ACTOR.shop.orders") == 1 and ROUND_65.count("or shop.orders") == 1
        folder = tempfile.mkdtemp()
        with open(os.path.join(folder, "order.edda"), "w") as f:
            f.write(ROUND_65)
        m = check.model_of(folder)
        cls.found = {s["line"]: s for s in view.story_sentences(m["stories"][0], m["operations"], m["entities"],
                                                                m["roles"])}

    def said(self, text, condition=False):
        W = typed(kept=("order", "l", "n"))
        return W.of(expr(text), condition=condition), W.unread

    def test_or_as_a_value_reads_or_else(self):
        """or gives a value where its result is used as one: "a, or else b";
        as a condition it stays "or" """
        for text, words in [
            ("order.a == (order.b or 1)", "order's a is (order's b, or else 1)"),
            ("check(order.b or 1)", "the check of (order's b, or else 1)"),
            ("(l or n)[0]", "the first of (l, or else n)"),
            ("order.a + (order.b or order.c or 0)", "order's a plus (order's b, or else order's c, or else 0)"),
            ("[x or 1 for x in l]", "(x, or else 1) for every x in l"),
        ]:
            self.assertEqual(self.said(text), (words, False), text)
        self.assertEqual(self.said("order.a or order.b", condition=True),
                         ("order's a is yes or order's b is yes", False))
        self.assertEqual(self.found[59]["text"], "Open orders gives (every order in the shop's orders where order's "
                                                 "status is incoming), or else the shop's orders, ordered by the "
                                                 "order's units sent.")

    def test_and_or_no_yes_no_as_written(self):
        """and as a value, and a value that is no yes or no standing as a
        condition, have no reading: shown as written, a warning"""
        for text, condition in [("order.a == (order.b and 1)", False), ("check(order.b and 1)", False),
                                ("len(l)", True), ("not len(l)", True), ("order.a + 1", True),
                                ("not [1]", True), ("n or 2", True)]:
            self.assertEqual(self.said(text, condition), (f'"{text}"', True), text)
        self.assertEqual(self.said("not order.ok"), ("order's ok is no", False))
        self.assertEqual(self.said("OLD(order.ok)", condition=True), ("order's ok before is yes", False))

    def test_actor_condition_not_after_whose_ends_with_if(self):
        self.assertEqual(self.found[44]["text"],
                         "A shop user whose shop is the order's shop may remove an order, and because, an optional "
                         "text, while the order's units sent is 0, if there is an o in the orders of the asker's "
                         "shop where o's status is incoming.")
        self.assertEqual(self.found[58]["text"], "A shop user may open orders a shop, if not the asker's shop is "
                                                 "the shop.")

    def test_article_by_sound(self):
        for w, said in [("s in l", "an s in l"), ("x", "an x"), ("p", "a p"), ("f", "an f"), ("u", "a u"),
                        ("order", "an order"), ("shop user", "a shop user"), ("operator", "an operator")]:
            self.assertEqual(view.a(w), said, w)

    def test_list_in_a_list_keeps_its_grouping(self):
        for text, words in [
            ("[[1, 2], 3]", "the list of (the list of 1 and 2) and 3"),
            ("[1, [2, 3]]", "the list of 1 and (the list of 2 and 3)"),
            ("[1, 2, 3]", "the list of 1 and 2 and 3"),
            ("check([1, 2], 3)", "the check of (the list of 1 and 2) and 3"),
            ("[check(1, 2), 3]", "the list of (the check of 1 and 2) and 3"),
            ("[\"a and b\", 3]", "the list of \"a and b\" and 3"),
        ]:
            self.assertEqual(self.said(text), (words, False), text)


TEXT_CONDITION = SMALL.replace('when: "because == \\"no\\""', 'when: "order.label"')


def pinned_text_condition():
    """story_grown, its order as pinned holding a TEXT label and a YES_NO
    paid that the current text does not, and its version refusing on
    each standing alone as a condition"""
    folder = tempfile.mkdtemp()
    for name in ("order.edda", "order.edda.vc"):
        with open(os.path.join(ROOT, "fixtures", "story_grown", name)) as f:
            text = f.read()
        if name.endswith(".vc"):
            text = text.replace("        units_sent: DEFAULT 0\n",
                                "        units_sent: DEFAULT 0\n        label: TEXT\n        paid: YES_NO\n")
            text = text.replace('              reason: "already sent"\n',
                                '              reason: "already sent"\n'
                                '            - when: "order.label"\n              reason: "labelled"\n'
                                '            - when: "not order.paid"\n              reason: "unpaid"\n')
        with open(os.path.join(folder, name), "w") as f:
            f.write(text)
    return folder


class Round66(unittest.TestCase):
    """Astra round 66 (kb:9380540): a reading keeps the meaning or shows
    the source, marked"""

    def said(self, text, condition=False):
        W = typed(kept=("order", "l", "n"))
        return W.of(expr(text), condition=condition), W.unread

    def test_text_as_a_condition_is_shown_as_written(self):
        """a TEXT standing as a condition never reads "is yes"; only a value
        proven YES_NO does"""
        for text in ["order.label", "not order.label", "order.ok and order.label", "OLD(order.label)",
                     "order.nothing", "n", "check(order)"]:
            self.assertEqual(self.said(text, condition=True), (view.quoted(text), True), text)
        for text, words in [("order.ok", "order's ok is yes"), ("not order.ok", "order's ok is no"),
                            ("OLD(order.ok)", "order's ok before is yes"),
                            ("any(x.ok for x in l)", "there is an x in l where x's ok is yes")]:
            self.assertEqual(self.said(text, condition=True), (words, False), text)

    def test_text_condition_in_the_current_text(self):
        folder = tempfile.mkdtemp()
        with open(os.path.join(folder, "order.edda"), "w") as f:
            f.write(TEXT_CONDITION)
        self.assertNotEqual(TEXT_CONDITION, SMALL)
        self.assertFalse(check.refused(folder))
        m = check.model_of(folder)
        found = [s for s in view.story_sentences(m["stories"][0], m["operations"], m["entities"], m["roles"])
                 if s["line"] == 48]
        self.assertEqual([(s["text"], s["shade"]) for s in found],
                         [("If remove is asked and \"order.label\", then the system shall refuse it: not wanted.",
                           "warning")])

    def test_text_condition_in_a_pinned_version(self):
        """the types come from the blocks the version pins, not the current
        text: label is TEXT and paid YES_NO only as pinned"""
        folder = pinned_text_condition()
        self.assertFalse(check.refused(folder))
        found = view.version_sentences(check.model_of(folder)["stories"][0]["versions"][0])
        self.assertEqual([(s["text"], s["shade"]) for s in found if s["kind"] == "refusal"][1:],
                         [("If remove is asked and \"order.label\", then the system shall refuse it: labelled.",
                           "warning"),
                          ("If remove is asked and the order's paid is no, then the system shall refuse it: unpaid.",
                           "plain")])

    def test_a_declared_operation_returning_yes_no(self):
        ops = [{"name": "is_big", "inputs": [{"name": "o", "type": "entity", "entity": "order"}], "who": [],
                "returns": expr("o.big")},
               {"name": "label_of", "inputs": [{"name": "o", "type": "entity", "entity": "order"}], "who": [],
                "returns": expr("o.label")}]
        W = view.Words(("order",), types=view.Types([ORDER], (), ops), scope=SCOPE)
        self.assertEqual(W.of(expr("is_big(order)"), condition=True), "the is big of order is yes")
        self.assertFalse(W.unread)
        self.assertEqual(W.of(expr("label_of(order)"), condition=True), '"label_of(order)"')
        self.assertTrue(W.unread)

    def test_a_list_inside_is_bracketed(self):
        for text, words in [
            ("order.status in [removed]", "order's status is in (the list of removed)"),
            ("check([1])", "the check of (the list of 1)"),
            ("[[1]]", "the list of (the list of 1)"),
            ("[[1], 2]", "the list of (the list of 1) and 2"),
            ("[1][0]", "the first of (the list of 1)"),
            ("[x for x in [1, 2]]", "every x in (the list of 1 and 2)"),
            ("[1]", "the list of 1"),
        ]:
            self.assertEqual(self.said(text), (words, False), text)

    def test_grouping_from_the_tree_a_quote_escaped(self):
        """an item whose reading holds an "and" is in brackets whatever
        quotes it holds; a quote inside a text is escaped"""
        for text, words in [
            ("check(order.a == check('\"', 2), 3)", 'the check of order\'s a is (the check of "\\"" and 2) and 3'),
            ("['x\"', check(1, 2)]", 'the list of "x\\"" and (the check of 1 and 2)'),
            ("['a and b', 3]", 'the list of "a and b" and 3'),
            ("check(1, k=check(2, 3))", "the check of 1, k (the check of 2 and 3)"),
            ("order.label == 'say \"hi\"'", 'order\'s label is "say \\"hi\\""'),
        ]:
            self.assertEqual(self.said(text), (words, False), text)
        self.assertEqual(view.quoted('a\\b"c'), '"a\\\\b\\"c"')

    def test_articles(self):
        for w, said in [("user", "a user"), ("unit", "a unit"), ("usual", "a usual"), ("euro", "a euro"),
                        ("hour", "an hour"), ("honest", "an honest"), ("honour", "an honour"),
                        ("umbrella", "an umbrella"), ("under", "an under"), ("hat", "a hat"),
                        ("order", "an order"), ("s", "an s"), ("u", "a u")]:
            self.assertEqual(view.a(w), said, w)


# order with an OPTIONAL YES_NO held, and a refusal on it standing alone
OPTIONAL_YES_NO = (SMALL.replace("      label: TEXT, OPTIONAL\n", "      label: TEXT, OPTIONAL\n"
                                 "      held: YES_NO, OPTIONAL\n")
                   .replace('when: "because == \\"no\\""', 'when: "not order.held"'))
# Astra's case: a comprehension's because, yes or no, and the TEXT input
# because after it
COMPREHENSION_SCOPE = SMALL.replace(
    'when: "because == \\"no\\""',
    'when: "any(because for because in [o.units_sent > 0 for o in order.shop.orders]) and because"')


def sentences(text, kind):
    """the (text, shade) of each sentence of a kind of the spec text's story"""
    folder = tempfile.mkdtemp()
    with open(os.path.join(folder, "order.edda"), "w") as f:
        f.write(text)
    assert not check.refused(folder)
    m = check.model_of(folder)
    return [(s["text"], s["shade"]) for s in view.story_sentences(m["stories"][0], m["operations"], m["entities"],
                                                                   m["roles"]) if s["kind"] == kind]


def refusals(text):
    return sentences(text, "refusal")


class Round67(unittest.TestCase):
    """Astra round 67 (kb:9380552): no reading drops "has no value" or
    borrows a comprehension's type"""

    def said(self, text, types=None):
        W = view.Words(("order", "l", "n"), types=types or MAYBE_TYPES, scope=SCOPE)
        return W.of(expr(text), condition=True), W.unread

    def test_optional_yes_no_under_not(self):
        """an OPTIONAL YES_NO is yes, or is no or has no value"""
        for text, words in [
            ("order.held", "order's held is yes"),
            ("not order.held", "order's held is no or has no value"),
            ("OLD(order.held)", "order's held before is yes"),
            ("not OLD(order.held)", "order's held before is no or has no value"),
            ("not is_held(order)", "the is held of order is no or has no value"),
            ("not (order.held and order.ok)", "not (order's held is yes and order's ok is yes)"),
            ("all(not x.held for x in l)", "for every x in l, (x's held is no or has no value)"),
            ("not order.ok", "order's ok is no"),
            ("not is_ok(order)", "the is ok of order is no"),
        ]:
            self.assertEqual(self.said(text), (words, False), text)

    def test_optional_yes_no_in_a_spec(self):
        self.assertNotEqual(OPTIONAL_YES_NO, SMALL)
        self.assertEqual(refusals(OPTIONAL_YES_NO)[1],
                         ("If remove is asked and (the order's held is no or has no value), then the system shall "
                          "refuse it: not wanted.", "plain"))

    def test_an_actor_property_optional_in_one_role(self):
        types = view.Types((), [{"name": "r1", "properties": [{"name": "f", "type": "YES_NO"}]},
                                {"name": "r2", "properties": [{"name": "f", "type": "YES_NO", "optional": True}]}])
        W = view.Words(types=types, scope={"ACTOR": ("actor", "one", ("r1", "r2"))})
        self.assertEqual(W.of(expr("not ACTOR.f"), condition=True), "the asker's f is no or has no value")

    def test_comprehension_names_stay_inside(self):
        self.assertNotEqual(COMPREHENSION_SCOPE, SMALL)
        text = "any(because for because in [o.units_sent > 0 for o in order.shop.orders]) and because"
        self.assertEqual(refusals(COMPREHENSION_SCOPE)[1],
                         (f'If remove is asked and "{text}", then the system shall refuse it: not wanted.',
                          "warning"))
        for text in ["all(n for n in [x.ok for x in l]) and n",
                     "[n for n in [x.ok for x in l]] and n",
                     "any(any(n for n in [x.ok for x in l]) for y in l) and n",
                     "any(any(y.ok for y in l) and y for y in [x.ok for x in l]) and y"]:
            self.assertEqual(self.said(text), (view.quoted(text), True), text)
        self.assertEqual(self.said("all(n for n in [x.ok for x in l])"),
                         ("for every n in (x's ok for every x in l), n is yes", False))

    def test_version_fields_in_section_9(self):
        """the model table lists every field a version has"""
        with open(os.path.join(ROOT, "language", "reference.md")) as f:
            row = next(line for line in f if line.startswith("| a version |"))
        v = check.model_of(os.path.join(ROOT, "fixtures", "story_grown"))["stories"][0]["versions"][0]
        self.assertEqual([k for k in v if f"`{k}`" not in row], [])

    def test_an_before_un(self):
        for w, said in [("unable", "an unable"), ("uninstalled", "an uninstalled"), ("unimportant", "an unimportant"),
                        ("unit", "a unit"), ("union", "a union"), ("unique", "a unique"), ("under", "an under"),
                        ("unusual", "an unusual"), ("user", "a user")]:
            self.assertEqual(view.a(w), said, w)


MAYBE_TYPES = view.Types([thing("order", yes_no=("ok",), maybe=("held",)), thing("item", yes_no=("ok",), maybe=("held",))], (),
                         [{"name": "is_held", "inputs": [{"name": "o", "type": "entity", "entity": "order"}],
                           "who": [], "returns": expr("o.held")},
                          {"name": "is_ok", "inputs": [{"name": "o", "type": "entity", "entity": "order"}],
                           "who": [], "returns": expr("o.ok")}])


# Astra round 68's case in a refusal, and an OPTIONAL yes/no in a then
ROUND_68 = (OPTIONAL_YES_NO.replace('when: "not order.held"', 'when: "not order.held and order.units_sent > 0"')
            .replace('              - "purchase.status == removed"\n', '              - "not purchase.held"\n'))


class Round68(unittest.TestCase):
    """Astra round 68 (kb:9380559): a reading with an "or" or "and" the view
    puts in itself is in brackets inside a larger condition or value"""

    def said(self, text, condition=True):
        W = view.Words(("order", "l", "n"), types=ROUND_68_TYPES, scope=SCOPE)
        n = ast.parse(text, mode="eval").body
        return W.c(n) if condition else W.w(n)

    def test_astra_case(self):
        """held is no or has no value is one clause: "held is no" alone is
        not enough"""
        self.assertEqual(self.said("not order.held and order.units_sent > 0"),
                         "(order's held is no or has no value) and order's units sent is more than 0")
        self.assertEqual(self.said("order.units_sent > 0 and not order.held"),
                         "order's units sent is more than 0 and (order's held is no or has no value)")

    def test_under_or(self):
        self.assertEqual(self.said("not order.held or order.units_sent > 0"),
                         "(order's held is no or has no value) or order's units sent is more than 0")
        self.assertEqual(self.said("order.ok or not order.held"),
                         "order's ok is yes or (order's held is no or has no value)")

    def test_whole_condition_keeps_no_brackets(self):
        self.assertEqual(self.said("not order.held"), "order's held is no or has no value")
        self.assertEqual(self.said("not order.ok and order.units_sent > 0"),
                         "order's ok is no and order's units sent is more than 0")

    def test_every_place_the_view_puts_a_connective(self):
        for text, words, condition in [
            ("any(not x.held for x in l)", "there is an x in l where (x's held is no or has no value)", True),
            ("[x for x in l if not x.held]", "every x in l where (x's held is no or has no value)", False),
            ("check(not order.held, 1)", "the check of (order's held is no or has no value) and 1", False),
            ("(not order.held) or order.ok", "(order's held is no or has no value), or else order's ok", False),
            ("[x for x in (l or n)]", "every x in (l, or else n)", False),
            ("check(1, 2) == 1", "(the check of 1 and 2) is 1", True),
            ("check(1, 2 == 1)", "the check of 1 and 2 is 1", False),
            ("check(1, 2) + 1", "(the check of 1 and 2) plus 1", False),
            ("held_for(order, n)", "(the held for of order and n) is yes", True),
            ("not held_for(order, n)", "(the held for of order and n) is no or has no value", True),
        ]:
            self.assertEqual(self.said(text, condition), words, text)

    def test_in_a_spec(self):
        """after "is asked and" and "it is done and" too"""
        self.assertNotEqual(ROUND_68, OPTIONAL_YES_NO)
        self.assertEqual(refusals(ROUND_68)[1],
                         ("If remove is asked and (the order's held is no or has no value) and the order's units "
                          "sent is more than 0, then the system shall refuse it: not wanted.", "plain"))
        self.assertEqual(sentences(ROUND_68, "then")[0][0],
                         "Then it is done and (purchase's held is no or has no value).")
        self.assertEqual(refusals(SMALL.replace('when: "because == \\"no\\""',
                                                'when: "because == \\"no\\" or because is None"'))[1][0],
                         'If remove is asked and either because is "no" or because has no value, then the system '
                         'shall refuse it: not wanted.')


ROUND_68_TYPES = view.Types([thing("order", yes_no=("ok",), maybe=("held",)), thing("item", maybe=("held",))], (),
                            [{"name": "held_for", "inputs": [{"name": "o", "type": "entity", "entity": "order"},
                                                             {"name": "k", "type": "TEXT"}],
                              "who": [], "returns": expr("o.held")}])


RULE_KEY_SECOND = SMALL.replace('      - rule: "an unsent order can be removed"\n'
                                '        shown_by: ["a fresh order is removed"]\n',
                                '      - shown_by: ["a fresh order is removed"]\n'
                                '        rule: "an unsent order can be removed"\n')


class RuleAnchor(unittest.TestCase):
    def test_rule_key_line_wherever_it_stands(self):
        """a rule's anchor is its rule: key's line, not the item's"""
        self.assertNotEqual(RULE_KEY_SECOND, SMALL)
        folder = tempfile.mkdtemp()
        with open(os.path.join(folder, "order.edda"), "w") as f:
            f.write(RULE_KEY_SECOND)
        self.assertEqual([r["line"] for r in check.model_of(folder)["stories"][0]["rules"]], [37, 38])


class Shades(unittest.TestCase):
    def test_drifted_refusal_is_a_warning(self):
        m = check.model_of(os.path.join(ROOT, "fixtures", "reason_changed"))
        found = view.story_sentences(m["stories"][0], m["operations"], m["entities"], m["roles"])
        self.assertEqual([(s["line"], s["shade"]) for s in found if s["kind"] == "refusal"],
                         [(29, "plain"), (31, "warning")])
        self.assertEqual({s["shade"] for s in found if s["kind"] != "refusal"}, {"plain"})

    def test_version_from_its_snapshot(self):
        m = check.model_of(os.path.join(ROOT, "fixtures", "story_grown"))
        v = m["stories"][0]["versions"][0]
        found = view.version_sentences(v)
        self.assertEqual(found[0], {"kind": "story", "line": 1, "shade": "plain",
                                    "text": "Remove an order. As a shop user, I want to remove an order, "
                                            "so that the list is clean."})
        self.assertEqual([s["text"] for s in found if s["kind"] == "refusal"],
                         ["If remove is asked for an order whose units sent is more than 0, "
                          "then the system shall refuse it: already sent."])
        self.assertEqual([s["line"] for s in found if s["kind"] == "refusal"], [13])
        self.assertEqual(len(found), 13)

    def test_old_form_in_a_snapshot(self):
        """Astra round 64: a retired form a snapshot keeps (section 10) is
        shown as written, a warning, never a crash"""
        folder = tempfile.mkdtemp()
        for name in ("order.edda", "order.edda.vc"):
            with open(os.path.join(ROOT, "fixtures", "story_grown", name)) as f:
                text = f.read()
            if name.endswith(".vc"):
                text = text.replace('"order.units_sent > 0"', '"order.status.startswith(\'in\')"')
            with open(os.path.join(folder, name), "w") as f:
                f.write(text)
        found = view.version_sentences(check.model_of(folder)["stories"][0]["versions"][0])
        self.assertEqual([(s["text"], s["shade"]) for s in found if s["kind"] == "refusal"],
                         [("If remove is asked and \"order.status.startswith('in')\", "
                           "then the system shall refuse it: already sent.", "warning")])
        self.assertEqual({s["shade"] for s in found if s["kind"] != "refusal"}, {"plain"})


class Run(unittest.TestCase):
    def test_edda_007_passes(self):
        self.assertEqual(run.run(SPECS, ["EDDA-007"]), [("EDDA-007", "examples passed", "all 5", [])])

    def test_a_broken_renderer_fails_edda_007(self):
        real = view.story_sentences

        def broken(story, operations, entities, roles, functions=()):     # the permissions left out
            return [s for s in real(story, operations, entities, roles, functions) if s["kind"] != "permission"]
        binding.viewer.story_sentences = broken
        try:
            sid, status, detail, failed = run.run(SPECS, ["EDDA-007"])[0]
        finally:
            binding.viewer.story_sentences = real
        self.assertEqual((status, detail), ("failing", "2 of 5 examples failed"))
        self.assertEqual([t for t, _ in failed], ["the clean fixture reads as twenty sentences",
                                                  "a note reads in its place, grey, and a question after it, marked"])


class Command(unittest.TestCase):
    def test_specs(self):
        code, out = cli("specs/")
        self.assertEqual(code, 0)
        lines = [l[2:] for l in out.splitlines() if l]
        model = check.model_of(SPECS)
        ids = [s["id"] for s in model["stories"]]
        self.assertEqual(sorted(ids), [f"EDDA-00{i}" for i in range(1, 9)])
        for s in model["stories"]:
            self.assertEqual(sum(l.startswith(view.stop(view.cap(s["sentence"])) + " As ") for l in lines), 1, s["id"])
        shown = {(s["text"], s["kind"]) for st in model["stories"]
                 for s in view.story_sentences(st, model["operations"], model["entities"], model["roles"])}
        for text, kind in shown:
            if kind in ("note", "question"):
                continue        # shown as written
            self.assertFalse(re.search(r"EDDA-\d+", re.sub(r'"[^"]*"', "", text)), text)

    def test_one_story(self):
        code, out = cli("specs/", "EDDA-007")
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("  The operator reads a story as sentences. As an operator, "))
        self.assertNotIn("\n\n", out)

    def test_unknown_story(self):
        self.assertEqual(cli("specs/", "EDDA-999"), (2, "no such story: EDDA-999\n"))      # a usage error

    def test_refused_project(self):
        code, out = cli("fixtures/unknown_key")
        self.assertEqual(code, 1)
        self.assertIn("unknown_key: unknown key: ensures", out)


if __name__ == "__main__":
    unittest.main(verbosity=2, warnings=False)
