# Edda: language reference

Revision 25, 2 Oct 2026. Replaces revision 24 (kb:9378643). Decisions
behind it: kb:9378274, direction rounds 1 and 2, and the round 2
decisions of 2 Oct 2026. The skeleton is YAML; the words are keys; the
logic is expressions borrowed from Ruby and Python. Everything here is
mirrored by `language/schema.json` (the keys) and `language/keywords.edda`
(the registry: every key and every expression form, with what it means,
why it exists and where it comes from).

## 1. The idea

- **Two levels.** Level 1 states: entities, statuses, who may do what,
  what an operation refuses and what is true after it, stories and
  examples. Level 2 does: ordered steps, in code. Level 1 cannot hold a
  step, because its only places for logic are expressions.
- **Who writes, who reads.** An agent writes level 1 from the customer's
  words. A person reads the read view and approves. The agent builds
  level 2 and the code. The checker decides done.
- **Structure in keys, logic in expressions.** Everything that is
  structure (a request, a given, a fixture, an order, a permission list)
  is a key the schema names. Only conditions, facts and values are
  expressions. Edda invents no expression form: each is taken from an
  existing language with its meaning, Ruby first for what reads well,
  Python for what runs, one source per form so nothing clashes.
- **Checked, not trusted.** Names, links, versions and rules are checked
  against the code on every test run. Nothing the checker cannot read
  counts as a promise.

## 2. Files and the YAML subset

```
specs/
  glossary.edda      roles:
  epics.edda         epics:
  order.edda         entities: order (and its parts), stories: about order
  order.edda.vc      versions of those stories and entity blocks, append-only
  order.links        level 2: business name -> code path, name map
  order.binding      level 2: how examples make, call and read entities
fixtures/
  <name>/order.edda  one whole spec in one folder, checked under its own
                     file name, used by examples through `fixture:`
language/
  reference.md       this file
  schema.json        the keys, JSON Schema 2020-12
  keywords.edda      the registry
```

A `.edda` file is YAML 1.2, core schema, in this subset, which the
checker enforces at the source, before the schema:

- every sentence, reason, description and free text is quoted; an
  unquoted ` #` would silently drop the rest of the line;
- one physical line per expression; a block scalar (`|`) is allowed only
  for a text literal in a `given` and in `.vc`;
- repeated things are sequences (`- `): refusals, ensures, givens,
  always-rules, notes; mapping order is never relied on;
- no anchors, aliases, the `<<` key, tags, directives, complex keys,
  tabs or a second document;
- two-space indentation; keys are snake_case; ids are `ABC-123`;
- `#` starts a comment outside a string; comments carry no rules.

**Placement.** A story carries `about: <entity>` and lives in that
entity's file; the checker refuses it elsewhere and flags an `about`
that disagrees with the entity its first `ensure` changes or its first
input names. A part lives with its owner. One home per story; a story
with two homes is two stories under one epic.

## 3. Roles

```yaml
roles:
  shop_user:
    is: "a person at a shop who orders from the workshop"
    has: {shop: one shop}
  admin:
    is: "a person who runs the system"
    includes: [shop_user]
  agent:
    is: "a program that writes .edda files"
```

| key | means | why |
|---|---|---|
| `roles:` | the kinds of actor, person or program | permissions and stories name roles |
| `is:` | one sentence of description | the read view |
| `has:` | the properties a holder of this role has | `shop_user whose shop is ...` needs a shop |
| `includes:` | every permission line admitting those roles admits this one too, condition included | RBAC's role hierarchy |

An actor holds a set of roles. A request is allowed when any of its
roles passes any permission line, condition included. The permission
refusal reads `"<operation> is not allowed for <the actor's roles>"`.

## 4. Entities

```yaml
entities:
  order:
    is: "what a workshop buys"
    properties:
      shop: one shop
      workshop: one workshop
      lines: many order_line, in order
      status: default incoming | delivered | removed
      wanted_day: time, optional
      message: text, optional
      units_held: {computed: "sum(line's units_held for line in lines)"}
      units_sent: {computed: "sum(line's units_sent for line in lines)"}
    may_change: {status: {incoming: [delivered, removed]}}
    wording: {status: {incoming: {shop_user: "Inkommande", workshop_user: "Beställd"}}}
    always:
      - "units_sent is at most count(lines)"
    while:
      - when: "status is removed"
        holds: "units_held is 0"
    may_create: ["workshop_user"]
    may_read:
      - "shop_user whose shop is the order's shop"
      - "workshop_user whose workshop is the order's workshop while status is not removed"
      - "admin"
    may_update: ["shop_user whose shop is the order's shop", "admin"]
    may_delete: ["nobody"]

  order_line:
    is: "one article on an order"
    part_of: order
    properties:
      article: one article
      units_held: default 0
      units_sent: default 0
```

