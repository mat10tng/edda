#!/usr/bin/env python3
"""The frozen clock in examples (reference sections 7, 8 and 9; decision
FF, with Z and GG).

    python3 tools/test_clock.py

An example that uses time runs on a clock that starts at its starts_at:,
else at the project's clock_start:; with neither it is refused
(no_clock_start), and an example that does not use time needs no
start (a start there is flagged, clock_unused). Only a step's at: moves
the clock: to a time, or to NOW moved by DAYS, HOURS or MINUTES. An at:
earlier than the clock is refused when the checker can tell
(clock_backwards), else the example fails at the at:. DAYS is a
calendar day in the business zone, HOURS elapsed time, across a
daylight-saving change in Europe/Oslo. TODAY is the day of the frozen
NOW. A duration anywhere but after TIME + or - is refused. The
binding is told the time whenever the clock is set or moves, before
anything is read at it, so a bound property that reads the time is
judged at the step's time; the read view shows each step's
resolved time; generated cases run on the project's clock_start, or
skip what reads the clock without one; and nothing reads the
machine's clock while examples run. The settings refuse an unknown
zone and a clock_start that is no time.
"""
import contextlib
import datetime
import io
import os
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["EDDA_LOG"] = "off"     # the tools and their children never write the log (section 11)
import check                     # noqa: E402
import edda_binding as binding   # noqa: E402
import run                       # noqa: E402
import settings                  # noqa: E402
import view                      # noqa: E402

GIVEN = """\
        given:
          - actor: ann
            with: {roles: [clerk]}
          - task: t
"""

SPEC = """\
roles:
  clerk:
    is: "a person at the desk"
entities:
  task:
    is: "something to do"
    properties:
      stamped: TIME, OPTIONAL
      count: DEFAULT 1
    may_update: [{role: clerk}]
stories:
  CLK-001:
    story: "stamp a task"
    about: task
    as_a: clerk
    i_want: "to stamp a task with the time"
    so_that: "I know when it was seen"
    operations:
      stamp:
        is: "stamps a task with the time"
        inputs: {task: task}
        who: [{role: clerk}]
        ensure:
          - "task.stamped == NOW"
      today:
        is: "the day it is"
        who: [{role: clerk}]
        returns: "TODAY"
      count_of:
        is: "how many a task counts"
        inputs: {task: task}
        who: [{role: clerk}]
        returns: "task.count"
    examples:
EXAMPLES"""

MOVES = """\
      "the clock moves only with at":
        starts_at: "2026-10-05 09:00"
""" + GIVEN + """\
        steps:
          - when: {actor: ann, call: "stamp(t)"}
            then: [DONE, "t.stamped == TIME(\\"2026-10-05 09:00\\")"]
          - when: {actor: ann, call: "stamp(t)", at: "2026-10-06 10:00"}
            then: [DONE, "t.stamped == TIME(\\"2026-10-06 10:00\\")"]
          - when: {actor: ann, call: "stamp(t)", at: "NOW + DAYS(1)"}
            then: [DONE, "t.stamped == TIME(\\"2026-10-07 10:00\\")", "today() == TIME(\\"2026-10-07\\")"]
          - when: {actor: ann, call: "stamp(t)", at: "NOW + HOURS(2) + MINUTES(30)"}
            then: [DONE, "t.stamped == TIME(\\"2026-10-07 12:30\\")", "today() == TODAY"]
          - when: {actor: ann, call: "count_of(t)"}
            then: [DONE, "t.stamped == NOW", "TODAY == TIME(\\"2026-10-07\\")"]
"""

DEFAULT_START = """\
      "the clock starts at the project's start":
""" + GIVEN + """\
        steps:
          - when: {actor: ann, call: "stamp(t)"}
            then: [DONE, "t.stamped == TIME(\\"2026-10-01 09:00\\")"]
"""

NO_TIME = """\
      "counting reads no time":
""" + GIVEN + """\
        steps:
          - when: {actor: ann, call: "count_of(t)"}
            then: [DONE, "RESULT == 1"]
"""


