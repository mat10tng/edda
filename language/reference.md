# Edda: language reference

Revision 75, 5 Oct 2026. Replaces revision 74. Decisions behind it:
kb:9378274, rounds 1 to 4 (entries 1 to 46) and later entries (the
shrink: entry 138; the naming pass: entry 136; `TODAY` returns: entry
139; examples run against real code: decision EE, the vision
kb:9378618, and the build Plan kb:9379223; the JSON model and graphs
as data: decision N, kb:9379218; the read view: the build Plan's
phase 2622; links per operation: decision N, Q6, and the build Plan's
phase 2623; generated cases: decision T, kb:9379252, and the build
Plan's phase 2636; the analyser: decision U, kb:9379257, and the build
Plan's phase 2648; problem dimensions and watching: decision U,
questions 4 to 6, and the build Plan's phase 2649; the import contract:
decisions W and X, kb:9380137, and the build Plan's phase 2657; the
opt-in problem log: decision HH, entry 140, which amends decision Y;
one `edda` command with `--json` and fixed exit codes: decision AA,
entry 132; both the build Plan's phase 2809; the frozen clock in
examples: decision FF, entry 138, kb:9380368 section 2, with decisions
Z (a day is a calendar day) and GG (`TODAY` is the day of `NOW`), and
the build Plan's phase 2727; client functions: decisions EE and FF,
kb:9380368 section 3, and the build Plan's phase 2728; a read inside a
generated step's rule: Astra's round 80, kb:9380659, item 2, and the
build Plan's phase 2793; the root opened without following a link:
Astra's round 91, kb:9380698, item 1, and the build Plan's phase
2794; the host contract: operator decision KK, 5 Oct 2026, the
findings kb:9380940, and task 2894; every story run against
Edda's own code: operator decisions LL and MM, 5 Oct 2026, and task
2905), and Astra's review
rounds. The skeleton is YAML; the words are keys; the logic is Python expressions in a whitelisted subset. Everything here is mirrored
by `language/schema.json` (the keys of a `.edda` file),
`language/vc-schema.json` (the keys of a `.edda.vc` file),
`language/command.schema.json` (the `--json` document, section 13),
`language/model.schema.json` (the JSON model, section 9) and
`language/keywords.yaml` (the registry: every key, expression form,
fixed name, checker rule and sentence kind, with what it means, why it
exists and where it comes from; generated plain YAML, not a spec file,
so the subset below does not apply to it).

## 1. The idea

- **Two levels.** Level 1 states: entities and their properties, who
  may do what, what an operation refuses and what is true after, stories and
  examples. Level 2 does: ordered steps, in code. Level 1 cannot hold a
  step, because its only places for logic are expression slots, and a
  slot holds one expression, never a statement.
- **Who writes, who reads.** An agent writes level 1 from the customer's
  words. The operator, a person, reads the read view and approves. The
  agent builds level 2 and the code. The checker decides done.
- **Structure in keys, logic in Python.** Everything that is structure
  (a request, a given, a fixture, an order, a permission) is a key the
  schema names. Only conditions, facts and values are expressions, and
  an expression is Python 3, parsed by Python's own `ast` and limited
  to the whitelist of section 7. Nothing is invented.
- **Meaning above examples.** A story's `rules:` say in one sentence
  each what a group of its examples shows, as Gherkin's `Rule:` does;
  the checker holds every example to exactly one rule. Conditions stay
  in `refuse:` and `ensure:`, Design by Contract's form.
- **Shape tells words apart.** Declared names are snake_case; YAML keys
  are snake_case; ids are `ABC-123`; the fixed names `OLD`, `ACTOR`,
  `RESULT`, `NOW`, `TODAY` and the type-phrase words (`MANY`, `DEFAULT`,
  `TEXT`, ...) are UPPERCASE; Python's own keywords
  (`and`, `or`, `not`, `in`, `is`, `for`, `if`, `None`,
  `True`, `False`) are Python's.
- **Checked, not trusted.** Names, links, versions and the body of every
  story are checked against the code on every test run. Nothing the
  checker cannot read counts as a promise. Comments are never part of
  the body.

## 2. Files and the YAML subset

```
specs/
  glossary.edda      roles: (and functions:, in any file)
  glossary.edda.vc   versions of the role blocks, append-only
  epics.edda         epics:
  order.edda         entities: order (and its parts), stories: about order
  order.edda.vc      versions of those stories and entity blocks, append-only
  glossary.links     level 2: the code target, the naming rule, the
                     code files the link check reads
  order.links        level 2: the operations of order.edda whose function
                     does not follow the rule
  order.binding      level 2: how examples make, call and read entities
fixtures/
  <name>/order.edda  one whole spec in one folder, checked under its own
                     file name, used by examples through `fixture:`
  <name>/order.edda.vc   its history, when the fixture has one
  <name>/*.links, <name>/code.py   a fixture of the link layer
language/
  reference.md       this file
  schema.json        the keys of .edda, JSON Schema 2020-12
  vc-schema.json     the keys of .edda.vc
  command.schema.json   the --json document of every command
  model.schema.json  the JSON model
  keywords.yaml      the registry, generated from this file
```

A `.edda` file is YAML 1.2, core schema, in this subset, which the
checker enforces at the source, before the schema:

- free text (`is:` of a role, entity, operation or function, `story:`, `i_want:`, `so_that:`, `reason:`,
  `means:`, `rule:`, notes, questions, example
  titles, as keys and under `shown_by:`) and
  every expression (an `also_changes` path with them) is quoted, with
  double quotes; a single-quoted
  scalar is `yaml_feature`; every key is plain, except example titles;
  names, numbers, ids, `True`, `False` and type-phrase words are
  plain (a quoted name is `bad_name`); `DONE` is plain only as the
  first `then` item (a quoted `DONE` there is `bad_name`, like any
  quoted name); an unquoted ` #` would silently drop the rest of
  the line;
- one physical line per expression, per type phrase and per example
  title, as a key and under `shown_by:`; a `|` scalar (never a folded
  `>` one) is allowed only for `text:` in `.edda.vc`; other free text, a
  `rule:` sentence with it, may wrap onto further lines as YAML allows;
- repeated things are lists (`- `): refusals, ensures, givens, steps,
  then items, always-rules, notes, questions, who-lists, pins; mapping
  order is never a meaning, with two stated exceptions: the order of
  `inputs:` is the order of positional arguments in a call, and the
  read view, the diff and the `blocks` and `stories` indexes keep file
  order;
- no anchors, aliases, the `<<` key, tags, directives, complex keys,
  tabs or a second document;
- a key is written `name:`, the colon straight after the key: never
  with a space before the colon (`operations :`) or introduced by an
  explicit `?` key indicator, in `.edda` and `.edda.vc` alike;
- `roles:`, `entities:`, `functions:` and `stories:`, each role,
  entity, function and story under them, and each operation under
  `operations:` and example under a story's `examples:` are written out,
  one key per line, never in flow form (`{ }` or `[ ]`); values below
  them (`inputs:`, `who:`, `with:`, `then:`, a function's rows and the
  like) may be flow;
- two-space indentation, enforced: a line's indentation is even and at
  most two deeper than the line before it, a list dash counting as two
  for the line after it; keys are snake_case except
  story ids (`ABC-123`), epic ids (`ABC`) and example titles (quoted
  text);
- a duplicate key is `declared_twice` at the second key; so is a
  role, entity, story or operation name declared twice in one
  project, a function name that is also a role, entity, operation or
  another function, or one of Edda's own words (`len`, `sum`, `any`,
  `all`; section 4) (at the second, in file order, then file-name
  order), a
  given name used twice in one example, and a role property named
  `name` or `roles`, which every actor has already; a declared
  name or choice value that is a Python keyword (`class`, `in`,
  `None`, ...) is `bad_name`, in the shape layer, since an expression
  could not reach it;
- `#` starts a comment outside a string; comments are never part of
  the body, are invisible to the views and ignored by the version
  comparison.

**Placement.** A story carries `about: <entity>` and lives in that
entity's file, which for a part is its owner's (`wrong_file`
otherwise). `about` is authoritative. A part (`part_of:`)
lives in its owner's file, through the whole chain of owners
(`wrong_file` otherwise). One home per story; a story with two homes
is two stories under one epic. A client function (section 4) may live
in any file; its versions are in the history beside that file.

## 3. Roles

```yaml
roles:
  shop_user:
    is: "a person at a shop who orders from the workshop"
    properties: {shop: shop}
  admin:
    is: "a person who runs the system"
  agent:
    is: "a program that writes .edda files"
```

| key | means | why |
|---|---|---|
| `roles:` | the kinds of actor, person or program | permissions and stories name roles |
| `is:` | one sentence of description | the read view |
| `properties:` | the properties a holder of this role has, name to type phrase | `ACTOR.shop == order.shop` needs a shop |

An actor holds a set of roles. A request is allowed when any of its
roles passes any who-line, condition included. The permission
refusal reads `"<operation> is not allowed for <roles>"`, roles in the
order the actor's `roles:` lists them. `ACTOR` is the one asking: it has
`name` (its given name, text), `roles` (list of role names) and the
properties of its roles: on a who-line, those of that line's
role; inside an operation's body, those
every role on its `who:` has (a property two of them declare with
different types may be either, two lists of different elements
staying two lists); in an example, those of the given
actor's roles, and `ACTOR` is the step's actor. `name` and `roles`
are fixed; a role's `properties:` cannot redeclare them, and a given
cannot set `name` (`derived_in_given`). Role blocks are versioned and pinned
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
      units_held: {computed: "sum(line.units_held for line in lines)"}
      units_sent: {computed: "sum(line.units_sent for line in lines)"}
    may_change: {status: {incoming: [delivered, removed]}}
    always:
      - "units_sent <= len(lines)"
    may_create: [{role: workshop_user}]
    may_read:
      - {role: shop_user, when: "ACTOR.shop == order.shop"}
      - {role: workshop_user, when: "ACTOR.workshop == order.workshop and order.status != removed"}
      - {role: admin}
    may_update: [{role: shop_user, when: "ACTOR.shop == order.shop"}, {role: admin}]

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
| `may_change:` | per choice property, optional or not, the only allowed changes from one choice value to others (`type_mismatch` on a property that is no choice) | a change outside it fails at run time; an unreached value of a choice with `DEFAULT` is flagged |
| `always:` | facts that hold after every operation | invariants checked on the suite |
| `may_create:` | who may create one, as a list of who-lines; left out, nobody may | the CRUD matrix, default deny |
| `may_read:` | who may read one, as a list of who-lines; left out, nobody may | the CRUD matrix, default deny |
| `may_update:` | who may change one, as a list of who-lines; left out, nobody may | the CRUD matrix, default deny |
| `may_delete:` | who may delete one, as a list of who-lines; left out, nobody may | the CRUD matrix, default deny |

**Type phrases**, one closed grammar for entity and role properties
and `inputs:`:

```
type_phrase := DEFAULT literal [, DERIVED]
             | DEFAULT choice [, DERIVED]
             | type [, OPTIONAL] [, DERIVED]
type        := TEXT | NUMBER | INTEGER | TIME | YES_NO | <entity>
             | MANY <entity> [, IN ORDER] | choice
choice      := name | name | name ...      two or more, distinct, snake_case
literal     := number | "text" | "time" | True | False
number      := -?[0-9]+ (an INTEGER) | -?[0-9]+.[0-9]+ (a NUMBER)
```

There is no duration type: `DAYS`, `HOURS` and `MINUTES` (7.1) only
move a time inside an expression; no property, input or `DEFAULT`
holds one.

`DEFAULT` fixes the type from what follows: `DEFAULT 0` is an INTEGER,
`DEFAULT 1.5` a NUMBER, `DEFAULT "none"` a TEXT, `DEFAULT False` a
YES_NO, `DEFAULT incoming | removed` a choice whose first value is the
default; the type word is then not written. A number is read by the
grammar, so `DEFAULT 01` is 1. A quoted `DEFAULT` whose text is
exactly a time in the format of section 7.2, `"YYYY-MM-DD HH:MM"` or
`"YYYY-MM-DD"`, and a real date and time, is a TIME:
`DEFAULT "2026-10-04 09:00"` compares with `TIME("2026-10-05")`, `NOW`
and `TODAY` as any TIME property does. Any other quoted `DEFAULT` is a
TEXT, `DEFAULT "2026-02-30"` included, since no such day exists. So a
TEXT property cannot default to a text that looks exactly like a time:
declare it a TIME, or give the value in each example. The text of a `"text"` or `"time"` is
what stands between the quotes, exactly as written: a backslash is an
ordinary character and there are no escape sequences, so
`DEFAULT "C:\New"` is the text `C:\New`. The text ends at the next
quote, so a quote cannot stand inside it: `DEFAULT "a\"b"` is
`bad_type_phrase`. The checker's model and the runner read a `DEFAULT`
the same way. `DEFAULT` never goes with a
reference, a `MANY` or `OPTIONAL`, by the grammar. `INTEGER` is a whole
number; `NUMBER` any number; an INTEGER is accepted where a NUMBER is
expected, not the reverse. A bare name is a single reference to that
entity; a name that is no entity is `unknown_name`; a single-value
choice does not exist and a repeated value is `bad_type_phrase`. `, DERIVED` marks a property the checker computes by a rule of
section 11 named `<entity>.<property>`; it cannot be given
(`derived_in_given`). Anything else is `bad_type_phrase`. A computed
property is always `{computed: "<expression>"}`; one whose expression is
a condition is yes/no and is used as a condition (`order.approved`).
Edda does not accept a computed property that depends on itself,
directly (`a: "a + [1]"`) or through other computed properties: its own
entity's, those reached through a reference (`a: "b"`, `b: "a"`), and
those read by an operation the expression calls. Each such operation is
summarised once, as the computed properties a call can read: its
`refuse` conditions and `returns`, every input taken at its declared
type, not the call's argument, and its `ordered_by` over one result
item; plus the summaries of the operations it calls. Its `who:`
conditions are left out, as such a call has no actor and no permission
check (section 6), and so is `ensure`, as it is always a read. Such a
property is `computed_cycle`; a calculation Edda cannot express this way
is left to the host. A stored property or a comprehension's variable
never forms a loop, and calling the same operation twice is not one.

**Who-lines.** A who-line is `{role: <role>}` or `{role: <role>, when:
"<condition>"}`. The roots in scope in the condition are `ACTOR`, the
entity's own name on its `may_*` lines, and the inputs' names on an
operation's `who:` line. A property written without its root
(`shop == order.shop` for the actor's shop) is `unknown_name`.

**Scope of bare names.** A root is a name an expression may start
from. Inside `always` and `computed` the roots are the
entity's own properties; inside an operation its inputs; inside an
example its given names; inside `ordered_by` the result item, reached
by its entity's name; on a who-line, as above. A comprehension's
variable is a root inside that comprehension, with Python's scope.
Choice values are in scope only where their property is compared:
beside `==` or `!=`, or as the bare names of a list after `in`; a
bare choice value anywhere else, `<` and `in` included, is
`unknown_name`.
A choice value keeps its list: a choice stands for another only when
every value of its list is in the other's. The
fixed names of 7.2 are roots everywhere they are allowed.

**Client functions** (decisions EE and FF). Anything Edda cannot say is
a function the client provides, declared once, in a top-level
`functions:` block of any `.edda` file, with its meaning, its types and
example rows:

```yaml
functions:
  shipping_cost:
    is: "what a parcel of that weight costs to ship"
    inputs: {weight: NUMBER}
    returns: NUMBER
    examples:
      - {given: {weight: 1}, gives: 5}
      - {given: {weight: 10}, gives: 12}
```

| key | section | means | why |
|---|---|---|---|
| `functions:` | Client functions | name to client function: a value Edda cannot compute, which the client's code provides | anything Edda cannot say is declared, never left implicit (decision EE) |
| `is:` | Client functions | what the function gives, one sentence; required | the read view; its meaning beside its rows |
| `inputs:` | Client functions | name to type phrase, in call order; every input is passed by position | calls are typed against it |
| `returns:` | Client functions | the type phrase of its result | a call has this type |
| `examples:` | Client functions | the rows, at least one, each `{given: {<input>: <value>, ...}, gives: <value>}` | the function's contract: they answer for it in examples and are run against the real function |
| `given:` | Client functions | in a row, every input by name, each once, to a value | the row's inputs |
| `gives:` | Client functions | in a row, the result for those inputs | the row's result |

A function's inputs and result are `TEXT`, `NUMBER`, `INTEGER`, `TIME`,
`YES_NO` or a choice; any other type phrase there (an entity, `MANY`,
`DEFAULT`, `OPTIONAL`, `DERIVED`) is `bad_type_phrase`. A row's values
are literal values only, written as a `with:` value of that type is
(section 8): a number, quoted text, a quoted time, `True`, `False`, a
choice value. A row that leaves out an input is `missing_key`, one that
names an input the function has not `unknown_key` (and then only that,
as for a block, section 11), a value of another type `type_mismatch`;
two rows with the same inputs and different results are
`contradicting_rows`, values compared as values: `1` and `1.0` are one
number, two times one when they stand for one moment. A function's name
is unique across the project: one that is also a role, an entity, an
operation or another function, or one of Edda's own words (`len`,
`sum`, `any`, `all`; the fixed names of 7.2 are uppercase and so never
a name), is `declared_twice` (the same name from two sources, decision
EE).

A function is called in any expression slot as a read is,
`shipping_cost(order.weight)`, its inputs by position, with no actor
and no permission check; it never changes anything (7.1). In an
example, a call answers only from the rows (section 8); `edda run` runs
the same rows against the client's real function through the binding
(section 9), so its contract is never checked by the code under test.
Results only: no call counts, no "was it called". A function is a block,
approved and pinned like an entity block (section 10).

A `DERIVED` property is not a client function: it is a value of one
record the host computes, by a rule of section 11, with no rows, and
the runner reads it from the binding. Growing `DERIVED` into client
functions, and moving `ordered_by` and nested or filtered list-building
to them, is the second part of decision FF, not in this revision.

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
    rules:
      - rule: "a removed order gives its held stock back"
        shown_by: ["Ta bort frees held stock"]
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
| `i_want:` | what the role wants, free text | stored and shown; nothing runs on it |
| `so_that:` | why the role wants it, free text | stored and shown; nothing runs on it |
| `epic:` | the id of the epic the story belongs to | grouping; changeable without a new version |
| `tags:` | a list of labels | grouping; changeable without a new version |
| `notes:` | what the grammar cannot say, on a story, an operation or an example; ignored by the checker, grey in the view, collected across files | nothing the customer said is lost; repeated notes are the evidence for a new key |
| `questions:` | the undecided | a flag on an approved story, never a block |
| `rules:` | optional; a list of rules, each a `rule:` sentence and the examples that show it; when present, every example of the story is named by exactly one rule (`no_rule` for one named by none, `declared_twice` for one named twice, `unknown_name` for a title that names no example of the story) | Gherkin's Rule:, with one check: every example belongs to exactly one rule; the layer between the story's meaning and its examples; decision kb:9378274 entry 100 |
| `rule:` | inside `rules:`, what the examples under it show, one sentence of free text | the read view heads the examples with it |
| `shown_by:` | inside `rules:`, the titles of the examples the rule groups, a list of quoted text | each example tied to the meaning it shows |

The acceptance criteria of a story are its operations and examples.
`rules:` is no second list of criteria: each rule is a sentence over
examples already there, as Gherkin's `Rule:` holds its scenarios, and
the checker holds the grouping, every example under exactly one rule.
`examples:` absent or empty is one flag,
`no_example`.

## 6. Operations

```yaml
operations:
  remove:
    is: "takes an unsent order off the list and frees its held stock"
    inputs: {order: order, because: "TEXT, OPTIONAL"}
    who: [{role: shop_user, when: "ACTOR.shop == order.shop"}]
    refuse:
      - when: "order.status == removed"
        reason: "the order is already removed"
      - when: "order.units_sent > 0"
        reason: "the order has been sent and cannot be removed"
    ensure:
      - "order.status == removed"
      - "order.removed_by == ACTOR.name"
      - "order.removed_at == NOW"
      - fact: "order.units_held == 0"
        means: "the held stock goes back to the shelf"
    also_changes: ["order.history"]
    notes: ["the shop calls this Ta bort"]

  open_orders:
    is: "lists the orders a shop still waits for"
    inputs: {shop: shop}
    who: [{role: shop_user, when: "ACTOR.shop == shop"}]
    returns: "[order for order in shop.orders if order.status == incoming]"
    ordered_by: ["order.wanted_day", "order.id"]
```

| key | means | why |
|---|---|---|
| `operations:` | name to operation; one thing an actor can ask for | the anchor the code carries |
| `is:` | one sentence of what it does; required | heads the operation in the read view; its meaning beside the mechanics |
| `inputs:` | name to type phrase, in call order; required inputs are passed by position, `, OPTIONAL` inputs by keyword (`remove(purchase, because="moved")`) and are `None` when left out; an input declared `MANY ..., IN ORDER` takes only an ordered list | the binding and placement need the types |
| `who:` | list of who-lines; required | no defaults; `wider_than_entity` when it admits a role the `about` entity's matrix never admits |
| `refuse:` | list of `when` condition and `reason`; the first that holds is given | preconditions with a reason tests match |
| `ensure:` | list of facts true after; a fact is a quoted expression or `{fact, means}`; may use `OLD(...)` | postconditions, each with its meaning when the mechanics do not read |
| `returns:` | the expression a read operation gives back; never with `ensure` or `also_changes` (`returns_and_ensure`) | one word for reads and writes, command-query separation |
| `ordered_by:` | list of expressions over one result item, reached by its entity's name, ascending, ties keep input order; only with a `returns` that is a list (`returns_and_ensure` without `returns`, `type_mismatch` on a result that is no list) | sorts; without it or an `IN ORDER` source, a positional check on `RESULT` is `not_ordered` |
| `also_changes:` | quoted property paths (`"order.history"`), each segment resolved from an input, that the frame rule allows to change without an `ensure` fact; only with `ensure` (`returns_and_ensure` otherwise) | everything else stays unchanged |
| `notes:` | free text | as on stories |

- **Order of checks.** Permission, then refusals in the order written,
  then the operation, then every `ensure` and `always`.
- **Frame rule.** After an operation, every stored property location of
  every entity reachable from the givens, and of every actor, is
  unchanged unless it is
  named: a location is named when it is the left operand of an
  `ensure` fact's comparison (`==`, `!=`, `<`, `>`, `<=`, `>=`, `in`,
  `is None`, `is not None`), the argument of `len` in that operand, or
  listed under `also_changes`. Naming a computed or derived property
  names the stored locations it derives from, on that entity only. A
  location read on the right side
  is not named. Naming a list allows elements to be added or removed
  and new elements to appear with their parts; the elements already
  there are entities of their own and stay unchanged unless named.
  Computed and derived properties follow.
- **`OLD(x)`** is the value of `x` captured after the refusals were
  checked and before the operation changed anything: a deep, frozen
  copy; `OLD(len(x))` is allowed. Inside a comprehension it keeps the
  comprehension's names: `sum(OLD(e.amount) for e in account.entries)`
  is each entry's amount before the call, and an entry the call added
  has no `OLD` value, which fails the example. An `OLD` value is found
  by what the call cannot change: an input or `ACTOR` by its name, a
  comprehension's name by the value it took before the call, an entity
  or a list by identity. So with an input `entries` that is
  `account.entries`, `account.entries == OLD(entries) + [fresh]` holds
  after a correct append. Only under `ensure`.
- **Equality of entities.** Two references are equal when they are the
  same entity, never by value; a frozen copy keeps every identity, so
  `OLD(history.versions) + [story.versions[-1]]` compares element by
  element with the live list by identity. Texts, numbers, times and
  choice values compare by value. A binding implements the same rule.
- **No value.** An `OPTIONAL` property or left-out input is `None`;
  `None == None` is true, as in Python; `<`, `>` and arithmetic on
  `None` fail the example.
- **Reads inside expressions.** `check(file)` in a fact calls a declared
  read operation, as the checker itself, with no actor and no
  permission check; a changing operation there is refused
  (`not_an_expression`). A client function (section 4) is called the
  same way and never changes anything. `call:` in a step is the
  example asking as an actor, and only an operation can be asked for.
- **One at a time.** Operations have the results they would have if run
  one at a time. `NOW` is the example's clock (section 8): its start,
  moved only by a step's `at:`; nothing reads the machine's clock.

**How the runner holds a call to these rules** (section 9). The spec
checks the code's refusals; it never stands in for them. Every call of
a bound operation, a step's `call:` or a read inside a fact, goes:

1. permission, for a step's call only (a read inside a fact has no
   actor);
2. the `refuse` conditions in the order written: the first that holds
   is the refusal the spec expects, or there is none;
3. a snapshot of every stored property location of every entity
   reachable from the givens and the call's inputs, and of every actor
   among them (the properties its roles declare), and each `OLD(x)` of
   the `ensure` facts, for each value of the comprehension names around
   it;
4. the bound operation;
5. the outcome must match step 2: refused with exactly that reason, or
   not refused when no condition held;
6. a refused call changed nothing, the actor included; a call not
   refused makes every
   `ensure` fact hold, every `always` fact of every entity reachable
   from the givens and the inputs hold, and changed no location the
   spec does not name (the frame rule).

Any break fails the example there, at the rule's own file and line:
`<operation> should refuse: "<reason>", but it did not refuse` or `but
it refused: "<other reason>"` at the `refuse` condition;
`<operation> refused: "<reason>", but the spec does not refuse` at the
operation; `<operation>: ensure <fact>: found <what>` at the fact;
`<operation>: always <fact>, on <entity>: found <what>` at the
`always` fact; `<operation> changed <x>.<property>, which the spec
does not name` at the operation, `<x>` the given's name or, for an
entity no given names, its kind.

Reachable means through stored properties, entity references and lists
of them, from the givens and the inputs; an actor is no entity and is
not looked into, but the properties its roles declare are in the
snapshot like an entity's; an element added by the call is new and not
in the snapshot. A location
is compared without reading it, so an unset value (section 8) is never
read: an entity or an unset value by identity, a list element by
element, any other value by its kind and value. `OLD(x)` is a copy of
lists with every element the same entity; an entity in it is the live
entity, as equality of entities says. Naming a computed property on
an entity names the stored locations its expression reads when the
runner evaluates it on that entity, before the call and after it,
through other computed properties and the read operations it calls
(their `refuse` conditions, `returns`, and `ordered_by` on each item
returned); naming one account's
`total` names that account's `entries` and the `amount` of each of its
entries, never another account's. Naming a derived property (section
11) names the stored properties of that same entity only. A read
inside a fact names nothing, so it changes nothing; while the `always`
facts after a call are judged, a read they call keeps its refusal and
frame checks but does not judge the `always` facts again.

## 7. Expressions

An expression slot (`when`, `always`, `computed`, `returns`,
`ordered_by`, `fact`, a bare fact, a `then` item, `call`, a who-line's
`when`) holds one Python 3 expression, parsed by `ast.parse(text,
mode="eval")`. The checker walks the tree and refuses any node outside
this table (`not_an_expression`) and any lowercase name not declared
(`unknown_name`). Precedence, short-circuit and the meaning of every
form are Python's.

