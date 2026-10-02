#!/usr/bin/env python3
"""Generate Edda's fixtures (revision 26) from one clean spec and print
the expected lines, counts and strings the stories assert."""
import json, os, re, shutil, sys

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fixtures")

CLEAN = """\
# A fixture is one whole spec in one file. Line numbers matter: the
# examples in specs/spec_file.edda name them.
roles:
  shop_user:
    is: "a person at a shop"

entities:
  order:
    is: "what a workshop buys"
    properties:
      status: DEFAULT incoming | removed
      units_sent: DEFAULT 0
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
        is: "takes an unsent order off the list"
        inputs: {order: order}
        who: [{role: shop_user}]
        refuse:
          - when: "order.status == removed"
            reason: "already removed"
          - when: "order.units_sent > 0"
            reason: "already sent"
        ensure:
          - "order.status == removed"
    examples:
      "a fresh order is removed":
        given:
          - actor: erik
            with: {roles: [shop_user]}
          - order: purchase
            with: {status: incoming, units_sent: 0}
        steps:
          - when: {actor: erik, call: "remove(purchase)"}
            then: [DONE, "purchase.status == removed"]
      "a sent order is not removed":
        given:
          - actor: erik
            with: {roles: [shop_user]}
          - order: shipped
            with: {status: incoming, units_sent: 2}
        steps:
          - when: {actor: erik, call: "remove(shipped)"}
            then: [{refused: "already sent"}, "shipped.status == incoming"]
      "a removed order is not removed again":
        given:
          - actor: erik
            with: {roles: [shop_user]}
          - order: purchase
            with: {status: incoming, units_sent: 0}
        steps:
          - when: {actor: erik, call: "remove(purchase)"}
            then: [DONE]
          - when: {actor: erik, call: "remove(purchase)"}
            then: [{refused: "already removed"}, "purchase.status == removed"]
"""

L = CLEAN.splitlines()
EXPECT = {}


def find(lines, text, start=0):
    for i in range(start, len(lines)):
        if text in lines[i]:
            return i
    raise KeyError(text)


def write(folder, name, text):
    d = os.path.join(ROOT, folder)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, name), "w") as f:
        f.write(text)


def edit(folder, fn, bad_text=None, file="order.edda"):
    lines = list(L)
    line = fn(lines)
    write(folder, file, "\n".join(lines) + "\n")
    if line is not None:
        EXPECT[folder] = {"line": line + 1}
    return lines


# --- normalisation and .vc ---------------------------------------------

def strip_comment(s):
    out, q = [], False
    i = 0
    while i < len(s):
        c = s[i]
        if c == '"' and (i == 0 or s[i - 1] != "\\"):
            q = not q
        if c == "#" and not q and (i == 0 or s[i - 1] == " "):
            break
        out.append(c)
        i += 1
    return "".join(out).rstrip()


def block(lines, key_line_text):
    """lines of the block whose key line contains key_line_text, from the
    key line to the last line indented deeper than it; normalised."""
    start = find(lines, key_line_text)
    indent = len(lines[start]) - len(lines[start].lstrip())
    out = [lines[start]]
    for s in lines[start + 1:]:
        t = strip_comment(s)
        if t.strip() == "":
            if s.strip() == "" or s.strip().startswith("#"):
                continue
        ind = len(s) - len(s.lstrip())
        if s.strip() and ind <= indent:
            break
        out.append(s)
    norm = []
    for s in out:
        t = strip_comment(s)
        if t.strip() == "":
            continue
        norm.append(t[indent:])
    return norm


def vc_entry(kind, name, number, at, by, text_lines, because=None, pins=None):
    e = [f"- {kind}: {name}", f"  number: {number}",
         f'  approved_at: "{at}"', f"  approved_by: {by}"]
    if because:
        e.append(f'  because: "{because}"')
    if pins is not None:
        e.append("  pins: [" + ", ".join(
            "{%s: %s, number: %d}" % p for p in pins) + "]")
    e.append("  text: |")
    e += ["    " + t for t in text_lines]
    return "\n".join(e) + "\n"


def lcs_changes(old, new):
    """changes between old and new line lists, by the reference's rule"""
    n, m = len(old), len(new)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            if old[i] == new[j]:
                dp[i][j] = dp[i + 1][j + 1] + 1
            else:
                dp[i][j] = max(dp[i + 1][j], dp[i][j + 1])
    i = j = 0
    changes = []
    while i < n or j < m:
        if i < n and j < m and old[i] == new[j]:
            i += 1; j += 1
        elif i < n and (j >= m or dp[i + 1][j] >= dp[i][j + 1]):
            changes.append({"kind": "removed", "line": j + 1, "sentence": old[i]}); i += 1
        else:
            changes.append({"kind": "added", "line": j + 1, "sentence": new[j]}); j += 1
    return changes


