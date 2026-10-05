#!/usr/bin/env python3
"""The link layer (reference sections 9 and 11).

    python3 tools/test_links.py

Every operation of EDDA-001 to EDDA-008 resolves to one function that
carries its story's marker, none of them NOT_BUILT; the plain run
prints a link line under each story and exits 0. Each link fixture is
caught by its rule at its line. Small projects made from
fixtures/approved hold each other case: two functions for one
operation, an exception naming no function, a marker not above a
function, not a marker, a missing marker, a marker on a function doing
none of its story's operations, an unknown story or target, a covered
file that does not exist, an unquoted path, NOT_BUILT; and the reach
rule: through a call, an import alias and a top-level table, never
through the command line block. A marker on a def that a later
binding replaces as a direct statement, or in a branch proven to run, is
refused, naming the line; one nested in any other branch of a compound
statement, or in an operand that may not run, leaves the link and is
flagged maybe_replaced (REBINDINGS, one row per form); a branch that
never runs (if False, if TYPE_CHECKING) counts for nothing; a bare
annotation binds nothing, a match capture binds. A .links line that
fails is refused once, with no naming-rule fallback. A name stands for
what its bindings resolve to once its module has loaded: imports by
module path, package and relative ones too, aliases, re-exports and
module aliases followed, a replacing import replaces, a conditional one
keeps both, and an import that runs runs the top level of each module
it names, every package on a dotted path too, used or not
(IMPORT_SHAPES, one row per shape). What Python evaluates as a top
level runs reaches what it names: decorators, default values,
annotations (not under from __future__ import annotations), bases,
class keywords and whole class bodies, never a function or lambda body
(IMPORT_TIME, one row per position). Rows needing match run
on Python 3.10+, except* on 3.11+. Only the body of a real
if __name__ == "__main__": is left out of the reach; a != test and a real guard's else run on import. A
project without a glossary.links has no link layer.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["EDDA_LOG"] = "off"     # the tools and their children never write the log (section 11)
import check  # noqa: E402

ROOT = check.ROOT
GLOSSARY = 'target: python\nrule: same_name\ncovers:\n  - "proj/code.py"\n'
TWO = GLOSSARY + '  - "proj/more.py"\n'
MARKED = '# FIX-001@1\ndef remove(order):\n    order.status = "removed"\n'


def layer(folder):
    """links_of over a folder whose four layers refuse nothing"""
    P = check.project_of(folder)
    assert not check.refused(folder), folder
    return check.links_of(folder, P)


def rules(result):
    """(shown file, rule, line) of every refusal and flag"""
    return sorted((f, r, line) for f, refusals, flags in result[0] for r, line, _ in refusals + flags)


class Project:
    """fixtures/approved copied to <tmp>/proj, with the files given"""

    def __init__(self, files):
        self.tmp = tempfile.mkdtemp(prefix="edda-links-")
        self.folder = os.path.join(self.tmp, "proj")
        shutil.copytree(os.path.join(ROOT, "fixtures", "approved"), self.folder)
        for name, text in files.items():
            os.makedirs(os.path.dirname(os.path.join(self.folder, name)), exist_ok=True)
            with open(os.path.join(self.folder, name), "w") as f:
                f.write(text)

    def __enter__(self):
        return layer(self.folder)

    def __exit__(self, *exc):
        shutil.rmtree(self.tmp)


def project(code, glossary=GLOSSARY, **more):
    return Project(dict({"glossary.links": glossary, "code.py": code}, **more))


class Specs(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.files, cls.linked = layer(os.path.join(ROOT, "specs"))

    def test_nothing_refused(self):
        self.assertEqual([f for f, refusals, _ in self.files if refusals], [])

    def test_every_operation_linked(self):
        P = check.project_of(os.path.join(ROOT, "specs"))
        self.assertEqual(sorted(P.stories), [f"EDDA-00{i}" for i in range(1, 9)])
        self.assertEqual(self.linked, {
            "EDDA-001": "EDDA-001: linked (check -> tools/check.py::check)",
            "EDDA-002": "EDDA-002: no operations to link",
            "EDDA-003": "EDDA-003: linked (notes -> tools/check.py::notes)",
            "EDDA-004": "EDDA-004: no operations to link",
            "EDDA-005": "EDDA-005: linked (approve -> tools/approve.py::approve)",
            "EDDA-006": "EDDA-006: linked (diff -> tools/check.py::changes)",
            "EDDA-007": "EDDA-007: linked (view -> tools/view.py::story_sentences, "
                        "view_at -> tools/edda_binding.py::view_at)",
            "EDDA-008": "EDDA-008: linked (approve_block -> tools/approve.py::approve)"})

    def test_nothing_not_built(self):
        self.assertEqual([line for line in self.linked.values() if "not linked" in line], [])

    def test_only_flags(self):
        found = {r for _, _, flags in self.files for r, _, _ in flags}
        self.assertEqual(found, {"unapproved_link", "no_story"})

    def test_plain_run(self):
        p = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "check.py")],
                           cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(p.returncode, 0)
        self.assertIn("    story EDDA-001: approved v3\n    EDDA-001: linked (check -> tools/check.py::check)\n",
                      p.stdout)
        self.assertIn("\nspecs/glossary.links OK\n", p.stdout)
        self.assertIn("\n  stale_link/code.py: flagged\n", p.stdout)


class Fixtures(unittest.TestCase):

    def test_each_fixture(self):
        want = {
            "stale_link": [("stale_link/code.py", "stale_link", 4)],
            "unapproved_link": [("unapproved_link/code.py", "unapproved_link", 4)],
            "no_story": [("no_story/code.py", "no_story", 13)],
            "unknown_link": [("unknown_link/order.links", "unknown_link", 3)],
            "no_function": [("no_function/glossary.links", "no_function", 4)],
            "bad_marker": [("bad_marker/code.py", "bad_marker", 4)],
            "bad_links": [("bad_links/glossary.links", "unknown_key", 4)],
            "maybe_replaced": [("maybe_replaced/code.py", "maybe_replaced", 4)],
        }
        for name, expected in want.items():
            with self.subTest(name):
                self.assertEqual(rules(layer(os.path.join(ROOT, "fixtures", name))), expected)

    def test_no_glossary_no_layer(self):
        self.assertIsNone(layer(os.path.join(ROOT, "fixtures", "approved")))


class Cases(unittest.TestCase):

    def test_two_functions(self):
        other = 'target: python\nrule: same_name\ncovers:\n  - "proj/code.py"\n  - "proj/more.py"\n'
        with project(MARKED, other, **{"more.py": "def remove(order):\n    pass\n"}) as r:
            self.assertEqual(rules(r), [("proj/glossary.links", "no_function", 2)])
            self.assertIn("two functions for remove of FIX-001: proj/code.py::remove, proj/more.py::remove; "
                          "name one in order.links", r[0][0][1][0][2])

    def test_exception_resolves(self):
        other = 'target: python\nrule: same_name\ncovers:\n  - "proj/code.py"\n  - "proj/more.py"\n'
        with project(MARKED, other, **{"more.py": "def remove(order):\n    pass\n",
                                       "order.links": 'links:\n  remove: "proj/code.py::remove"\n'}) as r:
            self.assertEqual([x for x in rules(r) if x[1] != "no_story"], [])
            self.assertEqual(r[1]["FIX-001"], "FIX-001: linked (remove -> proj/code.py::remove)")

    def test_exception_to_no_function(self):
        with project(MARKED, **{"order.links": 'links:\n  remove: "proj/code.py::take_off"\n'}) as r:
            self.assertEqual(rules(r), [("proj/order.links", "no_function", 2)])

    def test_exception_outside_covers(self):
        with project(MARKED, **{"order.links": 'links:\n  remove: "proj/other.py::remove"\n'}) as r:
            self.assertEqual(rules(r), [("proj/order.links", "unknown_link", 2)])

    def test_unquoted_path(self):
        with project(MARKED, **{"order.links": "links:\n  remove: proj/code.py::remove\n"}) as r:
            self.assertEqual(rules(r), [("proj/order.links", "unquoted_text", 2)])

    def test_not_built(self):
        with project("def other():\n    pass\n", **{"order.links": "links:\n  remove: NOT_BUILT\n"}) as r:
            self.assertEqual(r[1]["FIX-001"], "FIX-001: not linked (remove: not built)")
            self.assertEqual(rules(r), [("proj/code.py", "no_story", 1)])

    def test_links_beside_no_file(self):
        with project(MARKED, **{"basket.links": "links: {}\n"}) as r:
            self.assertEqual(rules(r), [("proj/basket.links", "unknown_link", 1)])

    def test_marker_not_above_a_function(self):
        with project('# FIX-001@1\n\ndef remove(order):\n    pass\n') as r:
            self.assertEqual(rules(r), [("proj/code.py", "bad_marker", 1), ("proj/code.py", "bad_marker", 3)])

    def test_marker_after_code(self):
        with project('x = 1  # FIX-001@1\n' + MARKED) as r:
            self.assertEqual(rules(r), [("proj/code.py", "bad_marker", 1)])

    def test_not_a_marker(self):
        with project('# FIX-001@v1\ndef remove(order):\n    pass\n') as r:
            self.assertEqual([x[1:] for x in rules(r)], [("bad_marker", 1), ("bad_marker", 2)])

    def test_missing_marker(self):
        with project("def remove(order):\n    pass\n") as r:
            self.assertEqual(rules(r), [("proj/code.py", "bad_marker", 1)])
            self.assertIn("carries no # FIX-001@<version>", r[0][1][1][0][2])

    def test_marker_on_a_helper(self):
        with project(MARKED + "\n\n# FIX-001@1\ndef helper():\n    pass\n") as r:
            self.assertEqual(rules(r), [("proj/code.py", "bad_marker", 6)])

    def test_marker_on_a_method(self):
        with project(MARKED + "\n\nclass Box:\n    # FIX-001@1\n    def remove(self):\n        pass\n") as r:
            self.assertEqual(rules(r), [("proj/code.py", "bad_marker", 7)])

    def test_marked_twice(self):
        with project("# FIX-001@1\n" + MARKED) as r:
            self.assertEqual(rules(r), [("proj/code.py", "bad_marker", 2)])

    def test_decorated_function(self):
        with project("def deco(f):\n    return f\n\n\n# FIX-001@1\n@deco\ndef remove(order):\n    pass\n") as r:
            self.assertEqual(rules(r), [])

    def test_unknown_story(self):
        with project("# FIX-009@1\n" + MARKED) as r:
            self.assertEqual(rules(r), [("proj/code.py", "unknown_link", 1)])

    def test_unknown_target(self):
        with project(MARKED, GLOSSARY.replace("python", "java")) as r:
            self.assertEqual(rules(r), [("proj/glossary.links", "unknown_link", 1)])

    def test_no_such_covered_file(self):
        with project(MARKED, GLOSSARY.replace("code.py", "gone.py")) as r:
            self.assertEqual(rules(r), [("proj/glossary.links", "unknown_link", 4)])

    def test_reach(self):
        code = ("import more as m\n\n\n" + MARKED + "    m.helper()\n\n\n"
                "def tabled():\n    pass\n\n\ndef main():\n    pass\n\n\n"
                "TABLE = {'t': tabled}\n\nif __name__ == '__main__':\n    main()\n")
        more = "def helper():\n    pass\n\n\ndef unused():\n    pass\n"
        glossary = 'target: python\nrule: same_name\ncovers:\n  - "proj/code.py"\n  - "proj/more.py"\n'
        with project(code, glossary, **{"more.py": more}) as r:
            self.assertEqual([(f, rule) for f, rule, _ in rules(r)],
                             [("proj/code.py", "no_story"), ("proj/more.py", "no_story")])
            flagged = [m for _, _, flags in r[0] for _, _, m in flags]
            self.assertEqual(flagged, ["no linked function reaches main", "no linked function reaches unused"])


def flagged(r):
    """the no_story messages of a result"""
    return [m for _, _, flags in r[0] for rule, _, m in flags if rule == "no_story"]


class Replaced(unittest.TestCase):
    """a marker belongs to the def in force once the module has loaded"""

    def test_later_def(self):
        with project(MARKED + "\n\ndef remove(order):\n    pass\n") as r:
            self.assertEqual(rules(r), [("proj/code.py", "bad_marker", 1), ("proj/code.py", "bad_marker", 6)])
            msgs = [m for _, refusals, _ in r[0] for _, _, m in refusals]
            self.assertIn("remove at line 2 is replaced by a def at line 6, so the marker is on code "
                          "that does not run: # FIX-001@1", msgs)
            self.assertIn("remove does remove of FIX-001 and carries no # FIX-001@<version>", msgs)

    def test_assigned_none(self):
        with project(MARKED + "\n\nremove = None\n") as r:
            self.assertEqual(rules(r), [("proj/code.py", "bad_marker", 1), ("proj/glossary.links", "no_function", 2)])
            msgs = [m for _, refusals, _ in r[0] for _, _, m in refusals]
            self.assertIn("remove at line 2 is replaced by a binding at line 6, so the marker is on code "
                          "that does not run: # FIX-001@1", msgs)
            self.assertIn("no function remove for FIX-001 in the covered files "
                          "(proj/code.py::remove, replaced by a binding at line 6)", msgs)

    def test_imported_over(self):
        with project(MARKED + "\n\nfrom more import remove\n", TWO,
                     **{"more.py": "def other():\n    pass\n"}) as r:
            self.assertEqual([x for x in rules(r) if x[1] != "no_story"],
                             [("proj/code.py", "bad_marker", 1), ("proj/glossary.links", "no_function", 2)])

    def test_exception_to_a_replaced_def(self):
        with project(MARKED + "\n\nremove = None\n", **{"order.links": 'links:\n  remove: "proj/code.py::remove"\n'}) as r:
            self.assertEqual(rules(r), [("proj/code.py", "bad_marker", 1), ("proj/order.links", "no_function", 2)])
            msgs = [m for _, refusals, _ in r[0] for _, _, m in refusals]
            self.assertIn("no function remove in proj/code.py, replaced by a binding at line 6", msgs)

    def test_in_a_top_level_if(self):
        with project(MARKED + "\n\nif True:\n    remove = None\n") as r:
            self.assertIn(("proj/code.py", "bad_marker", 1), rules(r))

    def test_in_the_command_line_block(self):
        with project(MARKED + "\n\nif __name__ == '__main__':\n    remove = None\n") as r:
            self.assertEqual(rules(r), [])

    def test_in_the_else_of_the_command_line_block(self):
        with project(MARKED + "\n\nif __name__ == '__main__':\n    pass\nelse:\n    remove = None\n") as r:
            self.assertIn(("proj/code.py", "bad_marker", 1), rules(r))

    def test_earlier_binding_is_fine(self):
        with project("remove = None\n\n\n" + MARKED) as r:
            self.assertEqual(rules(r), [])


def maybe(r):
    """the maybe_replaced flags of a result, (line, message)"""
    return [(line, m) for _, _, flags in r[0] for rule, line, m in flags if rule == "maybe_replaced"]


class Conditional(unittest.TestCase):
    """only a rebinding every import runs replaces a marked def; one in a
    top-level if or try leaves the link and is flagged; a branch that never
    runs counts for nothing"""

    def test_if_false(self):
        with project(MARKED + "\n\nif False:\n    remove = None\n") as r:
            self.assertEqual(rules(r), [])

    def test_type_checking(self):
        code = "from typing import TYPE_CHECKING\n\n\n" + MARKED + "\n\nif TYPE_CHECKING:\n    remove = None\n"
        with project(code) as r:
            self.assertEqual(rules(r), [])

    def test_typing_type_checking_else_runs(self):
        code = "import typing\n\n\n" + MARKED + "\n\nif typing.TYPE_CHECKING:\n    pass\nelse:\n    remove = None\n"
        with project(code) as r:
            self.assertIn(("proj/code.py", "bad_marker", 4), rules(r))

    def test_optional_fast_implementation(self):
        code = MARKED + "\n\ntry:\n    from _fast_orders import remove\nexcept ImportError:\n    pass\n"
        with project(code) as r:
            self.assertEqual(rules(r), [("proj/code.py", "maybe_replaced", 1)])
            self.assertEqual(maybe(r), [(1, "remove at line 2 may be replaced by a binding at line 7, "
                                           "which not every import runs: # FIX-001@1")])
            self.assertEqual(r[1]["FIX-001"], "FIX-001: linked (remove -> proj/code.py::remove)")

    def test_except_import_error_fallback(self):
        code = (MARKED + "\n\ntry:\n    import _fast_orders\nexcept ImportError:\n"
                "    def remove(order):\n        pass\n")
        with project(code) as r:
            self.assertEqual(rules(r), [("proj/code.py", "maybe_replaced", 1)])
            self.assertIn("by a def at line 9", maybe(r)[0][1])

    def test_conditional_if(self):
        with project("import os\n\n\n" + MARKED + "\n\nif os.environ.get('X'):\n    remove = None\n") as r:
            self.assertEqual(rules(r), [("proj/code.py", "maybe_replaced", 4)])

    def test_sure_replacement_first_wins(self):
        with project(MARKED + "\n\nremove = None\n\ntry:\n    remove = 1\nexcept ImportError:\n    pass\n") as r:
            self.assertNotIn("maybe_replaced", [x[1] for x in rules(r)])
            self.assertIn(("proj/code.py", "bad_marker", 1), rules(r))

    def test_finally_runs(self):
        with project(MARKED + "\n\ntry:\n    pass\nfinally:\n    remove = None\n") as r:
            self.assertIn(("proj/code.py", "bad_marker", 1), rules(r))


class Bindings(unittest.TestCase):
    """a bare annotation binds nothing; a match capture binds"""

    def test_bare_annotation(self):
        with project(MARKED + "\n\nremove: int\n") as r:
            self.assertEqual(rules(r), [])

    def test_annotated_assignment_binds(self):
        with project(MARKED + "\n\nremove: int = 1\n") as r:
            self.assertIn(("proj/code.py", "bad_marker", 1), rules(r))

    @unittest.skipIf(sys.version_info < (3, 10), "match needs Python 3.10")
    def test_match_capture_always_runs(self):
        with project(MARKED + "\n\nmatch 1:\n    case remove:\n        pass\n") as r:
            self.assertIn(("proj/code.py", "bad_marker", 1), rules(r))

    @unittest.skipIf(sys.version_info < (3, 10), "match needs Python 3.10")
    def test_match_capture_in_a_pattern(self):
        with project(MARKED + "\n\nmatch [1]:\n    case [remove]:\n        pass\n") as r:
            self.assertEqual(rules(r), [("proj/code.py", "maybe_replaced", 1)])


class ExplicitOnce(unittest.TestCase):
    """a .links line that fails is the one report: no naming-rule fallback"""

    def test_no_such_function(self):
        with project("def other():\n    pass\n", **{"order.links": 'links:\n  remove: "proj/code.py::take_off"\n'}) as r:
            self.assertEqual(rules(r), [("proj/order.links", "no_function", 2)])

    def test_not_a_link(self):
        with project("def other():\n    pass\n", **{"order.links": 'links:\n  remove: "take_off"\n'}) as r:
            self.assertEqual(rules(r), [("proj/order.links", "unknown_link", 2)])

    def test_refused_links_file(self):
        with project("def other():\n    pass\n", **{"order.links": "links:\n  remove: proj/code.py::take_off\n"}) as r:
            self.assertEqual(rules(r), [("proj/order.links", "unquoted_text", 2)])


class Imports(unittest.TestCase):
    """imports resolve by module path against the covered files"""

    def reach(self, line, call, more_files=None, glossary=TWO):
        code = line + "\n\n\n" + MARKED + "    " + call + "\n"
        files = more_files or {"more.py": "def helper():\n    pass\n\n\ndef unused():\n    pass\n"}
        return project(code, glossary, **files)

    def test_package_import_alias(self):
        with self.reach("import proj.more as m", "m.helper()") as r:
            self.assertEqual(flagged(r), ["no linked function reaches unused"])

    def test_package_import_dotted(self):
        with self.reach("import proj.more", "proj.more.helper()") as r:
            self.assertEqual(flagged(r), ["no linked function reaches unused"])

    def test_relative_import_alias(self):
        with self.reach("from .more import helper as h", "h()") as r:
            self.assertEqual(flagged(r), ["no linked function reaches unused"])

    def test_relative_module_import(self):
        with self.reach("from . import more as mm", "mm.helper()") as r:
            self.assertEqual(flagged(r), ["no linked function reaches unused"])

    def test_package_re_export(self):
        glossary = GLOSSARY + '  - "proj/pkg/__init__.py"\n  - "proj/pkg/impl.py"\n'
        files = {"pkg/__init__.py": "from .impl import helper\n",
                 "pkg/impl.py": "def helper():\n    pass\n\n\ndef unused():\n    pass\n"}
        with self.reach("from proj.pkg import helper", "helper()", files, glossary) as r:
            self.assertEqual(flagged(r), ["no linked function reaches unused"])

    def test_re_export_chain_and_loop(self):
        glossary = GLOSSARY + '  - "proj/pkg/__init__.py"\n  - "proj/pkg/mid.py"\n  - "proj/pkg/impl.py"\n'
        files = {"pkg/__init__.py": "from .mid import helper\n",
                 "pkg/mid.py": "from .impl import helper\nfrom . import helper as again\n",
                 "pkg/impl.py": "from . import helper as back\n\n\ndef helper():\n    pass\n"}
        with self.reach("import proj.pkg as p", "p.helper()", files, glossary) as r:
            self.assertEqual(flagged(r), [])

    def test_same_basename_in_two_folders(self):
        glossary = GLOSSARY + '  - "proj/more.py"\n  - "proj/sub/more.py"\n'
        files = {"more.py": "def helper():\n    pass\n", "sub/__init__.py": "",
                 "sub/more.py": "def helper():\n    pass\n"}
        with self.reach("import proj.sub.more as m", "m.helper()", files, glossary) as r:
            self.assertEqual([(f, rule, line) for f, rule, line in rules(r)], [("proj/more.py", "no_story", 1)])


REPLACED, MAYBE, NOTHING = "replaced", "maybe", "nothing"
PY310, PY311 = sys.version_info >= (3, 10), sys.version_info >= (3, 11)

# (case, code after the marked def, outcome, runs on this Python)
REBINDINGS = [
    ("direct statement", "remove = None\n", REPLACED, True),
    ("direct import", "from fast import remove\n", REPLACED, True),
    ("del", "del remove\n", REPLACED, True),
    ("walrus in a statement", "x = (remove := None)\n", REPLACED, True),
    ("if True", "if True:\n    remove = None\n", REPLACED, True),
    ("else of if False", "if False:\n    pass\nelse:\n    remove = None\n", REPLACED, True),
    ("if False", "if False:\n    remove = None\n", NOTHING, True),
    ("else of if True", "if True:\n    pass\nelse:\n    remove = None\n", NOTHING, True),
    ("if TYPE_CHECKING", "if TYPE_CHECKING:\n    remove = None\n", NOTHING, True),
    ("if of a test", "if x:\n    remove = None\n", MAYBE, True),
    ("else of a test", "if x:\n    pass\nelse:\n    remove = None\n", MAYBE, True),
    ("try body", "try:\n    from fast import remove\nexcept ImportError:\n    pass\n", MAYBE, True),
    ("except", "try:\n    pass\nexcept ImportError:\n    remove = None\n", MAYBE, True),
    ("except as", "try:\n    pass\nexcept ImportError as remove:\n    pass\n", MAYBE, True),
    ("try else", "try:\n    pass\nexcept ImportError:\n    pass\nelse:\n    remove = None\n", MAYBE, True),
    ("finally", "try:\n    pass\nfinally:\n    remove = None\n", REPLACED, True),
    ("with suppress", "with suppress(ImportError):\n    from fast import remove\n", MAYBE, True),
    ("with target", "with open('x') as remove:\n    pass\n", REPLACED, True),
    ("for body", "for x in y:\n    remove = None\n", MAYBE, True),
    ("for target", "for remove in y:\n    pass\n", MAYBE, True),
    ("for else", "for x in y:\n    pass\nelse:\n    remove = None\n", MAYBE, True),
    ("while body", "while x:\n    remove = None\n", MAYBE, True),
    ("while else", "while x:\n    pass\nelse:\n    remove = None\n", MAYBE, True),
    ("if True holding a with", "if True:\n    with x:\n        remove = None\n", MAYBE, True),
    ("finally holding an if", "try:\n    pass\nfinally:\n    if x:\n        remove = None\n", MAYBE, True),
    ("right of or", "x = y or (remove := None)\n", MAYBE, True),
    ("arm of if-else", "x = 1 if y else (remove := None)\n", MAYBE, True),
    ("walrus in a comprehension", "x = [(remove := i) for i in y]\n", MAYBE, True),
    ("comprehension target", "x = [remove for remove in y]\n", NOTHING, True),
    ("class body", "class Box:\n    remove = None\n", NOTHING, True),
    ("def body", "def other():\n    remove = None\n", NOTHING, True),
    ("match case", "match x:\n    case 1:\n        remove = None\n", MAYBE, PY310),
    ("match capture in a pattern", "match x:\n    case [remove]:\n        pass\n", MAYBE, PY310),
    ("match first catch-all", "match x:\n    case remove:\n        pass\n", REPLACED, PY310),
    ("match guarded catch-all", "match x:\n    case remove if y:\n        pass\n", MAYBE, PY310),
    ("except*", "try:\n    pass\nexcept* ImportError:\n    remove = None\n", MAYBE, PY311),
]


class Rebinding(unittest.TestCase):
    """rule 1, over every compound statement form: a rebinding replaces the
    marked def only as a direct statement or in a branch proven to run;
    anywhere else it may be skipped and flags maybe_replaced; a branch that
    never runs counts for nothing"""

    def test_each_form(self):
        for case, code, outcome, runs in REBINDINGS:
            with self.subTest(case):
                if not runs:
                    self.skipTest(f"{case} needs a newer Python")
                with project(MARKED + "\n\n" + code) as r:
                    got = [x for x in rules(r) if x[1] != "no_story"]
                    if outcome == REPLACED:
                        self.assertIn(("proj/code.py", "bad_marker", 1), got)
                    elif outcome == MAYBE:
                        self.assertEqual(got, [("proj/code.py", "maybe_replaced", 1)])
                        self.assertEqual(r[1]["FIX-001"], "FIX-001: linked (remove -> proj/code.py::remove)")
                    else:
                        self.assertEqual(got, [])

    def test_with_suppress_message(self):
        with project(MARKED + "\n\nwith suppress(ImportError):\n    from fast import remove\n") as r:
            self.assertEqual(maybe(r), [(1, "remove at line 2 may be replaced by a binding at line 7, "
                                           "which not every import runs: # FIX-001@1")])


PKG = GLOSSARY + '  - "proj/pkg/__init__.py"\n  - "proj/pkg/impl.py"\n'
IMPL = "def helper():\n    pass\n\n\ndef unused():\n    pass\n"
MORE = {"more.py": IMPL}
# a module whose top level registers: register is reached only when an
# import runs it
PLUGIN = "def register():\n    pass\n\n\ndef unused():\n    pass\n\n\nregister()\n"

# (case, import line in code.py, the call in remove, files, glossary, the
# (file, name) pairs flagged no_story)
IMPORT_SHAPES = [
    ("plain", "import more", "more.helper()", MORE, TWO, [("proj/more.py", "unused")]),
    ("plain dotted", "import proj.more", "proj.more.helper()", MORE, TWO, [("proj/more.py", "unused")]),
    ("from", "from more import helper", "helper()", MORE, TWO, [("proj/more.py", "unused")]),
    ("relative", "from .more import helper", "helper()", MORE, TWO, [("proj/more.py", "unused")]),
    ("alias", "from more import helper as h", "h()", MORE, TWO, [("proj/more.py", "unused")]),
    ("module alias", "import proj.more as m", "m.helper()", MORE, TWO, [("proj/more.py", "unused")]),
    ("relative module alias", "from . import more as m", "m.helper()", MORE, TWO,
     [("proj/more.py", "unused")]),
    ("import inside the function", "", "from more import helper\n    helper()", MORE, TWO,
     [("proj/more.py", "unused")]),
    ("module import inside the function", "", "import more as m\n    m.helper()", MORE, TWO,
     [("proj/more.py", "unused")]),
    ("re-export", "from proj.pkg import helper", "helper()",
     {"pkg/__init__.py": "from .impl import helper\n", "pkg/impl.py": IMPL}, PKG, [("proj/pkg/impl.py", "unused")]),
    ("re-export through a package alias", "import proj.pkg as p", "p.helper()",
     {"pkg/__init__.py": "from .impl import helper\n", "pkg/impl.py": IMPL}, PKG, [("proj/pkg/impl.py", "unused")]),
    ("re-export of a module alias", "from proj.pkg import api", "api.helper()",
     {"pkg/__init__.py": "from . import impl as api\n", "pkg/impl.py": IMPL}, PKG, [("proj/pkg/impl.py", "unused")]),
    ("re-export of a module alias, dotted", "import proj.pkg as p", "p.api.helper()",
     {"pkg/__init__.py": "from . import impl as api\n", "pkg/impl.py": IMPL}, PKG, [("proj/pkg/impl.py", "unused")]),
    ("replacing import", "from proj.pkg import helper", "helper()",
     {"pkg/__init__.py": "def helper():\n    pass\n\n\nfrom .impl import helper\n", "pkg/impl.py": IMPL}, PKG,
     [("proj/pkg/__init__.py", "helper"), ("proj/pkg/impl.py", "unused")]),
    ("conditional import keeps both", "from proj.pkg import helper", "helper()",
     {"pkg/__init__.py": "def helper():\n    pass\n\n\ntry:\n    from .impl import helper\nexcept ImportError:\n"
                         "    pass\n", "pkg/impl.py": IMPL}, PKG, [("proj/pkg/impl.py", "unused")]),
    ("an import before a def is replaced by it", "from proj.pkg import helper", "helper()",
     {"pkg/__init__.py": "from .impl import helper\n\n\ndef helper():\n    pass\n", "pkg/impl.py": IMPL}, PKG,
     [("proj/pkg/impl.py", "helper"), ("proj/pkg/impl.py", "unused")]),
    ("side-effect import runs the top level", "import proj.more", "pass", {"more.py": PLUGIN}, TWO,
     [("proj/more.py", "unused")]),
    ("relative side-effect import", "from . import more", "pass", {"more.py": PLUGIN}, TWO,
     [("proj/more.py", "unused")]),
    ("from-import of a submodule runs it", "from proj import more", "pass", {"more.py": PLUGIN}, TWO,
     [("proj/more.py", "unused")]),
    ("dotted path runs each package", "import proj.pkg.impl", "pass",
     {"pkg/__init__.py": PLUGIN, "pkg/impl.py": PLUGIN}, PKG,
     [("proj/pkg/__init__.py", "unused"), ("proj/pkg/impl.py", "unused")]),
    ("conditional side-effect import", "try:\n    import proj.more\nexcept ImportError:\n    pass", "pass",
     {"more.py": PLUGIN}, TWO, [("proj/more.py", "unused")]),
    ("side-effect import inside the function", "", "import proj.more", {"more.py": PLUGIN}, TWO,
     [("proj/more.py", "unused")]),
]


def no_story(r):
    """(file, name) of every no_story flag"""
    return sorted((f, m.rsplit(" ", 1)[1]) for f, _, flags in r[0] for rule, _, m in flags if rule == "no_story")


class ImportShapes(unittest.TestCase):
    """rule 2: a name stands for what its binding resolves to once its
    module has loaded, through imports, re-exports and module aliases"""

    def test_each_shape(self):
        for case, line, call, files, glossary, want in IMPORT_SHAPES:
            with self.subTest(case):
                code = line + "\n\n\n" + MARKED + "    " + call + "\n"
                with project(code, glossary, **files) as r:
                    self.assertEqual([x for x in rules(r) if x[1] != "no_story"], [])
                    self.assertEqual(no_story(r), want)


LAZY = "from __future__ import annotations\n\n\n"

# (case, code before the marked def, code after it, whether helper is
# reached): what Python evaluates when the module's top level runs
IMPORT_TIME = [
    ("decorator", "", "@helper\ndef other():\n    pass\n", True),
    ("decorator with arguments", "", "@helper(1)\ndef other():\n    pass\n", True),
    ("default value", "", "def other(x=helper()):\n    pass\n", True),
    ("keyword-only default", "", "def other(*, x=helper()):\n    pass\n", True),
    ("annotation", "", "def other(x: helper):\n    pass\n", True),
    ("return annotation", "", "def other() -> helper:\n    pass\n", True),
    ("module annotation", "", "x: helper = 1\n", True),
    ("annotation, future import", LAZY, "def other(x: helper):\n    pass\n", False),
    ("return annotation, future import", LAZY, "def other() -> helper:\n    pass\n", False),
    ("module annotation, future import", LAZY, "x: helper = 1\n", False),
    ("value of an annotated name, future import", LAZY, "x: int = helper()\n", True),
    ("default value, future import", LAZY, "def other(x: int = helper()):\n    pass\n", True),
    ("base class", "", "class Other(helper):\n    pass\n", True),
    ("metaclass keyword", "", "class Other(metaclass=helper):\n    pass\n", True),
    ("class decorator", "", "@helper\nclass Other:\n    pass\n", True),
    ("class body call", "", "class Other:\n    x = helper()\n", True),
    ("class body annotation", "", "class Other:\n    x: helper\n", True),
    ("class body annotation, future import", LAZY, "class Other:\n    x: helper\n", False),
    ("nested class body", "", "class Other:\n    class Inner:\n        x = helper()\n", True),
    ("class-level decorator", "", "class Other:\n    @helper\n    def m(self):\n        pass\n", True),
    ("method default value", "", "class Other:\n    def m(self, x=helper()):\n        pass\n", True),
    ("lambda default value", "", "x = lambda y=helper(): y\n", True),
    ("lambda body not run", "", "x = lambda: helper()\n", False),
    ("function body not run", "", "def other():\n    helper()\n", False),
    ("method body not run", "", "class Other:\n    def m(self):\n        helper()\n", False),
]


class ImportTime(unittest.TestCase):
    """what Python evaluates when a module's top level runs reaches what
    it names: all of it but the bodies of functions and lambdas, and
    annotations the future import defers"""

    def test_each_position(self):
        for case, before, after, reached in IMPORT_TIME:
            with self.subTest(case):
                code = before + MARKED + "\n\ndef helper(*a, **k):\n    pass\n\n\n" + after
                with project(code) as r:
                    self.assertEqual([x for x in rules(r) if x[1] != "no_story"], [])
                    self.assertEqual(("proj/code.py", "helper") not in no_story(r), reached)


class CommandLine(unittest.TestCase):
    """only the body of a real if __name__ == "__main__": is left out"""

    def run_with(self, block):
        code = MARKED + "\n\ndef main():\n    pass\n\n\ndef other():\n    pass\n\n\n" + block
        return project(code)

    def test_reversed_operands(self):
        with self.run_with("if '__main__' == __name__:\n    main()\n") as r:
            self.assertEqual(flagged(r), ["no linked function reaches main", "no linked function reaches other"])

    def test_not_equal_runs_on_import(self):
        with self.run_with("if __name__ != '__main__':\n    main()\n") as r:
            self.assertEqual(flagged(r), ["no linked function reaches other"])

    def test_else_runs_on_import(self):
        with self.run_with("if __name__ == '__main__':\n    main()\nelse:\n    other()\n") as r:
            self.assertEqual(flagged(r), ["no linked function reaches main"])


if __name__ == "__main__":
    unittest.main(verbosity=2, warnings=False)
