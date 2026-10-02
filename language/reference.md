# Edda: language reference

Revision 26, 2 Oct 2026. Replaces revision 25 (kb:9378910). Decisions
behind it: kb:9378274, rounds 1 to 3 (entries 1 to 43), and Astra's
round 3 review. The skeleton is YAML; the words are keys; the logic is
expressions borrowed from SQL and Python. Everything here is mirrored
by `language/schema.json` (the keys of a `.edda` file),
`language/vc-schema.json` (the keys of a `.edda.vc` file) and
`language/keywords.edda` (the registry: every key, expression form and
language word, with what it means, why it exists and where it comes
from).

## 1. The idea

- **Two levels.** Level 1 states: entities, statuses, who may do what,
  what an operation refuses and what is true after, stories and
  examples. Level 2 does: ordered steps, in code. Level 1 cannot hold a
  step, because its only places for logic are expressions.
- **Who writes, who reads.** An agent writes level 1 from the customer's
  words. A person reads the read view and approves. The agent builds
  level 2 and the code. The checker decides done.
- **Structure in keys, logic in expressions.** Everything that is
  structure (a request, a given, a fixture, an order, a permission list)
  is a key the schema names. Only conditions, facts and values are
  expressions. Every expression form is borrowed with its meaning: SQL
  for comparison and logic, Python for lists, indexing, arithmetic and
  text, Design by Contract for `OLD`. One source per form; nothing
  clashes; nothing is said two ways.
- **Shape tells words apart.** Language words are UPPERCASE (`AND`,
  `COUNT`, `MANY`, `DONE`); declared names are snake_case; YAML keys are
  snake_case; ids are `ABC-123`. An uppercase word must be in the
  registry; a lowercase word must be declared. No reserved list.
- **Checked, not trusted.** Names, links, versions and rules are checked
  against the code on every test run. Nothing the checker cannot read
  counts as a promise. Comments carry no rules.

## 2. Files and the YAML subset

```
specs/
  glossary.edda      roles:
  glossary.edda.vc   versions of the role blocks, append-only
  epics.edda         epics:
  order.edda         entities: order (and its parts), stories: about order
  order.edda.vc      versions of those stories and entity blocks, append-only
  order.links        level 2: business name -> code path, name map
  order.binding      level 2: how examples make, call and read entities
fixtures/
  <name>/order.edda  one whole spec in one folder, checked under its own
                     file name, used by examples through `fixture:`
  <name>/order.edda.vc   its history, when the fixture has one
language/
  reference.md       this file
  schema.json        the keys of .edda, JSON Schema 2020-12
  vc-schema.json     the keys of .edda.vc
  keywords.edda      the registry
```

A `.edda` file is YAML 1.2, core schema, in this subset, which the
checker enforces at the source, before the schema:

- free text (`is:`, `story:`, `i_want:`, `so_that:`, `reason:`,
  `means:`, notes, questions, example titles) and every expression is
  quoted; names, numbers, ids and language words are plain; an
  unquoted ` #` would silently drop the rest of the line;
- one physical line per expression and per type phrase; a block scalar
  (`|`) is allowed only for `text:` in `.edda.vc`; free text may wrap
  onto further lines as YAML allows;
- repeated things are lists (`- `): refusals, ensures, givens, steps,
  then items, always-rules, notes, questions, who-lists, pins; mapping
  order is never a meaning, but the read view, the diff and `blocks`
  and `stories` indexes keep file order;
- no anchors, aliases, the `<<` key, tags, directives, complex keys,
  tabs or a second document;
- two-space indentation; keys are snake_case except story ids
  (`ABC-123`), epic ids (`ABC`) and example titles (quoted text);
- a duplicate key is `declared_twice` at the second key;
- `#` starts a comment outside a string; comments carry no rules, are
  invisible to the views and ignored by the version comparison.

**Placement.** A story carries `about: <entity>` and lives in that
entity's file (`wrong_file` otherwise). `about` is authoritative; the
checker only flags `about_untouched` when the story names that entity
nowhere else (no input, given, fact or who-line). A part lives with its
owner. One home per story; a story with two homes is two stories under
one epic.

## 3. Roles