# --- the clean fixture ---------------------------------------------------
shutil.rmtree(ROOT, ignore_errors=True)
write("order", "order.edda", CLEAN)
ROLE_V1 = block(L, "shop_user:")
ORDER_V1 = block(L, "  order:")
STORY_V1 = block(L, "FIX-001:")
EXPECT["order"] = {"story_lines": len(STORY_V1)}
AT = "2026-09-28 10:00"

# --- refusals ------------------------------------------------------------

def unknown_key(ls):
    i = find(ls, "        ensure:"); ls[i] = "        ensures:"; return i
edit("unknown_key", unknown_key)

def unknown_name(ls):
    i = find(ls, 'when: "order.units_sent > 0"'); ls[i] = ls[i].replace("units_sent", "units_sold"); return i
edit("unknown_name", unknown_name)

def not_an_expression(ls):
    i = find(ls, '          - "order.status == removed"'); ls[i] = '          - "set the order status to removed"'; return i
edit("not_an_expression", not_an_expression)

def declared_twice(ls):
    i = find(ls, "      units_sent: DEFAULT 0"); ls.insert(i + 1, "      units_sent: DEFAULT 1"); return i + 1
edit("declared_twice", declared_twice)

def unknown_status(ls):
    i = find(ls, 'when: "order.status == removed"'); ls[i] = ls[i].replace("removed", "archived"); return i
edit("unknown_status", unknown_status)

def returns_and_ensure(ls):
    i = find(ls, "        ensure:"); ls.insert(i, '        returns: "order"'); return find(ls, "      remove:")
edit("returns_and_ensure", returns_and_ensure)

def wrong_file(ls):
    return find(ls, "  FIX-001:")
edit("wrong_file", wrong_file, file="stock.edda")

def not_a_list(ls):
    i = find(ls, "        ensure:"); ls[i] = '        ensure: "order.status == removed"'; del ls[i + 1]; return i
edit("not_a_list", not_a_list)

def unquoted_text(ls):
    i = find(ls, 'reason: "already sent"'); ls[i] = ls[i].replace('"already sent"', "already sent"); return i
edit("unquoted_text", unquoted_text)

def yaml_feature(ls):
    i = find(ls, "with: {roles: [shop_user]}"); ls[i] = ls[i].replace("with: {", "with: &who {")
    j = find(ls, "with: {roles: [shop_user]}", i + 1); ls[j] = ls[j].replace("with: {roles: [shop_user]}", "with: *who")
    return i
edit("yaml_feature", yaml_feature)

def missing_key(ls):
    i = find(ls, '        is: "takes an unsent order off the list"'); del ls[i]; return find(ls, "      remove:")
edit("missing_key", missing_key)

def wrong_type(ls):
    i = find(ls, "        inputs: {order: order}"); ls[i] = "        inputs: [order]"; return i
edit("wrong_type", wrong_type)

def bad_type_phrase(ls):
    i = find(ls, "      units_sent: DEFAULT 0"); ls[i] = "      units_sent: DEFAULT 0 NUMBER"; return i
edit("bad_type_phrase", bad_type_phrase)

def not_ordered(ls):
    i = find(ls, "entities:")
    ls[i + 1:i + 1] = ["  line:", '    is: "one row of an order"', "    properties:",
                       "      units: DEFAULT 0", ""]
    j = find(ls, "      units_sent: DEFAULT 0"); ls.insert(j + 1, "      lines: MANY line")
    k = find(ls, "    examples:")
    ls[k:k] = ["      open_lines:", '        is: "lists the rows of an order"',
               "        inputs: {order: order}", '        who: [{role: shop_user}]',
               '        returns: "order.lines"']
    e = find(ls, '      "a removed order is not removed again":')
    tail = ['      "the first row is read":', "        given:", "          - actor: erik",
            "            with: {roles: [shop_user]}", "          - line: row",
            "            with: {units: 0}", "          - order: purchase",
            "            with: {status: incoming, lines: [row]}", "        steps:",
            '          - when: {actor: erik, call: "open_lines(purchase)"}',
            '            then: [DONE, "RESULT[0].units == 0"]']
    ls += tail
    return len(ls) - 1
edit("not_ordered", not_ordered)

def role_cycle(ls):
    i = find(ls, '    is: "a person at a shop"')
    ls[i + 1:i + 1] = ["    includes: [admin]", "  admin:", '    is: "a person who runs the shop"',
                       "    includes: [shop_user]"]
    return i + 1