| key | means | why |
|---|---|---|
| `entities:` | the kinds of business object the system keeps | the glossary; every expression is over declared names |
| `is:` | one sentence of description | the read view |
| `properties:` | name to type phrase, or `{computed: expr}` | the shape the checker and the binding read |
| `part_of:` | this entity belongs to that one | placement and the frame rule follow the owner |
| `may_change:` | per status property, the only allowed changes | a change outside it fails; an unreached status is flagged |
| `wording:` | per value and role, the words shown | the one piece of screen wording kept |
| `always:` | facts that hold after every operation | invariants checked on the suite |
| `while:` | `when` a condition holds, `holds` a fact | state-bound invariants, EARS WHILE |
| `may_create:` `may_read:` `may_update:` `may_delete:` | who may, as a list of who-expressions | the CRUD matrix, default deny |

**Type phrases** (one closed grammar, used for properties and inputs):
`text`, `number`, `time`, `yes_no`, `one <entity>`, `many <entity>`,
`many <entity>, in order`, `a | b | c`, with `default <value>` in
front of the value (`default incoming | delivered`, `default 0`) and
`, optional` after. Anything else is a computed property, written
`{computed: "<expression>"}`; a computed property whose expression is
a condition is yes/no and reads `the order is approved`.

**Who-expressions:** `<role>`, `<role> whose <condition>`, either
followed by `while <condition>`, or `nobody`. `actor` in a condition
is the one asking now.

## 5. Stories

```yaml
epics:
  ORD: "the workshop orders from the shop"

stories:
  FUL-005:
    story: "remove orders from the list"
    about: order
    as_a: shop_user
    i_want: "to remove an order that was never sent"
    so_that: "the list shows only live orders"
    epic: ORD
    tags: [ordering, shop]
    notes: ["the shop asked for undo; no rule yet"]
    questions: ["may a removed order be restored?"]
    operations: ...
    examples: ...
```

| key | means | why |
|---|---|---|
| `epics:` | id to one sentence of intent; no rules | one level above the story, nothing deeper; done when its stories are |
| `stories:` | id to story | the unit of done, review, version and delivery |
| `story:` | the sentence | what the customer said |
| `about:` | the entity it is about | placement, checked |
| `as_a:` | the one role it serves, declared | the read view groups by role |
| `i_want:` `so_that:` | free text | stored and shown; nothing runs on them |
| `epic:` `tags:` | labels | grouping; changeable without a new version |
| `notes:` | what the grammar cannot say; ignored by the checker, grey in the view, collected across files | nothing the customer said is lost; repeated notes are the evidence for a new key |
| `questions:` | the undecided | a warning on a done story, never a block |

The acceptance criteria of a story are its operations and examples.
There is no separate list.

## 6. Operations

```yaml
operations:
  remove:
    inputs: {order: order}
    who: ["shop_user whose shop is the order's shop"]
    refuse:
      - when: "the order's status is removed"
        reason: "the order is already removed"
      - when: "the order's units_sent is more than 0"
        reason: "the order has been sent and cannot be removed"
    ensure:
      - "the order's status is removed"
      - "the order's removed_by is actor"
      - "the order's removed_at is now"
      - "the order's units_held is 0"
    also_changes: ["the order's history"]
    notes: ["the shop calls this Ta bort"]

  open_orders:
    inputs: {shop: shop}
    returns: "[order for order in shop's orders if order's status is incoming]"
    ordered_by: ["wanted_day", "id"]
```

| key | means | why |
|---|---|---|
| `operations:` | name to operation; one thing an actor can ask for | the anchor the code carries |
| `inputs:` | name to type phrase; `"text, optional"` may be omitted in a call | the binding and placement need the types |
| `who:` | list of who-expressions; optional | defaults to the entity's `may_update`, `may_create` or `may_read` |
| `refuse:` | list of `when` condition and `reason`; the first that holds is given | preconditions with a reason tests match |
| `ensure:` | list of facts true after; may use `old(...)` | postconditions |
| `returns:` | the expression a read operation gives back; never with `ensure` | one word for reads and writes, command-query separation |
| `ordered_by:` | list of expressions over one item, ascending, ties keep input order | without it a positional check on the result is refused |
| `also_changes:` | changes the frame rule allows without an `ensure` fact | everything else stays unchanged |