FRAME = SPEC.replace("""      count: DEFAULT 1
""", """      count: DEFAULT 1
      expired: {computed: "stamped < NOW"}
""").replace("""    examples:
""", """      bump:
        is: "counts a task once more"
        inputs: {task: task}
        who: [{role: clerk}]
        ensure:
          - "task.count == OLD(task.count) + 1"
        also_changes: ["task.expired"]
    examples:
""")

BUMP = """\
      "bumping reads the clock through the frame rule":
""" + GIVEN.replace("- task: t", '- task: t\n            with: {stamped: "2026-10-01"}') + """\
        steps:
          - when: {actor: ann, call: "bump(t)"}
            then: [DONE, "t.count == 2"]
"""


def task(name, values, workdir):
    return binding.Thing("task", values)


class Clocked(unittest.TestCase):
    """a project root with an edda.yaml and its specs/, and a binding whose
    operations read the time the runner tells it"""

    def setUp(self):
        self.root = tempfile.TemporaryDirectory()
        self.specs = os.path.join(self.root.name, "specs")
        os.mkdir(self.specs)
        self.seen = []      # each time the clock was set or moved, as the binding was told it

        def stamp(actor, t):
            t.stamped = self.seen[-1]

        def today(actor):
            now = self.seen[-1]
            return datetime.datetime(now.year, now.month, now.day)
        binding.ENTITIES["task"] = task
        def bump(actor, t):
            t.count += 1
        binding.OPERATIONS.update(stamp=stamp, today=today, count_of=lambda actor, t: t.count, bump=bump)
        binding.clock = self.seen.append

    def tearDown(self):
        del binding.ENTITIES["task"], binding.clock
        for name in ("stamp", "today", "count_of", "bump"):
            del binding.OPERATIONS[name]
        self.root.cleanup()

    def project(self, examples, settings_text="", spec=SPEC):
        with open(os.path.join(self.root.name, "edda.yaml"), "w") as f:
            f.write("stack: python\n" + settings_text)
        with open(os.path.join(self.specs, "task.edda"), "w") as f:
            f.write(spec.replace("EXAMPLES", examples))

    def problems(self):
        P = check.project_of(self.specs)
        found = check.check(os.path.join(self.specs, "task.edda"), P)
        return [(rule, msg) for rule, _, msg in found[2]], [(rule, msg) for rule, _, msg in found[4]]

    def run_story(self):
        return run.run(self.specs, ["CLK-001"])[0][1:]


class StartTest(Clocked):

    def test_the_clock_starts_at_the_examples_start_and_moves_only_with_at(self):
        self.project(MOVES)
        self.assertEqual(self.problems(), ([], []))
        self.assertEqual(self.run_story(), ("examples passed", "all 1", []))
        self.assertEqual([check.clock_words(t) for t in self.seen], [     # the start, then each at:
            "2026-10-05 09:00", "2026-10-06 10:00", "2026-10-07 10:00", "2026-10-07 12:30"])

    def test_the_clock_starts_at_the_projects_default(self):
        self.project(DEFAULT_START, 'clock_start: "2026-10-01 09:00"\n')
        self.assertEqual(self.problems(), ([], []))
        self.assertEqual(self.run_story(), ("examples passed", "all 1", []))

    def test_an_examples_start_wins_over_the_default(self):
        self.project(MOVES, 'clock_start: "2026-01-01 00:00"\n')
        self.assertEqual(self.run_story(), ("examples passed", "all 1", []))
        self.assertEqual(check.clock_words(self.seen[0]), "2026-10-05 09:00")

    def test_an_example_that_uses_time_and_has_no_start_is_refused(self):
        self.project(DEFAULT_START)
        self.assertEqual(self.problems()[0], [(
            "no_clock_start", 'example "the clock starts at the project\'s start" uses time (reads NOW) but has no '
                              "start; give it starts_at: or the project clock_start:")])

    def test_a_time_read_through_another_operation_counts(self):
        self.project(NO_TIME.replace('"RESULT == 1"', '"today() == TIME(\\"2026-10-01\\")"'))
        self.assertEqual(self.problems()[0][0][0], "no_clock_start")
        self.assertIn("calls today, which reads the clock", self.problems()[0][0][1])

    def test_an_example_that_uses_no_time_needs_no_start(self):
        self.project(NO_TIME)
        self.assertEqual(self.problems(), ([], []))
        self.assertEqual(self.run_story(), ("examples passed", "all 1", []))
        self.assertEqual(self.seen, [None])        # told there is no clock

    def test_a_start_on_an_example_that_uses_no_time_is_flagged(self):
        self.project(NO_TIME.replace("        given:", '        starts_at: "2026-10-05 09:00"\n        given:', 1))
        self.assertEqual(self.problems(), ([], [(
            "clock_unused", 'example "counting reads no time" uses no time; its starts_at: is never read')]))

    def test_a_start_that_is_no_time_is_refused(self):
        self.project(MOVES.replace('starts_at: "2026-10-05 09:00"', 'starts_at: "soon"'))
        self.assertEqual(self.problems()[0], [
            ("type_mismatch", 'starts_at expects a time, "YYYY-MM-DD HH:MM" or "YYYY-MM-DD": soon')])