edit("role_cycle", role_cycle)

# bad_version: approved file whose history numbers the entity 2 first
edit("bad_version", lambda ls: None)
vc = vc_entry("role", "shop_user", 1, AT, "tuan", ROLE_V1)
vc += vc_entry("entity", "order", 2, AT, "tuan", ORDER_V1)
write("bad_version", "order.edda.vc", vc)
EXPECT["bad_version"] = {"line": vc.splitlines().index("  number: 2") + 1}

# --- flags ---------------------------------------------------------------

def unreachable_status(ls):
    i = find(ls, "      status: DEFAULT incoming | removed"); ls[i] = "      status: DEFAULT incoming | delivered | removed"; return i
edit("unreachable_status", unreachable_status)

def no_example(ls):
    i = find(ls, "    examples:"); del ls[i:]; return find(ls, "  FIX-001:")
edit("no_example", no_example)

def plural_name(ls):
    i = find(ls, "entities:")
    ls[i + 1:i + 1] = ["  line:", '    is: "one row of an order"', "    properties:",
                       "      units: DEFAULT 0", ""]
    j = find(ls, "      units_sent: DEFAULT 0"); ls.insert(j + 1, "      line: MANY line"); return j + 1
edit("plural_name", plural_name)

def about_untouched(ls):
    i = find(ls, "entities:")
    ls[i + 1:i + 1] = ["  shop:", '    is: "a shop that orders"', "    properties:",
                       "      name: TEXT", '    may_update: [{role: shop_user}]', ""]
    s = find(ls, "stories:")
    del ls[s + 1:]
    ls += ["  FIX-002:", '    story: "rename a shop"', "    about: order", "    as_a: shop_user",
           '    i_want: "to rename my shop"', '    so_that: "the name is right"',
           "    operations:", "      rename:", '        is: "gives the shop a new name"',
           "        inputs: {shop: shop, name: TEXT}", '        who: [{role: shop_user}]',
           "        ensure:", '          - "shop.name == name"',
           "    examples:", '      "a shop is renamed":', "        given:",
           "          - actor: erik", "            with: {roles: [shop_user]}",
           "          - shop: butik", '            with: {name: "Butik"}', "        steps:",
           '          - when: {actor: erik, call: "rename(butik, \\"Boden\\")"}',
           '            then: [DONE, "butik.name == \\"Boden\\""]']
    return s + 1
edit("about_untouched", about_untouched)

# --- notes ---------------------------------------------------------------

def notes_a(ls):
    i = find(ls, '    so_that: "the list is clean"')
    ls[i + 1:i + 1] = ["    notes:", '      - "the stock feed is refreshed every night"',
                       "    questions:", '      - "does the shop want to see the refresh time?"']
    j = find(ls, '        is: "takes an unsent order off the list"')
    ls.insert(j + 1, '        notes: ["a removed order keeps its history"]')
    EXPECT["notes_a"] = {"note": i + 3, "question": i + 5, "op_note": j + 2}
    return None
edit("notes_a", notes_a)

STOCK = """\
roles:
  workshop_user:
    is: "a person at the workshop"

entities:
  stock:
    is: "what the workshop has on the shelf"
    properties:
      units: DEFAULT 0
    may_update: [{role: workshop_user}]

stories:
  FIX-002:
    story: "see the stock"
    about: stock
    as_a: workshop_user
    i_want: "to see how many units are on the shelf"
    so_that: "I know what to order"
    notes:
      - "the stock feed is refreshed every night"
      - "a workshop sees stock as of the last refresh"
    operations:
      units_of:
        is: "gives the units on the shelf"
        inputs: {stock: stock}
        who: [{role: workshop_user}]
        returns: "stock.units"
    examples:
      "the units are read":
        given:
          - actor: lena
            with: {roles: [workshop_user]}
          - stock: bolts
            with: {units: 7}
        steps:
          - when: {actor: lena, call: "units_of(bolts)"}
            then: [DONE, "RESULT == 7"]
"""
write("notes_b", "stock.edda", STOCK)
EXPECT["notes_b"] = {"note1": STOCK.splitlines().index('      - "the stock feed is refreshed every night"') + 1,
                     "note2": STOCK.splitlines().index('      - "a workshop sees stock as of the last refresh"') + 1}

# --- histories -----------------------------------------------------------