- **Order of checks.** Permission, then refusals in the order written,
  then the operation, then every `ensure`, `always` and `while`.
- **Frame rule.** After an operation, every stored property of every
  declared entity not named in `ensure` or `also_changes` is unchanged;
  computed properties follow; undeclared data is not checked.
- **`old(x)`** is the value of `x` captured after the refusals were
  checked and before the operation changed anything: a deep, frozen
  copy. Allowed only in `ensure`.
- **One at a time.** Operations have the results they would have if
  run one at a time.

## 7. Expressions

Every expression form is borrowed; the source is part of the rule.

| form | means | from |
|---|---|---|
| `the order's status`, `order's status`, `shop's orders` | reach into an entity; chains allowed | Edda |
| `x is v`, `x is not v` | equal, not equal | Edda |
| `x is more than v`, `x is less than v`, `x is at least v`, `x is at most v` | number or time comparison | Edda |
| `x is before v`, `x is after v` | time comparison | Edda |
| `x is between a and b` | inclusive range | Ruby |
| `x is empty`, `x is set` | an optional property has no value, has a value | Ruby |
| `x starts with "t"`, `x is longer than N characters` | text | Ruby |
| `the story is approved`, `fresh is not approved` | a yes/no computed property | Ruby |
| `a and b`, `a or b`, `not a` | combined; `not` first; short-circuit | Python |
| `a if c else b` | conditional; the untaken side is not evaluated | Python |
| `x in list`, `x not in list` | membership | Python |
| `[x for x in list if c]`, `[y for x in xs for y in x's ys]` | filtered and nested lists | Python |
| `sum(e for x in list)`, `count(list)`, `min`, `max`, `any(c for x in list)`, `all(...)` | the six list words | Python |
| `list[0]`, `list[-1]`, `list[1:]` | indexing and slicing; out of range fails the example | Python |
| `+ - * /` | with Python precedence; `+` joins lists into a new list | Python |
| `"text"` with `\n` and `\"`, `"#{x} units"` | text; interpolation only in reasons | Python, Ruby |
| `3`, `2026-10-03 10:00`, `1 hour`, `now`, `today`, `actor`, `result` | literals and the four fixed names; times in the business zone | Edda |
| `old(x)` | the value before the operation | Design by Contract |
| `check(file)` inside an expression | a read operation; never a changing one | Edda |

Nothing else. Percent, rounding, money and date arithmetic are backlog
#2494.

## 8. Examples

```yaml
examples:
  "Ta bort frees held stock":
    given:
      - actor: erik
        roles: [shop_user]
        shop: butik
      - order_line: held
        units_held: 3
        units_sent: 0
      - order: purchase
        shop: butik
        status: incoming
        lines: [held]
    steps:
      - when: {actor: erik, call: "remove(purchase)", at: "2026-10-03 10:00"}
        then:
          - done
          - "purchase's status is removed"
          - "held's units_held is 0"
      - when: {actor: erik, call: "remove(purchase)"}
        then:
          - refused: "the order is already removed"
```

| key | means | why |
|---|---|---|
| `examples:` | name to example; one concrete run | the acceptance criteria that run |
| `given:` | a list of entities or actors to make: `- <entity>: <name>` or `- actor: <name>` with `roles:`, then properties; `fixture:` names a fixture folder | names declared here are used below; the binding makes them; no glue is written |
| `steps:` | a list of `when` and `then`; `when` may be left out to check the given state | a flow is several steps |
| `when:` | `actor`, `call` (the operation with its arguments, Python call form), `at` (optional time) | one fixed shape, keys not words |
| `then:` | a list of `done`, `refused: "<reason>"`, or facts | the checker compares; `result` is what the latest call returned |

After `refused`, `result` has no value; a changing operation returns
nothing. Facts after `refused` check that nothing changed.

## 9. Level 2: links and binding

Unchanged from revision 24. `order.links` holds every path and the
business-to-code name map; the code carries `# FUL-005@3`; the binding
is written once per entity, role and operation; the checker emits one
versioned JSON model of the whole spec, which every binding consumes,
so the write form never ties the spec to one stack.

## 10. Versions and approval

