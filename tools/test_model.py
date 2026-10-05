#!/usr/bin/env python3
"""The JSON model and the status life graph (reference section 9).

    python3 tools/test_model.py

The text graph of fulfillment.status in fixtures/inventory_autopart, line
by line; the model of specs/ is JSON, the same bytes on two runs, and
holds every story of EDDA-001 to EDDA-008 and every operation; each
expression's ast reads back to the checker's own parse; a fixture that
refuses gives exit 1 and no model; the plain run prints no model.
Astra's round 60, each on a small spec made from unreachable_choice: a
with: value keeps its kind, an empty may_change keeps its graph, a
computed choice property's graph has its values, a verdict has its
line, DEFAULT 01 is 1; a DEFAULT text is taken as written, a
backslash an ordinary character, and a quote inside it is refused.
Astra's round 62: a quoted DEFAULT in the time format is a TIME, its
default as written, and compares with TIME("..."); an invalid date
such as "2026-02-30" stays a TEXT.
"""
import ast
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["EDDA_LOG"] = "off"     # the tools and their children never write the log (section 11)
import check  # noqa: E402

ROOT = check.ROOT


def run(*args):
    p = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "check.py"), *args],
                       cwd=ROOT, capture_output=True, text=True)
    return p.returncode, p.stdout


def expressions(x):
    """every {"text", "line", "ast"} in a model"""
    if isinstance(x, dict):
        if set(x) == {"text", "line", "ast"}:
            yield x
        for v in x.values():
            yield from expressions(v)
    elif isinstance(x, list):
        for v in x:
            yield from expressions(v)


def spec(text, *edits):
    """a folder holding order.edda: text, or unreachable_choice's with each
    (old, new) edit made once"""
    if text is None:
        with open(os.path.join(ROOT, "fixtures", "unreachable_choice", "order.edda")) as f:
            text = f.read()
    for old, new in edits:
        assert text.count(old) == 1, old
        text = text.replace(old, new)
    d = tempfile.mkdtemp()
    with open(os.path.join(d, "order.edda"), "w") as f:
        f.write(text)
    return d


def model(folder):
    code, out = run("--model", folder)
    assert code == 0, out
    return json.loads(out)


MAY = ("may_change: {status: {incoming: [removed]}}",)

HOME = """roles:
  shop_user:
    is: "a person at a shop"
    properties:
      home: place
  visitor:
    is: "a person passing by"
    properties:
      home: TEXT

entities:
  place:
    is: "where someone lives"
    properties:
      label: TEXT
    may_read: [{role: shop_user}]
  order:
    is: "what a workshop buys"
    properties:
      status: DEFAULT incoming | removed
    may_change: {status: {incoming: [removed]}}
    may_update: [{role: shop_user}]

stories:
  FIX-001:
    story: "remove an order"
    about: order
    as_a: shop_user
    i_want: "to remove an order"
    so_that: "the list is clean"
    operations:
      remove:
        is: "takes an order off the list"
        inputs: {order: order}
        who: [{role: shop_user}]
        refuse:
          - when: "order.status == removed"
            reason: "already removed"
        ensure:
          - "order.status == removed"
    examples:
"""
for title, home in (("a given home", "primary"), ("a text home", '"primary"')):
    HOME += f"""      "{title}":
        given:
          - actor: erik
            with: {{roles: [shop_user, visitor], home: {home}}}
          - place: primary
            with: {{label: "main"}}
          - order: purchase
            with: {{status: incoming}}
        steps:
          - when: {{actor: erik, call: "remove(purchase)"}}
            then: [DONE, "purchase.status == removed"]
"""


class Round60(unittest.TestCase):
    def test_with_keeps_its_kind(self):
        ex = model(spec(HOME))["stories"][0]["examples"]
        homes = [x["given"][0]["with"]["home"] for x in ex]
        self.assertEqual(homes, [{"kind": "given", "value": "primary"}, {"kind": "text", "value": "primary"}])
        self.assertEqual(ex[0]["given"][0]["with"]["roles"],
                         {"kind": "list", "value": [{"kind": "role", "value": "shop_user"}, {"kind": "role", "value": "visitor"}]})
        self.assertEqual(ex[0]["given"][2]["with"]["status"], {"kind": "choice", "value": "incoming"})

    def test_empty_may_change(self):
        d = spec(None, (MAY[0], "may_change: {status: {}}"))
        ent = next(e for e in model(d)["entities"] if e["name"] == "order")
        self.assertEqual(ent["may_change"], [{"property": "status", "line": 13, "arrows": []}])
        self.assertEqual(run("--graph", "order.status", d),
                         (0, "incoming (default)\ndelivered (unreached)\nremoved (unreached)\n"))

    def test_computed_choice_graph(self):
        d = spec(None, ("      units_sent: DEFAULT 0\n", "      units_sent: DEFAULT 0\n      mirror: {computed: \"status\"}\n"),
                 (MAY[0], "may_change: {status: {incoming: [removed]}, mirror: {incoming: [removed]}}"))
        mirror = next(p for e in model(d)["entities"] for p in e["properties"] if p["name"] == "mirror")
        self.assertEqual((mirror["type"], mirror["values"]), ("choice", ["incoming", "delivered", "removed"]))
        self.assertEqual(run("--graph", "order.mirror", d), (0, "incoming -> removed\ndelivered\nremoved\n"))

    def test_verdict_line(self):
        steps = [s for x in model(os.path.join(ROOT, "fixtures", "unreachable_choice"))["stories"][0]["examples"]
                 for s in x["steps"]]
        self.assertEqual([s["verdict"] for s in steps], [
            {"kind": "DONE", "reason": None, "line": 44},
            {"kind": "refused", "reason": "already sent", "line": 53},
            {"kind": "DONE", "reason": None, "line": 62},
            {"kind": "refused", "reason": "already removed", "line": 64}])

    def test_default_01(self):
        d = spec(None, ("units_sent: DEFAULT 0", "units_sent: DEFAULT 01"))
        sent = next(p for e in model(d)["entities"] for p in e["properties"] if p["name"] == "units_sent")
        self.assertEqual((sent["type"], sent["default"]), ("INTEGER", 1))

    def test_default_text_as_written(self):
        d = spec(None, ("      units_sent: DEFAULT 0\n",
                        '      units_sent: DEFAULT 0\n      path: DEFAULT "C:\\New"\n      mark: DEFAULT "\\N"\n'))
        props = {p["name"]: p for e in model(d)["entities"] for p in e["properties"]}
        self.assertEqual([(props[n]["type"], props[n]["default"]) for n in ("path", "mark")],
                         [("TEXT", "C:\\New"), ("TEXT", "\\N")])

    def test_quote_inside_default_text_is_refused(self):
        d = spec(None, ("      units_sent: DEFAULT 0\n", '      units_sent: DEFAULT 0\n      mark: DEFAULT "a\\"b"\n'))
        code, out = run("--model", d)
        self.assertEqual(code, 1)
        self.assertIn('bad_type_phrase: not a type phrase: DEFAULT "a\\"b"', out)