def hist(blocks_only=False, story_text=None, story_pins=None, extra=""):
    v = vc_entry("role", "shop_user", 1, AT, "tuan", ROLE_V1)
    v += vc_entry("entity", "order", 1, AT, "tuan", ORDER_V1)
    if not blocks_only:
        v += vc_entry("story", "FIX-001", 1, "2026-09-28 10:05", "tuan",
                      story_text or STORY_V1,
                      pins=story_pins or [("role", "shop_user", 1), ("entity", "order", 1)])
    return v + extra

edit("blocks_approved", lambda ls: None)
write("blocks_approved", "order.edda.vc", hist(blocks_only=True))

edit("approved", lambda ls: None)
write("approved", "order.edda.vc", hist())

def approved_question(ls):
    i = find(ls, '    so_that: "the list is clean"')
    ls.insert(i + 1, '    questions: ["may a removed order be restored?"]'); return i + 1
edit("approved_question", approved_question)
write("approved_question", "order.edda.vc", hist())

# block_edited: the entity block was edited after its approval; the story still matches v1
def block_edited(ls):
    i = find(ls, '    is: "what a workshop buys"'); ls[i] = '    is: "what a workshop buys from the shop"'; return None
edit("block_edited", block_edited)
write("block_edited", "order.edda.vc", hist())

# pinned_old: current entity has may_create (v2); story matches v1, pinned to order 1
def pinned_old(ls):
    i = find(ls, '    may_update: [{role: shop_user}]'); ls.insert(i + 1, '    may_create: [{role: shop_user}]'); EXPECT["pinned_old"] = {"story_line": find(ls, "  FIX-001:") + 1}; return None
po = edit("pinned_old", pinned_old)
ORDER_V2 = block(po, "  order:")
write("pinned_old", "order.edda.vc", hist(extra=vc_entry("entity", "order", 2, "2026-10-01 09:00", "tuan", ORDER_V2, because="nobody may delete an order")))

# story_grown: v1 had no "already removed" refusal and no third example
def story_grown(ls):
    return None
sg = edit("story_grown", story_grown)
v1 = [l for l in STORY_V1]
i = v1.index('        - when: "order.status == removed"')
del v1[i:i + 2]
j = v1.index('    "a removed order is not removed again":')
del v1[j:]
write("story_grown", "order.edda.vc", hist(story_text=v1))
ch = lcs_changes(v1, STORY_V1)
EXPECT["story_grown"] = {"changes": ch, "count": len(ch), "v1_lines": len(v1)}

# reason_changed: current reason reworded; v1 is the clean story
def reason_changed(ls):
    i = find(ls, 'reason: "already sent"'); ls[i] = ls[i].replace("already sent", "the order has already been sent"); j = find(ls, 'refused: "already sent"'); ls[j] = ls[j].replace("already sent", "the order has already been sent"); return i
rc = edit("reason_changed", reason_changed)
write("reason_changed", "order.edda.vc", hist())
EXPECT["reason_changed"]["changes"] = lcs_changes(STORY_V1, block(rc, "FIX-001:"))

# relabelled: tags, a note, a comment and a blank line added; v1 is the clean story
def relabelled(ls):
    i = find(ls, '    so_that: "the list is clean"')
    ls[i + 1:i + 1] = ["    tags: [shop]", '    notes: ["the shop asked for undo"]', ""]
    j = find(ls, "      remove:"); ls.insert(j + 1, "        # frees the stock"); return None
rl = edit("relabelled", relabelled)
write("relabelled", "order.edda.vc", hist())
EXPECT["relabelled"] = {"changes": lcs_changes(STORY_V1, block(rl, "FIX-001:"))}

# comment_changed: only a comment added
def comment_changed(ls):
    j = find(ls, "      remove:"); ls.insert(j + 1, "        # frees the held stock"); return None
cc = edit("comment_changed", comment_changed)
write("comment_changed", "order.edda.vc", hist())
EXPECT["comment_changed"] = {"changes": lcs_changes(STORY_V1, block(cc, "FIX-001:"))}

# swapped: v1 had the two refusals in the other order
edit("swapped", lambda ls: None)
v1 = list(STORY_V1)
i = v1.index('        - when: "order.status == removed"')
v1[i:i + 4] = v1[i + 2:i + 4] + v1[i:i + 2]
write("swapped", "order.edda.vc", hist(story_text=v1))
EXPECT["swapped"] = {"changes": lcs_changes(v1, STORY_V1)}

# the never-approved diff
EXPECT["order"]["changes"] = lcs_changes([], STORY_V1)
EXPECT["order"]["story_text"] = STORY_V1
EXPECT["order"]["order_text"] = ORDER_V1
EXPECT["order"]["role_text"] = ROLE_V1

print(json.dumps(EXPECT, indent=1))