```yaml
roles:
  shop_user:
    is: "a person at a shop who orders from the workshop"
    has: {shop: shop}
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
| `has:` | the properties a holder of this role has, as type phrases | `shop_user WHOSE shop = order.shop` needs a shop |
| `includes:` | every permission line admitting those roles admits this one too, condition included; a cycle is `role_cycle` | RBAC's role hierarchy |

An actor holds a set of roles. A request is allowed when any of its
roles passes any permission line, condition included. The permission
refusal reads `"<operation> is not allowed for <roles>"`, roles in the
order the actor's `roles:` lists them. `ACTOR` is the one asking: it has
`name` (its given name, text), `roles` (list of role names) and the
`has:` properties of its roles. Role blocks are versioned and pinned
exactly like entity blocks (section 10).

## 4. Entities

```yaml
entities:
  order:
    is: "what a workshop buys"
    properties:
      shop: shop
      workshop: workshop
      lines: MANY order_line, IN ORDER
      status: DEFAULT incoming | delivered | removed
      wanted_day: TIME, OPTIONAL
      message: TEXT, OPTIONAL
      units_held: {computed: "SUM(line.units_held FOR line IN lines)"}
      units_sent: {computed: "SUM(line.units_sent FOR line IN lines)"}
    may_change: {status: {incoming: [delivered, removed]}}
    wording: {status: {incoming: {shop_user: "Inkommande", workshop_user: "Beställd"}}}
    always:
      - "units_sent <= COUNT(lines)"
    while:
      - when: "status = removed"
        holds: "units_held = 0"
    may_create: ["workshop_user"]
    may_read:
      - "shop_user WHOSE shop = order.shop"
      - "workshop_user WHOSE workshop = order.workshop WHILE status != removed"
      - "admin"
    may_update: ["shop_user WHOSE shop = order.shop", "admin"]
    may_delete: ["NOBODY"]

  order_line:
    is: "one article on an order"
    part_of: order
    properties:
      article: article
      units_held: DEFAULT 0
      units_sent: DEFAULT 0
```

| key | means | why |
|---|---|---|
| `entities:` | the kinds of business object the system keeps | the glossary; every expression is over declared names |
| `is:` | one sentence of description | the read view |
| `properties:` | name to type phrase, or `{computed: expr}` | the shape the checker and the binding read |
| `part_of:` | this entity belongs to that one | placement and the frame rule follow the owner |
| `may_change:` | per status property, the only allowed changes | a change outside it fails at run time; an unreached status is flagged |
| `wording:` | per value and role, the words shown | the one piece of screen wording kept |
| `always:` | facts that hold after every operation | invariants checked on the suite |
| `while:` | `when` a condition holds, `holds` a fact | state-bound invariants, EARS WHILE |
| `may_create:` `may_read:` `may_update:` `may_delete:` | who may, as a list of who-expressions | the CRUD matrix, default deny |

**Type phrases**, one closed grammar for properties, `has:` and
`inputs:`:

```
type_phrase := [DEFAULT literal | type] [, OPTIONAL] [, DERIVED]
type        := TEXT | NUMBER | TIME | YES_NO | <entity>
             | MANY <entity> [, IN ORDER] | choice