EXPIRY = SPEC.replace("""      count: DEFAULT 1
""", """      count: DEFAULT 1
      open: YES_NO, OPTIONAL
""").replace("""    examples:
""", """      work_on:
        is: "works on a task that has not expired"
        inputs: {task: task}
        who: [{role: clerk}]
        refuse:
          - when: "not task.open"
            reason: "expired"
        returns: "task.count"
      look_at:
        is: "looks at a task while it is open"
        inputs: {task: task}
        who: [{role: clerk, when: "task.open"}]
        returns: "task.count"
    examples:
""")

EXPIRES = """\
      "a task expires at ten":
        starts_at: "2026-10-05 09:00"
""" + GIVEN + """\
        steps:
          - when: {actor: ann, call: "work_on(t)"}
            then: [DONE]
          - when: {actor: ann, call: "work_on(t)", at: "2026-10-05 11:00"}
            then: [{refused: "expired"}]
"""

LOOKS = """\
      "a task is looked at from the start":
        starts_at: "2026-10-05 09:00"
""" + GIVEN + """\
        steps:
          - when: {actor: ann, call: "look_at(t)"}
            then: [DONE, "RESULT == 1"]
          - when: {actor: ann, call: "stamp(t)"}
            then: [DONE]
"""


class BoundTimeTest(Clocked):
    """a bound property that reads the binding's clock is judged at the
    step's time: the binding hears the start before the givens are made
    and the first permission, and each at: before that step's call is
    judged (Astra round 95)"""

    def setUp(self):
        super().setUp()
        seen, self.made_at = self.seen, []
        ten = datetime.datetime(2026, 10, 5, 10, 0)

        class Expiring(binding.Thing):
            @property
            def open(self):
                return not seen or seen[-1] < ten     # a binding not yet told is at no time past ten

        def task_at(name, values, workdir):
            self.made_at.append(seen[-1] if seen else None)     # making a task reads the time
            return Expiring("task", values)
        binding.ENTITIES["task"] = task_at
        def work_on(actor, t):
            if not t.open:
                raise binding.Refused("expired")
            return t.count
        binding.OPERATIONS.update(work_on=work_on, look_at=lambda actor, t: t.count)

    def tearDown(self):
        del binding.OPERATIONS["work_on"], binding.OPERATIONS["look_at"]
        super().tearDown()

    def test_a_refusal_at_eleven_is_judged_at_eleven(self):
        self.project(EXPIRES, spec=EXPIRY)
        self.assertEqual(self.problems(), ([], []))
        self.assertEqual(self.run_story(), ("examples passed", "all 1", []))
        self.assertEqual([check.clock_words(t) for t in self.seen], ["2026-10-05 09:00", "2026-10-05 11:00"])

    def test_the_start_is_heard_before_the_givens_and_the_first_permission(self):
        self.project(LOOKS, spec=EXPIRY)
        self.assertEqual(self.problems(), ([], []))
        self.assertEqual(self.run_story(), ("examples passed", "all 1", []))
        self.assertEqual([t and check.clock_words(t) for t in self.made_at], ["2026-10-05 09:00"])