TIMES = ("      units_sent: DEFAULT 0\n",
         '      units_sent: DEFAULT 0\n      due: DEFAULT "2026-10-04 09:00"\n'
         '      day: DEFAULT "2026-10-04"\n      odd: DEFAULT "2026-02-30"\n')
LATE = ('            reason: "already sent"\n',
        '            reason: "already sent"\n          - when: "order.due > TIME(\\"2026-10-05\\")"\n'
        '            reason: "too late"\n')


class Round62(unittest.TestCase):
    """a quoted DEFAULT in the time format of section 7.2 is a TIME"""

    def test_default_time_is_a_time(self):
        props = {p["name"]: p for e in model(spec(None, TIMES))["entities"] for p in e["properties"]}
        self.assertEqual([(props[n]["type"], props[n]["default"]) for n in ("due", "day", "odd")],
                         [("TIME", "2026-10-04 09:00"), ("TIME", "2026-10-04"), ("TEXT", "2026-02-30")])

    def test_default_time_compares_with_a_time(self):
        code, out = run("--model", spec(None, TIMES, LATE))
        self.assertEqual(code, 0, out)


class Graph(unittest.TestCase):
    def test_fulfillment_status(self):
        code, out = run("--graph", "fulfillment.status", "fixtures/inventory_autopart")
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines(), [
            "draft (default) -> pending, cancelled",
            "pending -> shipped, cancelled",
            "shipped",
            "cancelled",
        ])

    def test_unreached_value(self):
        code, out = run("--graph", "order.status", "fixtures/unreachable_choice")
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines(), ["incoming (default) -> removed", "delivered (unreached)", "removed"])

    def test_no_may_change_or_no_property(self):
        self.assertEqual(run("--graph", "fulfillment.reference", "fixtures/inventory_autopart"),
                         (2, "fulfillment.reference has no may_change\n"))      # usage errors (section 13)
        self.assertEqual(run("--graph", "fulfillment.nope", "fixtures/inventory_autopart"),
                         (2, "no such property: fulfillment.nope\n"))


class Model(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code, cls.out = run("--model")
        cls.model = json.loads(cls.out)

    def test_exit_and_version(self):
        self.assertEqual(self.code, 0)
        self.assertEqual((self.model["edda_model"], self.model["revision"]), (1, 70))

    def test_deterministic(self):
        self.assertEqual(run("--model"), (self.code, self.out))

    def test_every_story_and_operation(self):
        ids = [s["id"] for s in self.model["stories"]]
        self.assertEqual(sorted(ids), [f"EDDA-00{i}" for i in range(1, 9)])
        self.assertEqual(sorted(o["name"] for o in self.model["operations"]),
                         sorted(check.project_of(os.path.join(ROOT, "specs")).operations))
        for o in self.model["operations"]:
            self.assertIn(o["name"], next(s for s in self.model["stories"] if s["id"] == o["story"])["operations"])

    def test_ast_reads_back(self):
        found = list(expressions(self.model))
        self.assertTrue(found)
        for e in found:
            self.assertEqual(ast.dump(check.json_ast(e["ast"])), ast.dump(ast.parse(e["text"], mode="eval").body), e["text"])

    def test_refusing_fixture_gives_no_model(self):
        code, out = run("--model", "fixtures/unknown_name")
        self.assertEqual(code, 1)
        self.assertIn("unknown_name: unknown name: units_sold", out)
        self.assertNotIn("edda_model", out)

    def test_plain_run_prints_no_model(self):
        code, out = run()
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("specs/block.edda OK\n"))
        self.assertIn("\nfixtures: which layer catches each file\n", out)
        self.assertNotIn("edda_model", out)


if __name__ == "__main__":
    unittest.main(verbosity=2, warnings=False)    # as test_run.py: check.py leaves files to the collector