choice      := name | name | name ...      two or more, distinct, snake_case
literal     := number | "text" | time | YES | NO | name of a choice
```

`DEFAULT` fixes the type from its literal (`DEFAULT 0` is a NUMBER,
`DEFAULT "none"` a TEXT, `DEFAULT NO` a YES_NO, `DEFAULT incoming |
removed` a choice whose first value is the default); the type word is
then not written. `DEFAULT` never goes with a reference, a `MANY` or
`OPTIONAL`. A bare name is a single reference to that entity; a name
that is no entity is `unknown_name`; a single-value choice does not
exist. `, DERIVED` marks a property the checker computes by a rule of
section 11 named `<entity>.<property>`; it cannot be given
(`derived_in_given`). Anything else is `bad_type_phrase`. A computed
property is always `{computed: "<expression>"}`; one whose expression is
a condition is yes/no and is used as a condition (`order.approved`).

**Naming convention, flagged not refused:** a `MANY` property has a
plural name, a single reference a singular one (`plural_name`).

**Who-expressions:** `<role>`, `<role> WHOSE <condition>`, either
followed by `WHILE <condition>`, or `NOBODY` alone. In a `WHOSE`
condition a bare name is the actor's property (from the role's `has:`)
and the entity is reached by its name (`order.shop`); in a `WHILE`
condition a bare name is the entity's property. Permission lines on an
entity speak of the entity; `who:` on an operation speaks of its
inputs.

**Scope of bare names.** Inside `always`, `while` and `computed` a bare
name is the entity's own property; inside an operation it is an input;
inside an example it is a given name; inside `ordered_by` it is a
property of one result item. The entity's own name is not in scope
inside its block except on permission lines. Status values are in scope
wherever their property is compared.

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
| `about:` | the entity it is about | placement, authoritative |
| `as_a:` | the one role it serves, declared | the read view groups by role |
| `i_want:` `so_that:` | free text | stored and shown; nothing runs on them |
| `epic:` `tags:` | labels | grouping; changeable without a new version |
| `notes:` | what the grammar cannot say, on a story, an operation or an example; ignored by the checker, grey in the view, collected across files | nothing the customer said is lost; repeated notes are the evidence for a new key |
| `questions:` | the undecided | a flag on an approved story, never a block |

The acceptance criteria of a story are its operations and examples.
There is no separate list. `examples:` absent or empty is one flag,
`no_example`.

## 6. Operations

```yaml
operations:
  remove:
    is: "takes an unsent order off the list and frees its held stock"
    inputs: {order: order}
    who: ["shop_user WHOSE shop = order.shop"]
    refuse:
      - when: "order.status = removed"
        reason: "the order is already removed"
      - when: "order.units_sent > 0"
        reason: "the order has been sent and cannot be removed"
    ensure:
      - "order.status = removed"
      - "order.removed_by = ACTOR.name"
      - "order.removed_at = NOW"
      - fact: "order.units_held = 0"
        means: "the held stock goes back to the shelf"
    also_changes: ["order.history"]
    notes: ["the shop calls this Ta bort"]

  open_orders:
    is: "lists the orders a shop still waits for"
    inputs: {shop: shop}
    who: ["shop_user WHOSE shop = shop"]
    returns: "[order FOR order IN shop.orders IF order.status = incoming]"
    ordered_by: ["wanted_day", "id"]