class FrameRuleClockTest(Clocked):
    """the clock is found wherever the runner reads it: a computed property
    the frame rule reads through also_changes counts"""

    def test_a_clock_read_through_also_changes_needs_a_start(self):
        self.project(BUMP, spec=FRAME)
        self.assertEqual(self.problems()[0], [(
            "no_clock_start", 'example "bumping reads the clock through the frame rule" uses time '
                              "(reads task.expired, which reads the clock) but has no start; "
                              "give it starts_at: or the project clock_start:")])
        self.project(BUMP, 'clock_start: "2026-10-05 09:00"\n', spec=FRAME)
        self.assertEqual(self.problems(), ([], []))
        self.assertEqual(self.run_story(), ("examples passed", "all 1", []))

    def test_generated_cases_skip_it_without_a_start(self):
        self.project(NO_TIME, "generated_cases: {on: true, runs: 10, steps: 3}\n", spec=FRAME)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            run.main(["--root", self.root.name, "--seed", "3"])
        line = next(x for x in out.getvalue().splitlines() if "generated cases" in x)
        self.assertIn("; skipped bump: no clock start", line)

    def test_a_clock_read_the_checker_missed_is_edda_failing(self):
        self.project(BUMP, spec=FRAME)
        out = io.StringIO()
        with mock.patch.object(check, "time_uses", return_value=[]), contextlib.redirect_stdout(out):
            code = run.main(["--root", self.root.name])
        self.assertEqual(code, 3)
        self.assertEqual(out.getvalue().strip(), "edda failed: NOW was read, but the example has no clock: "
                                                 "the runner read the clock without a start")


class FoldTest(Clocked):
    """the two 02:30s of Oslo's doubled hour are two moments everywhere"""

    OSLO = "Europe/Oslo"
    FIRST = datetime.datetime(2026, 10, 25, 2, 30)
    SECOND = FIRST.replace(fold=1)

    def setUp(self):
        super().setUp()
        self.zone, run.ZONE[0] = run.ZONE[0], self.OSLO

    def tearDown(self):
        run.ZONE[0] = self.zone
        super().tearDown()

    def test_folded_times_are_unequal_by_every_comparison(self):
        import ast
        a, b = self.FIRST, self.SECOND
        self.assertFalse(run.compare(ast.Eq(), a, b))
        self.assertTrue(run.compare(ast.NotEq(), a, b))
        self.assertTrue(run.compare(ast.Lt(), a, b))
        self.assertFalse(run.compare(ast.In(), a, [b]))
        self.assertTrue(run.compare(ast.NotIn(), a, [b]))
        self.assertTrue(run.compare(ast.In(), b, [a, b]))
        self.assertFalse(run.compare(ast.Eq(), [a], [b]))
        self.assertTrue(run.compare(ast.Eq(), [[b]], [[b]]))
        self.assertFalse(run.same(a, b))
        self.assertFalse(run.same([a], [b]))
        self.assertTrue(run.same(b, b.replace()))

    def test_the_frame_rule_catches_a_one_hour_change(self):
        def later(actor, t):
            t.stamped = t.stamped.replace(fold=1)     # an hour later, the same wall clock
            return t.count
        binding.OPERATIONS["count_of"] = later
        self.project(NO_TIME.replace("- task: t", '- task: t\n            with: {stamped: "2026-10-25 02:30"}'),
                     "zone: Europe/Oslo\n")
        status, _, failed = self.run_story()
        self.assertEqual(status, "failing")
        self.assertEqual([found for _, _, found in failed[0][1]],
                         ["count_of changed t.stamped, which the spec does not name"])

    def test_a_zero_shift_is_the_identity(self):
        for unit in ("DAYS", "HOURS", "MINUTES"):
            moved = check.shift(self.SECOND, unit, 0, self.OSLO)
            self.assertEqual((moved, moved.fold), (self.SECOND, 1), unit)
        moved = check.shift(self.SECOND, "DAYS", 1, self.OSLO)     # a real move keeps the wall clock, fold=0
        self.assertEqual((moved, moved.fold), (datetime.datetime(2026, 10, 26, 2, 30), 0))

    def test_a_zero_day_at_is_never_backwards(self):
        examples = """\
      "the second 02:30 stays":
        starts_at: "2026-10-25 01:30"
""" + GIVEN + """\
        steps:
          - when: {actor: ann, call: "stamp(t)", at: "NOW + HOURS(2)"}
            then: [DONE, "t.stamped == NOW"]
          - when: {actor: ann, call: "stamp(t)", at: "NOW + DAYS(0)"}
            then: [DONE, "t.stamped == NOW", "t.stamped != TIME(\\"2026-10-25 02:30\\")"]
"""
        self.project(examples, "zone: Europe/Oslo\n")
        self.assertEqual(self.problems(), ([], []))
        self.assertEqual(self.run_story(), ("examples passed", "all 1", []))
        self.assertEqual([t.fold for t in self.seen], [0, 1, 1])     # the start, then each at:


class BackwardsTest(Clocked):

    def test_a_broken_rule_inside_an_at_is_that_examples_failure(self):
        def counted(actor, t):
            t.count += 1        # a read that changes what it reads
            return 1
        binding.OPERATIONS["count_of"] = counted
        self.project(MOVES.replace('at: "NOW + DAYS(1)"', 'at: "NOW + DAYS(count_of(t))"'))
        self.assertEqual(self.problems(), ([], []))
        status, detail, failed = self.run_story()
        self.assertEqual((status, detail), ("failing", "1 of 1 examples failed"))
        self.assertEqual([found for _, _, found in failed[0][1]],
                         ["count_of changed t.count, which the spec does not name"])


    def test_an_at_the_checker_can_tell_is_earlier_is_refused(self):
        self.project(MOVES.replace('at: "NOW + DAYS(1)"', 'at: "NOW - DAYS(2)"'))
        self.assertEqual(self.problems()[0], [(
            "clock_backwards",
            "at NOW - DAYS(2) (2026-10-04 10:00) is before the clock's 2026-10-06 10:00; time never goes backwards")])
        self.project(MOVES.replace('at: "2026-10-06 10:00"', 'at: "2026-10-04"'))
        self.assertEqual(self.problems()[0], [(
            "clock_backwards", "at 2026-10-04 is before the clock's 2026-10-05 09:00; time never goes backwards")])

    def test_an_at_the_checker_cannot_tell_fails_the_example_at_its_line(self):
        self.project(MOVES.replace('at: "NOW + DAYS(1)"', 'at: "NOW - DAYS(t.count + 1)"'))
        self.assertEqual(self.problems(), ([], []))
        status, detail, failed = self.run_story()
        self.assertEqual((status, detail), ("failing", "1 of 1 examples failed"))
        (where, text, found), = failed[0][1]
        with open(os.path.join(self.specs, "task.edda")) as f:
            line = next(i for i, x in enumerate(f, 1) if "t.count + 1" in x)
        self.assertEqual((where.rsplit(":", 1)[1], text, found), (
            str(line), None, "at NOW - DAYS(t.count + 1) (2026-10-04 10:00) is before the clock's 2026-10-06 10:00; "
                        "time never goes backwards"))


AT_COUNT = """\
      "the clock moves by a count":
        starts_at: "2026-10-05 09:00"
""" + GIVEN + """\
        steps:
          - when: {actor: ann, call: "stamp(t)", at: "NOW + DAYS(count_of(t))"}
            then: [DONE]
"""

DOUBLE = SPEC.replace("""    examples:
""", """      double_count:
        is: "twice what a task counts"
        inputs: {task: task}
        who: [{role: clerk}]
        refuse:
          - when: "count_of(task) > 5"
            reason: "too many"
        returns: "task.count * 2"
    examples:
""")

DOUBLED = """\
      "a then fact reads through a read":
        starts_at: "2026-10-05 09:00"
""" + GIVEN + """\
        steps:
          - when: {actor: ann, call: "stamp(t)"}
            then: [DONE, "double_count(t) == 2"]
"""

FRAME_TODAY = FRAME.replace('expired: {computed: "stamped < NOW"}', 'expired: {computed: "stamped < today()"}')