### 7.1 Forms

| form | means | from |
|---|---|---|
| `order.status`, `order.shop.name`, `story.versions[-1].text` | reach into an entity or a list element; chains allowed | Python |
| `x == v`, `x != v`, `x < v`, `x > v`, `x <= v`, `x >= v` | compare, one operator per comparison: `==` and `!=` take two values of one kind (`None` beside anything), two lists compare element by element, `<` and the rest two numbers, two texts or two times (`type_mismatch` otherwise) | Python syntax, Edda type rule |
| `a and b`, `a or b`, `not a` | logic; `not` binds tightest, then `and`, then `or`; short-circuit; `and` and `or` give one of their operands, as in Python, so `[1] or []` is a list | Python |
| `x is None`, `x is not None` | an optional value has no value, has a value | Python |
| `x in list`, `x not in list` | membership in a list; every value `x` may be is of the kind of every element (`type_mismatch` otherwise); a bare choice value in a literal list belongs to the compared property, the other elements are typed as usual | Python syntax, Edda type rule |
| `"t" in text` | a text contains a text | Python |
| `len(x)` | the number of elements of a list or characters of a text | Python |
| `sum(e for x in list)`, `any(c for x in list)`, `all(c for x in list)` | the three list words, each with exactly one generator and nothing else; a generator appears nowhere else | Python |
| `[e for x in list if c]`, `[y for x in xs for y in x.ys]` | filtered and nested lists; order of the source kept; the variable is a plain name, never a path; never `async` | Python |
| `list[0]`, `list[-1]`, `list[n - 1]` | index, on a list only (an index on a text is `type_mismatch`); an index is an INTEGER-valued expression (a constant, a name, a path, or those with `+ - *`), never a yes/no or a NUMBER; out of range fails the example | Python |
| `story.approved`, `not fresh.approved` | a yes/no property as a condition | Python |
| `+ - * /`, `( )` | arithmetic; `+` joins two lists into a new list | Python |
| `"text"`, `\n`, `\"` | a text literal | Python |
| `TIME("2026-10-03 10:00")`, `TIME("2026-10-03")` | a time: one quoted text literal in the time format of 7.2; any other argument, or a text in another format, is `type_mismatch` | Python syntax, Edda meaning |
| `NOW + DAYS(1)`, `order.due - HOURS(2)`, `NOW + MINUTES(n)` | a time moved by a duration, giving a time: `DAYS(n)` n calendar days in the business zone, the same wall-clock time across a daylight-saving change; `HOURS(n)` and `MINUTES(n)` elapsed time; a count of 0 leaves the time as it is; n an INTEGER expression; only `TIME + duration` and `TIME - duration`, in any expression slot; a duration anywhere else, or a count that is no INTEGER, is `type_mismatch` | Python syntax, Edda meaning (decision Z) |
| `3`, `-2`, `1.5`, `True`, `False`, `None`, `[]`, `[a, b]` | integer, number, yes/no, no value (`None`) and list literals | Python |
| `NOW`, `TODAY`, `ACTOR`, `RESULT` | the four fixed names: the time, the day, the asker, the latest call's return | Edda |
| `OLD(x)` | the value before the operation, one argument, only under `ensure` | Edda, after Eiffel's `old` |
| `len(x)` | one argument, no keywords | Python |
| `check(file)`, `approve(story, because="why")` | a declared operation called in Python call form: required inputs by position, optional ones by keyword | Python |
| `shipping_cost(order.weight)` | a client function (section 4) called in Python call form, every input by position, no keyword; its type is its `returns` | Python syntax, Edda meaning (decision EE) |

Nothing else: no lambda, dict, set, tuple, slice, conditional
(`a if c else b`), comparison chain (`a <= x <= b`), f-string, walrus,
star, `is` against anything but `None`, no bare generator, and no
method or function beyond those listed. Percent, rounding, money and
date arithmetic beyond moving a time by a duration are backlog #2494. A list word on a
non-list, `len` on a number, `+` between a list and a number, a
NUMBER as an index, an index on a text, or a comparison of two values
that do not compare is `type_mismatch`; the checker knows a list from
its declaration (`MANY`, a comprehension, a list literal) and
an element's type from the list's. A call of a declared operation is
checked against its `inputs:`: as many positional arguments as
required inputs, keywords only for optional inputs, each once, each
argument of its input's type (`type_mismatch` otherwise); a changing
operation inside a fact is `not_an_expression`; after a call, `RESULT`
has the type of the operation's `returns`. A call of a client function
is checked against its `inputs:` the same way, every argument by
position (`type_mismatch` for a keyword, too many or too few, or an
argument of another type), and has the type of its `returns:`. A property read on a value
that is no entity (`order.units_sent.made_up`) is `type_mismatch`. A
value that may be of two types (`x or y`) stands only where both fit,
and in a comparison every value one side may be is checked against
every value the other may be; an `OPTIONAL` property or
input may be `None`, so it stands only where `None` fits: an optional
input or a comparison; `[]` fits every list. An ordered list is a
`MANY ..., IN ORDER` property, a list literal, a comprehension over an
ordered list, a `+` of two ordered lists, or the result of an
operation with `ordered_by`; any other list has no order, and
`RESULT[n]` on one is `not_ordered`, through an `or` or a
comprehension of `RESULT` as well.

### 7.2 Fixed names

| word | means | from |
|---|---|---|
| `OLD` | the value before the operation, only under `ensure` | Design by Contract |
| `ACTOR` | the asker: `name`, `roles`, and the properties of its roles | Edda |
| `RESULT` | what the latest call returned; no value after `refused`; in scope only in a `then` item after a call (`not_an_expression` elsewhere) | Edda |
| `NOW` | the clock's time, in the business zone: the example's start, moved only by a step's `at:` (section 8); in generated cases the project's `clock_start:`; never the machine's clock | Edda (decision FF) |
| `TODAY` | the day of `NOW` in the business zone: the time 00:00 that day, the same value as `TIME("YYYY-MM-DD")` for that date | Edda (decision GG) |
| `DAYS` `HOURS` `MINUTES` | durations, only as `TIME + DAYS(n)` or `TIME - DAYS(n)` (7.1): a day a calendar day, an hour or a minute elapsed time | Edda (decision Z) |
| `DONE` | the verdict of a successful call, as the first `then` item, not inside an expression | Edda |
| `MANY` `IN ORDER` `DEFAULT` `OPTIONAL` `DERIVED` `TEXT` `NUMBER` `INTEGER` `TIME` `YES_NO` | type-phrase words, section 4, not inside an expression, except `TIME("...")` (7.1) | Edda |

**Time format.** A time is written `YYYY-MM-DD HH:MM`, or `YYYY-MM-DD`
for 00:00 that day, a real calendar date and clock time, in the
business zone. Inside an expression a time is always `TIME("...")`; a
plain text literal is a TEXT and never stands for a time. `at:`, a
`with:` value of a `TIME` property and `approved_at` are written the
same way, quoted.

**Days and moments.** A day (`TODAY`, `TIME("2026-10-04")`) and a
moment (`NOW`, `TIME("2026-10-04 10:00")`) are both of type `TIME`;
the checker cannot tell them apart. So `due == TODAY` compares a
property with the day, as written, and a comparison of `TODAY` with a
moment, such as `TODAY == NOW`, also passes the checker. A day counts
as its 00:00 instant. So `TODAY == NOW` is true only at 00:00, while
`<`, `>` and the other comparisons use that instant: `TODAY < NOW` is
true all day after midnight. Write a calendar-day contract against a
property that holds a day.

**The business zone and daylight saving.** The business zone is the
`zone:` of `edda.yaml` (section 9), UTC when it names none. `DAYS(1)`
keeps the wall-clock time: in `Europe/Oslo`, `TIME("2026-03-28 09:00")
+ DAYS(1)` is `2026-03-29 09:00`, 23 hours later, while `+ HOURS(24)`
is `2026-03-29 10:00`. A wall-clock time that does not exist, or
happens twice, around a daylight-saving change is read as Python's
zoneinfo reads it with fold=0: a time in the gap moves on by the gap
(`02:30` in a gap of an hour is `03:30`), and of a doubled time the
first is meant, also where `DAYS(n)` lands on one. A move by 0 of any
unit is the time itself, so `NOW + DAYS(0)` at the second `02:30` stays
there. A time is the moment it stands for everywhere it is compared:
`==`, `!=`, `<`, `in`, inside lists, and the frame rule's check that a
stored value did not change; the two `02:30`s of a doubled hour are two
times, an hour apart, though both show as `02:30`.

## 8. Examples

```yaml
examples:
  "Ta bort frees held stock":
    starts_at: "2026-10-03 09:00"
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
          - "purchase.status == removed"
          - "held.units_held == 0"
      - when: {actor: erik, call: "remove(purchase)", at: "NOW + DAYS(1)"}
        then:
          - refused: "the order is already removed"
    notes: ["erik is the shop's buyer"]
```

| key | means | why |
|---|---|---|
| `examples:` | quoted title to example; one concrete run | the acceptance criteria that run |
| `starts_at:` | the example's start, a quoted time (7.2); only on an example that uses time | the clock it runs on (below); left out, the project's `clock_start:` (section 9); an example that uses time with neither is `no_clock_start`, and a `starts_at:` on one that does not is flagged `clock_unused` |
| `given:` | a list of things to make; each item has exactly one key besides `with`: `- <entity>: <name>` or `- actor: <name>` | order-independent, schema-checked; names declared here are used below; the binding makes them (section 9); no glue is written |
| `with:` | property name to value: a number, quoted text, a quoted time, `True`, `False`, a choice value, a given name, or a flat list of those; `roles:` (a list of role names) for an actor, `fixture:` for a `spec_file` only | a property left out takes its `DEFAULT`, `[]` for `MANY`, `None` for `OPTIONAL`, otherwise unset: reading it fails the example; a derived or computed property, or an actor's `name`, is `derived_in_given`; every value is checked against the property's declared type, and a value whose property may be of several types must fit one of them as a whole, a list included: a plain text or time is `unquoted_text`, the wrong kind `type_mismatch`, a choice value not one of its property's values `unknown_choice`, a name no given declares `unknown_name`; `roles:` written as one name is `not_a_list` |
| `fixture:` | the folder under `fixtures/`; its file, and its history when present, become the given `spec_file` | the whole spec is the given, never a hand-made fragment |
| `steps:` | a list of `when` and `then`; `when` may be left out to check the given state | a flow is several steps |
| `when:` | `actor` (a declared given), `call` (a call of a declared operation with its arguments, Python call form; anything else is `not_an_expression`), `at` (optional: a time, or `NOW` moved by durations; it moves the example's clock, below) | one fixed shape; every actor is declared (`unknown_name` otherwise) |
| `then:` | with `when`: the verdict first, `DONE` or `refused: "<reason>"`, then facts; without `when`: facts only | the checker compares; `RESULT` is what the latest call returned |
| `notes:` | free text | as on stories |

After `refused`, `RESULT` has no value; a changing operation returns
nothing. Facts after `refused` check that nothing changed.

**The clock** (decision FF). Only an example that uses time has one.
An example uses time when a step has `at:`, or `NOW` or `TODAY` is
read in what the runner evaluates or the code decides for it: a step's
call and its `then` facts, the called operation's who-line conditions,
`refuse` conditions, `ensure` facts and `also_changes` paths (the
frame rule reads them), a computed property they read
and an operation they call whose `returns`, `refuse` conditions or
`ordered_by` read it (nested calls and computed properties included),
and the `always` facts of every entity the givens, the called
operations' inputs and their returns reach, as declared. Its clock
starts at its `starts_at:`, else at the project's `clock_start:`; with
neither the example is refused (`no_clock_start`). The clock stands
still: only a step's `at:` moves it, before that step's call, and it
stays there for the later steps until another `at:`. `at:` is a time
(quoted, 7.2) or an expression whose only time is `NOW`, the clock
before the step, moved by durations: `NOW + DAYS(1)`, `NOW + HOURS(2)
- MINUTES(30)`; like the call, it sees the givens and the step's
`ACTOR`, never `RESULT`. Time never goes backwards: an `at:` earlier
than the clock is refused (`clock_backwards`) when the checker can
tell, the start and every count being constants, else the example
fails at the `at:` line. An `at:` is judged as a step's call is: a
read inside it that breaks a rule fails the example at the rule's line.
`NOW` is the clock's time and `TODAY` its day
(7.2). Nothing reads the machine's clock. `no_clock_start` and
`clock_backwards` are judged only when the rest of the meaning layer
found nothing in the file, since an example's use of time is read
through expressions that must check first.

**Client functions in an example** (decision FF). A call of a client
function (section 4), wherever the runner evaluates it in an example,
answers only from the function's rows: the `gives` of the row whose
inputs are the call's values, compared as values (a time as the moment
it stands for). That holds in every phase: a step's `at:`, its call and
arguments, a `then` fact, the called operation's who-line and refuse
conditions, its `OLD` captures, its ensure facts, the frame rule's
tracking of what a named property derives from, a read's `returns` and
`ordered_by`, and an `always` fact. A call no row
covers fails the example there, `no row for shipping_cost(3)`, at the
line of the fact (or the verdict, for a step's call and for what its
operation evaluates before the code runs: its conditions, `OLD`
captures and frame rule); no phase swallows it or answers it some other
way. The real function is never called by the spec inside an example,
and nothing counts or checks calls.

**A computed property the code gives.** Wherever an example reads a
computed property, the value is the code's bound property, which may
call the client's real function itself: that is the code under test
(decision II). Edda does not work out the property's spec expression
to compare with it, whether or not the expression calls a client
function. Facts that read the property are what catch wrong code: with
the code's `parcel.cost` at 999, a `then` fact `box.cost == 5` fails,
`box.cost is 999`, and a refuse condition `parcel.cost > 100` makes a
refusal due that correct code would not give. A computed property no
fact reads is not checked. The frame rule's tracking of what a named
computed property derives from evaluates the spec's expression; that
is not a read of its value.

A failure of the generated cases (section 9) is printed in this form,
ready to paste under a story's `examples:`; pasted, it is an example
like any other. When the failing run called a client function on
inputs no row covers, the failure also lists, under that function, the
rows the pasted example needs, `- {given: {weight: 3}, gives: 12}`,
each the real function's answer, to add only once a person approves
them; if the function has no binding or is not verified, it says so
and names the calls instead.

**Keys inside keys**, for the registry, each with the section that
defines it:

| key | section | means | why |
|---|---|---|---|
| `computed:` | Entities | the one key of a computed property, holding its expression | a property that is an expression, never stored |
| `role:` | Entities | in a who-line, the role it admits | one shape for every who-line |
| `when:` | Entities | in a who-line, the condition under which the role is admitted; optional | one shape for every who-line |
| `when:` | Operations | in a `refuse` item, the condition under which the operation is refused | preconditions with a reason tests match |
| `reason:` | Operations | in a `refuse` item, the reason given when its condition holds | preconditions with a reason tests match |
| `fact:` | Operations | in an `ensure` item, the fact as an expression | the meaning beside the mechanics (decision 40) |
| `means:` | Operations | in an `ensure` item, the fact's meaning in words | the meaning beside the mechanics (decision 40) |
| `actor:` | Examples | in a step's `when`, the given actor who asks | one fixed request shape |
| `call:` | Examples | in a step's `when`, the call of a declared operation | one fixed request shape |
| `at:` | Examples | in a step's `when`, the time of the request: a quoted time, or `NOW` moved by durations; optional; it moves the example's clock | one fixed request shape; one key moves time, never a separate set and advance |
| `refused:` | Examples | the verdict of a refused call, as the first `then` item, with the reason given | tests match the reason |
| `roles:` | Examples | inside `with:`, an actor's roles, a list | the binding reads them |
| `fixture:` | Examples | inside `with:`, a spec_file's folder under `fixtures/` | the binding reads them |

## 9. Level 2: links and binding

**Links.** Built, for Python code. A link joins an operation, not a
line, to the code (decision N, Q6). `glossary.links`, one per project
folder, names the code's target, the naming rule and the code files
the link check reads; an `<entity>.links` beside `<entity>.edda` lists
only the operations of that file whose function does not follow the
rule, or that no code does yet. Both are YAML in the subset of section
2: names and `NOT_BUILT` plain, paths quoted.

```yaml
# glossary.links
target: python
rule: same_name
covers:
  - "shop/orders.py"
# order.links
links:
  remove: "shop/orders.py::take_off"
  restore: NOT_BUILT
```

| key | means | why |
|---|---|---|
| `target:` | the code's stack; `python` is the one known | the naming rule and the markers are per stack |
| `rule:` | the naming rule; `same_name`: an operation's function is the covered top-level function of its snake_case name | most operations need no line in a `.links` |
| `covers:` | the code files the link check reads, each a `.py` file relative to the project's root (Settings, below): the folder that holds `edda.yaml`, or with no `edda.yaml` the folder above the spec folder (the repository, for `specs/`); each must resolve inside the root | markers are read, and code no story reaches is flagged, only there |
| `links:` | in an `<entity>.links`: operation name to `"path::function"`, a top-level function in a covered file, or to `NOT_BUILT` | the operations that do not follow the rule |

The code carries `# <STORY-ID>@<n>`, a comment line of its own
directly above the top-level function that does an operation of that
story (above its decorators, when it has any), `n` the story's version
the code was written against: its newest approved version, or 0 for a
story never approved. Markers may stand one above the other: one
function may do operations of several stories. A marker belongs to the
def in force once the module has loaded. A later binding of the same
name (a def, class, import, assignment such as `remove = None`, `del`,
walrus, `with` or `except` target, loop target or match capture)
replaces it only when every import runs it: a direct top-level
statement of the module, or inside branches proven to run (the body of
`if` with a true constant test, the `else` of a false one, the
`finally` of a `try`, a first `match` case that is unguarded and
catches all). The marker on a replaced def is refused, naming the
replacing line; the name is then that later binding, a function only
when it is a def. A later binding anywhere else may be skipped at run
time: nested in any other branch of a compound statement (`with`, `if`,
`try`, `except`, its `else`, `for`, `while`, `match`, or any form
Python adds), or in an operand that may not be evaluated (the right of
`and`/`or`, an arm of `x if c else y`, a comprehension). It does not
replace the def: the link stays, and the marker is flagged
`maybe_replaced`, naming that line (an optional fast version under
`with suppress(ImportError):`, an `except ImportError:` fallback). A
branch that never runs counts for nothing: the body of an `if` whose
test is a false constant or `TYPE_CHECKING`, the `else` of a true one.
A bare annotation (`remove: int`) binds nothing, and neither does a
binding inside a def, class or lambda body. Every operation
resolves to exactly one function: its `.links` line, else by the rule;
none, or one in each of two covered files, is refused. An operation
with a `.links` line is never resolved by the rule: a line that fails
is refused once, at that line. An operation is
linked when it resolves both ways: to one function, and that function
carries a marker of the operation's story. A marker behind its story's
newest approved version, or on a story never approved, is flagged
(section 11).

**Reach.** Each top-level name of a covered file stands for what its
bindings resolve to: a top-level function or class of a covered file,
a covered module, or nothing (an assignment, a loop target, an import
of code no `covers:` names). A name takes its bindings in line order,
as in the marker rule above: one every import runs replaces what came
before (an import after a def of the same name stands for the imported
definition), one only some imports run adds to it (a conditional
import keeps both). An import resolves through the covered files:
`import a.b as m` makes `m` the module `a.b`; `import a.b` binds `a`,
through which `a.b` is that module; `from m import f` makes `f` whatever `f` stands
for in `m` once `m` has loaded, or the submodule `m.f` when there is
one; `as` renames. A dotted name goes on through each step: `m.f` is
what `f` stands for in module `m`, or its submodule. So re-exports and
module aliases are followed however deep (`from .impl import helper`
in a package's `__init__.py`; `from . import impl as api` there, then
`api.helper()`), each (file, name) once per lookup, so a loop ends. A
module is found by its path: an absolute one is every covered file
whose path ends in it (`a/b.py`, or `a/b/__init__.py` for a package),
a relative one is counted from the importing file's folder.

A top-level function or class is reached when a name or dotted name
in the body of a linked function, or of one reached already, stands
for it once its module has loaded. Called or passed as a value, both
count, and so does a local name that happens to be the same: the rule
errs toward reached, so it never flags code a linked function names.
A file's top level runs on import: once anything in a file is reached,
an import resolves through it, or code that runs imports it (used or
not, in a branch or not; `import a.b.c` runs `a`, `a.b` and `a.b.c`,
`from a import b` runs `a` and the submodule `b`), everything Python
evaluates as its top level runs reaches what it names (as bound at
that line, or once loaded): every module-level statement, and of a
`def` its decorators, default values and annotations, of a `class`
its decorators, base classes, keywords (`metaclass=`) and its whole
body, nested classes too, of a `lambda` its default values. Only the
bodies of functions and lambdas wait until they are called, and so do
annotations when the module has `from __future__ import annotations`.
The body of the command line block (`if __name__ == "__main__":`,
either operand order) is left out; its `else` branch, and an
`if __name__ != "__main__":`, run on import and count. A reached
function's body reaches what it names, nested functions too. A class
is one unit with its methods. A call through
`getattr`, a string or other dynamic dispatch is not seen. A covered
function or class no linked function reaches is flagged `no_story`.

Edda's own links cover `tools/check.py`, `tools/approve.py`,
`tools/view.py` and `tools/edda_binding.py`, the tools that do an
operation of a story; `tools/run.py` (it holds operations to their
rules and does none), the generators and the tests are left out.
`check` is `check.py`'s `check` (the binding has a `check` too, so
`spec_file.links` names it); `approve` and `approve_block` are both
`approve.py`'s `approve`, which carries both stories' markers; `diff`
is `check.py`'s `changes`, `story.changes`; `view` is `view.py`'s
`story_sentences`; `view_at` is the binding's `view_at`, since only
the binding picks the version and refuses "no such version"; `notes`
is `check.py`'s `notes` (`view.py` and the binding each have a `notes`
too, so `spec_file.links` names it), and the binding's `notes` calls
it. `NOT_BUILT` stays for an operation no code does yet; Edda's own
specs use it nowhere. Flagged `no_story`: the command lines (`report`,
`model_main`, each `main`), the link layer itself, which no story
covers yet, and `make_actor` and `clock`, which only the runner calls.

A binding in another stack (not built) reads the model below and
evaluates its expression trees (the whitelist is small) or calls
Python. That an approval lands in the `.vc` file on disk and survives
a re-read is the binding's test, not a level 1 fact.

**The binding.** Written once per entity, role and operation; glue
only, it holds no rule: permission, refusals and the facts after are
the spec's, and the runner checks them. A binding provides:

| part | given | gives |
|---|---|---|
| an entity's maker | the given's name, its values and a fresh work folder | the thing: an object whose attributes are the entity's properties |
| the actor maker | the actor's name, its `roles:` and its other values | the actor: `name`, `roles` and the properties of its roles |
| an operation | the asking actor (none for a read inside a fact), the required inputs by position, every optional one by keyword, `None` when the call leaves it out | the operation's return, or a refusal with its reason |
| a value space, optional | an entity and a `with:` key the types cannot generate | the values generated cases pick there (section 9, generated cases): Edda's own `spec_file` takes the fixture folders holding one `.edda` |
| a client function, optional (`FUNCTIONS`) | the function's inputs by position | the client's real result, which `edda run` holds to the rows (below); Edda's own binding has none |

The runner fills in the values a maker gets, so the binding holds no
rule of section 8. They hold every `with:` value: a value names a
given, already made, only where its property's declared type is an
entity or an actor; role names, choice values and text stay as
written; a quoted time for a `TIME` property is a time. They also
hold every stored property the given leaves out: its `DEFAULT`, `[]`
for `MANY`, `None` for `OPTIONAL`, and otherwise the binding's unset
marker. A maker keeps that marker on the thing, carrying it there
unread in the one way the binding provides for it, or puts there a
value of its own (a `spec_file`'s text comes from its fixture, never from
`with:`).

Unset is not unbound. Reading an unset property fails the example,
`<x>.<property> is unset`; leaving it unread is fine. The read itself
fails, in a fact or inside bound code: reading it from the thing, by
attribute or through the thing's own dict, or from the values a maker
gets raises at once, so not even a test of identity (`is None`) on it
can pass. Copying or listing the thing's dict or the values reads every
value in them, so it raises too when one is unset; names alone hand out
no value, and the runner reports `<x>.<property> is unset`. The marker
is a second line: should bound code reach it some other way, any
comparison, truth test, arithmetic or other use of it raises the same
way. A property the
thing does not have at all has no binding yet, and neither has an
entity or operation the binding leaves out; a story that needs one is
not run. Edda's own binding,
`tools/edda_binding.py`, binds `spec_file` (the `fixture:` folder
copied to the work folder, never the original; its one `.edda` is the
file; `history`, the `.edda.vc` beside it, its `text` the file as it
is; `blocks` and `stories` read from the copy as YAML, whether or not
it checks; `notes` from `check.py`'s `notes`, in file order), `history`
(`text`, `versions`), `note` (`file`, `story_id`, `line`, `text`),
`notes` (`check.py`'s `notes` over the given files, a file that does
not check refused "a file does not check"), `problem` (`kind`, `rule`,
`file_name`, `line`, `message`), `check` (the real checker,
`tools/check.py`, over the copy and its history), `block` (`file`,
`kind`, `name`, `text`, `versions`, `version` and `approved`), `story`
(`file`, `text`, `body_text`, `blocks` as `approve.py` works them out,
`versions`, `version`, `approved`, `pins_stale`, `changes` and
`sentences`), `version` (`number`, `approved_at`, `approved_by`,
`because`, `text`, `body_text`, `pins`, `sentences`), `pin` (`kind`,
`name`, `number`, `block`), `change` (`kind`, `line`, `sentence`),
`sentence` (`kind`, `text`, `line`, `shade`), `view` and `view_at`
(the read view of section 12, `tools/view.py`, over the model of the
copy; `view_at` gives "no such version" itself, and the runner holds
it to the spec's refusal), `diff` (`story.changes`, `check.py`'s
`changes`), and `approve` and `approve_block` (`approve.py`'s
`approve` over the copy, by the actor, at the clock's time, its
refusal as its reason). Each block, story and version is read from
the files on disk at every read and is one thing for the whole
example, so a version read before an approval is the same thing
after it. A computed property (`version`, `approved`, `pins_stale`)
is the code's own reading, not the spec's expression, so the runner
compares the two.

**The runner.** `python3 tools/run.py [--root DIR | --project DIR] [--seed N] [STORY ...]`,
over the spec folder `--project` names, else the one the project's
`edda.yaml` names (Settings, below). The spec must check first. For each
story, or each one named, and each example: make the givens through
the binding, in a fresh work folder, on the example's clock (section
8) when it uses time; for each step with `when`, move the clock by its
`at:`, check permission (section 3: any of the actor's roles passes any who-line,
condition included; otherwise refused, `"<operation> is not allowed
for <roles>"`), then call the operation, held to its rules (section 6:
the spec's refusal, `ensure` with `OLD`, `always`, the frame rule);
then judge the `then` items.
`ACTOR` is the actor of the latest step with `when`, and `RESULT` the
return of its call, both kept across later steps without `when`;
`RESULT` has no value after a refusal or before any call.
The verdict is `DONE` when the call was not refused, `refused:
"<reason>"` when it was refused with that reason; a call that raises
fails the verdict. A fact is evaluated over its parsed `ast`, form by
form of 7.1, never by `eval`: a bare lowercase name that is no given
is a choice value; entities are equal only to themselves (section 6);
a read inside a fact calls the bound operation with no actor, held to
its rules the same way; an index
out of range, a property read on no entity or `RESULT` after a
refusal fails the example. A wrong verdict or a broken rule of a
step's call ends the example; every fact of a step is judged, and a
read inside one that breaks a rule fails the example at the rule's
line. A property or operation found to have no
binding while running ends that example; the failures found before it
stay.

The binding is told the time: a binding may define `clock(now)`, which
the runner calls whenever the clock is set or moves, before anything
is read at that time: at an example's start, before its givens are
made; at each step's `at:`, before its call's permission, refusal and
`OLD` values are judged; and at the start of generated cases, with
their `clock_start:`. `now` is the clock's time, or `None` in an
example that uses no time. A time is a `datetime` with no zone, the
business zone's wall clock (its `fold` set for the second of a doubled
hour), as every time the binding is given is, a `with:` time
included. Edda's own binding has one: `approve` and `approve_block`
record its time as `approved_at`.