```

| key | means | why |
|---|---|---|
| `operations:` | name to operation; one thing an actor can ask for | the anchor the code carries |
| `is:` | one sentence of what it does; required | heads the operation in the read view; its meaning beside the mechanics |
| `inputs:` | name to type phrase; an `, OPTIONAL` input may be omitted in a call and `IS EMPTY` then | the binding and placement need the types |
| `who:` | list of who-expressions; required | no defaults; `wider_than_entity` when it admits a role the `about` entity's matrix never admits |
| `refuse:` | list of `when` condition and `reason`; the first that holds is given | preconditions with a reason tests match |
| `ensure:` | list of facts true after; a fact is a quoted expression or `{fact, means}`; may use `OLD(...)` | postconditions, each with its meaning when the mechanics do not read |
| `returns:` | the expression a read operation gives back; never with `ensure` or `also_changes` | one word for reads and writes, command-query separation |
| `ordered_by:` | list of expressions over one result item, bare property names, ascending, ties keep input order; only with `returns` | sorts; without it or an `IN ORDER` source, a positional check on `RESULT` is `not_ordered` |
| `also_changes:` | property paths (`order.history`) the frame rule allows to change without an `ensure` fact | everything else stays unchanged |
| `notes:` | free text | as on stories |

- **Order of checks.** Permission, then refusals in the order written,
  then the operation, then every `ensure`, `always` and `while`.
- **Frame rule.** After an operation, every stored property location of
  every entity reachable from the givens is unchanged unless it is
  named: a location is named when it is the left operand of a fact's
  top-level comparison (`=`, `!=`, `<`, `>`, `<=`, `>=`, `STARTS WITH`,
  `IN`, `IS EMPTY`, `IS SET`) under `ensure`, the argument of `COUNT`
  or `LENGTH` in that operand, or listed under `also_changes`. A
  location read on the right side is not named. Naming a list allows
  elements to be added or removed and new elements to appear with their
  parts; the elements already there are entities of their own and stay
  unchanged unless named. Computed and derived properties follow.
- **`OLD(x)`** is the value of `x` captured after the refusals were
  checked and before the operation changed anything: a deep, frozen
  copy; `OLD(COUNT(x))` is allowed. Only under `ensure`.
- **Empty values.** An `OPTIONAL` property or omitted input with no
  value `IS EMPTY`; `=` between two empty values is true (unlike SQL's
  NULL); any other comparison with an empty value fails the example.
- **Reads inside expressions.** `check(file)` in a fact calls a declared
  read operation in Python call form, as the checker itself, with no
  actor and no permission check; a changing operation there is refused
  (`not_an_expression`). `call:` in a step is the example asking as an
  actor.
- **One at a time.** Operations have the results they would have if run
  one at a time. Without `at:`, `NOW` is the example's start, fixed by
  the binding.

## 7. Expressions

Every form is borrowed; the source is part of the rule. Expressions
appear in `when`, `holds`, `always`, `computed`, `returns`,
`ordered_by`, `fact`, bare facts, `then` items, `call` and
who-conditions.

### 7.1 Forms

| form | means | from |
|---|---|---|
| `order.status`, `order.shop.name`, `story.versions[-1].text` | reach into an entity or a list element; chains allowed | Python |
| `x = v`, `x != v`, `x < v`, `x > v`, `x <= v`, `x >= v` | compare numbers, times, text, choice values and references | SQL |
| `a AND b`, `a OR b`, `NOT a` | logic; `NOT` binds tightest, then `AND`, then `OR`; left to right; short-circuit | SQL |
| `x IS EMPTY`, `x IS SET` | an optional value has no value, has a value | SQL (IS NULL) |
| `x BETWEEN a AND b` | inclusive range | SQL |
| `x IN list`, `x NOT IN list` | membership in a list | SQL |
| `x STARTS WITH y`, `x CONTAINS y` | prefix of a text or a list; a text contains a text | Cypher |
| `LENGTH(text)` | characters of a text; on a list it is `wrong_type` | SQL |
| `COUNT(list)`, `SUM(e FOR x IN list)`, `MIN(e FOR x IN list)`, `MAX(e FOR x IN list)`, `ANY(c FOR x IN list)`, `ALL(c FOR x IN list)` | the six list words; `COUNT` on a text is `wrong_type` | SQL words, Python generator form |
| `[x FOR x IN list IF c]`, `[y FOR x IN xs FOR y IN x.ys]` | filtered and nested lists; order of the source kept | Python |
| `list[0]`, `list[-1]`, `list[1:]` | index and slice; an index is a whole number in range, else the example fails | Python |
| `a IF c ELSE b` | conditional; the untaken side is not evaluated | Python |
| `story.approved`, `NOT fresh.approved` | a yes/no property as a condition | Python |
| `+ - * /`, `( )` | arithmetic with Python precedence; `+` joins two lists into a new list | Python |
| `"text"`, `\n`, `\"` | a text literal | Python |
| `"#{x} units"` | interpolation, only in `reason` | Ruby |
| `3`, `-2`, `1.5`, `2026-10-03 10:00`, `2026-10-03`, `1 HOUR`, `30 MINUTES`, `2 DAYS`, `[]`, `[a, b]` | number, time and list literals; times in the business zone | Python, SQL interval words |
| `YES`, `NO` | the yes/no literals, only under `DEFAULT` and `with:` | Edda (the type's name) |
| `NOW`, `TODAY`, `ACTOR`, `RESULT` | the four fixed names: the time, the day, the asker, the latest call's return | Edda |
| `OLD(x)` | the value before the operation | Design by Contract |
| `check(file)` | a declared read operation called inside an expression | Python |

Nothing else. Percent, rounding, money and date arithmetic are backlog
#2494. A lowercase word that is not declared is `unknown_name`; an
uppercase word not in 7.2 is `not_an_expression`; a list word on a
non-list, or `+` between a list and a number, is `wrong_type`. The
checker knows a list from its declaration (`MANY`, a comprehension, a
slice, a list literal); hover shows the type.

### 7.2 Language words

| word | means | from |
|---|---|---|
| `AND` `OR` `NOT` | logic | SQL |
| `IS EMPTY` `IS SET` | no value, a value | SQL |
| `BETWEEN` | inclusive range, with `AND` | SQL |
| `IN` `NOT IN` | membership | SQL |
| `STARTS WITH` `CONTAINS` | prefix, containment | Cypher |
| `LENGTH` `COUNT` `SUM` `MIN` `MAX` `ANY` `ALL` | text length and the list words | SQL |
| `FOR` `IF` `ELSE` | generator and conditional | Python |
| `OLD` | the value before | Design by Contract |
| `NOW` `TODAY` `ACTOR` `RESULT` | the fixed names | Edda |
| `YES` `NO` | the yes/no literals | Edda |
| `HOUR` `HOURS` `MINUTE` `MINUTES` `DAY` `DAYS` | durations | SQL |
| `DONE` | the outcome of a successful call, in `then` | Edda |
| `NOBODY` `WHOSE` `WHILE` | who-expressions | Edda |
| `MANY` `IN ORDER` `DEFAULT` `OPTIONAL` `DERIVED` `TEXT` `NUMBER` `TIME` `YES_NO` | type phrases | Edda |

## 8. Examples

```yaml
examples:
  "Ta bort frees held stock":
    given:
      - actor: erik
        with: {roles: [shop_user], shop: butik}
      - order_line: held
        with: {units_held: 3, units_sent: 0}
      - order: purchase
        with: {shop: butik, status: incoming, lines: [held]}
    steps:
      - when: {actor: erik, call: "remove(purchase)", at: "2026-10-03 10:00"}
        then:
          - DONE
          - "purchase.status = removed"
          - "held.units_held = 0"
      - when: {actor: erik, call: "remove(purchase)"}
        then:
          - refused: "the order is already removed"
    notes: ["erik is the shop's buyer"]
```

| key | means | why |
|---|---|---|
| `examples:` | title to example; one concrete run | the acceptance criteria that run |
| `given:` | a list of things to make; each item has exactly one key besides `with`: `- <entity>: <name>` or `- actor: <name>`; `with:` holds property values, `roles:` for an actor, `fixture:` for a `spec_file` | order-independent, schema-checked; names declared here are used below; the binding makes them; no glue is written |
| `with:` | property name to value: a number, quoted text, a quoted time, `YES`/`NO`, a choice value, a given name, or a list of those | a property left out takes its `DEFAULT`, `[]` for `MANY`, empty for `OPTIONAL`, otherwise unset: reading it fails the example; a derived property is `derived_in_given` |
| `fixture:` | the folder under `fixtures/`; its file, and its history when present, become the given `spec_file` | the whole spec is the given, never a hand-made fragment |
| `steps:` | a list of `when` and `then`; `when` may be left out to check the given state | a flow is several steps |
| `when:` | `actor` (a declared given), `call` (the operation with its arguments, Python call form), `at` (optional time) | one fixed shape; every actor is declared (`unknown_name` otherwise) |
| `then:` | with `when`: the outcome first, `DONE` or `refused: "<reason>"`, then facts; without `when`: facts only | the checker compares; `RESULT` is what the latest call returned |
| `notes:` | free text | as on stories |

After `refused`, `RESULT` has no value; a changing operation returns
nothing. Facts after `refused` check that nothing changed.

## 9. Level 2: links and binding

Unchanged from revision 24. `order.links` holds every path and the
business-to-code name map; the code carries `# FUL-005@3`; the binding
is written once per entity, role and operation; the checker emits one
versioned JSON model of the whole spec, which every binding consumes,
so the write form never ties the spec to one stack. That an approval
lands in the `.vc` file on disk and survives a re-read is the binding's
test, not a level 1 fact.

## 10. Versions and approval

```yaml
# order.edda.vc  (append-only, oldest first)
- entity: order
  number: 2
  approved_at: "2026-10-01 09:00"
  approved_by: tuan
  because: "nobody may delete an order"
  text: |
    order:
      is: "what a workshop buys"
      ...the block as approved, normalised...
- story: FUL-005
  number: 3
  approved_at: "2026-10-01 14:00"
  approved_by: tuan
  because: "the shop asked that sent orders cannot be removed"
  pins: [{entity: order, number: 2}, {role: shop_user, number: 1}]
  text: |
    FUL-005:
      story: "remove orders from the list"
      ...the whole story as approved, normalised...
```

- `.edda` is current; the agent edits it. `.edda.vc` is the file's
  history: append-only, oldest first, one entry per approved version of
  a story, an entity block or a role block (role blocks in
  `glossary.edda.vc`); only the operator's approve command writes it; a
  repository guard keeps the agent out.
- **Normalised text.** A block's `text` is its lines from its key line
  (`order:`, `FUL-005:`) to its last line, with comments, blank lines
  and trailing spaces removed and re-indented so the key line starts at
  column 0. A `#` inside a quoted string is not a comment. The entry's
  `text` must equal that; `number` must be the next in sequence for
  that story or block (`bad_version` otherwise, in the `.vc`).
- **Draft, story.** Its `rules_text` differs from the newest version's:
  `rules_text` is `text` with only `about:`, `as_a:`, `operations:` and
  `examples:` kept and every `notes:` entry removed. The sentence,
  `i_want`, `so_that`, `epic`, `tags`, notes, questions, comments and
  blank lines change freely. **Draft, block.** Its `text` differs from
  the newest version's.
- **Pins.** A story version records every block the story names
  (section 11, `story.blocks`) at its version then: one pin each, no
  extras. A newer block version flags the story
  `approved_against_older`: "FUL-005 approved against entity order v2,
  order is now v3". A flag, not a draft.
- **Approve a story.** Refused when the file does not check ("the file
  does not check"), when a named block has no version yet ("approve its
  blocks first"), or when the story is approved and no pin is stale
  ("nothing to approve: the story matches its newest version and its
  pins are current"). Otherwise one entry is appended: the next number,
  the normalised text, the asker, the time, the `because`, and a pin
  for every named block at its current version. Blocks first, then
  stories; for Edda itself the ten entities and two roles, then
  EDDA-001.
- **Approve a block.** Refused when the file does not check or when the
  block is approved ("nothing to approve: the block matches its newest
  version"). Otherwise one entry is appended, without pins.
- **Wording drift.** In a draft, a pair whose one side differs from the
  newest version while the other does not: `fact`/`means`,
  `when`/`reason`, an operation's body/`is:`, the story's rules/`story:`
  sentence. Flagged `wording_drift` at the smallest pair that holds it;
  enclosing pairs stay quiet. Shown side by side in the diff view, in
  the warning shade in the read view. The agent's standing rule is to
  re-read the meaning against the mechanics and fix or justify;
  approval clears it.
- **What changed** is derived (`story.changes`, section 11): added and
  removed lines between the newest version's text and the current text.
- Git keeps the history of both files; the KB keeps the audit copy.

## 11. The checker

**Layers.** Each file is read in four layers; a layer runs only when
the earlier ones found nothing, and every independent problem of the
first failing layer is reported, ordered by file, line, rule name.
Problems in the `.vc` carry that file's name. Two problems are
dependent: a block with an unknown key reports only that, never a
missing key (the unknown key is usually the missing one misspelt); an
anchor and its aliases are one problem, at the anchor.

1. source: `not_yaml`, `yaml_feature`;
2. shape: `unquoted_text`, `not_a_list`, `wrong_type`, `missing_key`,
   `unknown_key`, `declared_twice`;
3. meaning: `unknown_name`, `unknown_status`, `bad_type_phrase`,
   `not_an_expression`, `returns_and_ensure`, `wrong_file`,
   `not_ordered`, `role_cycle`, `derived_in_given`, `wider_than_entity`;
4. history and flags: `bad_version`, then every flag.

**Refusals** (`problem.kind = refused`), with their messages:

| rule | when | message |
|---|---|---|
| `not_yaml` | the file does not parse | `not YAML: <parser message>` |
| `yaml_feature` | an anchor (its aliases with it), tag, directive, `<<`, complex key, tab or second document | `anchors and aliases are not allowed` (and likewise for each feature) |
| `unquoted_text` | free text or an expression written plain | `quote the <key>; an unquoted # drops the rest of the line` |
| `not_a_list` | a repeated thing written as a scalar or a mapping | `<key> must be a list, one <item> per line` |
| `wrong_type` | a mapping, list or scalar where another is expected; a list word on a non-list | `<key> must be a <mapping/list/text>` |
| `missing_key` | a required key absent | `<block> needs <key>:` |
| `unknown_key` | a key the schema does not name | `unknown key: <key>` |
| `declared_twice` | a duplicate key or name, at the second | `declared twice: <name>` |
| `unknown_name` | an undeclared lowercase word, actor, entity, role or given | `unknown name: <name>` |
| `unknown_status` | a status value not in its property's list | `status not in its list: <value>` |
| `bad_type_phrase` | a type phrase outside the grammar | `not a type phrase: <text>` |
| `not_an_expression` | a string outside section 7, an uppercase word not in 7.2, a step in disguise, a changing call inside a fact | `not an expression: <text>` |
| `returns_and_ensure` | both on one operation | `returns and ensure on one operation: <name>` |
| `wrong_file` | a story in another entity's file | `story <id> is about <entity> and belongs in <entity>.edda` |
| `not_ordered` | `RESULT[n]` on an unordered return | `<operation> gives no order; RESULT[<n>] needs ordered_by or IN ORDER` |
| `role_cycle` | `includes` reaches itself, at the first role in file order | `role <name> includes itself` |
| `derived_in_given` | a `with:` value for a derived property | `<property> is derived and cannot be given` |
| `wider_than_entity` | `who:` admits a role the `about` entity's matrix never names | `<operation> admits <role>, which <entity> does not` |
| `bad_version` | a `.vc` number out of sequence or an unknown story or block | `<kind> <name> version <n> out of sequence; expected <m>` |

**Flags** (`problem.kind = flagged`):

| rule | when | message |
|---|---|---|
| `unreachable_status` | no `may_change` arrow reaches a status | `no change reaches status: <value>` |
| `no_example` | a story with no example | `story <id> has no example` |
| `approved_against_older` | a pin older than its block | `<id> approved against <kind> <name> v<n>, <name> is now v<m>` |
| `question_on_approved` | a question on an approved story | `story <id> is approved and still has a question` |
| `wording_drift` | section 10 | `<id> <operation>: <side> changed, <other> did not` |
| `plural_name` | a `MANY` property with a singular name, or a reference with a plural one | `<property> holds MANY and should be plural` |
| `about_untouched` | a story that never names its `about` entity | `story <id> is about <entity> but never names it` |

Level 2 adds: code with no story; code behind the spec or at an
unapproved version.

**Derived properties** (`, DERIVED`), by name:

- `spec_file.blocks`, `spec_file.stories`: the role and entity blocks,
  the stories, in file order.
- `spec_file.notes`: every `notes:` entry under a story, an operation or
  an example, in file order; `story_id` is the enclosing story's id.
- `spec_file.problems`: the refusals and flags above for this file and
  its history, ordered as the layers say.
- `block.kind`, `block.name`, `block.text`, `story.id`, `story.about`,
  `story.as_a`, `story.sentence`, `story.epic`, `story.text`: from the
  block; `text` is the normalised text of section 10.
- `story.rules_text`, `version.rules_text`: section 10, over `text`.
- `story.blocks`: the blocks the story names: its `about` entity; every
  entity in an input type phrase or a given; every role in `as_a`,
  `who:`, a given's `roles:`, and on a `may_*` line of a named entity;
  each once, in file order.
- `story.versions`, `block.versions`: the history's entries for this
  story or block, oldest first.
- `pin.block`: the block of the pin's kind and name in the file.
- `story.changes`: take the longest common sequence of lines between
  the newest version's `text` (no lines when there is no version) and
  the current `text`; every other line is a change, removed if only in
  the old text, added if only in the new, in line order; at one
  position removed lines come before added; a removed line's `line` is
  the line of the next common or added line in the new text, or one
  past the end; among equally long common sequences the one pairing
  earlier old lines with earlier new lines wins.
- `story.sentences`, `version.sentences`: section 12 over `text`.

**Done.** A story is done when, at its approved version: it is not a
draft; no pin is stale; every example passes; the rule checks pass on
the whole suite for its operations; every link resolves both ways. The
checker computes it; the agent never marks it.

**Runs, test only.** Examples through the binding; refusals, ensures,
always, while and the frame rule wrapped round the linked operation
for every test in the suite. Never in production.

## 12. Views

**Read view.** Generated from the checked tree, never edited. A
`sentence` has `kind`, `text`, `line` (where it comes from) and
`shade` (`plain`, `grey` for notes, `warning` for questions and
drifted pairs). Sentences come in file order, one per rule:

| kind | template |
|---|---|
| story | `<Story>. As a <role>, I want <i_want>, so that <so_that>.` |
| note, question | the text; a story's notes after the story sentence, then its questions; an operation's or example's after its own sentences |
| operation | `<Name> <is-sentence>.` |
| permission | `A <role> [whose <condition>] may <name> <inputs> [while <condition>].` |
| refusal | `If <name> is asked for <an input> whose <condition>, then the system shall refuse it: <reason>.` when every left side is that input's property; otherwise `If <name> is asked and <condition>, then ...` |
| outcome | `When <name> succeeds, <means>.` or, without `means`, `When <name> succeeds, <fact in words>.` |
| read | `<Name> gives <returns in words>[, ordered by <keys>].` |
| invariant | `Always, <fact>.` and `While <condition>, <fact>.` |
| example, given, when, then | `Example: <title>.`, `Given <name>, a <entity> with <property> <value> and ...` (actors: `<name>, a <role>`), `When <actor> asks to <name> <arguments>.`, `Then it is done and <facts>.` / `Then it is refused: <reason>, and <facts>.` |

Expressions in words: `.` reads `'s` (`the order's status`); `=` is,
`!=` is not, `>` is more than, `<` is less than, `>=` is at least, `<=`
is at most; `AND` and, `OR` or, `NOT` not; `IS EMPTY` is empty; `IS
SET` is set; `BETWEEN a AND b` is between a and b; `IN` is in; `STARTS
WITH` starts with; `CONTAINS` contains; `COUNT(x)` the number of x;
`LENGTH(x)` the length of x; `SUM(e FOR x IN l)` the sum of e over l;
`ANY(c FOR x IN l)` some x in l has c; `ALL` every x in l has c; `[x FOR
x IN l IF c]` every x in l where c; `l[0]` the first of l; `l[-1]` the
last of l; `OLD(x)` x before; `ACTOR` the asker; `RESULT` the result. A
name reads as words (`units_sent` reads "units sent"); an entity type
takes "a" or "an"; a given or input keeps its name. Structural ids
(story keys) are hidden; an id written inside quoted text stays. Hover
shows each key's and word's meaning from the registry. `view_at` renders
a version's text with the wording and permissions of its pinned blocks.

**Write view.** The YAML with colour. **Diff view.** Two versions as
added and removed lines; drifted pairs side by side.

## 13. Not in this revision

Qualities and infrastructure (#2487), time-triggered operations
(#2486), screens beyond `wording` (#2488), timing and concurrency
(#2489), generated cases (#2490), the analyser (#2491), drafting from
existing code (#2492), story to Plan tasks (#2493), richer calculations
(#2494), tooling (#2495), the KDL skeleton trial (#2512); the running of
examples, the frame-rule test and the done computation are build step 4
and get their own stories then.

## 14. Changes from revision 25

- Language words are UPPERCASE, names snake_case; `'s` became `.`;
  articles dropped from expressions; `IS`, `IS NOT`, `MORE THAN` and the
  other phrase comparisons replaced by SQL's `= != < > <= >=`; `AND OR
  NOT`, `BETWEEN`, `IN`, `IS EMPTY`, `IS SET`, `LENGTH` from SQL;
  `STARTS WITH` and `CONTAINS` from Cypher, on lists too; Ruby predicate
  phrases dropped; `one` dropped, a bare entity name is a reference;
  `DEFAULT` fixes the type; `, DERIVED` added; the complete type and
  who grammars; the scope of bare names.
- `given` items are `- <entity>: <name>` plus `with:`; every actor is
  declared; a left-out property has a stated value; derived properties
  cannot be given.
- Every operation has `is:` and `who:`; a fact may be `{fact, means}`;
  `also_changes` holds property paths; the frame rule names locations by
  the left operand; `creates` is not a key; empty values compare.
- Approval: refused for an unchecked file, unversioned blocks, or
  nothing to approve; allowed when rules changed or a pin is stale; pins
  cover roles; role blocks versioned; `against` became `pins`;
  `wording_drift`; normalised text defined; `.vc` has a schema.
- The checker's four layers, every rule with its message, seven new
  rules (`not_yaml`, `not_a_list` renamed and fixed, `wrong_type`,
  `missing_key`, `bad_type_phrase`, `not_ordered`, `role_cycle`,
  `derived_in_given`, `wider_than_entity`, `bad_version`) and four new
  flags (`question_on_approved`, `wording_drift`, `plural_name`,
  `about_untouched`); derived properties as named rules, not comments;
  the diff's tie-breaks; the read view's sentence model and templates.
- Notes live on stories, operations and examples only; `examples: {}`
  and no `examples:` are the same flag.