class UnboundTest(Clocked):
    """an operation with no binding, wherever the runner would evaluate it
    (check.evaluated, and through it run.operations_run), keeps the
    story from running: not run, no binding for it, never a failing
    example (Astra round 96)"""

    def tearDown(self):
        for name in ("stamp", "today", "count_of", "bump"):
            binding.OPERATIONS.setdefault(name, None)
        binding.OPERATIONS.pop("double_count", None)
        super().tearDown()

    def test_an_unbound_read_inside_an_at(self):
        del binding.OPERATIONS["count_of"]
        self.project(AT_COUNT)
        self.assertEqual(self.problems(), ([], []))
        self.assertEqual(self.run_story(), ("not run", "no binding for count_of", []))

    def test_one_the_runner_meets_anyway_is_not_run_too(self):
        del binding.OPERATIONS["count_of"]
        self.project(AT_COUNT)
        with mock.patch.object(run, "needs", return_value=None):
            self.assertEqual(self.run_story(), ("not run", "no binding for count_of", []))

    def test_an_unbound_read_inside_a_read_a_then_fact_calls(self):
        del binding.OPERATIONS["count_of"]
        binding.OPERATIONS["double_count"] = lambda actor, t: t.count * 2
        self.project(DOUBLED, spec=DOUBLE)
        self.assertEqual(self.problems(), ([], []))
        self.assertEqual(self.run_story(), ("not run", "no binding for count_of", []))

    def test_an_unbound_read_inside_a_computed_property_also_changes_names(self):
        del binding.OPERATIONS["today"]
        self.project(BUMP, 'clock_start: "2026-10-05 09:00"\n', spec=FRAME_TODAY)
        self.assertEqual(self.problems(), ([], []))
        self.assertEqual(self.run_story(), ("not run", "no binding for today", []))

    def test_generated_cases_skip_it(self):
        del binding.OPERATIONS["today"]
        self.project(NO_TIME, 'generated_cases: {on: true, runs: 10, steps: 3}\nclock_start: "2026-10-05 09:00"\n',
                     spec=FRAME_TODAY)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            run.main(["--root", self.root.name, "--seed", "3"])
        line = next(x for x in out.getvalue().splitlines() if "generated cases" in x)
        self.assertIn("skipped bump: no binding for today", line)