**The rows against the real function.** Before the stories, `edda run`
runs the rows (section 4) of each client function, every one when no
`STORY` is named, else every one the named stories reach (the functions
of their `story.blocks`, section 11), through the binding's real
function, `FUNCTIONS[name](*inputs)`, in file-name, then file order; any
other function whose rows generated cases check (below) is reported
the same way after the stories. Whenever a run checks a function's rows,
for any reason, it reports them: a `TIME` input is a time, as a `with:` time
is, and the result is compared with `gives` as a value. Per function:
`function <name>: rows passed: all <n>`; `function <name>: failing: <k>
of <n> rows failed`, then one line per failing row, `<file>:<line>:
shipping_cost(10) gives 12, but the code gave 13` (or `raised <error>`),
a `failing_function` at the row's line; or `function <name>: not run: no
binding for function <name>`. A failing row makes the exit 1. Edda
itself calls the real function nowhere else but in generated cases
(below).

Per example: passed, or failed with, for each failing `then` item,
its file and line, its text and what was found (the left side of a
comparison, or why it could not be read). Per story: `examples
passed` (every example passed), `failing` (any example failed, even
when something after the failure had no binding), or `not run` with
the reason: no binding for an operation, entity or property, or no
examples; a client function a story calls needs no binding for its
examples, whose calls answer from the rows. The clock is no reason any more: an example that uses time
runs on its clock (section 8), and one with no start is refused
before the runner sees it (`no_clock_start`); a `NOW` or `TODAY` read
on no clock all the same is Edda's own failure, exit 3 (`edda failed:
... read the clock without a start`). The
runner never reports `done` (section 11): that needs more than it
computes. A draft story runs like an approved one. Exit 0 when no
story failed; 1 when one failed or the spec does not check; 3 when
Edda itself failed (decision AA). `tools/test_run.py` points the binding at a
checker broken on purpose and sees EDDA-001 fail on the example and
the `then` line that catch the break, and holds bound operations of a
small project of its own to each rule of section 6.

**Settings.** `edda.yaml`, at the project's root (the folder that
holds the spec folder; for most projects the repository), is the one
file that says a project uses Edda and how (section 13). It is written
in the YAML subset of section 2. Every key is optional; with no file,
the spec folder is `specs` and every setting is off. An empty file is
refused (`file must be a mapping`); whether it should mean "every
default" is open.

```yaml
edda: 70
specs: specs
stack: python
problem_log: local
zone: Europe/Oslo
clock_start: "2026-10-01 09:00"
generated_cases: {on: true, runs: 100, steps: 20}
```

The file's keys, for the registry:

| key | section | means | why |
|---|---|---|---|
| `edda:` | Settings | at the root of `edda.yaml`; the revision of Edda the project is written against, a whole number of at least 1; left out, no pin | tools older than the pin refuse to run; newer ones say so and run |
| `specs:` | Settings | at the root of `edda.yaml`; the spec folder, a path relative to the root and inside it (no `..`, not absolute, and resolving inside the root once symlinks are followed); `specs` when left out | a project keeps its stories where it chooses |
| `stack:` | Settings | at the root of `edda.yaml`; the code stack, `python` the one known; left out, none is named | the import names the stack once; a `glossary.links` that names another `target:` is refused |
| `problem_log:` | Settings | at the root of `edda.yaml`; `local` or `off`; left out, or no file, `off`; with `local` the checker and the runner append each problem to `.edda/checks.log`, which `edda trend` reads (section 11) | a KB is the main home of a project's history and reads `edda check --json` and `edda run --json` (section 13); a project keeps a history of its own only when it asks for one (decision HH) |
| `generated_cases:` | Settings | at the root of `edda.yaml`; a mapping; left out, or no file, generated cases are off | one switch per project, off unless asked for |
| `on:` | Settings | inside `generated_cases:`, required; a yes/no; no default | turning them on is a choice written down, never implied |
| `runs:` | Settings | inside `generated_cases:`; a whole number of at least 1; 100 when left out | how many random runs a story gets |
| `steps:` | Settings | inside `generated_cases:`; a whole number of at least 1; 20 when left out | how many calls a run may make at most |
| `zone:` | Settings | at the root of `edda.yaml`; the business zone, a time zone name Python's zoneinfo knows, such as `Europe/Oslo`; `UTC` when left out, or with no file; any other value is refused (`wrong_type`) | `NOW`, `TODAY` and `DAYS` mean one calendar in every example (7.2) |
| `clock_start:` | Settings | at the root of `edda.yaml`; a time (7.2), quoted: the start of the clock of every example that uses time and has no `starts_at:`, and of generated cases; left out, none; a value that is no time is refused (`wrong_type`) | one start for a project's examples, each free to give its own (section 8) |

Every tool that reads the spec folder (`check.py`, `run.py`,
`approve.py`, `view.py`; `edda check`, `run`, `approve` and `view`,
section 13) reads `edda.yaml` through one reader, `tools/settings.py`,
and `trend.py` finds the log in the same root.
Each takes `--root DIR`, the project's root, Edda's own repository
when left out. A tool given the spec folder by name (`--project`,
`--folder`, `DIR`) takes the folder above it as the root and does not
read `specs:`. A tool works on one root per run: given `--root` and a
spec folder by name whose folder above is another root, it prints one
line, `--root <root> and the spec folder <folder> name two roots; give
one`, and exits 2. A spec folder given alone, to a tool or to
`check.project_of`, takes its `zone:` and `clock_start:` from the
`edda.yaml` of the folder above; `trend.py` given `--root` and a `--log` that is not
that root's log does the same (`name two logs`). With no `edda.yaml`,
every tool does what it did in revision 67, but writes no log and
exits as section 13 says. For now, an `edda.yaml` in the spec
folder (`specs/edda.yaml`, the place of revisions 64 to 67) holding
only `generated_cases:` is still read; with one at the root too, both
are refused (`two_settings`). A later revision reads only the root.
Edda's own repository has an `edda.yaml` at its root: `edda: 70`,
`stack: python`, `problem_log: local` and `clock_start: "2026-10-01
09:00"` (no `zone:`, so UTC), its stories in `specs/`.

The pin: tools older than the pinned revision refuse to run, with one
line naming both revisions (`pinned_newer`), and exit 3. Tools newer
than the pin print one flag line (`pinned_older`) and run; the exit
code does not change. A `stack:` that differs from the `target:` of
the spec folder's `glossary.links` is refused (`stack_mismatch`). The
refusals and the flag are in section 11.

Every path the host gives stays inside its root. The spec folder
(however it is named), the log folder `.edda` when `problem_log:` is
`local`, each `covers:` path and
so each `.links` path (which must be a covered file) is resolved, every
symlink followed, and one that lands outside the root is refused
(`outside_root`): the spec folder at the `specs:` line that names it,
else at the folder itself; `.edda` at itself; a `covers:` path at its
line of `glossary.links`. `covers:` and `.links` paths are relative to
the root: with `specs: docs/specs`, `"shop/orders.py"` is
`<root>/shop/orders.py`. A log named by `EDDA_LOG` or `--log` is the
operator's choice and is not held to the root.

So is every file a tool opens under the root, not only every folder,
once `edda.yaml` or a root is in play (`--root`, or a spec folder
named): `edda.yaml` itself, each `.edda`, `.edda.vc` and `.links` file,
each covered code file, and the default log `.edda/checks.log` when the
log is on. Each is
checked on the path that is opened, as it is opened: the path is
resolved, and then opened from the resolved root down, the root
itself included, without following any symlink, so a symlink put in
place after the check, the root swapped for one included, makes the
open fail instead of leading out. The folders above the root are the
host's and are not guarded. A symlink that stays inside the root is
read.
A file that lands outside is refused (`outside_root`) at line 1 of
that file, with the message `<name> resolves outside the project root:
<resolved path>`; `edda.yaml` so under `the settings do not check:`. A default log that lands outside is not written: the
output and the exit code stay as they are and one line on stderr says
so (`.edda/checks.log: outside_root: the log resolves outside the
project root: <resolved path>; nothing logged`); `trend.py` refuses to
read it, exit 1. `approve.py` holds the spec folder open from the
first read to the rename and makes its temporary file and the rename
in that open folder, so it never writes through a symlink; a rename
replaces a symlink named by the history rather than writing where it
points. With no `edda.yaml` and no root (an Edda repository without
its own `edda.yaml`), the files are read as in revision 67.

**Generated cases.** Off by default. A project turns them on with
`generated_cases:` in its `edda.yaml` (above).

The root is a mapping; `on` is required; `runs` and `steps` are whole
numbers of at least 1 (`1.0`, `0`, `-1` and `true` are refused). With no file, or `on: false`, the runner does
only what is said above and never imports Hypothesis, the one library
generated cases need (`tools/requirements.txt` pins
`hypothesis==6.141.1`); with them on and Hypothesis missing, it exits
3 with one line saying how to install it. With them on, each story's
line is followed by one more, its generated cases
(`tools/generate.py`):

1. A starting world: an actor for each role the who-lines of the
   story's operations name, `<role>_1`, with a value for each property
   of its role, as below; one to three records of every entity the binding can make,
   `<entity>_<n>`, each stored property given a value of its type. A
   choice takes one of its values; `INTEGER` and `NUMBER` favour the
   numbers the spec's own expressions name, each read with its sign
   and given its neighbours and its negation (`n > 10` gives 9, 10, 11
   and -10; `count >= -10` gives -11, -10, -9 and 10), and 0, 1 and
   -1; `TEXT` the texts they name, the empty text and short texts;
   `TIME` the times they name, a day (`YYYY-MM-DD`) or a moment, read
   as section 7.2 reads a time in `with:`, or a time in 2026; a
   reference takes an earlier record; an `OPTIONAL` or `MANY` property
   may be left out (section 8), and an `OPTIONAL` reference with no
   record to point at is. An entity whose binding gives a value space
   is made from it alone, as an example gives it, and its maker fills
   in the rest; an entity holding a required reference waits until a
   record it can point at is made, and one that never can be (it needs
   itself, or a kind that waits on it) is not made and is listed:
   `skipped entity <name>: nothing to fill its required <property>`.
   A world in which an `always` fact does not hold is thrown away.