```yaml
# order.edda.vc  (append-only, oldest first)
- entity: order
  number: 2
  approved_at: "2026-10-01 09:00"
  approved_by: tuan
  because: "nobody may delete an order"
  text: |
    ...the entity block as approved...
- story: FUL-005
  number: 3
  approved_at: "2026-10-01 14:00"
  approved_by: tuan
  because: "the shop asked that sent orders cannot be removed"
  against: [{entity: order, number: 2}, {entity: order_line, number: 1}]
  text: |
    ...the whole story as approved...
```

- `.edda` is current; the agent edits it. `.edda.vc` is append-only,
  oldest first; only the person's `edda approve` writes it; the agent is
  denied by a repository guard.
- **Draft.** A story whose operations or examples differ from its newest
  version; an entity block whose lines differ from its newest version.
  Labels, notes, questions, comments and blank lines change freely.
- **Pins.** A story's version records the number of every entity block
  it names. A newer entity version flags the story: "FUL-005 approved
  against order v2, order is now v3". A flag, not a draft; approve the
  story again to clear it.
- **What changed** is computed: every line outside the longest common
  sequence of lines between two versions is added or removed, in line
  order; a moved rule shows as both.
- The version number of a block must equal that story's or entity's
  count so far; the checker refuses the whole file otherwise.
- Git keeps the history of both files; the KB keeps the audit copy.

## 11. The checker

**Refuses** (rule names as the `problem` entity lists them):
`yaml_feature` (anchor, alias, `<<`, tag, directive, complex key, tab,
second document); `unquoted_text`; `not_a_sequence` (a repeated thing
written as a mapping); `unknown_key` (not in the schema); `unknown_name`;
`declared_twice`; `unknown_status`; `returns_and_ensure`; `wrong_file`;
`not_an_expression` (a string that is not in section 7, which is also
how a step is caught); a positional check on an unordered result; a
version number out of sequence in `.vc`.

**Flags:** `unreachable_status`; `no_example`; `approved_against_older`;
a `question` on a done story; code with no story; code behind the spec
or at an unapproved version.

**Collects** every note across files, ordered by text, file name, line.

**Done.** A story is done when, at its approved version: it is not a
draft; no pin is older than its entity; every example passes; the rule
checks pass on the whole suite for its operations; every link resolves
both ways. The checker computes it; the agent never marks it.

**Runs, test only.** Examples through the binding; refusals, ensures,
always, while and the frame rule wrapped round the linked operation
for every test in the suite. Never in production.

## 12. Views

- **Read view.** Generated from the checked tree, never edited:
  sentences in story order, one per rule. "Remove an order. As a shop
  user, I want ..., so that ...". "A shop user may remove an order."
  "If remove is asked for an order whose units sent is more than 0,
  then the system shall refuse it: already sent." "When remove
  succeeds, the system shall leave the order with status removed."
  Examples as given, when, then. Notes in grey, questions after them,
  ids hidden, names read as words, hover shows each key's meaning and
  reason from the registry.
- **Write view.** The YAML with colour.
- **Diff view.** Two versions as added and removed lines.

## 13. Not in this revision

Qualities and infrastructure (#2487), time-triggered operations
(#2486), screens beyond `wording` (#2488), timing and concurrency
(#2489), generated cases (#2490), the analyser (#2491), drafting from
existing code (#2492), story to Plan tasks (#2493), richer calculations
(#2494), tooling (#2495), the KDL skeleton trial (#2512).

## 14. Changes from revision 24

- The skeleton is YAML 1.2 in an enforced subset; keys replace the
  keywords; `story:`, `entity` and every label take a colon; repeated
  things are sequences; ids are keys.
- Structure in keys, logic in expressions: `when: {actor, call, at}`
  replaces `erik asks remove(purchase)`; `given` is `- entity: name`
  with property keys; `fixture:` is a key; `result` is the latest
  call's return; `ordered_by:` is a key.
- Every expression form has a source language; Ruby first for reading,
  Python for what runs; `old(x)` from Design by Contract.
- Roles are kinds of actor, person or program, with `has:` and
  `includes:`; an actor holds a set of roles; admin is listed, never a
  wildcard.
- `about:` on every story; one home, many touched entities.
- `approvals` became `versions`; entity blocks are versioned; story
  versions carry `against:` pins; `.vc` is YAML, oldest first.
- `refuse` is `when`/`reason` pairs; `while` is `when`/`holds`;
  `may change` is a map; wording is `wording:`.