class DurationTest(Clocked):

    def test_days_keep_the_wall_clock_across_daylight_saving_and_hours_do_not(self):
        oslo = "Europe/Oslo"        # summer time begins 2026-03-29 02:00
        start = datetime.datetime(2026, 3, 28, 9, 0)
        self.assertEqual(check.shift(start, "DAYS", 1, oslo), datetime.datetime(2026, 3, 29, 9, 0))
        self.assertEqual(check.shift(start, "HOURS", 24, oslo), datetime.datetime(2026, 3, 29, 10, 0))
        self.assertEqual(check.shift(start, "MINUTES", 90, oslo), datetime.datetime(2026, 3, 28, 10, 30))
        self.assertEqual(check.shift(start, "DAYS", 1, "UTC"), check.shift(start, "HOURS", 24, "UTC"))
        gap = datetime.datetime(2026, 3, 28, 2, 30)      # the day after, 02:30 does not exist
        self.assertEqual(check.shift(gap, "DAYS", 1, oslo), datetime.datetime(2026, 3, 29, 3, 30))
        doubled = datetime.datetime(2026, 10, 25, 1, 30)  # winter time: 02:00 to 03:00 happens twice
        first = check.shift(doubled, "HOURS", 1, oslo)
        second = check.shift(first, "HOURS", 1, oslo)
        self.assertEqual((first, first.fold, second, second.fold),
                         (datetime.datetime(2026, 10, 25, 2, 30), 0, datetime.datetime(2026, 10, 25, 2, 30), 1))
        self.assertLess(check.instant(first, oslo), check.instant(second, oslo))

    def test_days_and_hours_in_an_example_in_a_named_zone(self):
        examples = """\
      "a day after":
        starts_at: "2026-03-28 09:00"
""" + GIVEN + """\
        steps:
          - when: {actor: ann, call: "stamp(t)", at: "NOW + DAYS(1)"}
            then: [DONE, "t.stamped == TIME(\\"2026-03-29 09:00\\")"]
      "24 hours after":
        starts_at: "2026-03-28 09:00"
""" + GIVEN + """\
        steps:
          - when: {actor: ann, call: "stamp(t)", at: "NOW + HOURS(24)"}
            then: [DONE, "t.stamped == TIME(\\"2026-03-29 10:00\\")"]
"""
        self.project(examples, "zone: Europe/Oslo\n")
        self.assertEqual(self.problems(), ([], []))
        self.assertEqual(self.run_story(), ("examples passed", "all 2", []))

    def test_a_duration_anywhere_else_is_refused(self):
        P = check.project_of(self.specs)
        scope = {"due": "TIME", "n": "INTEGER", "x": "NUMBER"}

        def said(text):
            c = check.Expr(P, scope)
            c.run(text)
            return c.out
        for ok in ("due + DAYS(1)", "NOW - HOURS(n)", "NOW + DAYS(1) + MINUTES(-5)", "due < NOW + DAYS(n * 2)"):
            self.assertEqual(said(ok), [], ok)
        moves = "expects to move a time, as TIME + {0}(n) or TIME - {0}(n): {1}"
        self.assertEqual(said("DAYS(1) == NOW"), [("type_mismatch", "DAYS " + moves.format("DAYS", "DAYS(1) == NOW"))])
        self.assertEqual(said("DAYS(1) + NOW"), [("type_mismatch", "DAYS " + moves.format("DAYS", "DAYS(1) + NOW"))])
        self.assertEqual(said("n + HOURS(1)"), [("type_mismatch", "HOURS " + moves.format("HOURS", "n + HOURS(1)"))])
        self.assertEqual(said("NOW * MINUTES(1)"),
                         [("type_mismatch", "MINUTES " + moves.format("MINUTES", "NOW * MINUTES(1)"))])
        self.assertEqual(said("NOW + DAYS(x)"), [("type_mismatch", "DAYS expects one INTEGER: NOW + DAYS(x)")])
        self.assertEqual(said("NOW + DAYS(1, 2)"), [("type_mismatch", "DAYS expects one INTEGER: NOW + DAYS(1, 2)")])

    def test_an_at_whose_time_is_not_now_is_refused(self):
        for at in ("TODAY + DAYS(1)", 'TIME(\\"2026-10-09\\")', "NOW + 1", "tomorrow", "t.stamped + DAYS(1)"):
            self.project(MOVES.replace('at: "NOW + DAYS(1)"', f'at: "{at}"'))
            rules = [rule for rule, _ in self.problems()[0]]
            self.assertTrue(rules and set(rules) <= {"type_mismatch", "unknown_name"}, (at, self.problems()))

    def test_the_analyser_keeps_skipping_time_conditions(self):
        self.project(MOVES.replace('      stamp:\n        is: "stamps a task with the time"\n'
                                   '        inputs: {task: task}\n        who: [{role: clerk}]\n',
                                   '      stamp:\n        is: "stamps a task with the time"\n'
                                   '        inputs: {task: task}\n        who: [{role: clerk}]\n'
                                   '        refuse:\n          - when: "task.stamped > NOW + DAYS(1)"\n'
                                   '            reason: "stamped ahead"\n'
                                   '          - when: "task.stamped > NOW + DAYS(2)"\n'
                                   '            reason: "stamped far ahead"\n'))
        self.assertEqual(self.problems(), ([], []))


class ViewTest(Clocked):

    def test_the_read_view_shows_each_steps_resolved_time(self):
        self.project(MOVES)
        m = check.model_of(self.specs)
        st = m["stories"][0]
        whens = [s["text"] for s in view.story_sentences(st, m["operations"], m["entities"], m["roles"])
                 if s["kind"] == "when"]
        self.assertEqual(whens, [
            "When ann asks to stamp t, at 2026-10-05 09:00 (the start).",
            "When ann asks to stamp t, at 2026-10-06 10:00 (start + 1 day 1 hour).",
            "When ann asks to stamp t, at 2026-10-07 10:00 (start + 2 days 1 hour).",
            "When ann asks to stamp t, at 2026-10-07 12:30 (start + 2 days 3 hours 30 minutes).",
            "When ann asks to count of t, at 2026-10-07 12:30 (start + 2 days 3 hours 30 minutes)."])
        self.assertEqual(st["examples"][0]["clock"], {"start": "2026-10-05 09:00", "zone": "UTC"})

    def test_a_time_known_only_when_it_runs_says_so(self):
        self.project(MOVES.replace('at: "NOW + DAYS(1)"', 'at: "NOW + DAYS(t.count)"'))
        m = check.model_of(self.specs)
        whens = [s["text"] for s in view.story_sentences(m["stories"][0], m["operations"], m["entities"], m["roles"])
                 if s["kind"] == "when"]
        self.assertEqual(whens[2], "When ann asks to stamp t, at NOW + DAYS(t.count) (known when it runs).")
        self.assertEqual(whens[4], "When ann asks to count of t, at a time (known when it runs).")

    def test_an_example_that_uses_no_time_shows_none(self):
        self.project(NO_TIME)
        m = check.model_of(self.specs)
        self.assertIsNone(m["stories"][0]["examples"][0]["clock"])
        whens = [s["text"] for s in view.story_sentences(m["stories"][0], m["operations"], m["entities"], m["roles"])
                 if s["kind"] == "when"]
        self.assertEqual(whens, ["When ann asks to count of t."])