2. Up to `steps` steps: one of the story's operations, an actor its
   who-lines name (a who-line's condition may still refuse it), and
   inputs: an entity from the records that exist, the givens and,
   for an entity the binding cannot make, what their properties reach
   at any depth, through records of other kinds too, each record once
   so a loop ends (`spec_file_1.stories[0]`,
   `shelf_1.bin.parts[0]`); any other value as above; an optional
   input given or left out, and left out when no record fits it; a
   `MANY` input may be empty, an ordered list for `IN ORDER`. Only a
   required single-record input with no record to point at keeps an
   operation from a step. The call is held to the rule wrapping of
   section 6 as a step's call is, the only oracle: permission, the
   refusal the spec gives, `ensure` with `OLD`, `always` and the frame
   rule. A call that raises, and a spec condition that cannot be
   judged, fail as they fail an example's verdict. Nothing else is
   expected.
3. Up to `runs` runs, under one seed: `--seed N`, or a random one. A
   failure is shrunk (steps and records dropped, values made simpler,
   while it still fails) and printed: what broke, at the rule's file
   and line as section 6 words it, the seed, and the run as an example
   ready to paste, titled `"generated: <operation> breaks a rule"`,
   each step's `then` the verdict the spec gives that call. A failure
   met in the starting world is titled `"generated: the starting world
   breaks a rule"` and has one fact step: the `always` fact whose call
   of a read broke a rule, written on the record it was judged on
   (`cheap(parcel_1.cost)`), or,
   when a given could not be made, a fact on the first given, as the
   example fails at its given before any step. In a story
   with `rules:`, the line its title needs under a rule's `shown_by:`
   follows (`and under the shown_by: of the rule "<rule>":` when the
   story has one rule, `of the rule it shows:` when it has more), so
   the pasted example checks; it then fails at the same rule. The
   failure prints the full command that replays it, `--seed` included.
   Replay holds only with the same command, settings, spec, code,
   Python and Hypothesis versions, and a binding whose state is the
   same each run; not across entry points (`tools/run.py` from the
   shell, a test calling its `main`). The pasted example is the lasting
   reproduction.

An operation that reads the clock, as section 8 counts it for
examples, runs on a clock stopped at the project's `clock_start:`,
never moved. A client function is the client's real function here,
since rows cannot answer random inputs: an operation whose rules make
one run (directly, through a computed property or a read they call, or
through the starting world's `always` facts) runs only when every row of
that function passes against it (above), else it is skipped, `function
<name> not verified`; a failing row found so is reported and makes the
exit 1 (above). A computed property is the code's value here too, never
compared with its spec expression (section 8): a rule that reads it
catches wrong code, and a starting world in which the code's value
breaks an `always` fact is thrown away like any other. The pasted
failure meets the same calls; a failure lists the rows it needs
(section 8).
An operation with no binding, with a required
single-record input of an entity no binding makes or reaches, calling
an operation with no binding in a condition or fact, or reading the
clock in a project with no `clock_start:` (`no clock start`), is
skipped and listed. What the binding cannot give never fails a run by
itself and never stops the runner: a property or operation with no
binding (`no binding for <entity>.<property>`), or a value nothing gave
(`<record>.<property> is unset`). A rule it meets cannot be judged,
and every other rule there still is: each `always` fact of the
starting world, and in a step each refuse condition, each `ensure`,
each `always` fact and the frame rule, path by path. An `OLD` value
it meets leaves only the facts that use it unjudged, and the call
still runs; a path or computed property the frame rule cannot read
leaves only that part unjudged (`not judged: <operation>: frame rule,
<path>`). What its unread rest could name is bounded from the spec
alone: every property its path and expression mention, and in turn
those of each computed property and read they mention (every stored
property of a `DERIVED` one), on any record of the matching entity. A
change the spec does not name fails only outside that bound; inside
it, it is not judged. Where no such bound can be built, a value of
unknown type on the way, no change to a record of an entity the path
could reach is judged, and the line says so (`<path> (no bound on what
it names: no change to <entity>, ... is judged)`). The refusal is judged condition by condition, in order: a
condition that holds still makes the refusal due, and code that does
not refuse fails; a refusal must give the reason of the first
condition that holds or of one before it that cannot be judged, and
any other reason fails, one no refusal declares included. With no
condition that holds, a refusal with the reason of one that cannot be
judged is judged only as changing nothing, and a call not refused has
every other rule judged. A read that a step's rule makes (in a refuse
condition, an `ensure`, an `OLD` value, an `always` fact, or a frame
rule path or the computed property it names) and that breaks a rule of
its own is one more failure of that step, named as the read's, `<read>
(read inside <rule>) ...`: `size (read inside put: ensure size(box) >=
0) refused: "closed", but the spec does not refuse`. It counts when
the read is made: a read taking an `OLD` value, or the source of a
comprehension around one, fails the step even when the `ensure` does
not read that value after the call (`box.count > 0 or OLD(size(box))
>= 0`). One failure met in two places is listed once, under the first
place met, in the order the step judges them: refuse conditions, `OLD`
values, frame rule paths before the call, `ensure` facts, `always`
facts. That rule is not
judged, every other rule of the step still is, and what the read could
not judge is listed with the step's. A read in a who-line's condition
still ends the step, as nothing is judged before permission. In an
example (and so in the pasted failure) a step's call still ends at
such a read, which fails it at the read's rule (section 8). A rule that
fails wins: the run fails with every failure, each rule that could not
be judged listed beside them, `<file>:<line>: not judged: <rule>:
<why>`. Once a step, or a read it makes, has found a failure, nothing
that then ends it loses that failure: the code's unset read or crash,
no binding, no row, or a rule broken by a read inside a read's
`returns` or `ordered_by` fails the step with every failure found, what
ended it added as a `not judged` line when the binding cannot give it
(`<file>:<line>: not judged: put: box_1.label is unset`), else as one
more failure. With nothing
failed, met in the starting world or its makers, the story is `not
run: <why>`; met in a step, the run ends, keeps what came before, and
the operation is skipped with that why. Runs pass only by
calling something: `<id>: generated cases: <n> runs passed; calls:
<operation> <count>, ...`, `<n>` the runs that ran to the end, each
count the calls of that operation those runs made (refused ones
included); an operation none of them called is skipped too (`never had
a record for each input`, or `not called in <n> runs`). When no run
called any operation the story is `<id>: generated cases: not run: no
call ran in <n> runs`, with the operations that never had a record for
each input, and never passed; `<id>: generated cases: not run: <why>`
when nothing is left to run (`no operations` for a story with none),
or `no starting world keeps every always-rule`. A failure is `<id>:
generated cases: failed (seed <n>)`, then `    replay: <command>`,
and makes the exit 1; the story's own line is unchanged.
On every one of these lines, passed, failed or not run, what was
skipped follows as `; skipped <operation>: <why>` or `; skipped entity
<name>: <why>`, each once, with the first why found. Edda's own specs keep generated cases off.

Linked now means the marker resolves; it changes nothing the runner
does: the runner still holds the bound operations to their rules.
Not built yet: bindings in other stacks.

**The model.** Built. `python3 tools/check.py [--root DIR] --model [DIR]` (`DIR`
the spec folder, else the one the project's `edda.yaml` names) prints one JSON model of the whole
project when no file of it is refused, and exits 0; otherwise it
prints the files and their problems as the checker's own run does and
exits 1, with no model. Its shape is `language/model.schema.json`.
With `--json` the model comes in one document with the check's files,
problems and counts (section 13). Every later tool reads this one file instead
of the YAML: the read view (built, section 12), links, a C4 Lens
import, bindings in other stacks. The same input gives the same bytes: keys in the order below,
lists in file order, files by name, JSON indented by two, ASCII only.
Every item carries its `line`, the line of its key or list item; an
expression's `line` is its value's line. A role, entity, epic, story
and operation carries its `file`; what is inside it shares that file.
A value left out is `null`, a list left out `[]`.

| field | holds |
|---|---|
| `edda_model` | the model's own version, 2 since revision 71 added the client functions (1 before); a reader refuses a version it does not know |
| `revision` | the language revision the model follows, 71: revision 71 added the client functions, revision 70 the clock of an example and the time of a step; revisions 64 to 69 left it as revision 63 made it |
| `files` | each `.edda` file: `name`, `history` (its `.edda.vc` or `null`), `blocks`: each role, entity, function and story in the order of the status lines (section 11) with `kind`, `name`, `line`, `status` (`approved` or `draft`), `version` and `pins_stale` |
| `epics` | `id`, `text`, `file`, `line` |
| `roles` | `name`, `is`, `properties`, `file`, `line` |
| `entities` | `name`, `is`, `part_of` and `part_of_line`, `properties`, `may_change` (one item per property it names, an empty one included: `property`, `line`, `arrows`: one per from-value, `from`, `to`, `line`), `always` (facts), `may_create`, `may_read`, `may_update` and `may_delete` (who-lines), `file`, `line` |
| `stories` | `id`, `sentence` (the `story:` text), `about`, `as_a`, `i_want`, `so_that`, `epic`, `tags`, `notes` and `note_lines` (the line of each note's text), `questions` and `question_lines`, `rules` (`rule`, `shown_by`, `line`), `operations` (their names), `examples`, `pins` (of the newest version: `kind`, `name`, `version`; `kind` `entity`, `role` or `function`), `versions`, `file`, `line` |
| `functions` | each client function: `name`, `is`, `inputs` (as properties), `returns` (a property, without its `name`), `examples` (the rows: `given`, each input to a `with:` value, `gives`, a `with:` value, and `line`), `file`, `line` |
| `operations` | `name`, `story`, `is`, `inputs` (as properties), `who` (who-lines), `refuse` (`when`, `reason`, `drift`, `line`), `ensure` (facts), `returns`, `ordered_by` and `also_changes` (expressions), `notes` and `note_lines`, `file`, `line` |
| a version | of a story, oldest first: `number`, `approved_at`, `approved_by`, `because`, `pins` (`kind`, `name`, `version`), `story` and `operations`: its snapshot modelled as the story is, read against the blocks it pins at their pinned versions, its lines counted from its key line, 1; `entities` and `roles`: the blocks it pins, at their pinned versions, each with `name` and `properties` typed as an entity's are; `functions`: the functions it pins, at their pinned versions, each as in `functions` (its `file` `null`); and `line` (of the version in the `.edda.vc`) |
| a property or input | `name`; `phrase` as written; `type`: `TEXT`, `NUMBER`, `INTEGER`, `TIME`, `YES_NO` (for a `DEFAULT` literal, the type it fixes), `choice` or `entity`; `values` (a choice's, in order); `entity` (a reference's or a `MANY`'s); `many`; `in_order`; `default` (the `DEFAULT` value as JSON, a choice's first value, a number read by the grammar of section 4, so `DEFAULT 01` is 1); `optional`; `derived`; `computed` (an expression; then `phrase` is `null`, and `type` and `values` are what the checker resolves the expression to: a choice with its values, a scalar word, or `null`); `line` |
| a who-line | `role`, `when` (an expression), `line` |
| a fact | `fact` (an expression), `means`, `drift`, `line` |
| `drift` | on a refusal or an `ensure` fact: `true` when `wording_drift` (section 10) flags one side of it |
| an example | `title`, `starts_at` (as written, or `null`), `clock` (`null` for an example that uses no time, else `start`, the resolved start or `null`, and `zone`), `given` (`kind`: `actor` or the entity, `name`, `with`: each property to a value, `line`), `given_line` (of the `given:` key), `steps`, `notes` and `note_lines`, `line` |
| a `with:` value | `kind`, `value`: the kind the checker resolved it to, for a property that may be of several types the one it fits, a given before a choice value as the runner reads it: `given` (a given's name), `choice`, `text`, `time`, `integer`, `number`, `yes_no`, `role` (in an actor's `roles`), `fixture` (a `spec_file`'s), or `list` with a list of these as its `value`; `null` where the property's type is not known |
| a step | `when` (`actor`, `call` as an expression, `at` as written, `time`: `null` in an example that uses no time, else `at`, the clock's time at the call, `YYYY-MM-DD HH:MM`, or `null` when it is known only when it runs, and `since`, its distance from the start in words, `line`), `verdict` (`kind`: `DONE` or `refused`, `reason` (a refusal's, else `null`), `line` (its `then` item's); `null` without `when`), `then` (the facts after the verdict, expressions), `then_line` (of the `then:` key), `line` |
| an expression | `text` as written, `line`, `ast`: the tree of `ast.parse(text, mode="eval").body` as `{"node": "<ast class>", <field>: ...}`, every field of the class in its order, lists as lists, constants as JSON values, no positions |
| `graphs` | `status_life`, `entity_map`, `role_inclusion`, `who_may`: below |

The graphs (decision N, Q7) are data: nodes and edges, each with its
`file` and `line`.

| graph | nodes | edges |
|---|---|---|
| `status_life`, one per choice property with `may_change`, an empty one included (`entity`, `property`, `file`, `line`) | each value in declared order, a computed property's as the checker resolves them: `value`, `default`, `unreached` (a value of a `DEFAULT` choice that no arrow reaches, as `unreachable_choice`) | `from`, `to`: one per value an arrow names |
| `entity_map` | each entity: `entity` | `from`, `to`, `kind` (`reference`, `many` or `part_of`), `property`, `in_order` |
| `role_inclusion` | each role: `role` | none: `includes:` left the language in revision 58, so the graph keeps its place empty |
| `who_may` | each role, operation and entity: `kind`, `name`, and an operation's `story` | role to operation, `kind` `asks`, with the who-line's `when` text; operation to its story's `about` entity, `kind` `about` |

A `with:` value carries its kind because YAML alone loses it: a given's
name, a choice value and a quoted text are all strings, and where a
property may be of several types (an actor's property two roles
declare differently) the declared type does not tell `home: primary`
from `home: "primary"`. Every other string in the model has one kind
by its place, and a `default` is read with its `type`. The `ast` is the running
Python's (3.9 or later); a reader in another stack walks it by `node`
and field name.

`python3 tools/check.py [--root DIR] --graph <entity>.<property> [DIR]` draws one
status life graph as text, one line per value in declared order: the
value, `(default)` or `(unreached)` when it is, and `-> ` with the
values it may change to; a value with no way out stands alone. For
fulfillment in `fixtures/inventory_autopart`:

```
draft (default) -> pending, cancelled
pending -> shipped, cancelled
shipped
cancelled
```

An empty `may_change` (`{status: {}}`) draws every value with no arrow.
A property with no `may_change`, that does not exist, or whose values
the checker does not know exits 2, a usage error (section 13), with
one line: `<entity>.<property> has no may_change`, `no such property:
<entity>.<property>` or `<entity>.<property> has no known values`. A project that is refused prints its problems
and exits 1, as `--model` does. The other three graphs are in the
model only; drawing them is not built.

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
  pins: [{role: shop_user, number: 1}, {entity: order, number: 2}]
  text: |
    FUL-005:
      story: "remove orders from the list"
      ...the whole story as approved, normalised...
```

| key | means | why |
|---|---|---|
| `story:` | which story this is a version of; exactly one of `story:`, `entity:`, `role:` and `function:` | one version, one story or block |
| `entity:` | which entity block this is a version of | one version, one story or block |
| `role:` | which role block this is a version of | one version, one story or block |
| `function:` | which client function block this is a version of | one version, one story or block |
| `number:` | 1, 2, 3 ... per story or block, in file order | `bad_version` otherwise |
| `approved_at:` | when, in the time format of 7.2 | the audit line |
| `approved_by:` | who: the operator's name | the audit line |
| `because:` | why, one line; optional | the audit line |
| `pins:` | on a story version: `{entity, number}`, `{role, number}` or `{function, number}` for every block the story names, in `story.blocks` order, no extras, no duplicates | the fence against a block changing under an approved story |
| `text:` | the block as approved, normalised | the exact copy |

- `.edda` is current; the agent edits it. `.edda.vc` is the file's
  history: append-only, oldest first, one version per approval of a
  story, an entity block, a role block or a function block of that file
  (role blocks in
  `glossary.edda.vc`; a version of a block of another file is
  `bad_version`, and a pin sees only the versions in the history
  beside the block's file; a history with no function version, as every
  one before revision 71, stays valid); only the operator's approve command,
  `tools/approve.py`, writes it; a repository guard keeps the agent out.
- **Normalised text.** A block's `text` is its lines from its key line
  (`order:`, `FUL-005:`) to its last line, with comments, blank lines
  and trailing spaces removed and re-indented so the key line starts at
  column 0. A flow mapping or list left open at a line's end keeps the
  block open until it closes. Quoting is tracked across lines: inside a quoted text that
  wraps, a `#`, a blank line and the spaces are kept as they are; a
  `#` right after a closing quote starts a comment, as YAML reads it. A
  version's
  `text` is a self-contained snapshot of the block as it was then: it
  must be normalised already (normalising it changes nothing), be in
  the subset of section 2 and pass the shape layer (its keys, names
  and duplicates), read as one block under the version's name,
  written out, one key per line, and name that block on its first line
  (`bad_snapshot` otherwise). A snapshot keeps the language of the
  revision it was approved under, and its bytes are never rewritten,
  so its shape layer also accepts the retired keys, with any value in
  the subset: `has:` and `includes:` in a role, `wording:` and
  `while:` in an entity (the checker's `RETIRED_KEYS`). A `.edda`
  may not use them (`unknown_key`). A snapshot is never checked for
  meaning, so an expression form a later revision removed (a slice, a
  conditional, a text where a TIME is expected, `startswith`,
  `min`, `max`, a second way) stays as it was written. It
  is never compared with the current block by the checker; `approved`
  does that, and only against the newest version.
- **Draft, story.** Its `body_text` differs from the newest version's:
  `body_text` is `text` with only `about:`, `as_a:`, `rules:`,
  `operations:` and `examples:` kept and every note removed.
  The sentence,
  `i_want`, `so_that`, `epic`, `tags`, notes, questions, comments and
  blank lines change freely. **Draft, block.** Its `text` differs from
  the newest version's.
- **Pins.** A story version records every block the story named
  (section 11, `story.blocks`) at its version then, in that order. The
  version's pins are its own record from approval time: the approve
  operation's ensure facts guarantee the set and the order; the checker
  never recomputes them from today's files, so a later who-line or
  re-ordering cannot invalidate an old version. The checker
  does verify that every pin points at an existing version of a block
  that exists, that no `(kind, name)` repeats, that a story version has
  pins and a block version has none (`bad_pin` otherwise). A newer block
  version than the pin in the story's newest version makes the pins
  stale (`story.pins_stale`), shown on the story's status line as
  "pins stale". Not a draft and not a flag; older versions are never
  looked at.
- **Approve a story.** Refused when the file does not check ("the file
  does not check"), when a named block is not approved, that is has no
  version or is itself a draft ("approve its blocks first"), or when
  the story is approved and no pin is stale ("nothing to approve: the
  story matches its newest version and its pins are current").
  Otherwise the history becomes exactly the old versions followed by
  one: the next number, the normalised text, the asker, the time, the
  `because`, and the pins. Blocks first, then stories; for Edda itself
  the ten entities and two roles, then EDDA-001.
- **Approve a block.** A role, entity or function block. Refused when
  the file does not check or when the
  block is approved ("nothing to approve: the block matches its newest
  version"). Otherwise the history becomes exactly the old versions
  followed by one, without pins. A story names among its blocks
  (section 11, `story.blocks`) every client function the runner may
  make run for it: in any expression it may evaluate for the story's
  examples and operations, the `always` facts their calls are held to
  included, and in the story's own expressions; so approving
  the story needs the function approved first ("approve its blocks
  first"), and a newer version of the function makes its pins stale.
- **The approve command** is `tools/approve.py`:

  ```
  python3 tools/approve.py NAME --by OPERATOR [--because TEXT]
      [--at "YYYY-MM-DD HH:MM"] [--dry-run] [--root DIR | --folder DIR]
  ```

  `NAME` is a story id or a role, entity or function name, looked up across the
  spec folder (the one the project's `edda.yaml` names, section 9,
  unless `--folder` names another); `--by` is
  `approved_by`; `--at` is `approved_at`, now in the host's local time
  when left out: the operator runs the command on that host, and its
  zone is taken as the business zone of `NOW` (section 7.2).
  `because:` is written only when `--because` is given, and is one
  line: a `--because` with a line break (any character Python's
  `str.splitlines()` splits on) is refused ("because is one line"). It
  refuses as the two items above say, in that order, with those
  messages; a
  file does not check when it or its history has a refusal, flags
  aside. Otherwise it appends one version to the `.edda.vc` beside the
  block's file (creating it when there is none): the next number, the
  normalised text, and for a story a pin on every block of
  `story.blocks`, in that order, at its version. When the history has
  versions, its old bytes are kept as they are, comments included, and
  the new version follows; when it has none (`[]`), the new file is the
  new version alone. One approval runs at a time per project folder:
  it holds a lock on the folder from its first read to the rename,
  reads the folder's `.edda` and `.edda.vc` files once, and computes
  and checks everything from that one reading. Before writing, the
  file and its history are checked as they would be, on a copy of the
  reading: no refusal, the old versions unchanged, the new version's
  number, text and pins as above and its `approved_at`, `approved_by`
  and `because` read back exactly as given, every block of `story.blocks` approved, and the
  story or block approved with its pins current; then the folder's
  files are read again, and if any changed since the reading nothing
  is written ("the folder changed while approving; nothing written").
  The file is
  written through a temporary file and a rename. `--dry-run` prints the
  new version and writes nothing. Who runs the command is not checked
  by it: that is the repository guard's.
- **Wording drift.** In a draft, a pair whose one side differs from the
  newest version while the other does not. There are two pairs: a
  refusal's `when` and `reason`, and an ensure item's `fact` and
  `means`, both in an operation of the same name in both versions,
  matched by position in their list (the first refusal with the first
  refusal) and only when both versions have an item at that position;
  the `fact`/`means` pair only when the newest version's item has a
  `means`. A function's `is:` has no such partner: its rows are its
  mechanics, and a change to either makes the block a draft, which the
  operator reads whole. Flagged `wording_drift` at the changed side. Shown side by
  side in the diff
  view, in the warning shade in the read view. The agent re-reads the
  meaning against the mechanics and fixes or justifies it; approval
  clears it.
- **What changed** is derived (`story.changes`, section 11): added and
  removed lines between the newest version's text and the current text.
- Git keeps the history of both files; the KB keeps the audit copy.

## 11. The checker

**Layers.** Each file is read in four layers; a layer runs only when
the earlier ones found nothing, and every independent problem of the
first failing layer is reported, ordered by file, line, rule name.
Problems in the `.vc` carry that file's name; every `.vc` of the
project is read, with or without a `.edda` beside it, and a block's
versions live in the history beside its file. A `with:` value's
quoting follows its property's declared type, so that one quoting
check runs in the meaning layer. Two problems are
dependent: a block with an unknown key reports only that, never a
missing key (the unknown key is usually the missing one misspelt); an
anchor and its aliases are one problem, at the anchor.

1. source: `not_yaml`, `yaml_feature`;
2. shape: `unquoted_text`, `not_a_list`, `wrong_type`, `missing_key`,
   `unknown_key`, `bad_name`, `declared_twice`;
3. meaning: `unknown_name`, `unknown_choice`, `bad_type_phrase`,
   `not_an_expression`, `type_mismatch`,
   `returns_and_ensure`, `wrong_file`, `not_ordered`,
   `computed_cycle`, `derived_in_given`, `wider_than_entity`, `no_rule`,
   `contradicting_rows`,
   then, only when those found nothing in the file, `no_clock_start`
   and `clock_backwards` (section 8);
4. history and flags: in a `.edda.vc`, `bad_version`, `bad_pin` and
   `bad_snapshot`; in a `.edda`, every flag. The checker's fixture
   report names the layer that refused a file, or says `flagged` or
   `passes`.

Then links, in a project with a `glossary.links` whose four layers
refused nothing (a project without one has no link layer): the
`.links` files through the source and shape rules above (`not_yaml`,
`yaml_feature`, `unquoted_text`, `not_a_list`, `wrong_type`,
`missing_key`, `unknown_key`, `bad_name`, `declared_twice`), then
`unknown_link`, `no_function` and `bad_marker` over the `.links` files
and the covered code; only when none of those, the flags `stale_link`,
`unapproved_link`, `maybe_replaced` and `no_story`. The plain run lists each `.links`
file, `glossary.links` first, then each covered file, after the
project's other files; the fixture report says `caught by links`.

**From the schema to a rule.** The shape layer is the JSON Schema plus
the quoting rule; a schema failure becomes: `additionalProperties`,
`unknown_key`; `required`, `missing_key`; `type` with an array
expected, `not_a_list`; any other `type`, `minProperties`,
`maxProperties`, `minItems`, `minLength`, `const` or `not`,
`wrong_type`; `propertyNames`, `pattern` or `enum` on a name,
`bad_name`. For `anyOf` and `oneOf` the checker takes the branch whose
`type` matches the value's YAML kind (a mapping, a list, a scalar),
drops the wrapper and maps that branch's own failures, each with its
own path; when no branch matches the kind, `wrong_type`. An empty expression or type phrase is
`wrong_type` (a text was expected, no value was given). The schemas
hold no history policy: sequence, pins and snapshots are layer 4.

**Anchors.** A problem's `line` is the line of the key or value its
message names: the key for `unknown_key` and `missing_key` (the block's
key line), the second declaration for `declared_twice`, the
expression's line, the property's line for `unknown_choice`,
`bad_type_phrase` and `unreachable_choice`, the first property's line
for `computed_cycle`, the `then` item's line for
`not_ordered`, the operation's key line for `returns_and_ensure`, the
entity's key line for `wrong_file` on a part, the example's title
line for `no_rule` and `no_clock_start`, the `at:` line for
`clock_backwards`, the later row's line for `contradicting_rows`, the `starts_at:` line for `clock_unused`, the title's line under `shown_by:` for
`unknown_name` on a title, the
story's key line for `wrong_file`, `no_example` and
`question_on_approved`, the changed
side's line for `wording_drift`, the refusal's `when:` line for
`dead_refusal`, the fact's line for `empty_ensure`, `forbidden_change`
and `conflicting_ensure` (of two facts, the later), and in the `.vc` the version's
`number:` line for `bad_version`, `bad_snapshot` and a story version
without pins, the version's `pins:` line for pins on a block version,
and the pin's line for every other `bad_pin`. In the link layer: the
key's or item's line in a `.links`, the `rule:` value's line for an
operation resolved by the rule, the marker's line for a marker, and the
`def` line for a function without its marker and for `no_story`.

**Refusals** (`problem.kind == refused`), with their messages:

| rule | when | message |
|---|---|---|
| `not_yaml` | the file does not parse | `not YAML: <parser message>` |
| `yaml_feature` | an anchor (its aliases with it), tag, directive, `<<`, complex key, tab, second document, single quotes, a folded scalar, a `|` scalar outside `.vc` text, an odd or jumping indentation, an expression, type phrase or example title (as a key or under `shown_by:`) on more than one line, a quoted key, a key with a space before its colon or an explicit `?`, `DONE` anywhere but first under `then`, or a role, entity, story, operation or example in flow form (section 2), at its key | `anchors and aliases are not allowed` (and likewise for each feature); `a key is plain, not quoted`; `a key is written name: with no ? and no space before the colon`; `DONE is allowed only as the first then item`; `a block is written one key per line, not in { } or [ ]` |
| `unquoted_text` | free text or an expression written plain | `quote the <key>; an unquoted # drops the rest of the line` |
| `not_a_list` | a repeated thing written as a scalar or a mapping, an actor's `roles` as one name among them | `<key> must be a list, one <item> per line`, the item being fact, refusal, who-line, given, step, item, note, question, pin, expression, path, rule, example, tag or role |
| `wrong_type` | a mapping, list or scalar where another is expected; an empty list where one item is needed; a given item without exactly one name; a `with` value that is not flat; an empty expression or type phrase; a quoted `DONE` after the first `then` item; a `.vc` version or pin naming no block | `<key> must be a <mapping, list, text, number or yes/no>`, or `<key> must be a <kind> or a <kind>` where the schema allows several; `<key> must be a list with at least one <item>`; `given must name exactly one thing besides with`; `<key> must be a number, text, yes/no, name or a flat list of those`; `<key> expects a text, no value was given`; `<key> expects an expression, not DONE`; `then must start with DONE or refused` for a first `then` item under a `when` that is neither; `<version> must name one of story or entity or role`; `<pin> must name one of entity or role` |
| `missing_key` | a required key absent; an input a function's row leaves out | `<block> needs <key>:`, the block named by kind and name: `operation remove`, `entity order`, `refusal 2`, `step 1`, `row 2`, `file` |
| `unknown_key` | a key the schema does not name; an input a function's row names that the function has not | `unknown key: <key>` |
| `bad_name` | a name not snake_case, an id not `ABC-123`, a name, choice value or role-list item that is a Python keyword (`True` and `False` as keys included), a quoted name, a quoted `DONE` as the first `then` item, a role-list item that is no name | `not a name: <text>`, the text as written; for a quoted name `not a name: "<text>" (a name is plain)` |
| `declared_twice` | a duplicate key, a name declared twice in one project, a function name that is also a role, entity, operation or function, or one of Edda's own words, a given name used twice in one example, a role property named `name` or `roles`, an example named twice under a story's `rules:`; at the second | `declared twice: <name>`; for an example, `declared twice: <title>`; for one of Edda's own words, `declared twice: <name> (a word of Edda's own)` |
| `unknown_name` | an undeclared lowercase word, actor, entity, role, epic, operation, property, fixture or given; a bare name that is neither in scope nor a choice value compared with a choice property; a `shown_by` title that names no example of the story | `unknown name: <name>`; for a `shown_by` title, `unknown example: <title>` |
| `unknown_choice` | a choice value that is not one of its property's values: in a comparison, `may_change` or a given | `not one of <property>'s values: <value>` |
| `bad_type_phrase` | a type phrase outside the grammar; a function's input or result that is not `TEXT`, `NUMBER`, `INTEGER`, `TIME`, `YES_NO` or a choice | `not a type phrase: <text>`; with a reason, `not a type phrase (<reason>): <text>`, for a function's `not a type phrase (a function takes and gives TEXT, NUMBER, INTEGER, TIME, YES_NO or a choice): <text>` |
| `not_an_expression` | a string Python cannot parse, a node outside 7.1, a step in disguise, a changing call inside a fact, a `call` that is not a call of an operation, `RESULT` outside a `then` item after a call (a `call` itself never sees it) | `not an expression: <text>`; with a reason, `not an expression (<reason>): <text>` |
| `type_mismatch` | a list word on a non-list, `len` on a number, `+` between a list and a number, a NUMBER or yes/no as an index, an index on a text, a `TIME` call whose argument is not one quoted time in the format of 7.2, a comparison of two values of different kinds (`==`), of a non-element with a list (`in`) or of anything but two numbers, texts or times (`<`), a call with the wrong inputs, `None` for a required input, a value of two possible types where one does not fit, a property read on a non-entity, an unordered list for an `IN ORDER` input, a choice value outside the expected list, `ordered_by` on a result that is no list, `may_change` on a property that is no choice, a given value of another type than its property or fitting none of its possible types, a duration (`DAYS`, `HOURS`, `MINUTES`) anywhere but after `TIME +` or `TIME -` or with a count that is no INTEGER, an `at:` that is neither a time nor `NOW` moved by durations, a `starts_at:` that is no time, a client function called with a keyword or the wrong inputs, a row's value of another type than its input or result, or a row's time that is no time | `<what> expects <kind>: <text>`; for a comparison `== expects two values of one kind: <text>`, `in expects an element of the list: <text>`, `in expects a text in a text: <text>`, `in expects a list or a text: <text>`, `< expects two numbers, two texts or two times: <text>`; `may_change expects a choice property: <property>`; `TIME expects one quoted time, "YYYY-MM-DD HH:MM" or "YYYY-MM-DD": <text>`; `DAYS expects to move a time, as TIME + DAYS(n) or TIME - DAYS(n): <text>`, `DAYS expects one INTEGER: <text>` (and so for `HOURS` and `MINUTES`); `at expects a time, "YYYY-MM-DD HH:MM", or NOW moved by DAYS, HOURS or MINUTES: <text>`; `starts_at expects a time, "YYYY-MM-DD HH:MM" or "YYYY-MM-DD": <text>` |
| `returns_and_ensure` | a read key with a write key, or `ordered_by` without `returns`, or `also_changes` without `ensure` | `returns and ensure on one operation: <name>`, `returns and also_changes on one operation: <name>`, `ordered_by needs returns: <name>`, `also_changes needs ensure: <name>` |
| `wrong_file` | a story in another entity's file; a part outside its owner's file | `story <id> is about <entity> and belongs in <entity>.edda`; `entity <name> is part of <owner> and belongs in <entity>.edda` |
| `not_ordered` | `RESULT[n]` on an unordered return, through an `or` or comprehension of `RESULT` as well | `<operation> gives no order; RESULT[<n>] needs ordered_by or IN ORDER` |
| `computed_cycle` | a computed property whose expression reads itself, directly or through other computed properties (bare in its own entity, through a path into another, or inside the refuse conditions, returns or ordered_by of a called operation, its inputs at their declared types); each group of properties that loop through one another once, at its first property in file-name, then file order | `computed properties loop: <a> -> <b> -> <a>`, a shortest loop from that first property; each property as `<entity>.<property>` when the loop crosses entities |
| `derived_in_given` | a `with:` value for a derived or computed property, or for an actor's `name` | `<property> is derived and cannot be given`, `<property> is computed and cannot be given`, `name is fixed and cannot be given` |
| `wider_than_entity` | `who:` admits a role the `about` entity's matrix never names | `<operation> admits <role>, which <entity> does not` |
| `no_rule` | a story with `rules:` has an example no rule names | `example "<title>" belongs to no rule` |
| `contradicting_rows` | two rows of a client function with the same inputs and different results, values compared as values (section 4), judged once every row's values check; at the later row | `<function>: rows <i> and <j> give different results for the same inputs` |
| `no_clock_start` | an example that uses time (section 8) with no `starts_at:` and no project `clock_start:` | `example "<title>" uses time (<how>) but has no start; give it starts_at: or the project clock_start:`, `<how>` the first use found: `reads NOW`, `moves time with at:`, `reads <entity>.<property>, which reads the clock` or `calls <operation>, which reads the clock` |
| `clock_backwards` | an `at:` the checker can tell is earlier than the clock before it (section 8) | `at <at> is before the clock's <time>; time never goes backwards`, an expression followed by its time in brackets |
| `bad_version` | a `.vc` number out of sequence, an unknown story or block, or a version of a block of another file | `<kind> <name> v<n> out of sequence; expected v<m>`; for an unknown block, `<kind> <name> v<n>: no such <kind>`; for another file's block, `<kind> <name> v<n>: belongs in <file>.edda.vc` |
| `bad_pin` | a pin on a block version, a story version without pins, a duplicate `(kind, name)`, a pin to no such block or version; a version exists when a history of the project holds it | `pin <kind> <name> v<n>: no such version`, `pin <kind> <name> v<n>: no such <kind>`, `pin <kind> <name> v<n>: pinned twice`, `story <id> v<n>: no pins`, `<kind> <name> v<n>: a block version has no pins` |
| `bad_snapshot` | a version's text that is not already normalised, is outside the subset of section 2 or fails the shape layer (a bad name, a wrong key, a duplicate; a retired key of section 10 is not wrong here), does not read as one block under the version's name, or does not name it on its first line | `text of <kind> <name> v<n> is not a normalised block` |
| `unknown_link` | a `.links` naming no known target or rule, no `.py` file, a file Python cannot read, no `.edda` beside it, no operation of that file or a file it does not cover; an exception written neither `"path::function"` nor `NOT_BUILT`; a marker naming no story | `unknown target: <x>`, `unknown naming rule: <x>`, `no such Python file: <path>`, `not Python (<reason>): <path>`, `no such file: <entity>.edda`, `unknown operation: <name>`, `not a covered file: <path>`, `not a link (write "path::function" or NOT_BUILT): <text>`, `unknown story: <id>` |
| `no_function` | an operation that resolves to no function or to two: an exception naming a function its file does not have; by the rule, no covered file, or more than one, with a top-level function of its name | `no function <function> in <path>[, replaced by <how> at line <m>]`, `no function <operation> for <id> in the covered files[ (<path>::<operation>, replaced by <how> at line <m>)]`, `two functions for <operation> of <id>: <path>::<function>, ...; name one in <entity>.links` |
| `pinned_newer` | an `edda.yaml` pinning a revision newer than the tools (section 9) | `edda.yaml pins revision <n>; these tools are revision <m>` |
| `stack_mismatch` | an `edda.yaml` whose `stack:` differs from the `target:` of the spec folder's `glossary.links` | `stack is <stack> but <glossary.links> names target <target>` |
| `two_settings` | an `edda.yaml` at the root and one in the spec folder, at the second | `two edda.yaml files; keep <edda.yaml> and move generated_cases: into it` |
| `outside_root` | a path the host gives that resolves, symlinks followed, outside the project's root: the spec folder, the log folder `.edda` (when the log is on), a `covers:` path, or a file a tool opens under the root (`edda.yaml`, a `.edda`, `.edda.vc` or `.links` file; section 9) | `<what> resolves outside the project root: <resolved path>`, `<what>` being `the spec folder`, `the log folder .edda`, the `covers:` path or the file's name |
| `bad_marker` | a comment that starts like a marker but is not `# <STORY-ID>@<n>`; a marker not on a line of its own directly above a top-level function; a version its story does not have; one story twice on one function; a marker above a function doing none of its story's operations; a function doing an operation without its story's marker; a marker on a def that a later binding of its name replaces, one every import runs: a direct top-level statement, or in a branch proven to run (section 9) | `not a marker (write # <STORY-ID>@<version>): <text>`, `a marker is a line of its own directly above a function: <text>`, `<function> at line <n> is replaced by a def, a class or a binding at line <m>, so the marker is on code that does not run: <text>`, `<id> has no version <n>`, `marked twice: <id> on <function>`, `<function> does no operation of <id>`, `<function> does <operation> of <id> and carries no # <id>@<version>` |

**Flags** (`problem.kind == flagged`):

| rule | when | message |
|---|---|---|
| `unreachable_choice` | a value of a `DEFAULT` choice that is neither its default nor the target of a `may_change` arrow; a choice without `DEFAULT` has no default and is not looked at | `no change reaches <property>'s value: <value>` |
| `no_example` | a story with no example | `story <id> has no example` |
| `dead_refusal` | a refusal that can never be the one given: every case it covers, an earlier refusal of the operation already covers (the analyser, below) | `<operation>: refusal <n> can never be given; refusal <m> covers it`; with more, `refusals <m> and <k> cover it`, only the earlier refusals needed |
| `conflicting_ensure` | two `ensure` facts of one operation on the same property with no case in common, or an `ensure` fact with no case in common with an `always` fact of an entity it reaches (the analyser, below) | `<operation>: ensure <i> and ensure <j> cannot both hold`; `<operation>: ensure <i> cannot hold with always <k> of <entity>: <fact>` |
| `empty_ensure` | an `ensure` fact that cannot fail: one comparison `==`, `>=` or `<=` whose two sides are the same expression, or a fact that calls its own operation | `<operation>: ensure <i> cannot fail; both sides are the same: <fact>`; for a call of its own operation, `<operation>: ensure <i> cannot fail; it calls <operation> itself: <fact>` |
| `forbidden_change` | an `ensure` fact that sets a choice property with `may_change` of an input of the operation to one value, from a start value that `may_change` gives no arrow to that value and that one start state has while passing every refusal, meeting a who-line and holding every `always` fact of the things read; checked only when the property is neither computed nor `DERIVED`, every refusal, who-line and `always` fact involved can be read and no `always` fact of another entity reaches the input's entity, else skipped; the start values of a `DEFAULT` choice are its default and the values an arrow reaches (the analyser, below) | `<operation> sets <property> to <value> from <start> or <start>, which may_change does not allow` |
| `question_on_approved` | a question on an approved story | `story <id> is approved and still has a question` |
| `wording_drift` | section 10 | `<id> <operation>: <side> changed, <other> did not` |
| `stale_link` | a marker whose version is behind its story's newest approved version | `<id>@<n> is behind its approved v<m>` |
| `unapproved_link` | a marker of a story with no approved version yet | `<id> has no approved version yet` |
| `maybe_replaced` | a marker on a def that a later binding of its name may replace on some imports: one nested in a branch of any compound statement not proven to run (`with`, `if`, `try`, `for`, `while`, `match`), or in an operand that may not be evaluated (section 9) | `<function> at line <n> may be replaced by a def, a class or a binding at line <m>, which not every import runs: <text>` |
| `no_story` | a top-level function or class of a covered file that no linked function reaches (section 9) | `no linked function reaches <name>` |
| `pinned_older` | an `edda.yaml` pinning a revision older than the tools (section 9); the tool runs | `edda.yaml pins revision <n>; these tools are revision <m>` |
| `clock_unused` | a `starts_at:` on an example that uses no time (section 8) | `example "<title>" uses no time; its starts_at: is never read` |

**Failures** (found by the runner, section 9; not the checker's):

| rule | when | message |
|---|---|---|
| `failing_example` | an example of a story whose operations are bound fails: a wrong verdict, a `then` fact that does not hold, a given that cannot be made, an `at:` that would move the clock back, or a call or a read inside a fact that breaks a rule of its operation; one per failure line, at that line | the runner's line under `example "<title>" failed`: `<file>:<line>: then <text>: found <found>`, or `<file>:<line>: <found>` |
| `failing_case` | a generated case breaks a rule (section 9); one per broken rule the failure names, at the rule's line, or one at no line when it names none | `<id>: generated cases: failed (seed <n>)`, then `<file>:<line>: <what>` for each broken rule |
| `failing_function` | a row of a client function that its bound real function does not give back (section 9): another result, or an error; one per failing row, at the row's line | `function <name>: failing: <k> of <n> rows failed`, then `<file>:<line>: <name>(<inputs>) gives <result>, but the code gave <found>` or `<name>(<inputs>) raised <error>` |

**Dimensions.** Every problem, a refusal, a flag or a failure, carries
six dimensions (decision U, kb:9379257), so problems can be counted and
crossed by kind. Four are fixed per rule, in the table below and so in
the registry; `where` comes from the problem's line and `found by` from
the tool that reports it.

| dimension | values | set by |
|---|---|---|
| what went wrong | `unreadable`, `unknown word`, `wrong kind`, `misplaced`, `contradiction`, `weak check`, `out of date`, `code differs` | the rule, with a sub-kind |
| fix | `missing`, `wrong`, `extra` | the rule: add, change or delete |
| acts | `agent`, `person`, `language` | the rule; a person may re-tag one problem as `language` |
| level | `blocks`, `warns`, `note` | the rule: a refusal or a failure blocks, a flag warns, a status only is a note |
| where | `role`, `entity property`, `status rules`, `always`, `permissions`, `function`, `story`, `story rules`, `operation who`, `refuse`, `ensure`, `returns`, `example given`, `example step`, `history`, `code`, `unknown` | the problem's line |
| found by | `reading`, `history`, `analyser`, `example run`, `generated case`, `person review` | the tool |

`what went wrong`: `unreadable`, the file is not valid Edda text;
`unknown word`, a name or value not declared or declared twice; `wrong
kind`, an expression of the wrong type or form; `misplaced`, the right
thing in the wrong place or scope; `contradiction`, rules that cannot
all hold; `weak check`, the spec tests too little; `out of date`,
approval and history; `code differs`, the code does not do what the
spec says (level 2). `acts`: `agent`, the agent fixes it alone;
`person`, it needs meaning or approval; `language`, the language cannot
say it, which is a bug in the language. A contradiction defaults to
`person`: a clash between two rules is usually a question of what the
customer meant. No rule is a `note` yet: `pins stale` is a status, not
a problem, and is neither counted nor logged.

| rule | went wrong | sub | fix | acts | level |
|---|---|---|---|---|---|
| `not_yaml` | unreadable | syntax | wrong | agent | blocks |
| `yaml_feature` | unreadable | banned YAML | extra | agent | blocks |
| `unquoted_text` | unreadable | quoting | wrong | agent | blocks |
| `not_a_list` | unreadable | shape | wrong | agent | blocks |
| `wrong_type` | unreadable | shape | wrong | agent | blocks |
| `missing_key` | unreadable | shape | missing | agent | blocks |
| `unknown_key` | unreadable | shape | extra | agent | blocks |
| `bad_name` | unknown word | spelling | wrong | agent | blocks |
| `declared_twice` | unknown word | twice | extra | agent | blocks |
| `unknown_name` | unknown word | undeclared | missing | agent | blocks |
| `unknown_choice` | unknown word | not in list | missing | agent | blocks |
| `unknown_link` | unknown word | link name | wrong | agent | blocks |
| `bad_type_phrase` | wrong kind | type phrase | wrong | agent | blocks |
| `not_an_expression` | wrong kind | outside whitelist | wrong | agent | blocks |
| `type_mismatch` | wrong kind | types | wrong | agent | blocks |
| `not_ordered` | wrong kind | order assumed | missing | agent | blocks |
| `derived_in_given` | wrong kind | given a computed | extra | agent | blocks |
| `returns_and_ensure` | misplaced | read and change | wrong | agent | blocks |
| `wrong_file` | misplaced | file | wrong | agent | blocks |
| `wider_than_entity` | misplaced | permission scope | extra | person | blocks |
| `computed_cycle` | misplaced | computed loop | wrong | person | blocks |
| `no_rule` | misplaced | example ungrouped | missing | agent | blocks |
| `contradicting_rows` | contradiction | function rows | wrong | person | blocks |
| `no_clock_start` | weak check | no clock start | missing | agent | blocks |
| `clock_backwards` | contradiction | time backwards | wrong | agent | blocks |
| `bad_version` | out of date | history broken | wrong | person | blocks |
| `bad_pin` | out of date | history broken | wrong | person | blocks |
| `bad_snapshot` | out of date | history broken | wrong | person | blocks |
| `no_function` | code differs | no function | missing | agent | blocks |
| `bad_marker` | code differs | marker | wrong | agent | blocks |
| `pinned_newer` | out of date | pin ahead | wrong | person | blocks |
| `stack_mismatch` | contradiction | stack | wrong | person | blocks |
| `two_settings` | misplaced | settings file | extra | agent | blocks |
| `outside_root` | misplaced | outside root | wrong | person | blocks |
| `unreachable_choice` | contradiction | status rules | missing | person | warns |
| `no_example` | weak check | no example | missing | agent | warns |
| `dead_refusal` | contradiction | refusals | extra | person | warns |
| `conflicting_ensure` | contradiction | ensures | wrong | person | warns |
| `empty_ensure` | weak check | says nothing | wrong | agent | warns |
| `forbidden_change` | contradiction | status rules | missing | person | warns |
| `question_on_approved` | out of date | open question | missing | person | warns |
| `wording_drift` | out of date | meaning drift | wrong | person | warns |
| `stale_link` | code differs | stale link | wrong | agent | warns |
| `unapproved_link` | out of date | not approved | missing | person | warns |
| `maybe_replaced` | code differs | marker | wrong | agent | warns |
| `no_story` | code differs | unlinked code | missing | agent | warns |
| `pinned_older` | out of date | pin behind | wrong | person | warns |
| `clock_unused` | misplaced | unused start | extra | agent | warns |
| `failing_example` | code differs | behaviour | wrong | agent | blocks |
| `failing_case` | code differs | behaviour | wrong | agent | blocks |
| `failing_function` | code differs | behaviour | wrong | agent | blocks |

`where` is read from the problem's file and line: any line of a
`.edda.vc` is `history`, of a `.links` or a code file `code`; in a
`.edda`, a problem names a line, not a key, so the place is named only
when every key and item that starts on the line maps to the same one
place, and a line that also holds a key of another place or of none (a
block written in flow form, `box: {is: ..., may_read: [...]}`) is
`unknown`. The places: a role's block, `role`; a client function's block, `function`; an entity's `properties`, `entity property`;
`may_change`, `status rules`; `always`, `always`; `may_create`,
`may_read`, `may_update` and `may_delete`, `permissions`; a story's key
or its own keys (its own `notes` among them), `story`, but `rules`,
`story rules`; an operation's `who`, `operation who`; `refuse`,
`refuse`; `ensure` and `also_changes`, `ensure`; `returns` and
`ordered_by`, `returns`; an example's `given` and `starts_at`,
`example given`; `steps`, `example step`. Anything else (`epics`, an entity's or an
operation's key line, `is`, `part_of`, `inputs`, an operation's or an
example's `notes`, an example's title, a file that does not parse, a
problem with no line) is `unknown`; it is never guessed.
`found by`: `history` for `bad_version`, `bad_pin`, `bad_snapshot`,
`wording_drift`, `question_on_approved`, `stale_link` and
`unapproved_link`; `analyser` for the analyser's four flags; `reading`
for every other rule of the checker; `example run` for
`failing_example` and `failing_function`; `generated case` for `failing_case`. `person review`
is for a problem a person finds; no tool sets it yet.

**Re-tagging as `language`.** A person who finds that a problem is the
language's fault, not the spec's, writes the comment `# edda: language`
at the end of the problem's line. That problem's `acts` is then
`language`; nothing else changes: a comment is never part of the body
(section 1), so the text, its version and every check stay as they
were, and the grammar needs no change.

**Counting and the log.** The checker's plain run ends with one line
counting the problems of the spec folder by `what went wrong`, in the order of
the table above, for example `3 contradiction, 1 weak check`; nothing
when there are none. The fixtures are never counted or logged: their
problems are there on purpose. The runner ends the same way, counting
its failures. The log is opt-in (decision HH, amending decision Y for
this case): only in a project whose `edda.yaml` says `problem_log:
local` (section 9) does each run of either append one line per problem
to `.edda/checks.log` at the project's root, the folder that holds
`edda.yaml` and the spec folder (for Edda itself, which turns it on,
the repository's root); keep `.edda/` out of git, as Edda's own
`.gitignore` does. With `problem_log: off`, with none, or with no
`edda.yaml`, nothing is written and no `.edda/` is made. A KB, the
main home of a project's history, reads `edda check --json` and `edda
run --json` instead (section 13). A line is one JSON object: `date` (local time with its
offset, to the second), `rule`, `file` (from the project's root),
`line` (`null` when there is none), `category`, `sub`, `fix`, `acts`,
`level`, `where`, `found_by` and `commit` (the project's short SHA, or
`none` outside git). A run with no problems appends nothing. Writing
the log never changes the output or an exit code: a folder that cannot
be written is left alone. `EDDA_LOG=off` turns the log off even when
`problem_log:` is `local`; `EDDA_LOG=<file>` writes to that file
instead, when the log is on; `EDDA_LOG` never turns it on. The tests
set one of them, so they never write into the repository. The runner logs only
its own failures: when the spec does not check it logs nothing, as the
checker's own run logs those. `--model` and `--graph` neither count nor
log. `edda trend [--root DIR] [--log FILE] [--by DIM[,DIM]] [--top N]`
(`python3 tools/trend.py`, the same) reads the log, whatever wrote it: the problems per day, then the counts grouped by one
dimension or a pair (`--by where,fix`; `category` when none is named),
then the rules that come up most. Every line is checked before it is
counted: a line that is not JSON, or a record with a field missing or
of the wrong type, a date not in the log's format or a dimension value
the registry does not allow, is skipped, and the report starts with one
line counting the skipped lines. `tools/watch.py` holds the
dimensions, the count line and the log for both tools. When one
category keeps coming back, the agent records a lesson and the fix goes
where it belongs, the agent's instructions or the language (decision
U); that is practice, not code.

**The analyser** (`tools/analyse.py`) finds `dead_refusal`,
`conflicting_ensure`, `empty_ensure` and `forbidden_change` by reading
the spec alone, before any code runs; no solver. A condition is read
as facts about single properties when it has that shape: `p == v`,
`p != v`, `p in [..]`, `p not in [..]`, `p < n`, `p <= n`, `p > n`,
`p >= n`, `p is None`, `p is not None` and a yes/no property on its
own, joined by `and`, `or` and `not`, `p` a dot path from an input
(`f.status`, `number`) and `v` or `n` a literal or a choice value. A
property's cases come from its type: the values of a choice, `True`
and `False` for a yes/no, ranges for a number (whole numbers for an
`INTEGER`, so `q < 1` and `q <= 0` are the same cases, and any number
for a `NUMBER`), and for any other type only "no value" and "a value";
an `OPTIONAL` property also has "no value". Two different paths are
taken as independent. A condition outside that shape, with a list word,
a sum, a call (a client function's included), `OLD`, `ACTOR` or two properties compared, is skipped for
the check that needs it, never guessed at. `forbidden_change` runs for
an `ensure` fact only in one shape, where a warning is provably right,
and is skipped for anything else:

1. The fact is `x.p == v`, or an `in` or `!=` form that leaves one
   value, where `x` is an input of the operation itself, not a path
   through a reference, and `p` a choice with `may_change`.
2. Every refusal and every who-line `when` of the operation can be
   read in the simple shape, reading no computed or `DERIVED`
   property; one that cannot ends the check for that fact.
3. Every `always` fact of the input's entity, and of each other thing
   the conditions read, can be read the same way; one that cannot ends
   the check.
4. No `always` fact of any other entity reads a path that reaches the
   input's entity (a reference to it, or a list of it); if one does,
   or it cannot be told, the check is skipped.
5. Two inputs of the input's entity may be one thing or two; the
   start state may pick two, and a condition relating them (`f != g`)
   cannot be read, so it ends the check by 2.
6. The property `p` being set is neither computed nor `DERIVED`. Its
   value follows from other properties, so a start value `may_change`
   allows may still be impossible; the check is skipped for that fact.

Within that shape it names a start value only when it can show one
start state with that value that passes every refusal, meets a
who-line and holds every `always` fact of each thing read, all at
once. Past 512 boxes, or past 16 things, the check is skipped. `dead_refusal` and `conflicting_ensure` read
every path as free, without `always` facts, so they can miss a flag
but never invent one. An `always` fact is read under the path of the entity the
`ensure` fact reaches (`quantity > 0` of `order`, beside `f.quantity ==
0` with `f: order`, is `f.quantity > 0`). `while:` is retired (section
10), so only `always` facts are compared. A flag never fails a file.

**Derived properties** (`, DERIVED`), by name:

- `spec_file.blocks`, `spec_file.stories`: the role and entity blocks,
  the stories, in file order.
- `spec_file.name`: the file name without `.edda` (`order`);
  `problem.file_name` carries the full name (`order.edda`,
  `order.edda.vc`).
- `spec_file.notes`: every note under a story, an operation or
  an example, in file order (`check.py`'s `notes` builds them; the
  operation `notes` of EDDA-003 orders those of several files by text,
  file name and line); `file` is the enclosing spec_file,
  `story_id` the enclosing story's id, `line` the line of the note's
  text, `text` the string as YAML reads it.
- `spec_file.problems`: the refusals and flags above for this file and
  its history, ordered as the layers say.
- `history.versions`: the versions in the file's `.vc`, oldest first;
  `[]` when there is no `.vc`.
- `block.kind`, `block.name`, `block.text`, `story.id`, `story.about`,
  `story.as_a`, `story.sentence`, `story.epic`, `story.text`: from the
  block; `text` is the normalised text of section 10.
- `story.body_text`, `version.body_text`: section 10, over `text`.
- `story.blocks`: the blocks the story names, looked up across the
  project's files: its `about` entity; every entity in an input type
  phrase or a given; every entity reached through a dot path in the
  story's expressions (the declared type of each step: the object read
  from, the value read and, for a `MANY` list, its element type, so a
  story reading `order.children` with `children: MANY item` names
  `item`); every role in
  `as_a`, a who-line, a given's `roles:`, and on a `may_*` line of a
  collected entity; every client function the runner may make run for
  the story: in every expression it may evaluate for the story's
  examples (a step's `at:` and call, its `then` facts, and the `always`
  facts of the things they reach), in every expression of the story's
  operations and the `always` facts their calls are held to, and in the
  story's own expressions; directly or through the computed properties
  read and the operations called (their every expression, nested to the
  end). The same set names the rows `edda run STORY` checks (section 9).
  Each once; ordered by file name, then file order.
- `story.versions`, `block.versions`: the history's versions of this
  story or block, oldest first. `pins_stale` looks at the newest
  version only.
- `pin.block`: the block of the pin's kind and name, looked up across
  the project's files.
- `story.changes`: walk the newest version's `text` (no lines when
  there is no version) and the current `text` from the top; two equal
  current lines match and both advance; otherwise skip the old line
  when the longest common sequence from there is at least as long as
  when skipping the new line, else skip the new line; a skipped old
  line is `removed`, with `line` the number of the next new line; a
  skipped new line is `added`, with its own number.
- `story.sentences`, `version.sentences`: section 12, rendered from
  the model (section 9) by `tools/view.py`; a sentence's `line` is its
  anchor's line in the file; for a version, the line within the
  version's text, counted from its key line, 1.

**The model and the graph.** `--model [DIR]` prints the JSON model
of a project that checks and `--graph <entity>.<property> [DIR]` its
status life graph as text (section 9); a refused project prints its
problems and exits 1. Without either, the checker's run is as above
and below, over the spec folder and, for Edda's own repository only,
the fixtures. `--root DIR` names the project (section 9).

**Status and changes.** Under each `.edda` file that checks, its
history included (no refusal in the file or in the `.edda.vc` beside
it), the checker prints one line per role, entity, function and story,
roles first, then entities, then functions, then stories, each in file
order: `<kind>
<name>: approved v<n>` or `<kind> <name>: draft v<n>` (`function shipping_cost: draft v0`), `n` the block's
or story's `version`, `len(versions)` (0 when there are none), with
`, pins stale` after an approved story whose pins are stale. Under a
story with a version, one line per change of `story.changes`, in walk
order: `- <line>: <sentence>` for a removed line, `+ <line>:
<sentence>` for an added one, the sentence as written in the text. A
story never approved and a role or entity block show no changes.
In a project whose link layer refused nothing, each story's link line
follows its status line and its changes: `<id>: linked (<operation> ->
<path>::<function>, ...)`, its operations in file order; `<id>: not
linked (...)` when one of them is `NOT_BUILT`, it reading `<operation>:
not built`; `<id>: no operations to link` for a story with none.
Status, changes and link lines are not problems: they never make the
run fail.

**Done.** A story is done when, at its approved version: it is not a
draft; no pin is stale; every example passes; its operations'
refusals, ensures, `always` and frame rule hold on the whole suite;
every link resolves both ways. The checker computes it; the agent never
marks it. Nothing computes done as one verdict yet. `tools/run.py` (section 9)
computes two parts for the stories whose operations are bound: every
example passes, and the operations' refusals, ensures, `always` and
frame rule hold on every call the examples make; it reports that as
`examples passed`, never as done. The checker's status and link lines
give the approved version, stale pins and links (section 9); the rules
on the host's whole test suite are not built.

**Settings.** Every tool reads the project's `edda.yaml` (section 9)
first. A pin newer than the tools is read before anything else, since
a newer revision may have keys this one does not know: the tool prints
one line, `<file>:<line>: pinned_newer: <message>`, and exits 3. Then
the source layer above, then the shape: `unknown_key`, `missing_key`
(`generated_cases needs on:`), `wrong_type` (`file must be a mapping`
for a root that is none, an empty file included; `on must be a
yes/no`; `runs must be a whole number of at least 1` for `1.0`, `0`,
`-1`, `true` or any value that is not one, `steps` and `edda` alike;
`specs must be a text`; `specs must be a folder inside the project,
without ..: <path>`; `stack must be python`) and `declared_twice`,
then `two_settings`, `outside_root` and `stack_mismatch`, each at its
line, as `<file>:<line>: <rule>: <message>` (`<folder>: outside_root:
<message>` for a folder no line names) under `the settings do not
check:`;
the tool then does nothing and exits 1. In the old place (section 9)
the only key is `generated_cases:`. A pin older than the tools prints
`<file>:<line>: flagged: pinned_older: <message>` first, and the tool
runs; the checker's plain run counts it, and logs it when the log is
on, with its other problems. `--model`, `--graph` and `approve.py` print these lines to
stderr, so what they print to stdout is unchanged.

**Runs, test only.** Examples through the binding, every call of a
bound operation wrapped in its refusals, ensures, always and the frame
rule (built, sections 6 and 9); generated cases, the same wrapping
round random runs, when a project turns them on (built, section 9); the same wrapping round the linked
operation for every test in the host's suite (not built yet: links now
name the operation's function, but nothing wraps it in the host's
tests). Never in production.

## 12. Views

**Read view.** Generated from the checked tree, never edited. A
`sentence` has `kind`, `text`, `line` (where it comes from) and
`shade` (`plain`, `grey` for notes, `warning` for questions,
drifted pairs and expressions shown as written). Sentences come in file order, one per item, except
that a story with `rules:` shows its examples grouped under their
rule:

| kind | template |
|---|---|
| story | `<Story>. As a <role>, I want <i_want>, so that <so_that>.` |
| note, question | the text; a story's notes after the story sentence, then its questions; an operation's or example's after its own sentences |
| operation | `<Name> <is-sentence>.` |
| permission | `A <role> [whose <actor condition>] may <name> <inputs> [while <state condition>][, if <other actor condition>].`; the condition is split only at its top-level `and`: a part that compares a property of `ACTOR` (its left side starts with `ACTOR.`) goes after "whose", any other part that mentions `ACTOR` (`any`, `all`, `not`, a call, an `or`, ...) after ", if", the rest after "while"; a condition whose top is not `and` is one part; an input reads as its type with "a" or "an" when its name is its type (`order: order` reads "an order"), else `<name>, a <type>` |
| refusal | `If <name> is asked for <an input> whose <condition>, then the system shall refuse it: <reason>.` when every left side starts with that input's name, which is then dropped; otherwise `If <name> is asked and <condition>, then ...` |
| outcome | `When <name> succeeds, <means>.` or, without `means`, `When <name> succeeds, <fact in words>.` |
| read | `<Name> gives <returns in words>[, ordered by <keys>].` |
| invariant | `Always, <fact>.` |
| function | `<Name> is <is>.`, a client function's meaning |
| signature | `<Name> takes <inputs> and gives <type>.`, its inputs read as a permission's are, `nothing` when it has none |
| row | `For example, the <name> of <values> gives <value>.`, one per row, the values read as a given's are, joined with "and" |
| rule | `Rule: <sentence>.` as a heading line before its examples; with `rules:`, the rules come where the examples stood, in `rules` order, each followed by its examples in `shown_by` order; without `rules:`, no rule sentence and the examples in file order |
| example | `Example: <title>.` |
| given | one sentence for all givens: `Given <item>, and <item>.`; an actor reads `<name>, a <role>`; an entity `<name>, a <entity> with <property> <value> and <property> <value>`; items are joined with `, ` and the last with `, and ` (the comma stays because each item carries its own apposition) |
| when | `When <actor> asks to <name> <arguments>[, at <time> (<since>)].`; the time only in an example that uses time (section 8): the clock's time at the call and its distance from the start, `the start` or `start + 1 day 2 hours`, the difference of the two wall clocks; a time known only when it runs, `, at <at:> (known when it runs)`, or `, at a time (known when it runs)` on a step with no `at:` |
| then | with facts: `Then it is done and <facts>.` or `Then it is refused: <reason>, and <facts>.`; without: `Then it is done.` or `Then it is refused: <reason>.`; a step without `when`: `Then <facts>.`; facts joined with "and" |

Expressions in words, one reading per form of 7.1, composed inside out:
a property read straight on a name reads `'s` (`order.status` reads
"the order's status", `purchase.status` "purchase's status"); any
longer path reads from its end with "of" (`block.versions[-1].number`
reads "the number of the last of the block's versions", `a.b.c` "the
c of a's b"); `==` is, `!=` is not, `>` is
more than, `<` is less than, `>=` is at least, `<=` is at most; `and`,
`or`, `not` as conditions as they are, grouped as **Grouping** below
says, and `or` as a value "or else" (**Values and conditions**); `is
None` has no value; `is not None` has a value; `in` is in; `len(x)`
the number of x; `sum(e for x in l)` the sum of e over every x in l;
`any(c for x in l)` there is an x in l where c; `all(c for x in l)` for
every x in l, c; `[e for x in l if c]`
e for every x in l where c (the projection `e` is kept; a bare `x`
reads "every x in l where c"); nested generators read in order; `l[0]`
the first of l; `l[-1]` the last of l; `l[n]` item n of l, counted
from 0; `TIME("t")` the time t; `DAYS(n)` n days, `HOURS(n)` n
hours, `MINUTES(n)` n minutes (`DAYS(1)` 1 day); `+ - * /` plus, minus, times, divided by; `OLD(x)` x before; `ACTOR`
the asker; `TODAY` today; `RESULT` the result; `True` yes, `False` no; `None`
no value; a text literal in double quotes, a double quote or a
backslash inside it with a backslash before it, so that a quote never
ends it early (`'say "hi"'` reads `"say \"hi\""`). A name reads as words
(`units_sent` reads "units sent"); an entity type takes "a" or "an"; a
given or input keeps its name. Every rendered sentence starts with a
capital letter and ends with a full stop; a note or question is shown
as written, verbatim. Structural ids (story keys) are
hidden; an id written inside quoted text stays. Hover shows each key's
and word's meaning from the registry. `view_at` renders a version's
text with the who-lines of its pinned blocks: the version's own
operations and who-lines, from its snapshot, read against the role and
entity blocks it pins, at their pinned versions; today's blocks are not
read.

**Anchors.** A sentence's `line` is: the story's key line for `story`;
the note's or question's text line; the operation's key line; the
who-line for `permission`; the `when` line for `refusal`; the fact's
line for `outcome`; the `returns` line for `read`; the fact's line for
`invariant`; the function's key line for `function`, its `returns:` line for `signature`, the row's line for `row`; the line of the `rule:` key for `rule`, wherever that
key stands in the item (after `shown_by:` too); the title line for
`example`; the `given:` line for
`given`; the step's `when` line for `when`; the step's `then` line for
`then`.

**Built.** `python3 tools/view.py [--lines] [--root ROOT | DIR] [STORY ...]`,
over the spec folder `DIR`, else the one the project's `edda.yaml`
names (section 9), renders every sentence from the model
(section 9), never from the YAML, and the binding's `view` and
`view_at` call the same renderer. It prints each story's sentences in
file order, one per line, a blank line between stories, each marked
by its shade: `~ ` grey, `? ` warning, two spaces plain; `--lines`
puts `<file>:<line>: ` before each. A project that does not check
prints its problems as the checker does and exits 1; a `STORY` the
project does not have (`no such story: <id>`) exits 2, a usage error
(section 13).

Where the rules above are silent, the view reads so:

- **Order.** A story: its sentence, notes, questions, then its
  operations and its examples by their first line; with `rules:`, the
  rules stand at the first example's line. An operation: its sentence,
  then its permissions, refusals, outcomes and read by their anchors,
  then its notes. An example: its sentence, the given, then each step,
  `when` before `then`, by line, then its notes.
- **Invariants** belong to no story: `view.py` prints an entity's
  `always` facts, one sentence each, before the stories of its file,
  only when no `STORY` is named. So are client functions: each one's
  sentences follow the invariants of its file, only when no `STORY` is
  named. A call of one reads as a call of an operation does ("the
  shipping cost of the order's weight"), and is proven yes or no by its
  `returns:`. Their bare names are the entity's own
  properties and read as words (`Always, units sent is at least 0.`).
- **Articles and stops.** "a" or "an" by the sound the word starts
  with, roles included (`As an operator`): a single-letter name goes by
  the sound of its letter ("an s", "an x", "an f", "a p", "a u"); a
  word starting "hour", "honest" or "honour" takes "an" (the h is not
  said); a word starting "un" takes "an" ("an unable", "an
  uninstalled", "an unimportant"), except one starting "uni" and not
  "unin" or "unim", said "you" ("a unit", "a union"); a word starting
  "eu", or any other "u" then a consonant then a vowel (said "you": "a
  user", "a usual"), takes "a"; any other
  word takes "an" before a vowel letter and "a" before a consonant
  ("an umbrella", "a hat"). A full stop is not added after a text
  that ends in `.`, `?` or `!`. Notes and questions are neither
  capitalised nor stopped.
- **Names.** A given, an input and a comprehension's name keep their
  name as written; an input named for its entity type reads "the
  <entity>" (`order: order` gives "the order's status"), and so does
  an `ordered_by` item; any other bare lowercase name is a choice value
  or an entity's own property and reads as words. A comprehension's
  name holds only inside it, nested ones included, as in Python: after
  it, the same name is the one outside again, with its own type.
- **Refusal.** Only a comparison has a left side; a condition with any
  other part (a bare yes/no path, a call) takes the second form. A left
  side starts with an input's name when a property is read on the input
  itself (`order.status`, not `order` alone); only the left sides lose
  it, and the property read on it then reads as a name
  (`order.shop.name` reads "shop's name", `order.lines[0].status` "the
  status of the first of lines"). The input reads as in a permission, and one read with its type
  after its name closes with a comma before "whose".
- **Permission.** Inputs are joined as givens are; a "whose" part
  compares a property of `ACTOR` and drops "the asker's" (`whose shop
  is the order's shop`); any other part that mentions `ACTOR` would not
  read after "whose" and stands at the end, after ", if": `A shop user
  may remove an order, if there is an o in the orders of the asker's
  shop where o's status is incoming.`; an input with its type after its
  name closes with a comma before "while". A type reads "a
  text", "a number", "an integer", "a time", "a yes or no", "a choice
  of a, b or c", "an order", "an order list" (`MANY`), "an ordered
  order list" (`IN ORDER`), with "optional" before it for `OPTIONAL`.
- **Expressions.** `NOW` reads "now"; a call of a declared operation
  "the <name> of <arguments>" (`the check of the story's file`);
  arguments by position are joined with "and", a keyword reads ",
  <keyword> <value>", in a `when` sentence too (`When tuan asks to
  approve the first of changed's stories, because "..."`); `-2` stays
  as written, a minus before anything else reads "minus"; `[]` reads
  "empty", a list literal "the list of a and b", in brackets whenever
  it stands inside a larger expression, a list of one too (`x in [a]`
  reads "x is in (the list of a)"); a value whose own reading holds an
  "and" or "or" the view puts in, outside its brackets, takes brackets
  wherever it stands inside a larger expression, and before "is yes"
  and "is no": `[[1, 2], 3]` reads "the list of (the list of 1 and 2)
  and 3", `check(1, 2) == 1` "(the check of 1 and 2) is 1",
  `check(n == check(1, 2), 3)` "the check of n is (the check of 1 and
  2) and 3". Whether it does is decided from the expression's tree (a
  list of two or more, a call of two or more arguments, an `and` or
  `or`, a comprehension, `any`, `all` or `sum`, at its top or on the
  path a property is read on), never from the rendered text, so a quote
  or an "and" inside a text changes nothing; a filter reads after
  its generator in `sum` (`the sum of e over every x in l where f`),
  joins the condition with "and" in `any` (`there is an x in l where f
  and c`) and ends the generator in `all` (`for every x in l where f,
  c`); nested generators are joined with ", and every".
- **Values and conditions.** A fact, a `when`, a filter, the
  condition of `any` and `all`, and each part of a condition's `and`,
  `or` and `not` are conditions; everything else is a value: a
  comparison's sides, an argument, a `returns`, an index and what it
  is read on, a list's elements, an arithmetic operand. A name, a
  path, `OLD` of one or a call of a declared operation standing as a
  condition on its own reads "<value> is yes" (`block.approved` reads
  "the block's approved is yes"), and under `not` "<value> is no", only
  when the view proves it is `YES_NO`: a property so typed in the model
  (a computed one by the type the checker resolved), `OLD` of such a
  value, or a call of a declared operation whose `returns` the view
  proves `YES_NO` (a comparison, `not`, `any`, `all`, `True` or `False`,
  an `and` or `or` of such, or such a path). One that may also have no
  value (an `OPTIONAL` property or input, `OLD` of one, a call whose
  `returns` may be one, an `and` or `or` with one among its parts)
  reads "is yes" alone, but under `not` "<value> is no or has no value",
  as `not` holds for both; that reading is one clause, in brackets
  wherever it stands inside a larger condition or value (**Grouping**).
  The types are the model's:
  the current text's entities and roles, or for `view_at` the blocks
  the version pins, at their pinned versions; a given's, an input's and
  a comprehension's name take their declared type, `ACTOR` its roles'
  properties (one optional in any of them may have no value). Anything
  else standing as a condition, or under `not`, is
  shown as written, a warning: a text (`order.label` for a `TEXT`
  label), a number, `None`, a list, arithmetic, `len`, `sum`, a time,
  or a value whose type the view cannot see. As a value it reads as the
  value alone. `True`, `False`, `any` and `all` read as they are. `a or b` as a value
  reads "a, or else b": its value is b when a is empty, zero, no or
  has no value, and a otherwise (`order.a == (order.b or 1)` reads
  "order's a is (order's b, or else 1)"; `a or b or c` "a, or else b,
  or else c"). `a and b` as a value gives one of its parts, has no
  reading and is shown as written; `not a` is yes or no wherever it
  stands and reads as a condition.
- **Grouping.** Two expressions with different trees never read the
  same. Arithmetic keeps a bracket wherever precedence needs it, and
  on the right of an operator of the same rank: `(x + 1) * 2` reads
  "(x plus 1) times 2", `x + 1 * 2` "x plus 1 times 2", `x - (y - 1)`
  "x minus (y minus 1)", `-(x + 1)` "minus (x plus 1)", `len(l + m)`
  "the number of (l plus m)". `not` over anything but one comparison
  or a yes/no value takes brackets: `not (a and b)` reads "not (a and
  b)", `(not a) and b` "not a and b" (for comparisons `a` and `b`). An
  `or` inside an `and` reads "either ... or", and is in brackets too
  unless it is the last part: `(a or b) and c` reads "(either a or b)
  and c", `c and (a or b)` "c and either a or b"; an `and` inside an
  `or` needs neither, as `and` binds tighter. A reading that ends
  open, so that what follows would be read into it (`any`, `all`,
  `sum`, a list comprehension, or an `and` or `or` ending in one),
  takes brackets when anything follows it: `all(c for x in l) and d`
  reads "(for every x in l, c) and d". An `or` read as a value takes
  brackets wherever anything stands around it: "(a, or else b) is 3",
  "the first of (l, or else m)", "(x, or else 1) for every x in l". A
  list literal inside a larger expression is in brackets (**Expressions**).
  A reading that holds an "or" or "and" the view puts in itself never
  merges with what stands around it: "<value> is no or has no value"
  takes brackets inside any larger condition or value, the last part of
  an `and` and a part of an `or` too (`not order.held and
  order.units_sent > 0` reads "(the order's held is no or has no value)
  and the order's units sent is more than 0"), and so does a value
  whose reading holds an "and" (**Expressions**); decided from the tree
  and the types, as above. The facts of one `then` are one `and`, and
  so is a refusal's condition after "is asked and": they join "it is
  done and" and "is asked and" as its last part (`If view at is asked
  and either number is less than 1 or ...`). A condition that stands
  whole (a fact, an invariant, after "while", "whose" or ", if") takes
  none.
- **As written.** An expression the view has no reading for, such as
  a retired form a snapshot keeps (section 10:
  `order.status.startswith('in')`, `min`, `max`, a slice, a
  conditional, a comparison chain, `is` against anything but `None`),
  is shown as written, its source text in double quotes, escaped as a
  text literal is, and its
  sentence is a warning; the view never guesses a reading and never
  stops. A step's call that is no plain call reads `When <actor> asks
  "<call>"`. In a who-line the whole condition stands after ", if" if
  it mentions `ACTOR`, else after "while"; in a refusal, after "and".
  Current text never reaches this: the checker refuses any form
  outside 7.1.
- **Values in a given.** By the kind the model gives them: a text in
  double quotes, escaped as a text literal is, a time "the time <t>", `True` and `False` "yes" and "no",
  a choice value or a role as words, a given or a fixture folder as
  written, a list joined with "and". An actor's roles read "a shop
  user and an agent", its other values follow "with" as an entity's
  do; a given without `with:` reads "butik, a shop".
- **Shade.** A refusal or outcome whose pair `wording_drift` flags
  (the model's `drift`) is a warning, and so is any sentence with an
  expression shown as written.

**Graph view.** The status life graph of one choice property as text,
from the model (`tools/check.py --graph`, section 9). The entity map,
role inclusion and who may do what are in the model as data, not drawn
yet.

**Write view.** The YAML with colour. **Diff view.** Two versions as
added and removed lines; drifted pairs side by side.

## 13. Importing Edda

Edda is the framework; a host project imports it (decisions W and X,
kb:9380137). The project gets three things, and one command runs
Edda's tools on it.

1. **`edda.yaml`** at its root (section 9): the one file that says the
   project uses Edda and how. With it, the tools run on the project:

   ```
   <edda>/edda check --root .
   <edda>/edda run --root .
   <edda>/edda view --root . [STORY ...]
   ```

   `<edda>` is where Edda's repository is. The operator approves with
   `<edda>/edda approve NAME --by OPERATOR --root .`
   (section 10). An agent runs the check after each change and acts
   on each problem's `acts`, who must act (decision X, operator
   decision, 3 Oct 2026); with `--json` it reads each problem and its
   dimensions from one JSON document, and the exit code says whether
   anything was refused or failed.
2. **The agent guide**, `language/guide.md`, for the agents working in
   the host's repository, then a short part for people. It is
   generated by `edda guide` from Edda's own stories,
   through the read view's sentences (section 12), and from named
   passages of this reference, never written by hand, so it cannot
   drift from what Edda does; `tools/test_import.py` fails when the
   file differs from what the script writes.
3. **The pointer line**, one line that tells the host's agents to load
   the guide, printed by `edda guide --pointer [--root HOST]`.

   It reads:

   ```
   This project uses Edda; load the Edda guide (<guide>) before working on specs or linked code.
   ```

   `<guide>` is the guide's path as the host reads it. With
   `--root HOST`, it is relative to the host's root when Edda's
   repository sits inside it or beside it (in the same folder), and
   absolute otherwise; without `--root`, it is relative to the
   current folder.

   Where it goes is the host's choice: its `CLAUDE.md` or `AGENTS.md`,
   its KB's skill routing, or wherever its agents read first. Edda does
   not place it.

**The `edda` command** (decision AA). `edda`, at the root of Edda's
repository, runs `tools/edda.py` with `python3`: `edda <command>
[--root DIR] [--json] ...`, the command one of `check`, `run`, `view`,
`approve`, `guide` and `trend`. Each takes the options of the tool it
runs (`tools/check.py`, `run.py`, `view.py`, `approve.py`, `guide.py`
and `trend.py`, sections 9 to 12 and above) and prints what that tool
prints. The tools still run on their own, with the same options and
output, and exit as the command does. Every command exits with one of
four codes:

| exit | means |
|---|---|
| 0 | nothing refused and nothing failed; flags alone are 0 |
| 1 | a refusal (of the settings, of the spec, or of the log folder by `trend`), a failing example, function row or generated case, or an approval refused |
| 2 | a usage error: no command or an unknown one, an unknown or missing option, a folder or file an option names that is not there or not of its kind (`no such folder`, `not a folder`, `no such file`, `not a file`, one line, before anything is done), a story or property named that is not there (or a property with no graph to draw), `--root` with a spec folder or a log of another root, an `--at`, `--by` or `--because` not well formed, `--root` to `guide` without `--pointer`, `trend` with the log off and no `--log` |
| 3 | Edda itself failed: an error the tools did not foresee (`edda failed: <error>`), a spec the runner meets that the checker should have refused, generated cases on and Hypothesis missing, a pin newer than the tools (`pinned_newer`), a passage the guide needs missing from this reference |

**`--json`.** With `--json` a command prints one JSON document on
stdout instead of its text, and exits as above. Its shape is format 3
(revision 74 gave `check --model` and `--graph` the check's `files`,
`problems` and `counts`; revision 71 added `run`'s `functions`, format
2; format 1 before), written down as JSON Schema 2020-12 in
`language/command.schema.json`, the model in it in
`language/model.schema.json`; a change to it is a new number, and a
new schema. Every document has `format` (3), `edda`
(the revision of the tools), `command` (`null` for an unknown one),
`exit` (the exit code), the command's own fields below, and `messages`:
every line the plain output would print that the fields do not hold,
in the order printed, whatever the outcome (a flag or refusal of the
settings, such as `pinned_older`, the lines of a usage error, of a spec
that does not check when the command stops there, of Edda failing, and
every line written to stderr); only the fixture report of Edda's own
repository stays plain output alone. A field the
command did not reach keeps its empty value (`[]`, `{}`, `null`, `0` or
`false`). A problem is `rule`, `file` (from the project's root), `line`
(`null` when there is none), the six dimensions of section 11
(`category` with its `sub`, `fix`, `acts`, `level`, `where` and
`found_by`) and `message`; `counts` maps each category that has problems to how many,
in the order of section 11.

| command | fields |
|---|---|
| `check` | `files`: in the plain run's order, each `.edda` and `.edda.vc` file of the spec folder, then each `.links` and covered code file, each with `file`, `ok` (no refusal), `status` (its status, change and link lines), `problems` and `flags` (each `rule`, `line` and `message`); `problems`: every problem of the project, a flag of the settings included; `counts`; `model`, the model, with `--model`; `graph`, its lines, with `--graph`. With `--model` or `--graph`, `files`, `problems` and `counts` are still those of the check, so one call gives the model and every problem; when a file is refused, `model` and `graph` are `null` and the exit is 1. The fixtures are not in it |
| `run` | `functions`: every client function whose rows the run checked against its real function (section 9), in the order reported: with no `STORY` every one, with `STORY` names those the named stories reach, then any other whose rows generated cases checked; each `name`, `status`, `detail` and `failures` (each `at`, the `file:line`, and `found`); `stories`: each `id`, `status`, `detail`, `examples_failed` (each `title` and `failures`, each `at`, the `file:line`, `then`, the fact or `null`, and `found`) and `generated` (the lines of its generated cases); `failures`: each failure as a problem; `counts` |
| `view` | `blocks`: in the plain order, each `file`, `kind` (`story`, `entity` for an entity's invariants, or `function`), `name` and `sentences`, each `line`, `kind`, `shade` and `text` (section 12) |
| `approve` | `name`, `kind`, `number`, `history` (the `.edda.vc`), `version` (the new version's text), `written` (`false` with `--dry-run`) and `refused` (why it was refused, or `null`) |
| `guide` | `pointer` (the line, with `--pointer`, else `null`), `guide` (the guide's path) and `written` |
| `trend` | `log`, `skipped`, `total`, `first` and `last` (the first and last day), `per_day` (each `date`, `total` and `counts`), `by`, `groups` (each `count` and `values`, one value per dimension of `by`) and `rules` (each `count` and `rule`) |

What `check`, `approve`, `view` and `run` take, give back and refuse
is to be stated as Edda's own stories, which the checker holds Edda's
code to; EDDA-001 to EDDA-008 state part of it.

Plain `check --model` prints the model alone, so its output stays one
JSON model, and a refused project's files as before; the counts line
and the problem log belong to `check` without `--model` or `--graph`,
plain or `--json`, so a host that calls both does not log a problem
twice.

**For a host** (operator decision KK, 5 Oct 2026). A host in any
language works with Edda through the command and these two schemas:

- *Read and find.* `edda check --root WORKTREE --model --json` gives,
  in one document, the model and every problem with its six
  dimensions, the exit code saying whether anything is refused. A
  story is found by its id with `edda view --root WORKTREE ID`, or in
  the model's `stories`; by a tag, in each story's `tags` in the model.
- *Edit.* The host's agents edit the `.edda` files in the host's own
  worktree, then run the check and act on each problem. Edda has no
  write command.
- *Approve.* The operator runs `edda approve`, which appends to the
  `.edda.vc` (section 10). Keeping agents from running it is the
  host's guard, not Edda's.
- *Stop using Edda.* Delete `edda.yaml` and the pointer line. Edda
  wrote nothing else in the host but the approved `.edda.vc` history
  and, with the log on, `.edda/checks.log`; the `.edda` files are the
  host's own, to keep or delete. `tools/test_command.py` runs a whole
  host session and fails when Edda writes anything else.

## 14. Not in this revision

Qualities and infrastructure (#2487), time-triggered operations
(#2486), screens (#2488), timing and concurrency
(#2489), an analyser beyond the simple rules of section 11 (#2491), drafting from
existing code (#2492), story to Plan tasks (#2493), richer calculations
and durations beyond moving a time (#2494), tooling (#2495), the KDL skeleton trial (#2512),
rule packs a project follows and their key in `edda.yaml` (#2612), the
agent guide served by the KB as a skill, the second part of client
functions (decision FF: `ordered_by`, nested or filtered list-building
and `DERIVED` moved to client functions);
the running of examples and the rule wrapping round every call are
begun (sections 6 and 9: Edda's own `check`); the rest of the done
computation gets its own stories.

## 15. Changes from revision 74

Operator decisions LL and MM (5 Oct 2026), task 2905: every story runs
against Edda's own code.

- Edda's own binding binds `approve`, `diff` and `approve_block`, and
  the `history`, `block`, `story`, `version`, `pin` and `change`
  properties their examples, refusals and ensures read, over
  `approve.py` and `check.py`, on the fixture copy in the work folder,
  never on `specs/` or `fixtures/` (9). It has a `clock(now)`, so an
  approval's `approved_at` is the example's time. `edda run` now runs
  EDDA-004, EDDA-005, EDDA-006 and EDDA-008; before, each was "not
  run: no binding for approve" (or `diff`, `approve_block`).
- `spec_file.blocks` and `spec_file.stories` are read from the copy
  as YAML, so a file that does not check has them too (9). Before,
  `stories` came from the model and a copy that did not check had
  none.
- EDDA-003's `notes` refuses a file given that does not check, "a file
  does not check", and lists no notes; a refusal's reason is fixed
  text, so it cannot name the file. A new fixture, `notes_bad`, holds
  notes in a file that does not check.
- The binding's `clock` is flagged `no_story`, as `make_actor` is:
  only the runner calls it.
- Edda's own `edda.yaml` pins `edda: 75`; `edda check` and `edda run`
  print what they did in revision 74, but for the stories now run and
  the new fixture.

## 16. Changes from revision 73

Operator decision KK (5 Oct 2026), from the findings kb:9380940, task
2894: the host contract.

- `edda check --model --json` and `edda check --graph
  ENTITY.PROPERTY --json` give the check's
  `files`, `problems` (each with its six dimensions) and `counts`, as
  `check --json` does, with the model or the graph (13). Before, they
  stopped before those fields: on Edda's own repository the model came
  with no problems where `check --json` gave 25 flags, and a refused
  spec's problems were plain lines in `messages`. Now a refused spec
  gives each problem with its fields, `model` and `graph` `null`, and
  exit 1. Plain `check --model` and `--graph` print what they did, and
  neither writes the problem log, as before (13).
- The `--json` document is format 3 (13). Its shape is published as
  `language/command.schema.json` and the model's as
  `language/model.schema.json`, both JSON Schema 2020-12;
  `tools/test_command.py` checks every document it reads against them.
  The model itself is unchanged: `edda_model` 2, `revision` 71 (9).
- Section 13 says how a host reads and finds, edits, approves and
  stops using Edda (delete `edda.yaml` and the pointer line), and a
  test runs a whole host session and fails when Edda writes anything
  in the host but the approved `.edda.vc` and, with the log on,
  `.edda/checks.log`.
- Edda's own `edda.yaml` pins `edda: 74`; `edda check` and `edda run`
  print what they did in revision 73.

## 17. Changes from revision 72

Build Plan kb:9379223, phase 2794, from Astra's round 91 (kb:9380698,
item 1): the root opened without following a link.

- A file a tool opens under the root, and the root itself when that is
  the path opened, is opened from the resolved root without following
  it if it is a symlink (9). Before, the root was opened following a
  link, so a root swapped for a symlink after it was resolved led the
  open out; now that open fails as one for a folder or file under the
  root swapped for a link does. The folders above the root are the
  host's and are not guarded (9).
- Edda's own `edda.yaml` pins `edda: 73`; `edda check` and `edda run`
  print what they did in revision 72.

## 18. Changes from revision 71

Build Plan kb:9379223, phase 2793, from Astra's round 80 (kb:9380659,
item 2): a read inside a generated step's rule.

- In generated cases, a read that a step's refuse condition, `ensure`,
  `OLD` value, `always` fact or frame rule path makes and that breaks a
  rule of its own no longer ends the judging of the step: it is one more
  failure of the step, named as the read's, `<read> (read inside
  <rule>) ...`, and the step's other failures and the rules it could
  not judge, those found before it included, are printed with it (9).
  Before, the read's failure alone was printed. It counts when the read
  is made, so a read taking an `OLD` value, or a comprehension's source
  around one, fails the step even when the `ensure` does not read the
  value after the call, as in revision 71; one failure met in two places
  is listed once, under the first place met (9).
- In generated cases, once a step or a read it makes has found a
  failure, whatever then ends it (the code's unset read or crash, no
  binding, no row, a read inside a read's `returns` or `ordered_by`
  breaking a rule) no longer drops it: the step fails with every
  failure found, what ended it added as a `not judged` line or one more
  failure (9). Before, the step was skipped, or only the last failure
  printed. With nothing found, it ends the step as before.
- Examples are unchanged: a step's call ends at such a read (8). A read
  in a who-line's condition still ends a generated step (9).
- Edda's own `edda.yaml` pins `edda: 72`; `edda check` and `edda run`
  print what they did in revision 71.

## 19. Changes from revision 70

Build Plan kb:9379223, phase 2728, part 1, and decisions EE and FF
(kb:9380368 section 3): client functions.

- A new top-level block `functions:`, in any `.edda` file: each client
  function with `is:`, `inputs:`, `returns:` and example rows,
  `examples:`, each `{given: {...}, gives: ...}` (4). Its inputs and
  result are scalars or a choice; its rows literal values of those
  types; a row leaving out or misnaming an input is `missing_key` or
  `unknown_key`; a function's name clashing with a role, entity,
  operation, function or one of Edda's own words is `declared_twice`
  (2, 4, 11).
- A new refusal `contradicting_rows`: two rows with the same inputs and
  different results, in the registry with its dimensions and with a
  fixture, `fixtures/contradicting_rows` (11).
- A client function is called in any expression slot,
  `shipping_cost(weight)`, by position, with no actor; its type is its
  `returns:` (7.1).
- In an example a call answers only from the rows; one no row covers
  fails the example, `no row for shipping_cost(3)`, in every phase (8).
- A computed property is still the code's bound property, as in
  revision 70, whether or not its expression calls a client function:
  Edda does not work out its spec expression to compare (decision II).
  Facts that read it catch wrong code; a computed property no fact
  reads is not checked (8, 9).
- `edda run` runs function rows through the binding's new `FUNCTIONS`
  before the stories: every function with no `STORY`, with `STORY`
  names those the named stories reach (`story.blocks`), then after the
  stories any other whose rows generated cases checked: `rows passed`,
  `failing` with a new failure `failing_function` per row (exit 1), or
  `not run: no binding for function <name>`. Generated cases call the
  real function only once its rows pass; an operation needing one that
  does not is skipped, `function <name> not verified` (9).
- A function is a block: `.edda.vc` gains `function:` versions and pins
  (`vc-schema.json`); `approve.py` approves a function; `story.blocks`
  names every function the runner may make run for a story (in its
  examples and the `always` facts they reach, its operations and the
  `always` facts their calls are held to, and its own expressions;
  directly or through computed properties and called operations), so
  approving the story needs it approved first and a newer version makes
  the pins stale. A history
  without function versions stays valid (10, 11).
- The read view gives a function's meaning, inputs and result and each
  row, `For example, the shipping cost of 1 gives 5.`; new sentence
  kinds `function`, `signature` and `row` (12). A new `where` value,
  `function` (11).
- The model lists `functions`, a version its pinned `functions`; its
  `edda_model` is now 2 and its `revision` 71. `--json` is format 2:
  `run` gains `functions` (9, 13).
- `DERIVED` is unchanged; section 4 says how it relates to a client
  function. Moving `ordered_by`, list-building and `DERIVED` to client
  functions is part 2, not here (4, 14).
- Edda's own repository declares no client function; its `edda.yaml`
  pins `edda: 71`. `edda check` adds `fixtures/contradicting_rows` to
  its fixture report, and the line numbers of its link flags on the
  changed tools move; `edda run` prints what it did in revision 70.

## 20. Changes from revision 69

Build Plan kb:9379223, phase 2727, and decision FF (entry 138,
kb:9380368 section 2), with decisions Z and GG: the frozen clock in
examples.

- An example that uses time (section 8) runs on a clock of its own: it
  starts at the new key `starts_at:`, else at the project's new
  `clock_start:` in `edda.yaml`, and only a step's `at:` moves it.
  Nothing reads the machine's clock. "Uses time" is what the runner
  counted as "needs the clock" in revision 69: `NOW` or `TODAY` read
  in what the runner evaluates or the code decides for the example,
  or any `at:` (8).
- New refusals `no_clock_start` (an example that uses time with no
  start) and `clock_backwards` (an `at:` the checker can tell is
  earlier than the clock), judged after the rest of the meaning layer
  found nothing in the file; a new flag `clock_unused` (a
  `starts_at:` on an example that uses no time). All three are in the
  registry with their dimensions, and have a fixture each (11).
- `at:`, a free text before, is a time or an expression whose only
  time is `NOW` moved by durations; anything else is `type_mismatch`.
  An `at:` the checker cannot place fails the example at its line when
  it would move the clock back (8, 11).
- New expression words `DAYS(n)`, `HOURS(n)` and `MINUTES(n)`: only
  `TIME + duration` and `TIME - duration`, giving a TIME. `DAYS` is a
  calendar day in the business zone, `HOURS` and `MINUTES` elapsed
  time (decision Z); a wall-clock time that does not exist or happens
  twice is read as zoneinfo reads it with fold=0. No property holds a
  duration (4, 7.1, 7.2).
- New key `zone:` in `edda.yaml`, the business zone, a name zoneinfo
  knows; UTC when left out. `NOW` is the clock's time and `TODAY` its
  day in that zone (decision GG). An unknown zone or a `clock_start:`
  that is no time is refused (`wrong_type`) (9).
- The runner no longer reports `not run: ... needs the clock, not built
  yet`. The binding may define `clock(now)`, told the time whenever the
  clock is set or moves, before anything is read at it; times reach the binding as before, a
  `datetime` with no zone, now the business zone's wall clock (9).
- Generated cases run an operation that reads the clock on a clock
  stopped at the project's `clock_start:`; with none, it is skipped,
  `no clock start` (9).
- The read view gives each step's time in an example that uses time:
  `When ..., at 2026-10-02 09:00 (start + 1 day).` (12). The model
  gains an example's `starts_at` and `clock` and a step's `time`, and
  its `revision` is now 70.
- Edda's own repository: 14 examples of EDDA-004, EDDA-005 and
  EDDA-008 read `NOW` through `approve`'s and `approve_block`'s
  `ensure` facts or move time with `at:`, so its `edda.yaml` gains
  `clock_start: "2026-10-01 09:00"` (UTC) and pins `edda: 70`. No
  `.edda` file changes. Those three stories stay `not run: no binding
  for ...`; no story changes status, and `edda run` prints what it did
  in revision 69. `edda check` adds the three new fixtures to its
  fixture report.

## 21. Changes from revision 68

Build Plan kb:9379223, phase 2809, and decisions HH (entry 140) and AA
(entry 132): the problem log is opt-in, and one `edda` command.

- New key `problem_log:` in `edda.yaml`, `local` or `off`, `off` when
  left out or with no file; in the registry. With `local`, the checker
  and the runner append to `.edda/checks.log` as revisions 67 and 68
  did, the log folder held inside the root; otherwise nothing is
  written and no `.edda/` is made. `EDDA_LOG=off` still turns the log
  off and `EDDA_LOG=<file>` still redirects it, but it never turns the
  log on. Decision HH amends decision Y for this one opt-in case; the
  KB stays the main home of history and reads `--json` (9, 11).
- The log folder `.edda` is held to the root only when the log is on:
  with it off, a `.edda` that resolves outside is no longer refused
  (9).
- One command, `edda` at the root of Edda's repository, runs
  `tools/edda.py`: `edda check`, `run`, `view`, `approve`, `guide` and
  `trend`, each with its tool's options and `--json`. The checker's run
  moved from `check.py`'s main block to `tools/edda.py`, since
  `check.py` is linked code; every tool's own script runs through the
  command, with the same options and output (13).
- Fixed exit codes, one table: 0, 1, 2 for a usage error, 3 when Edda
  failed. Every folder or file an option names must be there and of
  its kind, checked before anything is done, else one line and exit 2:
  `check --root`, `--model DIR`, `--graph ... DIR`, `run --root` and
  `--project`, `view DIR` and `--root`, `approve --root` and
  `--folder`, `guide --pointer --root`, `trend --root` and `--log`
  (`run --project` with a missing folder ran nothing and exited 0;
  `approve` exited 1; `trend` with a missing `--log` said nothing was
  logged; `run --root` and `view --root` named the spec folder, not
  the root). Changed to fit the table, the printed lines unchanged:
  `no such story` (`view`), `unknown story` (`run`, from 3),
  `--graph` with no graph to draw, and `approve` with an `--at`, `--by`
  or `--because` not well formed now exit 2, not 1; a source the guide
  needs missing, 3, not 1, and a reference with no revision line says
  so instead of failing; any error the tools did not foresee is
  `edda failed: <error>`, 3, in every tool, not only the runner (9, 12,
  13).
- `--json`: one document on stdout, format 1, its fields per command
  named in section 13; every other line the plain output prints is in
  `messages`, in order.
- Edda's own repository has an `edda.yaml`: `edda: 69`, `stack:
  python`, `problem_log: local`. Its checker's and runner's plain
  output is unchanged but for the lines of the flags of the linked
  tools that were edited; its model's `revision` stays 63. Every file
  a tool opens there is now opened inside the root (section 9).
- Revision 68 said revision 69 reads `edda.yaml` only at the root; the
  old place in the spec folder is still read, for a later revision.
- The guide and the README name the `edda` command; the guide is
  regenerated. No block's text changes.

## 22. Changes from revision 67

Build Plan kb:9379223, phase 2657, and decisions W and X (kb:9380137):
the import contract.

- `edda.yaml` moves to the project's root, the folder that holds the
  spec folder, and gains three keys, all optional: `edda:` the pinned
  revision, `specs:` the spec folder (`specs` when left out) and
  `stack:` the code stack (`python`). The keys are in the registry.
  With no file, every tool does what it did (9).
- Tools older than the pin refuse to run with one line naming both
  revisions and exit 3; newer ones print one flag line and run. New
  rules, each with its four fixed dimensions: `pinned_newer`,
  `stack_mismatch` and `two_settings` (refusals), `pinned_older`
  (a flag) (9, 11).
- `check.py`, `run.py`, `approve.py` and `view.py` take the spec folder
  from `edda.yaml` through one reader, `tools/settings.py`, and take
  `--root DIR`; `trend.py` takes `--root DIR` for the log. A tool given
  the spec folder by name takes the folder above it as the root. The
  checker reports the fixtures only for Edda's own repository (9, 11).
- One root per run: `--root` with a spec folder named by `--model DIR`,
  `--graph ENTITY.PROPERTY DIR`, `--project` or `--folder` whose folder
  above is another root is refused with one line and exit 2, and so is
  `trend.py --root` with another root's `--log`; when they agree the
  tool runs (9).
- Every path the host gives resolves, symlinks followed, inside its
  root, or is refused: new rule `outside_root` (a refusal), for the
  spec folder, the log folder `.edda` and each `covers:` path, and so
  each `.links` path. `covers:` and `.links` paths are relative to the
  root, so `specs: docs/specs` no longer reads them under `docs/`;
  with no `edda.yaml` the root is the folder above the spec folder, as
  before (9, 11).
- So does every file a tool opens under the root, checked on the path
  as it is opened: `edda.yaml`, each `.edda`, `.edda.vc` and `.links`
  file, each covered code file and the default log; a log that lands
  outside is not written, and `approve.py` writes only in the folder
  it holds open (9, 11).
- For this revision only, `specs/edda.yaml` holding only
  `generated_cases:` is still read; both places at once are refused.
  An empty `edda.yaml` is still refused; whether it should mean every
  default is open (9, 11).
- The agent guide, `language/guide.md`, is generated by
  `tools/guide.py` from Edda's own stories and named passages of this
  reference; `--pointer` prints the one pointer line, the guide's path
  in it as the host reads it (relative to `--root` when Edda sits
  inside or beside the host, else absolute; relative to the current
  folder without `--root`). Section 13 says what a project gets when
  it imports Edda, and that an agent runs the check after each change
  (decision X), which the guide quotes; `tools/test_import.py` tests
  the settings, the tools on a spec folder elsewhere, the guide and
  the pointer (13).
- Rule packs have no key yet (section 14). Edda itself has no
  `edda.yaml`, so its checker's run, its runner and its model are
  unchanged; the model's `revision` stays 63. No block's text changes.

## 23. Changes from revision 66

Build Plan kb:9379223, phase 2649, and decision U (kb:9379257,
questions 4 to 6): every problem carries six dimensions, and problems
are counted and logged.

- Every rule of the registry, the link layer's and the analyser's
  included, has four fixed dimensions: what went wrong (a category and
  a sub-kind), fix shape, who acts and level, in a table of section 11
  that `tools/gen_keywords.py` copies into each rule of
  `keywords.yaml`; it refuses to write the registry when a rule has
  none or a value is not allowed. `keywords.yaml` gains `failures:`
  and `dimensions:` (11).
- The runner's failures are rules too: `failing_example` and
  `failing_case`, `code differs`, blocking (11).
- Each problem also gets where in the spec, read from its line, or
  `unknown`, never guessed, and found by, set by the tool (11).
- A person re-tags one problem as `language` with the comment
  `# edda: language` on its line; no grammar change (11).
- The checker's plain run and the runner end with one count line per
  category with problems, `3 contradiction, 1 weak check`; nothing when
  there are none. That line is the only change to their output; exit
  codes are unchanged. The fixtures are not counted (11).
- Each run appends one JSON line per problem, all six dimensions with
  the rule, file, line, date and commit, to `.edda/checks.log` in the
  project folder, ignored by git; `EDDA_LOG=off` or `EDDA_LOG=<file>`
  turns it off or sends it elsewhere, and every test does. A log that
  cannot be written changes nothing (11).
- `tools/trend.py` prints the problems per day, counts grouped by one
  dimension or a pair, and the rules that come up most (11).
- `tools/watch.py` holds the dimensions, the count line and the log;
  `tools/test_dimensions.py` tests them. The model's `revision` stays
  63, and no block's text changes.

## 24. Changes from revision 65

Build Plan kb:9379223, phase 2648, and decision U (kb:9379257,
questions 1 to 3): the analyser, four flags found from the spec alone.

- `dead_refusal`: a refusal every case of which an earlier refusal of
  the operation already covers; `conflicting_ensure`: two `ensure`
  facts on one property with no case in common, or an `ensure` fact
  with none in common with an `always` fact of an entity it reaches;
  `empty_ensure`: a fact that cannot fail, its two sides the same, or
  a call of its own operation; `forbidden_change`: an `ensure` that
  sets a choice to a value `may_change` does not allow from a start
  value it can show possible: one start state passing the refusals,
  a who-line and the `always` facts at once. It runs only in one
  shape: an input's own choice, neither computed nor `DERIVED`, every
  refusal, who-line and `always` fact involved read, and no `always`
  fact of another entity reaching the input's entity; anything else is
  skipped (11).
- They are flags, so they never fail a file and never change an exit
  code; on by default, as every flag is. Each is in the registry.
- Simple rules only: facts about single properties joined by `and`,
  `or` and `not`, choices from the type, numbers as ranges with whole
  bounds for an `INTEGER`; a condition outside that shape is skipped
  for that check (11). No solver and no new dependency.
- `tools/analyse.py` holds the analyser and `check.py` calls it in the
  flag layer; `tools/test_analyse.py` shows each flag raised, a near
  miss not raised, and a condition too complex skipped, with the
  design note's four examples, an `always` clash, an integer edge
  (`q < 1` against `q <= 0`) and a refusal with `or`.
- Edda's own specs raise none of the four; the plain run, the runner
  and the model are unchanged, the model's `revision` stays 63, and
  no block's text changes.

## 25. Changes from revision 64

Build Plan kb:9379223, phase 2636, and decision T (kb:9379252):
generated cases, off by default.

- A project's `edda.yaml` turns them on: `generated_cases: {on: true,
  runs: 100, steps: 20}`; no file or `on: false` is off. Its keys have
  a table, with scope, type and default, and are in the registry. A
  file that breaks its shape, its root no mapping or a count no whole
  number of at least 1, is refused in the checker's words and the
  runner exits 1 (9, 11).
- On, each story gets one more line: random starting worlds from the
  glossary, edge values from the spec's own expressions, worlds that
  break an `always` thrown away; steps of the story's bound operations
  by actors its who-lines name, on records that exist; every call held
  to the rule wrapping of section 6, the only oracle. A failure is
  shrunk and printed as an example ready to paste, with the broken
  rule, the seed and the full command that replays it; replay holds
  with the same command, settings, spec, code, Python and Hypothesis
  versions and binding state, not across entry points, and the pasted
  example is the lasting reproduction; it makes the exit 1. In a
  story with `rules:`, it also gives the `shown_by:` line, so pasted
  it checks and fails at the same rule. Operations with no binding,
  on the clock or never called, and entities no record can be made
  of, are skipped and listed on every outcome (8, 9). What the binding
  cannot give, no binding or an unset value, is never a failure by
  itself or a crash. Every rule that can be judged is: a failure wins,
  listed with each rule that could not be judged beside it; with
  nothing failed, in the starting world the story is not run, with
  why; in a step the run ends and the operation is skipped, with why
  (9). This holds for every check in a step, not only the top-level
  ones: an `OLD` value that cannot be read leaves only the facts that
  use it unjudged; a path or computed property the frame rule cannot
  read, only that part, and a change only what it could still name,
  bounded from the spec, is not judged, never failed; a refuse condition that cannot be judged does
  not stop the later ones, so a later condition that holds still makes
  the refusal due, and a refusal's reason must be one the spec order
  allows, never one no refusal declares (9). A record may hold an unset
  value, and showing a run never reads it (9).
- Runs reach records through other records at any depth, loop-safe;
  the passed line counts the calls of each operation, and a story
  whose runs called nothing is not run, never passed. An `OPTIONAL`
  reference with nothing to point at is left out; a required one
  waits for a record. Only a required single-record input blocks an
  operation: an `OPTIONAL` one is left out, a `MANY` one may be
  empty. Edge values read a literal with its sign (`-10` gives -11,
  -10, -9) (9). A day (`YYYY-MM-DD`) is a time, read as a
  `with:` value is (9).
- Hypothesis is the one new dependency, pinned in
  `tools/requirements.txt`, imported only when generated cases are on;
  on without it, the runner exits 3 with one line (9).
- A binding may give a maker a value space for a key the types cannot
  generate; Edda's own gives `spec_file` the fixture folders holding
  one `.edda` (9).
- `tools/generate.py` builds them; `tools/test_generate.py` shows code
  that breaks a refusal only at an edge value found and shrunk to one
  step, code that keeps the spec passing, the seed replaying the same
  failure, an unbound property and an unset value in the starting
  world not run, an unset value read in a step skipping the operation,
  a failed `ensure` reported with an unjudged one beside it, a step
  whose only unkept rule cannot be judged skipping the operation, a
  failed `ensure` kept beside an unbound `OLD` value and beside a
  computed property the frame rule cannot read, a change that computed
  property could name, directly or through another, not judged while
  one outside it still fails, and examples judging it as before, a refusal still due
  after a condition that cannot be judged, a refusal no rule gives
  failing, and one only an unjudged condition gives not failed,
  optional and `MANY` inputs with nothing to point at not blocking,
  signed edge values, a world that breaks an `always` thrown away, a pasted
  failure in a story with `rules:` checking and failing at the same
  rule, a record two references away called, runs that call nothing
  not run, a reference with nothing to point at, a day as a time,
  malformed settings refused, and the runner without Hypothesis, off
  and on.
- Edda's own specs keep them off (no `specs/edda.yaml`), so the plain
  run, the checker's run and the model are unchanged; the model's
  `revision` stays 63. No block's text changes.

## 26. Changes from revision 63

Build Plan kb:9379223, phase 2623, and decision N (kb:9379218, Q6):
every operation is linked to the code that does it.

- `glossary.links` names the target (`python`), the naming rule
  (`same_name`: the operation's name is the function's) and the code
  files it covers; an `<entity>.links` lists only the operations that
  do not follow the rule, as `"path::function"` or `NOT_BUILT`; the
  code carries `# <STORY-ID>@<n>` directly above the function doing an
  operation (2, 9).
- A link layer runs after the four, only in a project with a
  `glossary.links` whose four layers refused nothing. Refused:
  `unknown_link`, `no_function`, `bad_marker`, and the source and shape
  rules on a `.links`. Flagged: `stale_link`, `unapproved_link`,
  `maybe_replaced`, `no_story`, the last by the reach rule of section 9. A link line
  follows each story's status line (11). "Level 2 adds" left section
  11: its cases are these flags.
- Edda's own: `specs/glossary.links`, `block.links`,
  `spec_file.links` and `story.links`, and markers in `check.py`,
  `approve.py`, `view.py` and `edda_binding.py`. Every operation of
  EDDA-001 to EDDA-008 resolves to one function that carries its
  story's marker (9).
- `notes` (EDDA-003) is built: `check.py`'s `notes` returns the notes
  of several spec files ordered by text, file name and line, carries
  `# EDDA-003@0` and is named in `spec_file.links`; the binding binds
  `note`, `spec_file.notes` and `notes`, so EDDA-003 runs and its one
  example passes (9, 11).
- A marker belongs to the def in force once the module has loaded: one
  on a def that a later binding of its name replaces is refused
  `bad_marker`, naming the replacing line, and the name resolves to
  that later binding. Only a binding every import runs replaces: a
  direct top-level statement, or one in a branch proven to run (`if
  True:`, a `finally`). One nested in any other branch of a compound
  statement (`with`, `if`, `try`, `except`, `else`, `for`, `while`,
  `match`, or a later form), or in an operand that may not be
  evaluated, leaves the link and flags `maybe_replaced`; a branch that
  never runs (`if False:`, `if TYPE_CHECKING:`) counts for nothing; a
  bare annotation binds nothing, a match capture binds (9, 11).
- An operation with a `.links` line is never resolved by the rule; a
  line that fails is refused once (9).
- Each covered file's top-level names resolve to a covered function or
  class, a covered module, or nothing, by the binding in force once the
  module has loaded (an import after a def stands for the imported
  definition; a conditional one keeps both). Imports are found by
  module path against the covered files, package and relative ones
  too, aliases followed, and on through re-exports and module aliases
  (`from . import impl as api`, then `api.helper()`), transitively,
  each name once per lookup. An import in code that runs runs the
  top level of each covered module it names, used or not: a
  side-effect `import a.plugins` reaches what `plugins.py` calls at
  module level, and `import a.b.c` runs each package on the way. What
  Python evaluates as a top level runs reaches what it names:
  decorators, default values, annotations (unless `from __future__
  import annotations`), base classes and class keywords, and whole
  class bodies, nested ones too; only function and lambda bodies wait
  until called. Only the body of `if __name__ == "__main__":`, either
  operand order, is left out of the reach (9).
- Linked now means the marker resolves; the runner still wraps the
  bound operations, as before (9, 11).
- New fixtures, one per link rule: `stale_link`, `unapproved_link`,
  `no_story`, `unknown_link`, `no_function`, `bad_marker`,
  `maybe_replaced` and `bad_links` (a `.links` with an unknown key).
  `tools/test_links.py` holds the layer to each rule, to the marker
  rule over every compound statement form and to the reach rule over
  every import shape and every import-time position.
- The plain run changes only by the link lines under specs/' stories,
  specs/' `.links` files and the four covered tools with their flags,
  and the new fixtures; no existing fixture has a `glossary.links`, so
  none changes. `--model`, the read view and the runner are unchanged;
  the model's `revision` stays 63, as nothing in it changed (9). No
  block's text changes, so nothing needs re-approval.

## 27. Changes from revision 62

Build Plan kb:9379223, phase 2622: the read view, built.

- `tools/view.py [--lines] [DIR] [STORY ...]` prints every story as
  the sentences of section 12, rendered from the model, with its
  shade; a project that does not check exits 1 (12).
- Where section 12 was silent it now says how the view reads: the
  order inside a story, an operation and an example; invariants; "a"
  or "an"; stops; names that keep their name and inputs that read "the
  <entity>"; when a refusal drops its input; how a permission splits
  and reads its inputs' types; `NOW`, calls, keywords, `[]` and list
  literals; the values in a given; the warning on a drifted pair (12).
  `view_at` reads a version against the blocks it pins (12).
- The model gains what the view needs and keeps the rest as it was:
  `note_lines`, `question_lines`, `given_line`, `then_line`, `drift` on
  refusals and facts, and each story's `versions`, each modelled from
  its snapshot; `revision` is 63, `edda_model` stays 1, as nothing was
  removed or changed (9).
- `story.sentences` and `version.sentences` are rendered from the
  model (11).
- Edda's binding binds `spec_file.stories`, `story`, `version`,
  `sentence`, `view` and `view_at`, so EDDA-007 runs and its examples
  pass (9).
- After Astra round 64 (kb:9380502), the view keeps meaning: brackets
  stay wherever the tree needs them, arithmetic by precedence, `not`
  over anything but one comparison or yes/no value, an `or` in an
  `and` that is not its last part, and a reading that ends open
  (`any`, `all`, `sum`, a comprehension) before anything that follows
  it; two different expressions never read the same (12).
- An expression the view has no reading for, a retired form a
  snapshot keeps (`startswith`, `min`, `max`, a slice, ...) or any
  other, is shown as written in its quotes, its sentence a warning;
  the view never stops on an old version (12).
- Values and conditions read apart: a property read straight on a
  name keeps the possessive, a longer path reads from its end with
  "of" (`the number of the last of the block's versions`); a yes/no
  value as a condition reads "is yes", under `not` "is no"; `any` reads
  "there is an x in l where c", `all` "for every x in l, c", a call of
  a declared operation "the <name> of <arguments>". The old "some x in
  l has c" and "every x in l has c" are gone (12).
- A rule's anchor is the line of its `rule:` key, wherever that key
  stands in the item (12); the model's rule `line` follows (9).
- After Astra round 65 (kb:9380533), no reading changes what an
  expression means: `or` as a value (a comparison's side, an argument,
  a `returns`, an index) reads "a, or else b", defined in 12; `and` as
  a value, and a value that is no yes or no standing as a condition
  (`len(l)`, `not len(l)`), are shown as written; `OLD` of a path and a
  call of a declared operation standing as a condition read "is yes"
  like a path (12).
- A permission's actor condition that does not compare a property of
  `ACTOR` (`any`, `all`, `not`, a call) stands at the end after ", if";
  "whose" stays for one that does, as EDDA-007 expects (12).
- A single-letter name takes "a" or "an" by its letter's sound ("an
  s", "an x", "a p"); an element of a list, or an argument, whose
  reading holds an "and" of its own is in brackets: `[[1, 2], 3]` reads
  "the list of (the list of 1 and 2) and 3" (12).
- After Astra round 66 (kb:9380540), a reading keeps the meaning or
  shows the source, marked: "is yes" and "is no" only for a value the
  view proves `YES_NO` from the model's types, in the current text and
  in a version read against its pins; any other value standing as a
  condition (a `TEXT` such as `order.label`) is shown as written, a
  warning. Each version in the model gains `entities` and `roles`: the
  blocks it pins, each with `name` and `properties` typed as an
  entity's are. A list literal inside a larger expression is
  always in brackets, a list of one too. Grouping is decided from the
  expression's tree, never the rendered text, and a double quote or
  backslash inside a text is shown with a backslash before it. "a" or
  "an" goes by sound: "a user", "a unit", "a euro", "an hour" (12).
  In specs/, five sentences change, none in meaning: one list now in
  brackets (block.edda, the then at line 149) and four whose quoted
  texts hold a quote, now escaped (spec_file.edda line 429, story.edda
  lines 270, 287 and 317).
- After Astra round 67 (kb:9380552), no reading drops "has no value"
  or borrows a comprehension's type: an `OPTIONAL` yes/no value
  standing as a condition reads "is yes", and under `not` "is no or has
  no value", as do `OLD` of one and a call that may return one; a
  comprehension's name holds only inside it, nested ones included, so
  an input of the same name after it keeps its own type (a `TEXT`
  `because` after `any(because for because in [...])` is shown as
  written). A word starting "un" takes "an" ("an unable", "an
  uninstalled"), except "uni" said "you" ("a unit", "a union") (12).
  Section 9's version row lists `entities` and `roles` (9). No
  sentence in specs/ changes.
- After Astra round 68 (kb:9380559), a reading that holds an "or" or
  "and" the view puts in itself never merges with the clauses around
  it: "<value> is no or has no value" is in brackets inside any larger
  condition or value, under `and` and `or` alike (`not order.held and
  order.units_sent > 0` reads "(the order's held is no or has no value)
  and the order's units sent is more than 0"), and a value whose
  reading holds an "and" (a call of two or more arguments, a list) is
  in brackets wherever it stands inside a larger expression and before
  "is yes" (`check(1, 2) == 1` reads "(the check of 1 and 2) is 1"); a
  refusal's condition after "is asked and" and the facts after "it is
  done and" are the last part of that `and`. All of it is decided from
  the tree. In specs/, one sentence changes, none in meaning: story.edda
  line 375's refusal now reads "If view at is asked and either number
  is less than 1 or number is more than the story's version, then ...".
- The operation-name permission template is unchanged ("A shop user
  may remove an order."), as EDDA-007 expects it.
- The checker's plain run is unchanged. No block's text changes, so
  nothing needs re-approval.

## 28. Changes from revision 61

Build Plan kb:9379223, phase 2621, and decision N (kb:9379218, Q7): one
versioned JSON model of the whole spec, the graphs in it as data.

- `tools/check.py --model [DIR]` prints the model of a project that
  checks: every file with its blocks' status, the epics, roles,
  entities, stories and operations, each with its file and line, every
  expression with its Python `ast` as JSON, and four graphs as nodes
  and edges (9). A refused project prints its problems and exits 1.
- The model's shape is written down in section 9, so another stack can
  read it; `edda_model` is its own version, 1.
- `tools/check.py --graph <entity>.<property> [DIR]` draws the status
  life graph as text (9, 11, 12).
- The role inclusion graph has nodes and no edges: `includes:` is no
  longer in the language (9).
- From Astra's round 60 (kb:9380471): a `with:` value carries the kind
  the checker resolved it to, so `home: primary` and `home: "primary"`
  differ in the model; an empty `may_change` keeps its graph, every
  value and no arrow; a computed choice property's graph has the
  values the checker resolves; a step's verdict carries its line; a
  `DEFAULT` number is read by the grammar, so `DEFAULT 01` is 1 (9).
- From Astra's round 61 (kb:9380474): the text of a `DEFAULT` is taken
  exactly as written; a backslash is an ordinary character, there are
  no escape sequences, and a quote cannot stand inside it, so
  `DEFAULT "C:\New"` is `C:\New` and `DEFAULT "a\"b"` is
  `bad_type_phrase` (4). One reading of a `DEFAULT` serves the model and
  the runner, so `DEFAULT 01` left out in a given is 1 there too (4, 8).
- From Astra's round 62 (kb:9380479): a quoted `DEFAULT` that is
  exactly a valid time of section 7.2 is a TIME, so
  `DEFAULT "2026-10-04 09:00"` compares with `TIME("2026-10-05")`; the
  model gives its type as `TIME` and its default as written, and the
  runner gives a time when a given leaves it out. Any other quoted
  `DEFAULT`, `"2026-02-30"` included, is a TEXT (4, 8, 9).
- The checker's plain run is unchanged. No block's text changes, so
  nothing needs re-approval.

## 29. Changes from revision 60

Build Plan kb:9379223, phase 2625: every bound operation is held to its
contract, on every call the runner makes.

- The runner wraps every call of a bound operation, a step's `call:`
  and a read inside a fact, in the rules of section 6 (6, 9): the
  spec's refusal, `ensure` with `OLD`, `always` and the frame rule.
  Until links are built, the operations wrapped are the bound ones.
- The spec checks the code's refusals, it does not replace them: the
  first `refuse` condition that holds before the call is the reason
  the code must give, and when none holds the code must not refuse.
  A refused call must change nothing.
- `OLD(x)` is taken after the refusals and before the call, a copy of
  lists that keeps every entity's identity (6). It is found after the
  call by what the call cannot change: an input by its name, a
  comprehension's name by the value it took before (6).
- The frame rule covers every stored property location of every entity
  reachable from the givens and the inputs; a location is compared
  without reading it, so an unset value is never read. The actor's
  role properties are covered too, so a refused call that changes the
  actor fails. Naming a computed property names the stored locations
  its expression reads on that entity, the `ordered_by` of a read it
  calls included; naming a derived property names the stored
  properties of that entity only (6).
- A read called by an `always` fact keeps its own refusal and frame
  checks but does not judge the `always` facts again (6).
- `OLD(x)` inside a comprehension keeps the comprehension's names (6).
- A broken rule fails the example at the rule's own file and line, with
  one plain message per rule (6).
- An `ensure` or `always` fact that reads the clock leaves its story
  not run, like any other read of the clock (9).
- "Done" (11) is still not computed; `examples passed` now also means
  the rules held on every call. Section 13 no longer lists the rule
  wrapping as not begun.
- No block's text changes, so nothing needs re-approval.

## 30. Changes from revision 59

Decision EE (the vision kb:9378618): one story checked end to end
against real code, a deliberately broken implementation failing it,
before any new language feature. Build Plan kb:9379223, phase 2624.

- The binding and the runner are built for Edda's own `check` (9):
  `tools/edda_binding.py` binds `spec_file`, `problem` and `check` to
  the real checker, working on a copy of each fixture in a temporary
  folder; `tools/run.py` runs the examples and reports each example,
  each story (examples passed, failing, not run and why) and an exit
  code (0, 1, 3 of decision AA). A known failure always fails its
  story, even when something later in it has no binding.
- `ACTOR` is the latest call's actor and `RESULT` its return, kept
  across later steps without `when` (9).
- A `with:` value names a given only where its property is an entity
  or an actor; role names, choice values and text stay as written (9).
- What a binding provides is written down (9), so a binding in another
  stack can follow it: the runner fills in the values a maker gets
  (`DEFAULT`, `[]` for `MANY`, `None` for `OPTIONAL`, times as times,
  given names as the things made) and marks a required property left
  out as unset. Using an unset value, in a fact or inside bound code,
  fails the example; a property the binding does not provide leaves
  the story not run.
- A fact or who-line that reads the clock, directly or through a
  computed property or an operation that reads it, nested calls
  included, leaves the story not run (9).
- Permission is checked on every call of a step: an actor none of
  whose roles passes a who-line is refused with the reason of
  section 3.
- EDDA-001 and EDDA-002 pass their examples against the real checker;
  the other
  stories are not run, for want of a binding (`notes`, `approve`,
  `approve_block`, `diff`, `view`). `tools/test_run.py` points the
  binding at a checker broken on purpose and sees EDDA-001 fail on the
  example and the `then` line that catch the break.
- "Done" (11) keeps its one meaning and is not computed yet; the
  runner reports `examples passed` instead. Section 13 no longer
  lists the running of examples as not begun.
- No block's text changes, so nothing needs re-approval.

## 31. Changes from revision 58

Operator decision GG (kb:9378274 entry 139), from Astra's round 42
(kb:9380388, finding 2): revision 58 removed `TODAY`, and with it the
way to state a calendar-day contract (`due == TODAY`).

- `TODAY` is a fixed name again (1, 7.1, 7.2): the day of `NOW` in the
  business zone, a `TIME` at 00:00, the same kind of value as
  `TIME("2026-10-04")`. It compares with a day: `TIME("...")` or a
  property that holds one. A comparison with a text, a number or a
  yes/no is `type_mismatch`.
- Revision 58 has one type, `TIME`, for days and moments, so the
  checker cannot refuse a comparison of `TODAY` with a moment
  (`TODAY == NOW`); it passes, as it did in revision 57. 7.2 says so
  under "Days and moments".
- The read view reads `TODAY` as "today" (12).
- No block's text changes, so nothing needs re-approval.

## 32. Changes from revision 57

Operator decision FF (kb:9378274 entry 138; design kb:9380368, part 1),
from the shrink audits kb:9380362 and kb:9380363. The first of two
passes for revision 58: the language shrinks, and nothing a business
contract needs is lost.

- A time inside an expression is `TIME("2026-10-02 09:00")` (7.1, and
  the time format under 7.2). A text literal no longer stands where a
  TIME is expected, so `approved_at == "2026-10-02 09:00"` is
  `type_mismatch`. The checker's literal and list-position tracking,
  which existed for that rule, is gone (many of the changes below
  describe how it grew), and the comparison row of 7.1 is one
  sentence. Two lists compare by their elements' types, so a list that
  mixes kinds (`[1, "x"]`) no longer compares with itself. EDDA-005
  compares `approved_at` with `TIME("...")`.
- The seven style rules of the old 7.2 and the `second_way` refusal
  are removed: they were writing preferences, not contracts. What was
  a second way (`len(x) == 0`, `x == None`) now passes as written; a
  form the grammar forbids, a comparison chain (`a <= x <= b`)
  included, is `not_an_expression`. The old 7.3, the fixed names, is
  now 7.2. EDDA-001's example "a condition written a second way is
  refused" and the fixture `second_way` are removed: "a string that is
  not an expression is refused" already shows `not_an_expression`. Its
  rule no longer says "each is written the one allowed way".
- Slices (`list[1:]`) and the conditional `a if c else b` are removed;
  each is `not_an_expression`.
- `includes:` and `role_cycle` are removed: a who-line names every
  role it admits. EDDA-001's example "a role that includes
  itself is refused" and the fixture `role_cycle` are removed.
- `wording:` is removed (unused; screens are #2488). The
  `wording_drift` flag stays: it is about a refusal's reason and an
  ensure's means, not about the `wording:` key.
- `while:` and its `holds:` are removed: `always: ["not (c) or f"]`
  says the same.
- `TODAY`, `startswith`, `min` and `max` are removed. `NOW`, `"t" in
  text`, and `sum`, `any` and `all` stay.
- The `problem` entity's `rule` choice drops `second_way` and
  `role_cycle`, so `problem` and EDDA-001 need re-approval.

Pass 2, naming (operator decision DD, kb:9378274 entry 136, from the
naming audit kb:9380258): one word for one thing.

- `unknown_status` is `unknown_choice` and `unreachable_status` is
  `unreachable_choice`, with the messages `not one of <property>'s
  values: <value>` and `no change reaches <property>'s value: <value>`.
  The prose says "choice value", never "status". The fixtures are
  renamed to match.
- A role's properties are under `properties:`, as an entity's are;
  `has:` is gone.
- `problem.file` is `problem.file_name`: it is a text, not a reference
  to a spec_file.
- An item of a `.edda.vc` is a version, never an "entry", in the
  reference, the checker and the approve command. Messages name a
  version `v<n>` everywhere: `bad_version` (`entity order v2 out of
  sequence; expected v1`), `bad_pin` and the approve command's last
  line.
- The first `then` item, `DONE` or `refused:`, is the verdict; the
  schema's `$defs/outcome` is `$defs/verdict`. The read view's
  sentence kind `outcome` keeps its name.
- `tools/validate.py` is `tools/check.py`, the checker; the approve
  command's single read of the folder is a "reading", and a version's
  text stays a snapshot (`bad_snapshot`).
- "The rules" in the sense of a story's body is "the body"; `rules:`
  and `problem.rule` keep the word. "Block" for YAML layout is gone: a
  block is written out, one key per line, and `|` is "a `|` scalar".
- One word each: who-line (not permission line), no value (not
  nothing, empty or no-value), the operator (the one who approves),
  yes/no.
- The registry has one row per key; the keys inside keys carry the
  section that defines them.
- From Astra's round 42: a snapshot approved before revision 58 may
  hold `has:`, `includes:`, `wording:` or `while:`. The shape layer
  refused those keys, so such a `.edda.vc` was `bad_snapshot`, and the
  operator could not approve the migrated block, because approval
  refuses while the file does not check. A snapshot's shape layer now
  accepts these retired keys (section 10); a `.edda` still refuses
  them. Snapshots were never checked for meaning, so the removed
  expression forms needed no change. A block moved from `has:` to
  `properties:` differs from its snapshot, shows as a draft, and
  approving it records the next version.
- The fourth layer is history in a `.edda.vc` and flags in a `.edda`;
  the checker's fixture report uses the same four layer names.
- EDDA-001's rule "YAML tricks" says "YAML features outside the
  subset", matching `yaml_feature`. `problem` and EDDA-001 need
  re-approval, as after pass 1.

## 33. Changes from revision 56

Operator decision BB (kb:9378274 entry 134; tasks 2563 and 2565):

- `computed_cycle`, a new refusal in the meaning layer: a computed
  property that depends on itself, directly or through other computed
  properties, a reference into another entity or the refuse
  conditions, returns or ordered_by of a called operation included, is
  refused once per group of properties
  that loop through one another, at its first property (sections 4 and
  11). Before, such a loop was not reported and every comparison on it
  passed silently.
  The fixture `computed_cycle` holds one two-property loop; EDDA-001
  asserts its line.
- `rules_text` is renamed `body_text` (sections 10 and 11, the `story`
  and `version` entities), so it no longer reads as the `rules:` key;
  the meaning is unchanged. The approved snapshots keep the old name,
  so the blocks that changed are drafts until re-approved.

## 34. Changes from revision 55

Operator decisions for the build (task 2568):

- The approve command of section 10 is `tools/approve.py`, which
  settles the open question of its name. It computes the entry that
  was typed by hand before: the next number, the normalised text and,
  for a story, the pins in `story.blocks` order, worked out with the
  checker's own types for the dot paths. It refuses with the messages
  of EDDA-005 and EDDA-008.
- `because` is optional on the command, as in the history: without
  `--because` the entry has no `because:` key.
- The history stays append-only: the new file is the old bytes and one
  entry, checked on a copy before it is written, and written through a
  temporary file and a rename. Nothing in the language changes.
- After Astra round 36: one approval at a time per folder, under a lock
  from the first read to the rename, computed and checked on one
  snapshot that is re-read before writing; the pre-write check also
  rechecks that the story's blocks are approved and that `approved_at`,
  `approved_by` and `because` read back as given; a `because` with a
  line break is refused; an empty history (`[]`) becomes the entry
  alone; `approved_at` is the host's local time, taken as the business
  zone; `story.blocks` says which types of a dot path count.

## 35. Changes from revision 54

Operator decisions for the build (task 2567, kb:9379093 item 5):

- The checker prints the status of every role, entity and story of a
  file that checks, draft or approved with its version, and under a
  story with a version its changes (section 11). It follows section
  10's draft rules and section 11's `pins_stale` and `story.changes`;
  nothing in the language changes.
- A story never approved and a role or entity block show no changes;
  a stale pin shows only as `, pins stale` on the status line.
- A file whose history is refused shows no status and no changes; the
  history's refusals say why. The version shown is `version`,
  `len(versions)`, not the newest entry's number (kb:9379121).

## 36. Changes from revision 53

Operator decisions after the review on Fable (kb:9379090) and its
removal audit (kb:9379093):

- `rules_text` is text, as this reference already defined it: the
  normalised story with only `about:`, `as_a:`, `rules:`,
  `operations:` and `examples:` kept and every `notes:` entry removed.
  The checker had compared parsed values, so a story with two keys
  swapped counted as approved.
- `wording_drift` keeps two pairs, `when`/`reason` and `fact`/`means`.
  The operation-body pair fired on nearly every draft, the story pair
  could not fire, and the rules pair was never built.
- `about_untouched` is removed: "names" was never defined and it
  flagged EDDA-004 wrongly; `wrong_file` already covers placement.
- `plural_name` is removed: a naming habit, not a modelling mistake,
  and it missed the singular-reference case.
- `approved_against_older` is removed: a stale pin shows on the
  story's status line as "pins stale" instead (`story.pins_stale`).
- `unreachable_status` stays and says that it looks only at a choice
  with `DEFAULT`; section 4's `may_change:` row says so too.
- A block (`roles:`, `entities:`, `stories:`, each role, entity and
  story, each operation and example) in flow form is `yaml_feature`
  (section 2), in `.edda` and in a `.vc` snapshot (`bad_snapshot`):
  `rules_text` and `text` are compared by lines, and a second way to
  write a block broke both (Astra round 32). Its message is `a block
  is written one key per line, not in { } or [ ]` (Astra round 33).
- A key with a space before its colon (`operations :`) or an explicit
  `?` key is `yaml_feature` at the key's line, in `.edda` and in a
  `.vc` snapshot (`bad_snapshot`): `rules_text` reads keys by line,
  and a second way to write a key let a changed section drop out of
  it (Astra round 33).
- `wording_drift` "fact changed, means did not" is anchored at the
  fact's own line, not at its list item.

## 37. Changes from revision 52

- From Astra's round 30, findings 1 and 2, the wording decided by the
  operator: EDDA-001's `i_want` is "every fault that stops a file from
  checking refused, with its file, line and one plain message"; rules
  1, 2, 4 and 6 are reworded to say what their examples show; the
  `no_rule` example moves to a new rule 8, "when a story has rules,
  every example belongs to exactly one of them".
- From finding 3: a title under `shown_by:` is one physical line, like
  an example title as a key; a wrapped one is `yaml_feature` at its
  first line (`an example title is one line`), since YAML would fold
  it into a title that may name an example. A wrapped `rule:` sentence
  stays free text and may wrap.
- A new fixture, `wrapped_title`, and its EDDA-001 example, "an
  example title wrapped over two lines is refused", under rule 3.

## 38. Changes from revision 51

- The rules layer, Gherkin's `Rule:` with one check (decision
  kb:9378274 entry 100): a story may carry `rules:`, each item a
  `rule:` sentence and the `shown_by:` titles of the examples it
  groups; when present, every example belongs to exactly one rule,
  `no_rule` for one in none and `unknown_name` (`unknown example:
  <title>`) for a title that names no example, both in the meaning
  layer, and `declared_twice` for one named twice, in the shape layer
  like a given name used twice, so each rule keeps one layer.
  `rules:` is part of `rules_text`; a rule's examples against its
  sentence is a new wording-drift pair; the read view shows the
  examples under a `Rule:` heading.
- Seven new fixtures, one problem each: the six refusals that had no
  fixture and no example, `not_yaml`, `bad_name`, `second_way`,
  `type_mismatch`, `derived_in_given` and `wider_than_entity`, and
  `no_rule`.
- EDDA-001 rewritten: `i_want` covers every problem the checker finds;
  seven rules group its examples, with seven new examples for the
  seven fixtures; the entity `problem`'s `rule` list gains `no_rule`,
  and the entity `sentence`'s `kind` list gains `rule`.

## 39. Changes from revision 50

- From Astra's round 28: a join waits until both its lists are
  known, so a computed property joined from properties declared after
  it has the same type as one joined from properties declared before;
  with `numbers` computed as `[1]` and `days` as `["2026-10-03"]`,
  `values` computed as `numbers + days` makes `values[1] == NOW` pass
  and `values[1] == 1` refused in either order, and a read operation
  returning it the same.

## 40. Changes from revision 49

- From Astra's round 27: a computed property, an operation's result
  and `RESULT` keep the literal markers of their expression, so with
  `earliest` computed as `min(d for d in days)`, `earliest == NOW`
  passes like `min(d for d in days) == NOW` does, and a read
  operation returning it compares and passes as an input the same
  way; naming a calculation changes nothing.

## 41. Changes from revision 48

- From Astra's round 26: `min` and `max` keep what the elements they
  choose from may be, literals included, so
  `min(d for d in days) == NOW` passes for `days` a comprehension of
  a time literal and `min(d for d in days) == 1` is refused.

## 42. Changes from revision 47

- From Astra's round 25: an index into a conditional of lists gives
  what each branch's element may be, a branch without literals
  included, so `days[0] == NOW` passes when one branch is a
  comprehension of a time literal and the other of a `TIME`; a
  comprehension's variable keeps what the elements of its list may
  be, literals included, so `[d for d in days] == [NOW]` and
  `all(d == NOW for d in days)` pass.

## 43. Changes from revision 46

- From Astra's round 24: a join, a slice with a variable bound and an
  index that is not a constant keep what a list's elements may be,
  literals included, so with `days` a comprehension of a time
  literal, `days + []`, `days[:index]` and `days[index]` compare and
  pass as inputs like `days` itself, an optional value among the
  elements still standing only where `None` fits.

## 44. Changes from revision 45

- From Astra's round 23: a flow mapping or list left open at a line's
  end keeps a block open until it closes, in the checker's normaliser
  and the fixture generator's alike, so a block written in flow form
  over several lines normalises whole; a comprehension whose
  projection is a text literal remembers it, so a computed property
  holding one compares, indexes and passes as an input like a list
  of such literals.

## 45. Changes from revision 44

- From Astra's round 22: `ordered_by` accepts a `returns` that is a
  conditional of lists, each branch ordered, and its expressions see
  the common entity; `OLD(x)` is seen through wherever the shape of
  `x` matters, so `OLD(order.days[0]) == NOW` reads like
  `order.days[0] == NOW`; the keys table names a `refuse` item's
  `when:` and `reason:`, so the registry holds every key.

## 46. Changes from revision 43

- From Astra's round 21: a slice, a join and a constant index apply to
  each branch of a conditional of written-out lists on its own, so
  with `values` computed as `[1, "x"] if flag else [1]`,
  `values[:1] == [1]`, `values + [] == values` and
  `values[0] + 1 == 2` pass, and `values[0]` is optional only when
  the position picked is.

## 47. Changes from revision 42

- From Astra's round 20: a conditional of two written-out lists keeps
  each branch's positions when they cannot be merged, so a computed
  property such as `[1, "x"] if flag else []` compares with itself
  and `[]` still fits every list; an element a constant index picks
  keeps its literal inside another written-out list, so
  `[days[0]]` compares and passes as an input like `days` itself,
  an optional value among them still standing only where `None`
  fits.

## 48. Changes from revision 41

- From Astra's round 19: a `None` picked out of a list by a constant
  index still stands only where `None` fits, so a required input
  refuses it; a list's positions remember a literal in each branch of
  a conditional, so a computed property such as
  `["2026-10-03" if flag else "2026-10-04"]` compares like the
  literals.

## 49. Changes from revision 40

- From Astra's round 18: a text literal's position in a list remembers
  that it may stand for a time, so a computed property's literals
  compare and pass as inputs like the literals themselves; an input
  argument picked out by a constant index is checked as written.

## 50. Changes from revision 39

- From Astra's round 17: a constant index gives the element as
  written, so a time literal picked out of a list still reads as a
  time; `approved_by` is a name, checked as one; an unknown role on a
  who-line is anchored at the `role` line.

## 51. Changes from revision 38

- From Astra's round 16: a negative whole-number index or bound
  (`-1`) keeps a list's known positions, as `list[-1]` promised; a
  constant slice has only the elements it keeps, so a list word or
  `in` over it sees the right types; a bad role-list item is named as
  written (`true`, `FALSE`).

## 52. Changes from revision 37

- From Astra's round 15: a snapshot passes the shape layer too, so a
  keyword or bad name, a wrong key or a duplicate given name inside a
  snapshot is `bad_snapshot`; a list keeps its known positions through
  a computed property, a constant index or slice and a `+`, so a
  mixed list compares with itself and `[1, "x"][:1] == [1]` stands; a
  key that is `True` or `False` is `bad_name`, as written.

## 53. Changes from revision 36

- From Astra's round 14: a snapshot's quoting and names are checked
  too, so an unquoted text or a quoted name in a snapshot is
  `bad_snapshot`; a step's `call` never sees `RESULT`, which belongs
  to the `then` items after a call; two written-out lists compare
  position by position, so `[id, approved] == ["FIX-001", False]`
  stands; `None` is no text for `in`; a key that fits no allowed
  name form is one `bad_name`, and the outcome message belongs to
  `then` alone.

## 54. Changes from revision 35

- From Astra's round 13: a block's versions live in the history
  beside its file, an entry elsewhere is `bad_version` and a pin sees
  only those versions, so one block version has one text; a snapshot
  must be in the subset of section 2 with no duplicate key, and may
  name its block in flow form; `RESULT` is in scope only in a `then`
  item after a call; `in` refuses a right side that can only be
  `None`; a time literal is seen inside a list through a slice, a `+`,
  a comprehension's projection, `OLD` and alternatives; a first `then`
  item under a `when` that is neither `DONE` nor `refused` gets its
  own message.

## 55. Changes from revision 34

- From Astra's round 12: every `.vc` of a project is checked, with or
  without a `.edda` beside it, so an unchecked history can no longer
  supply a pin target; a snapshot must also read as one block under
  the entry's name; a `#` right after a closing quote is a comment
  for normalisation, as YAML reads it; two lists compare element by
  element even when their types read the same; each value the right
  side of `in` may be is checked on its own, with its own elements;
  `None` compares with anything inside a list as well; the quoted-key
  and misplaced-`DONE` messages are in the `yaml_feature` row; the
  validator's own description names the history checks.

## 56. Changes from revision 33

- From Astra's round 11: `bad_pin` and `bad_snapshot` are checked, as
  section 10 states them, with their messages named and two fixtures
  and two EDDA-001 examples for them; a comparison checks every value
  one side may be against every value the other may be, so one
  fitting direction never excuses another branch; two lists compare
  by their elements whatever their order, and a time literal reads as
  a time inside a list and on either side; a list in a given must fit
  one declared list as a whole, two lists of different elements
  staying two lists; a literal list after `in` may mix bare statuses
  with other elements; an actor's `roles` written as one name is
  `not_a_list` in the shape layer; the union-kind `wrong_type`
  message is named; the comparison rows say which part is Python and
  which is Edda's type rule.

## 57. Changes from revision 32

- From Astra's round 10: a comparison types its operands (`==` two
  values of one kind, `in` an element of a list or a text in a text,
  `<` two numbers, texts or times); a given value whose property may
  be of several types must fit one of them; an optional choice keeps
  its statuses in comparisons, `may_change` and `wording`, and those
  two keys refuse a property that is no choice; types refine until
  nothing gets more precise, with no pass limit; two actors stay two
  alternatives, each with its roles' properties; each branch of a
  conditional and each operand of `and` or `or` is checked on its own,
  so a time literal in one branch reads as a time; an index or slice
  is for a list only, as 7.1 says; a part outside its owner's file is
  `wrong_file`; a given cannot set an actor's `name`; `None`, `True`
  and `False` as choice values and keywords in a role list are
  `bad_name` in the shape layer; a quoted `DONE` as the first `then`
  item is `bad_name`.

## 58. Changes from revision 31

- From Astra's round 9: a malformed shape never stops the shape
  layer; `None` stays an alternative, so an optional value stands only
  where `None` fits; types refine until nothing gets more precise,
  with `[]` apart from an unresolved element; a given actor has its
  roles' properties and `ACTOR` is the step's actor; a property two
  admitted roles declare differently may be either, and `name` and
  `roles` are fixed; a choice value keeps its list; alternatives are
  accepted wherever every one fits; `not_ordered` follows `RESULT`
  through a slice, an `or` or a comprehension; an `IN ORDER` input
  takes only an ordered list and `ordered_by` needs a list result; a
  bare status stands only beside `==` or `!=` or in a list after `in`;
  a role-list item must be a name, and a keyword choice value is
  refused in the shape layer; each cycle of includes is reported once
  at its first role; a duplicate is anchored at the second declaration
  in file order; the pin message is named; the schemas and the
  registry carry the revision from this file.

## 59. Changes from revision 30

- From Astra's round 8: `wrong_file` tests the file's name against the
  `about` entity's home; a value of two possible types stands only
  where both fit and `None` only for an optional input; a changing
  operation is allowed only as the step's own call; computed
  properties and `returns` types resolve together until nothing more
  resolves; text literals in rewrites are escaped exactly; a name
  declared twice in a project and a given name used twice are
  `declared_twice` in the shape layer; `also_changes` paths are quoted
  and resolved segment by segment; a bare status is in scope only in a
  comparison, and `ordered_by` sees only the result item; a text
  literal stands where a TIME is expected; a property read on a
  non-entity is `type_mismatch`; `ACTOR` has the properties of its
  roles, not of every role; `fixture:` only on a `spec_file`, `roles:`
  a list, computed properties cannot be given; a missing key is
  suppressed per block, not per line; a bad property name is anchored
  at its key; the message forms with a reason are named. Added to the
  checker: `not_ordered` through ordered list types, and `bad_version`
  as the first rule of the history layer.

## 60. Changes from revision 29

- From Astra's round 7: every style rewrite is built from the
  expression tree, so brackets survive; the prefix rewrite needs a text
  receiver, a whole-number bound and no step; comprehension variables
  are scoped as Python scopes them; list element types, `and`/`or`
  operand types, conditionals, the list words and computed properties
  propagate; a call is checked against its operation's `inputs:` and
  `RESULT` takes the `returns` type; the schema adapter keeps every
  failure of the matching branch; a recursive alias is one problem at
  the anchor; a comment never ends a normalised block;
  `spec_file.name` is `DERIVED`; choice checks apply only to choice
  productions; the messages name the block (`operation remove needs
  is:`) and the item (`one fact per line`), carry rule names and
  source lines, sorted; a quoted name is `bad_name` and a `with:`
  value is checked against its property's type; the history schema
  excludes Python keywords; the registry carries no invented `since`.
  Names are now resolved across the files of a folder: `unknown_name`,
  `unknown_status`, `wrong_file`, `role_cycle`, `wider_than_entity`
  and `derived_in_given` are checked.

## 61. Changes from revision 28

- From Astra's round 6: a story entry's pins are its own record from
  approval time, verified for targets and duplicates, never recomputed;
  normalisation tracks quotes across wrapped lines; Python keywords are
  `bad_name` as names and choice values; notes and questions are
  verbatim in the read view; `INTEGER` in the fixed-word table; a
  `call` is a call of an operation; `x[:n] == t` is a second way only
  when `t` has `n` characters, and every rewrite only where it means
  the same; every key plain and `wording` values quoted; the registry
  is `language/keywords.yaml`, generated plain YAML outside the
  subset; the validator infers types from literals and declarations,
  reports `type_mismatch`, collects every independent problem of a
  layer, maps schema failures to rule names with unknown-key
  suppression, checks every key's style, and matches type phrases on
  ASCII digits and escaped quotes.

## 62. Changes from revision 27

- From Astra's round 5: `INTEGER` beside `NUMBER`, and indices and
  bounds are INTEGER-valued expressions; the `DEFAULT` productions
  stand apart so `DEFAULT` never meets `OPTIONAL`; distinct choices;
  double quotes only, enforced indentation, one-line expressions,
  type phrases and titles, `DONE` only as the first `then` item;
  roots and property shorthand on who-lines; entity equality by
  identity and `OLD` keeping identities; a snapshot is self-contained
  and never compared with the current block; `bad_pin` checks the
  exact ordered pin set of the snapshot; the stale flag looks at the
  newest entry only; `type_mismatch` in the meaning layer and
  `returns_and_ensure` covering `ordered_by` and `also_changes`; the
  from-schema-to-rule table covers unions and the remaining keywords;
  no history policy in the schemas; `spec_file.name` is the stem and
  `note` fields are defined; 7.2 lists every second way with the
  writer's polarity kept; the read view keeps projections, splits
  permissions only at top-level `and`, renders input declarations,
  capitalises and anchors every sentence kind; `question_on_approved`
  at the story's key line; the registry labels say "Python syntax,
  Edda meaning" where that is the truth.

## 63. Changes from revision 26

- Expressions are Python (decision 46): one `ast` expression per slot,
  a whitelist of forms (7.1), a style rule (7.2), the fixed names
  (7.3). SQL spellings, UPPERCASE language words, `STARTS WITH`,
  `CONTAINS`, `COUNT`, `LENGTH`, `IS EMPTY`, `BETWEEN`, `YES`/`NO` and
  the Ruby interpolation are gone; `==`, `and`, `len`, `is None`,
  `True`/`False` and list equality (D1) are in. Times are quoted text.
- Who-lines are `{role, when}`; `WHOSE`, `WHILE` and `NOBODY` are
  gone; a `may_*` key left out means nobody; no bare names on a
  who-line.
- Required inputs by position, optional by keyword; the `inputs:` order
  is the call order; `has:` takes type phrases; `DEFAULT choice` is a
  production of the grammar.
- Approval: a named block must be approved, not just versioned; the
  history becomes exactly the old entries plus one; pins in
  `story.blocks` order; `story.blocks` and `pin.block` look across the
  project with closure through dot paths and `includes`; `bad_pin` and
  `bad_snapshot`; naming a derived property names its stored source.
- The default status counts as reached; the diff is stated as the exact
  walk; drift pairs are matched by position with a story-level
  message; a from-schema-to-rule table, an anchor rule and `bad_name`;
  the shape layer owns `returns`/`ensure` no longer (meaning layer).
- Read view: grouped givens, `Then it is done.`, steps without `when`,
  a source map for `line`, "whose" and "while" from the parts of one
  condition.
- Edda's own files: `block` and EDDA-008 in block.edda; `version` and
  `pin` beside `history` in spec_file.edda; the history's `versions`.