class GeneratedTest(Clocked):

    def generated(self, settings_text):
        self.project(MOVES, "generated_cases: {on: true, runs: 10, steps: 3}\n" + settings_text)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = run.main(["--root", self.root.name, "--seed", "3"])
        return code, out.getvalue().splitlines()[1]

    def test_with_a_clock_start_operations_that_read_the_clock_run_on_it(self):
        self.seen.clear()
        code, line = self.generated('clock_start: "2026-10-01 09:00"\n')
        self.assertEqual(code, 0)
        self.assertRegex(line, r"^CLK-001: generated cases: 10 runs passed; calls: .*stamp \d+")
        self.assertNotIn("skipped stamp", line)
        told = [t and check.clock_words(t) for t in self.seen[4:]]  # after the example's start and three at:
        self.assertEqual(told, ["2026-10-01 09:00", None])         # the generated runs' start, then no clock

    def test_without_one_they_are_skipped(self):
        code, line = self.generated("")
        self.assertEqual(code, 0)
        self.assertIn("; skipped stamp: no clock start; skipped today: no clock start", line)
        self.assertIn("calls: count_of", line)


class MachineClockTest(Clocked):

    def test_nothing_reads_the_machines_clock(self):
        real = datetime.datetime

        def read(*a, **k):
            raise AssertionError("the machine's clock was read")

        class Meta(type):
            def __instancecheck__(cls, x):
                return isinstance(x, real)

        class NoClock(real, metaclass=Meta):
            now = classmethod(read)
            utcnow = classmethod(read)
            today = classmethod(read)
        self.project(MOVES)
        with mock.patch("datetime.datetime", NoClock), mock.patch("time.time", read), \
                mock.patch("time.time_ns", read), mock.patch("time.localtime", read):
            found = self.run_story()
        self.assertEqual(found, ("examples passed", "all 1", []))
        self.assertIs(time.time, time.time)     # patched back


class SettingsTest(unittest.TestCase):

    def refused(self, text):
        with tempfile.TemporaryDirectory() as root:
            with open(os.path.join(root, "edda.yaml"), "w") as f:
                f.write(text)
            os.mkdir(os.path.join(root, "specs"))
            try:
                settings.read(root)
            except settings.Refused as r:
                return [line.split(": ", 1)[1] for line in r.lines]
            return []

    def test_zone_and_clock_start_are_checked(self):
        self.assertEqual(self.refused("zone: Europe/Oslo\nclock_start: \"2026-10-01 09:00\"\n"), [])
        self.assertEqual(self.refused("zone: Mars/Olympus\n"),
                         ["wrong_type: zone must be a time zone name, such as Europe/Oslo: Mars/Olympus"])
        self.assertEqual(self.refused("clock_start: \"2026-02-30\"\n"),
                         ['wrong_type: clock_start must be a time, "YYYY-MM-DD HH:MM" or "YYYY-MM-DD": 2026-02-30'])

    def test_the_defaults(self):
        s = settings.read()
        self.assertEqual((s.zone, s.clock_start), ("UTC", "2026-10-01 09:00"))     # Edda's own
        with tempfile.TemporaryDirectory() as root:
            os.mkdir(os.path.join(root, "specs"))
            self.assertEqual(settings.read(root).clock, (None, "UTC"))


if __name__ == "__main__":
    unittest.main()
