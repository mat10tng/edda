# Edda: language reference

Revision 51, 3 Oct 2026. Replaces revision 50 (kb:9378949). Decisions
behind it: kb:9378274, rounds 1 to 4 (entries 1 to 46), and Astra's
rounds 4 to 28. The skeleton is YAML; the words are keys; the logic is
Python expressions in a whitelisted subset. Everything here is mirrored
by `language/schema.json` (the keys of a `.edda` file),
`language/vc-schema.json` (the keys of a `.edda.vc` file) and
`language/keywords.yaml` (the registry: every key, expression form,
fixed name, checker rule and sentence kind, with what it means, why it
exists and where it comes from; generated plain YAML, not a spec file,
so the subset below does not apply to it).

## 1. The idea

- **Two levels.** Level 1 states: entities, statuses, who may do what,
  what an operation refuses and what is true after, stories and
  examples. Level 2 does: ordered steps, in code. Level 1 cannot hold a
  step, because its only places for logic are expression slots, and a
  slot holds one expression, never a statement.
- **Who writes, who reads.** An agent writes level 1 from the customer's
  words. A person reads the read view and approves. The agent builds
  level 2 and the code. The checker decides done.
- **Structure in keys, logic in Python.** Everything that is structure
  (a request, a given, a fixture, an order, a permission) is a key the
  schema names. Only conditions, facts and values are expressions, and
  an expression is Python 3, parsed by Python's own `ast` and limited
  to the whitelist of section 7. Nothing is invented; one way per
  meaning is kept by the whitelist.
- **Shape tells words apart.** Declared names are snake_case; YAML keys
  are snake_case; ids are `ABC-123`; the fixed names `OLD`, `ACTOR`,
  `RESULT`, `NOW`, `TODAY` and the type-phrase words (`MANY`,
  `DEFAULT`, `TEXT`, ...) are UPPERCASE; Python's own keywords
  (`and`, `or`, `not`, `in`, `is`, `for`, `if`, `else`, `None`,
  `True`, `False`) are Python's.
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
  keywords.yaml      the registry, generated from this file
```

A `.edda` file is YAML 1.2, core schema, in this subset, which the
checker enforces at the source, before the schema:

- free text (`is:`, `story:`, `i_want:`, `so_that:`, `reason:`,
  `means:`, `wording` values, notes, questions, example titles) and
  every expression (an `also_changes` path with them) is quoted, with
  double quotes; a single-quoted
  scalar is `yaml_feature`; every key is plain, except example titles;
  names, numbers, ids, `True`, `False` and type-phrase words are
  plain (a quoted name is `bad_name`); `DONE` is plain only as the
  first `then` item (a quoted `DONE` there is `bad_name`, like any
  quoted name); an unquoted ` #` would silently drop the rest of
  the line;
- one physical line per expression, per type phrase and per example
  title; a block scalar (`|`, never `>`) is allowed only for `text:` in
  `.edda.vc`; free text may wrap onto further lines as YAML allows;
- repeated things are lists (`- `): refusals, ensures, givens, steps,
  then items, always-rules, notes, questions, who-lists, pins; mapping
  order is never a meaning, with two stated exceptions: the order of
  `inputs:` is the order of positional arguments in a call, and the
  read view, the diff and the `blocks` and `stories` indexes keep file
  order;
- no anchors, aliases, the `<<` key, tags, directives, complex keys,
  tabs or a second document;
- two-space indentation, enforced: a line's indentation is even and at
  most two deeper than the line before it, a list dash counting as two
  for the line after it; keys are snake_case except
  story ids (`ABC-123`), epic ids (`ABC`) and example titles (quoted
  text);
- a duplicate key is `declared_twice` at the second key; so is a
  role, entity, story or operation name declared twice in one
  project (at the second, in file order, then file-name order), a
  given name used twice in one example, and a `has:` entry named
  `name` or `roles`, which every actor has already; a declared
  name or choice value that is a Python keyword (`class`, `in`,
  `None`, ...) is `bad_name`, in the shape layer, since an expression
  could not reach it;
- `#` starts a comment outside a string; comments carry no rules, are
  invisible to the views and ignored by the version comparison.

**Placement.** A story carries `about: <entity>` and lives in that
entity's file, which for a part is its owner's (`wrong_file`
otherwise). `about` is authoritative; the
checker only flags `about_untouched` when the story names that entity
nowhere else (no input, given, fact or who-line). A part (`part_of:`)
lives in its owner's file, through the whole chain of owners
(`wrong_file` otherwise). One home per story; a story with two homes
is two stories under one epic.

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
| `has:` | the properties a holder of this role has, as type phrases | `ACTOR.shop == order.shop` needs a shop |
| `includes:` | every permission line admitting those roles admits this one too, condition included; a cycle is `role_cycle` | RBAC's role hierarchy |

An actor holds a set of roles. A request is allowed when any of its
roles passes any permission line, condition included. The permission
refusal reads `"<operation> is not allowed for <roles>"`, roles in the
order the actor's `roles:` lists them. `ACTOR` is the one asking: it has
`name` (its given name, text), `roles` (list of role names) and the
`has:` properties of its roles: on a who-line, those of that line's
role and of the roles it includes; inside an operation's body, those
every role on its `who:` has (a property two of them declare with
different types may be either, two lists of different elements
staying two lists); in an example, those of the given
actor's roles, and `ACTOR` is the step's actor. `name` and `roles`
are fixed; a role's `has:` cannot redeclare them, and a given cannot
set `name` (`derived_in_given`). Role blocks are versioned and pinned
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
    wording: {status: {incoming: {shop_user: "Inkommande", workshop_user: "Beställd"}}}
    always:
      - "units_sent <= len(lines)"
    while:
      - when: "status == removed"
        holds: "units_held == 0"
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
| `may_change:` | per status property, the only allowed changes; only on a choice property, optional or not (`type_mismatch` otherwise) | a change outside it fails at run time; an unreached status is flagged |
| `wording:` | per value and role, the words shown; only on a choice property (`type_mismatch` otherwise) | the one piece of screen wording kept |
| `always:` | facts that hold after every operation | invariants checked on the suite |
| `while:` | `when` a condition holds, `holds` a fact | state-bound invariants, EARS WHILE |
| `may_create:` `may_read:` `may_update:` `may_delete:` | who may, as a list of who-lines; a key left out means nobody | the CRUD matrix, default deny |

**Type phrases**, one closed grammar for properties, `has:` and
`inputs:`:

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

`DEFAULT` fixes the type from what follows: `DEFAULT 0` is an INTEGER,
`DEFAULT 1.5` a NUMBER, `DEFAULT "none"` a TEXT, `DEFAULT False` a
YES_NO, `DEFAULT incoming | removed` a choice whose first value is the
default; the type word is then not written. `DEFAULT` never goes with a
reference, a `MANY` or `OPTIONAL`, by the grammar. `INTEGER` is a whole
number; `NUMBER` any number; an INTEGER is accepted where a NUMBER is
expected, not the reverse. A bare name is a single reference to that
entity; a name that is no entity is `unknown_name`; a single-value
choice does not exist and a repeated value is `bad_type_phrase`. `, DERIVED` marks a property the checker computes by a rule of
section 11 named `<entity>.<property>`; it cannot be given
(`derived_in_given`). Anything else is `bad_type_phrase`. A computed
property is always `{computed: "<expression>"}`; one whose expression is
a condition is yes/no and is used as a condition (`order.approved`).

**Naming convention, flagged not refused:** a `MANY` property has a
plural name, a single reference a singular one (`plural_name`).

**Who-lines.** A who-line is `{role: <role>}` or `{role: <role>, when:
"<condition>"}`. The roots in scope in the condition are `ACTOR`, the
entity's own name on its `may_*` lines, and the inputs' names on an
operation's `who:` line. A property written without its root
(`shop == order.shop` for the actor's shop) is `unknown_name`.

**Scope of bare names.** A root is a name an expression may start
from. Inside `always`, `while` and `computed` the roots are the
entity's own properties; inside an operation its inputs; inside an
example its given names; inside `ordered_by` the result item, reached
by its entity's name; on a who-line, as above. A comprehension's
variable is a root inside that comprehension, with Python's scope.
Status values are in scope only where their property is compared:
beside `==` or `!=`, or as the bare names of a list after `in`; a
bare status anywhere else, `<` and `in` included, is `unknown_name`.
A choice value keeps its list: a choice stands for another only when
every value of its list is in the other's. The
fixed names of 7.3 are roots everywhere they are allowed.

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
  then the operation, then every `ensure`, `always` and `while`.
- **Frame rule.** After an operation, every stored property location of
  every entity reachable from the givens is unchanged unless it is
  named: a location is named when it is the left operand of an
  `ensure` fact's comparison (`==`, `!=`, `<`, `>`, `<=`, `>=`, `in`,
  `is None`, `is not None`), the argument of `len` in that operand, or
  listed under `also_changes`. Naming a derived property names the
  stored locations it derives from. A location read on the right side
  is not named. Naming a list allows elements to be added or removed
  and new elements to appear with their parts; the elements already
  there are entities of their own and stay unchanged unless named.
  Computed and derived properties follow.
- **`OLD(x)`** is the value of `x` captured after the refusals were
  checked and before the operation changed anything: a deep, frozen
  copy; `OLD(len(x))` is allowed. Only under `ensure`.
- **Equality of entities.** Two references are equal when they are the
  same entity, never by value; a frozen copy keeps every identity, so
  `OLD(history.versions) + [story.versions[-1]]` compares element by
  element with the live list by identity. Texts, numbers, times and
  choice values compare by value. A binding implements the same rule.
- **Empty values.** An `OPTIONAL` property or left-out input is `None`;
  `None == None` is true, as in Python; `<`, `>` and arithmetic on
  `None` fail the example.
- **Reads inside expressions.** `check(file)` in a fact calls a declared
  read operation, as the checker itself, with no actor and no
  permission check; a changing operation there is refused
  (`not_an_expression`). `call:` in a step is the example asking as an
  actor.
- **One at a time.** Operations have the results they would have if run
  one at a time. Without `at:`, `NOW` is the example's start, fixed by
  the binding.

## 7. Expressions

An expression slot (`when`, `holds`, `always`, `computed`, `returns`,
`ordered_by`, `fact`, a bare fact, a `then` item, `call`, a who-line's
`when`) holds one Python 3 expression, parsed by `ast.parse(text,
mode="eval")`. The checker walks the tree and refuses any node outside
this table (`not_an_expression`), any lowercase name not declared
(`unknown_name`), and any form the style rule spells another way
(`second_way`). Precedence, short-circuit and the meaning of every
form are Python's.

### 7.1 Forms

| form | means | from |
|---|---|---|
| `order.status`, `order.shop.name`, `story.versions[-1].text` | reach into an entity or a list element; chains allowed | Python |
| `x == v`, `x != v`, `x < v`, `x > v`, `x <= v`, `x >= v` | compare numbers, times, text, choice values, references and lists; two lists are equal when they have the same elements in the same order; one operator per comparison; `==` and `!=` take two values of one kind, every value one side may be against every value the other may be (`None` beside anything; a time literal beside a TIME, inside a list too; two lists whose positions are known position by position, any other pair of lists every element against every element, an `IN ORDER` list beside an unordered one; a list's positions are known when it is written out, sliced or joined from such lists with whole-number bounds, `-1` included, or a computed property of one, and a conditional of such lists keeps each branch's positions, a slice, a join and a constant index applying to each branch on its own; a slice of such a list has only the elements it keeps, and a constant index gives the element as written, a computed property's literals included and each branch of a conditional on its own, in a comparison, as an input, inside another written-out list and under `OLD` alike, an optional value among them standing only where `None` fits; a comprehension whose projection is a text literal is a list of such literals of unknown length, compared, indexed and passed as an input like one; a join, a slice with a variable bound and an index that is not a constant keep what the elements may be, literals included, their positions then unknown, an index into a conditional of lists giving what each branch's element may be; a comprehension's variable keeps what the elements of its list may be, literals included, and so do `min` and `max` of them; a computed property, an operation's result and `RESULT` keep the literal markers of their expression, so naming a calculation changes nothing), `<` and the rest two numbers, two texts or two times (`type_mismatch` otherwise) | Python syntax, Edda type rule |
| `a and b`, `a or b`, `not a` | logic; `not` binds tightest, then `and`, then `or`; short-circuit; `and` and `or` give one of their operands, as in Python, so `[1] or []` is a list | Python |
| `x is None`, `x is not None` | an optional value has no value, has a value | Python |
| `x in list`, `x not in list` | membership in a list; every value `x` may be is of the kind of every element (`type_mismatch` otherwise); a bare status in a literal list belongs to the compared property, the other elements are typed as usual | Python syntax, Edda type rule |
| `"t" in text`, `text.startswith("t")` | a text contains, starts with a text | Python |
| `len(x)` | the number of elements of a list or characters of a text | Python |
| `sum(e for x in list)`, `min(e for x in list)`, `max(e for x in list)`, `any(c for x in list)`, `all(c for x in list)` | the five list words, each with exactly one generator and nothing else; a generator appears nowhere else | Python |
| `[e for x in list if c]`, `[y for x in xs for y in x.ys]` | filtered and nested lists; order of the source kept; the variable is a plain name, never a path; never `async` | Python |
| `list[0]`, `list[-1]`, `list[n - 1]`, `list[1:]`, `list[:n]` | index and slice, on a list only (an index or slice on a text is `type_mismatch`); an index or bound is an INTEGER-valued expression (a constant, a name, a path, or those with `+ - *`), never a yes/no or a NUMBER; out of range fails the example | Python |
| `a if c else b` | conditional; the untaken side is not evaluated | Python |
| `story.approved`, `not fresh.approved` | a yes/no property as a condition | Python |
| `+ - * /`, `( )` | arithmetic; `+` joins two lists into a new list | Python |
| `"text"`, `\n`, `\"` | a text literal | Python |
| `"2026-10-03 10:00"`, `"2026-10-03"` | a time, written as a text literal and read as a TIME where a TIME is expected | Python syntax, Edda meaning |
| `3`, `-2`, `1.5`, `True`, `False`, `None`, `[]`, `[a, b]` | integer, number, yes/no, no-value and list literals | Python |
| `NOW`, `TODAY`, `ACTOR`, `RESULT` | the four fixed names: the time, the day, the asker, the latest call's return | Edda |
| `OLD(x)` | the value before the operation, one argument, only under `ensure` | Edda, after Eiffel's `old` |
| `len(x)`, `x.startswith(t)` | one argument each, no keywords | Python |
| `check(file)`, `approve(story, because="why")` | a declared operation called in Python call form: required inputs by position, optional ones by keyword | Python |

Nothing else: no lambda, dict, set, tuple, slice step, f-string,
walrus, star, `is` against anything but `None`, no bare generator, and
no method or function beyond those listed. Percent, rounding, money,
durations and date arithmetic are backlog #2494. A list word on a
non-list, `len` on a number, `+` between a list and a number, a
NUMBER as an index, an index on a text, or a comparison of two values
that do not compare is `type_mismatch`; the checker knows a list from
its declaration (`MANY`, a comprehension, a slice, a list literal) and
an element's type from the list's. A call of a declared operation is
checked against its `inputs:`: as many positional arguments as
required inputs, keywords only for optional inputs, each once, each
argument of its input's type (`type_mismatch` otherwise); a changing
operation inside a fact is `not_an_expression`; after a call, `RESULT`
has the type of the operation's `returns`. A property read on a value
that is no entity (`order.units_sent.made_up`) is `type_mismatch`. A
value that may be of two types (`a if c else b`, `x or y`) stands only
where both fit, each branch or operand checked on its own, so a text
literal in one branch still reads as a time, and in a comparison every
value one side may be is checked against every value the other may
be; an `OPTIONAL` property or
input may be `None`, so it stands only where `None` fits: an optional
input or a comparison; `[]` fits every list; a text literal stands
where a TIME is expected. An ordered list is a `MANY
..., IN ORDER` property, a list literal, a slice of or a comprehension
over an ordered list, a `+` of two ordered lists, or the result of an
operation with `ordered_by`; any other list has no order, and
`RESULT[n]` on one is `not_ordered`, through a slice, an `or` or a
comprehension of `RESULT` as well.

### 7.2 One way per meaning

The style rule, enforced as `second_way` with the message `write <one
way> (not <other>)`:

| meaning | the one way | not |
|---|---|---|
| a list is empty, not empty | `x == []`, `x != []` | `len(x) == 0`, `len(x) != 0`, `len(x) > 0`, `not x` on a list |
| the number of elements | `len(x)` | `sum(1 for ...)` |
| the first, the last | `x[0]`, `x[-1]` | `x[len(x) - 1]` |
| no value, a value | `x is None`, `x is not None` | `x == None`, `x != None`, `None == x` |
| a yes/no property holds, does not | `x.approved`, `not x.approved` | `x.approved == True`, `x.approved == False`, `True == x.approved` |
| between | `a <= x and x <= b` | `a <= x <= b` and every other comparison chain |
| text prefix | `x.startswith("t")` | `x[:n] == "t"` where `"t"` has `n` characters |

Each rewrite applies only where it means the same: the list rows only
to a list, the yes/no rows only to a yes/no, `x[len(x) - 1]` only when
both are the same `x`, and a comparison chain is rewritten with its
own operands and operators. The message keeps the writer's meaning:
`len(x) != 0` gets `write x != [] (not len(x) != 0)`, `x[:1] != "t"`
gets `write not x.startswith("t")`. A form that is both a second way
and outside 7.1 is reported as `second_way`.

### 7.3 Fixed names

| word | means | from |
|---|---|---|
| `OLD` | the value before the operation, only under `ensure` | Design by Contract |
| `ACTOR` | the asker: `name`, `roles`, and the `has:` properties of its roles | Edda |
| `RESULT` | what the latest call returned; no value after `refused`; in scope only in a `then` item after a call (`not_an_expression` elsewhere) | Edda |
| `NOW` `TODAY` | the time and the day of the request, in the business zone | Edda |
| `DONE` | the outcome of a successful call, as a `then` item, not inside an expression | Edda |
| `MANY` `IN ORDER` `DEFAULT` `OPTIONAL` `DERIVED` `TEXT` `NUMBER` `INTEGER` `TIME` `YES_NO` | type-phrase words, section 4, not inside an expression | Edda |

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
          - "purchase.status == removed"
          - "held.units_held == 0"
      - when: {actor: erik, call: "remove(purchase)"}
        then:
          - refused: "the order is already removed"
    notes: ["erik is the shop's buyer"]
```

| key | means | why |
|---|---|---|
| `examples:` | quoted title to example; one concrete run | the acceptance criteria that run |
| `given:` | a list of things to make; each item has exactly one key besides `with`: `- <entity>: <name>` or `- actor: <name>` | order-independent, schema-checked; names declared here are used below; the binding makes them; no glue is written |
| `with:` | property name to value: a number, quoted text, a quoted time, `True`, `False`, a choice value, a given name, or a flat list of those; `roles:` (a list of role names) for an actor, `fixture:` for a `spec_file` only | a property left out takes its `DEFAULT`, `[]` for `MANY`, `None` for `OPTIONAL`, otherwise unset: reading it fails the example; a derived or computed property, or an actor's `name`, is `derived_in_given`; every value is checked against the property's declared type, and a value whose property may be of several types must fit one of them as a whole, a list included: a plain text or time is `unquoted_text`, the wrong kind `type_mismatch`, a status not in its list `unknown_status`, a name no given declares `unknown_name`; `roles:` written as one name is `not_a_list` |
| `fixture:` | the folder under `fixtures/`; its file, and its history when present, become the given `spec_file` | the whole spec is the given, never a hand-made fragment |
| `steps:` | a list of `when` and `then`; `when` may be left out to check the given state | a flow is several steps |
| `when:` | `actor` (a declared given), `call` (a call of a declared operation with its arguments, Python call form; anything else is `not_an_expression`), `at` (optional time) | one fixed shape; every actor is declared (`unknown_name` otherwise) |
| `then:` | with `when`: the outcome first, `DONE` or `refused: "<reason>"`, then facts; without `when`: facts only | the checker compares; `RESULT` is what the latest call returned |
| `notes:` | free text | as on stories |

After `refused`, `RESULT` has no value; a changing operation returns
nothing. Facts after `refused` check that nothing changed.

**Keys inside keys**, for the registry:

| key | means | why |
|---|---|---|
| `computed:` | the one key of a computed property, holding its expression | a property that is an expression, never stored |
| `when:` `holds:` | in `while`: the condition and the fact that holds under it | EARS WHILE |
| `fact:` `means:` | a fact with its meaning in words | the meaning beside the mechanics (decision 40) |
| `role:` `when:` | a who-line: the role and its condition | one shape for every permission |
| `actor:` `call:` `at:` | inside a step's `when`: who asks, what, when | one fixed request shape |
| `refused:` | a `then` outcome with the reason given | tests match the reason |
| `when:` `reason:` | a `refuse` item: the condition and the reason given when it holds | preconditions with a reason tests match |
| `roles:` `fixture:` | inside `with:`: an actor's roles, a spec_file's folder | the binding reads them |

## 9. Level 2: links and binding

Unchanged from revision 24. `order.links` holds every path and the
business-to-code name map; the code carries `# FUL-005@3`; the binding
is written once per entity, role and operation; the checker emits one
versioned JSON model of the whole spec, with every expression as its
Python `ast` tree in JSON, which every binding consumes; a binding in
another stack evaluates that tree (the whitelist is small) or calls
Python. That an approval lands in the `.vc` file on disk and survives
a re-read is the binding's test, not a level 1 fact.

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
| `story:` `entity:` `role:` | which block this entry is a version of; exactly one | one entry, one block |
| `number:` | 1, 2, 3 ... per story or block, in file order | `bad_version` otherwise |
| `approved_at:` `approved_by:` `because:` | when, who (a name), why; `because` optional | the audit line |
| `pins:` | on a story entry: `{entity, number}` or `{role, number}` for every block the story names, in `story.blocks` order, no extras, no duplicates | the fence against a block changing under an approved story |
| `text:` | the block as approved, normalised | the exact copy |

- `.edda` is current; the agent edits it. `.edda.vc` is the file's
  history: append-only, oldest first, one entry per approved version of
  a story, an entity block or a role block of that file (role blocks in
  `glossary.edda.vc`; an entry for a block of another file is
  `bad_version`, and a pin sees only the versions in the history
  beside the block's file); only the operator's approve command writes
  it; a repository guard keeps the agent out.
- **Normalised text.** A block's `text` is its lines from its key line
  (`order:`, `FUL-005:`) to its last line, with comments, blank lines
  and trailing spaces removed and re-indented so the key line starts at
  column 0. A flow mapping or list left open at a line's end keeps the
  block open until it closes. Quoting is tracked across lines: inside a quoted text that
  wraps, a `#`, a blank line and the spaces are kept as they are; a
  `#` right after a closing quote starts a comment, as YAML reads it. An
  entry's
  `text` is a self-contained snapshot of the block as it was then: it
  must be normalised already (normalising it changes nothing), be in
  the subset of section 2 and pass the shape layer (its keys, names
  and duplicates), read as one block under the entry's name, and name
  that block on its first line, in block or flow form (`bad_snapshot`
  otherwise). It
  is never compared with the current block by the checker; `approved`
  does that, and only against the newest entry.
- **Draft, story.** Its `rules_text` differs from the newest version's:
  `rules_text` is `text` with only `about:`, `as_a:`, `operations:` and
  `examples:` kept and every `notes:` entry removed. The sentence,
  `i_want`, `so_that`, `epic`, `tags`, notes, questions, comments and
  blank lines change freely. **Draft, block.** Its `text` differs from
  the newest version's.
- **Pins.** A story version records every block the story named
  (section 11, `story.blocks`) at its version then, in that order. The
  entry's pins are its own record from approval time: the approve
  operation's ensure facts guarantee the set and the order; the checker
  never recomputes them from today's files, so a later permission,
  inclusion or re-ordering cannot invalidate an old entry. The checker
  does verify that every pin points at an existing version of a block
  that exists, that no `(kind, name)` repeats, that a story entry has
  pins and a block entry has none (`bad_pin` otherwise). A newer block
  version than the pin in the story's newest entry flags the story
  `approved_against_older`: "FUL-005 approved against entity order v2,
  order is now v3". A flag, not a draft; older entries are never
  flagged.
- **Approve a story.** Refused when the file does not check ("the file
  does not check"), when a named block is not approved, that is has no
  version or is itself a draft ("approve its blocks first"), or when
  the story is approved and no pin is stale ("nothing to approve: the
  story matches its newest version and its pins are current").
  Otherwise the history becomes exactly the old entries followed by one
  entry: the next number, the normalised text, the asker, the time, the
  `because`, and the pins. Blocks first, then stories; for Edda itself
  the ten entities and two roles, then EDDA-001.
- **Approve a block.** Refused when the file does not check or when the
  block is approved ("nothing to approve: the block matches its newest
  version"). Otherwise the history becomes exactly the old entries
  followed by one entry, without pins.
- **Wording drift.** In a draft, a pair whose one side differs from the
  newest version while the other does not. The pairs, smallest first:
  `fact`/`means` and `when`/`reason`, matched by position in their
  list (the first refusal with the first refusal) and only when both
  versions have an item at that position; an operation's body (inputs,
  who, refuse, ensure, returns, ordered_by, also_changes; not notes)
  against its `is:`; the story's `rules_text` against its `story:`
  sentence. Flagged `wording_drift` at the smallest pair that holds
  it; an operation is flagged only when none of its pairs is, the story
  only when none of its operations is. Shown side by side in the diff
  view, in the warning shade in the read view. The agent's standing
  rule is to re-read the meaning against the mechanics and fix or
  justify; approval clears it.
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
3. meaning: `unknown_name`, `unknown_status`, `bad_type_phrase`,
   `not_an_expression`, `second_way`, `type_mismatch`,
   `returns_and_ensure`, `wrong_file`, `not_ordered`, `role_cycle`,
   `derived_in_given`, `wider_than_entity`;
4. history and flags: `bad_version`, `bad_pin`, `bad_snapshot`, then
   every flag.

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
`wrong_type` (a text was expected, nothing was given). The schemas
hold no history policy: sequence, pins and snapshots are layer 4.

**Anchors.** A problem's `line` is the line of the key or value its
message names: the key for `unknown_key` and `missing_key` (the block's
key line), the second declaration for `declared_twice`, the
expression's line, the property's line for `unknown_status`,
`bad_type_phrase`, `unreachable_status` and `plural_name`, the first
role's `includes:` line for `role_cycle`, the `then` item's line for
`not_ordered`, the operation's key line for `returns_and_ensure`, the
entity's key line for `wrong_file` on a part, the
story's key line for `wrong_file`, `no_example`, `about_untouched`,
`question_on_approved` and `approved_against_older`, the changed
side's line for `wording_drift`, and in the `.vc` the entry's
`number:` line for `bad_version`, `bad_snapshot` and a story entry
without pins, the entry's `pins:` line for pins on a block entry, and
the pin's line for every other `bad_pin`.

**Refusals** (`problem.kind == refused`), with their messages:

| rule | when | message |
|---|---|---|
| `not_yaml` | the file does not parse | `not YAML: <parser message>` |
| `yaml_feature` | an anchor (its aliases with it), tag, directive, `<<`, complex key, tab, second document, single quotes, a folded scalar, a block scalar outside `.vc` text, an odd or jumping indentation, an expression, type phrase or title on more than one line, a quoted key, or `DONE` anywhere but first under `then` | `anchors and aliases are not allowed` (and likewise for each feature); `a key is plain, not quoted`; `DONE is allowed only as the first then item` |
| `unquoted_text` | free text or an expression written plain | `quote the <key>; an unquoted # drops the rest of the line` |
| `not_a_list` | a repeated thing written as a scalar or a mapping, an actor's `roles` as one name among them | `<key> must be a list, one <item> per line`, the item being fact, refusal, who-line, given, step, item, note, question, pin, expression, path, rule, tag or role |
| `wrong_type` | a mapping, list or scalar where another is expected; an empty list where one item is needed; a given item without exactly one name; a `with` value that is not flat; an empty expression or type phrase; a quoted `DONE` after the first `then` item; a `.vc` entry or pin naming no block | `<key> must be a <mapping/list/text/number/yes-no>`, or `<key> must be a <kind> or a <kind>` where the schema allows several; `<key> must be a list with at least one <item>`; `given must name exactly one thing besides with`; `<key> must be a number, text, yes/no, name or a flat list of those`; `<key> expects a text, nothing was given`; `<key> expects an expression, not DONE`; `then must start with DONE or refused` for a first `then` item under a `when` that is neither; `<entry> must name one of story or entity or role`; `<pin> must name one of entity or role` |
| `missing_key` | a required key absent | `<block> needs <key>:`, the block named by kind and name: `operation remove`, `entity order`, `refusal 2`, `step 1`, `file` |
| `unknown_key` | a key the schema does not name | `unknown key: <key>` |
| `bad_name` | a name not snake_case, an id not `ABC-123`, a name, choice value or role-list item that is a Python keyword (`True` and `False` as keys included), a quoted name, a quoted `DONE` as the first `then` item, a role-list item that is no name | `not a name: <text>`, the text as written; for a quoted name `not a name: "<text>" (a name is plain)` |
| `declared_twice` | a duplicate key, a name declared twice in one project, a given name used twice in one example, a `has:` entry named `name` or `roles`; at the second | `declared twice: <name>` |
| `unknown_name` | an undeclared lowercase word, actor, entity, role, epic, operation, property, fixture or given; a bare name that is neither in scope nor a status compared with a choice property | `unknown name: <name>` |
| `unknown_status` | a status value not in its property's list: in a comparison, `may_change`, `wording` or a given | `status not in its list: <value>` |
| `bad_type_phrase` | a type phrase outside the grammar | `not a type phrase: <text>`; with a reason, `not a type phrase (<reason>): <text>` |
| `not_an_expression` | a string Python cannot parse, a node outside 7.1, a step in disguise, a changing call inside a fact, a `call` that is not a call of an operation, `RESULT` outside a `then` item after a call (a `call` itself never sees it) | `not an expression: <text>`; with a reason, `not an expression (<reason>): <text>` |
| `second_way` | a form 7.2 spells another way | `write <one way> (not <other>)` |
| `type_mismatch` | a list word on a non-list, `len` on a number, `+` between a list and a number, a NUMBER or yes/no as an index, an index or slice on a text, a comparison of two values of different kinds (`==`), of a non-element with a list (`in`) or of anything but two numbers, texts or times (`<`), a call with the wrong inputs, `None` for a required input, a value of two possible types where one does not fit, a property read on a non-entity, an unordered list for an `IN ORDER` input, a choice value outside the expected list, `ordered_by` on a result that is no list, `may_change` or `wording` on a property that is no choice, a given value of another type than its property or fitting none of its possible types | `<what> expects <kind>: <text>`; for a comparison `== expects two values of one kind: <text>`, `in expects an element of the list: <text>`, `in expects a text in a text: <text>`, `in expects a list or a text: <text>`, `< expects two numbers, two texts or two times: <text>`; `may_change expects a choice property: <property>` |
| `returns_and_ensure` | a read key with a write key, or `ordered_by` without `returns`, or `also_changes` without `ensure` | `returns and ensure on one operation: <name>`, `returns and also_changes on one operation: <name>`, `ordered_by needs returns: <name>`, `also_changes needs ensure: <name>` |
| `wrong_file` | a story in another entity's file; a part outside its owner's file | `story <id> is about <entity> and belongs in <entity>.edda`; `entity <name> is part of <owner> and belongs in <entity>.edda` |
| `not_ordered` | `RESULT[n]` on an unordered return, through a slice, `or` or comprehension of `RESULT` as well | `<operation> gives no order; RESULT[<n>] needs ordered_by or IN ORDER` |
| `role_cycle` | `includes` reaches itself; each cycle once, at its first role in file order | `role <name> includes itself` |
| `derived_in_given` | a `with:` value for a derived or computed property, or for an actor's `name` | `<property> is derived and cannot be given`, `<property> is computed and cannot be given`, `name is fixed and cannot be given` |
| `wider_than_entity` | `who:` admits a role the `about` entity's matrix never names | `<operation> admits <role>, which <entity> does not` |
| `bad_version` | a `.vc` number out of sequence, an unknown story or block, or an entry for a block of another file | `<kind> <name> version <n> out of sequence; expected <m>`; for an unknown block, `<kind> <name> version <n>: no such <kind>`; for another file's block, `<kind> <name> version <n>: belongs in <file>.edda.vc` |
| `bad_pin` | a pin on a block entry, a story entry without pins, a duplicate `(kind, name)`, a pin to no such block or version; a version exists when a history of the project holds it | `pin <kind> <name> v<n>: no such version`, `pin <kind> <name> v<n>: no such <kind>`, `pin <kind> <name> v<n>: pinned twice`, `story <id> version <n>: no pins`, `<kind> <name> version <n>: a block entry has no pins` |
| `bad_snapshot` | an entry's text that is not already normalised, is outside the subset of section 2 or fails the shape layer (a bad name, a wrong key, a duplicate), does not read as one block under the entry's name, or does not name it on its first line | `text of <kind> <name> v<n> is not a normalised block` |

**Flags** (`problem.kind == flagged`):

| rule | when | message |
|---|---|---|
| `unreachable_status` | a status that is neither the default nor the target of a `may_change` arrow | `no change reaches status: <value>` |
| `no_example` | a story with no example | `story <id> has no example` |
| `approved_against_older` | a pin older than its block | `<id> approved against <kind> <name> v<n>, <name> is now v<m>` |
| `question_on_approved` | a question on an approved story | `story <id> is approved and still has a question` |
| `wording_drift` | section 10 | `<id> <operation>: <side> changed, <other> did not`; for the story pair `<id>: rules changed, story sentence did not` |
| `plural_name` | a `MANY` property with a singular name, or a reference with a plural one | `<property> holds MANY and should be plural` |
| `about_untouched` | a story that never names its `about` entity | `story <id> is about <entity> but never names it` |

Level 2 adds: code with no story; code behind the spec or at an
unapproved version.

**Derived properties** (`, DERIVED`), by name:

- `spec_file.blocks`, `spec_file.stories`: the role and entity blocks,
  the stories, in file order.
- `spec_file.name`: the file name without `.edda` (`order`);
  `problem.file` carries the full name (`order.edda`, `order.edda.vc`).
- `spec_file.notes`: every `notes:` entry under a story, an operation or
  an example, in file order; `file` is the enclosing spec_file,
  `story_id` the enclosing story's id, `line` the line of the note's
  text, `text` the string as YAML reads it.
- `spec_file.problems`: the refusals and flags above for this file and
  its history, ordered as the layers say.
- `history.versions`: the entries of the file's `.vc`, oldest first;
  `[]` when there is no `.vc`.
- `block.kind`, `block.name`, `block.text`, `story.id`, `story.about`,
  `story.as_a`, `story.sentence`, `story.epic`, `story.text`: from the
  block; `text` is the normalised text of section 10.
- `story.rules_text`, `version.rules_text`: section 10, over `text`.
- `story.blocks`: the blocks the story names, looked up across the
  project's files: its `about` entity; every entity in an input type
  phrase or a given; every entity reached through a dot path in the
  story's expressions (the declared type of each step); every role in
  `as_a`, a who-line, a given's `roles:`, and on a `may_*` line of a
  collected entity; every role reached through `includes` of a
  collected role; each once; ordered by file name, then file order.
- `story.versions`, `block.versions`: the history's entries for this
  story or block, oldest first. `pins_stale` and
  `approved_against_older` look at the newest entry only.
- `pin.block`: the block of the pin's kind and name, looked up across
  the project's files.
- `story.changes`: walk the newest version's `text` (no lines when
  there is no version) and the current `text` from the top; two equal
  current lines match and both advance; otherwise skip the old line
  when the longest common sequence from there is at least as long as
  when skipping the new line, else skip the new line; a skipped old
  line is `removed`, with `line` the number of the next new line; a
  skipped new line is `added`, with its own number.
- `story.sentences`, `version.sentences`: section 12 over `text`; a
  sentence's `line` is the file line the normalised line came from
  (the checker keeps a source map); for a version, the line within the
  entry's text, counted from its key line.

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
| permission | `A <role> [whose <actor condition>] may <name> <inputs> [while <state condition>].`; the condition is split only at its top-level `and`: the parts that mention `ACTOR` go after "whose", the rest after "while"; a condition whose top is not `and` stays whole, after "whose" if it mentions `ACTOR`, else after "while"; an input reads as its type with "a" or "an" when its name is its type (`order: order` reads "an order"), else `<name>, a <type>` |
| refusal | `If <name> is asked for <an input> whose <condition>, then the system shall refuse it: <reason>.` when every left side starts with that input's name, which is then dropped; otherwise `If <name> is asked and <condition>, then ...` |
| outcome | `When <name> succeeds, <means>.` or, without `means`, `When <name> succeeds, <fact in words>.` |
| read | `<Name> gives <returns in words>[, ordered by <keys>].` |
| invariant | `Always, <fact>.` and `While <condition>, <fact>.` |
| example | `Example: <title>.` |
| given | one sentence for all givens: `Given <item>, and <item>.`; an actor reads `<name>, a <role>`; an entity `<name>, a <entity> with <property> <value> and <property> <value>`; items are joined with `, ` and the last with `, and ` (the comma stays because each item carries its own apposition) |
| when | `When <actor> asks to <name> <arguments>.` |
| then | with facts: `Then it is done and <facts>.` or `Then it is refused: <reason>, and <facts>.`; without: `Then it is done.` or `Then it is refused: <reason>.`; a step without `when`: `Then <facts>.`; facts joined with "and" |

Expressions in words, one rule per form of 7.1, composed inside out:
`.` reads `'s` (`the order's status`); `==` is, `!=` is not, `>` is
more than, `<` is less than, `>=` is at least, `<=` is at most; `and`,
`or`, `not` as they are, with brackets kept as "either ... or"; `is
None` is empty; `is not None` is set; `in` is in; `startswith` starts
with; `len(x)` the number of x; `sum(e for x in l)` the sum of e over
every x in l; `min`, `max` the smallest, the largest; `any(c for x in
l)` some x in l has c; `all` every x in l has c; `[e for x in l if c]`
e for every x in l where c (the projection `e` is kept; a bare `x`
reads "every x in l where c"); nested generators read in order; `l[0]`
the first of l; `l[-1]` the last of l; `l[n]` item n of l, counted
from 0; `l[a:b]` items a to b of l; `a if c else b` a if c, else b;
`+ - * /` plus, minus, times, divided by; `OLD(x)` x before; `ACTOR`
the asker; `RESULT` the result; `True` yes, `False` no; `None`
nothing; a text literal in its quotes. A name reads as words
(`units_sent` reads "units sent"); an entity type takes "a" or "an"; a
given or input keeps its name. Every rendered sentence starts with a
capital letter and ends with a full stop; a note or question is shown
as written, verbatim. Structural ids (story keys) are
hidden; an id written inside quoted text stays. Hover shows each key's
and word's meaning from the registry. `view_at` renders a version's
text with the wording and permissions of its pinned blocks.

**Anchors.** A sentence's `line` is: the story's key line for `story`;
the note's or question's text line; the operation's key line; the
who-line for `permission`; the `when` line for `refusal`; the fact's
line for `outcome`; the `returns` line for `read`; the fact's line for
`invariant`; the title line for `example`; the `given:` line for
`given`; the step's `when` line for `when`; the step's `then` line for
`then`.

**Write view.** The YAML with colour. **Diff view.** Two versions as
added and removed lines; drifted pairs side by side.

## 13. Not in this revision

Qualities and infrastructure (#2487), time-triggered operations
(#2486), screens beyond `wording` (#2488), timing and concurrency
(#2489), generated cases (#2490), the analyser (#2491), drafting from
existing code (#2492), story to Plan tasks (#2493), richer calculations
and durations (#2494), tooling (#2495), the KDL skeleton trial (#2512);
the running of examples, the frame-rule test and the done computation
are build step 4 and get their own stories then.

## 14. Changes from revision 50

- From Astra's round 28: a join waits until both its lists are
  known, so a computed property joined from properties declared after
  it has the same type as one joined from properties declared before;
  with `numbers` computed as `[1]` and `days` as `["2026-10-03"]`,
  `values` computed as `numbers + days` makes `values[1] == NOW` pass
  and `values[1] == 1` refused in either order, and a read operation
  returning it the same.

## 15. Changes from revision 49

- From Astra's round 27: a computed property, an operation's result
  and `RESULT` keep the literal markers of their expression, so with
  `earliest` computed as `min(d for d in days)`, `earliest == NOW`
  passes like `min(d for d in days) == NOW` does, and a read
  operation returning it compares and passes as an input the same
  way; naming a calculation changes nothing.

## 16. Changes from revision 48

- From Astra's round 26: `min` and `max` keep what the elements they
  choose from may be, literals included, so
  `min(d for d in days) == NOW` passes for `days` a comprehension of
  a time literal and `min(d for d in days) == 1` is refused.

## 17. Changes from revision 47

- From Astra's round 25: an index into a conditional of lists gives
  what each branch's element may be, a branch without literals
  included, so `days[0] == NOW` passes when one branch is a
  comprehension of a time literal and the other of a `TIME`; a
  comprehension's variable keeps what the elements of its list may
  be, literals included, so `[d for d in days] == [NOW]` and
  `all(d == NOW for d in days)` pass.

## 18. Changes from revision 46

- From Astra's round 24: a join, a slice with a variable bound and an
  index that is not a constant keep what a list's elements may be,
  literals included, so with `days` a comprehension of a time
  literal, `days + []`, `days[:index]` and `days[index]` compare and
  pass as inputs like `days` itself, an optional value among the
  elements still standing only where `None` fits.

## 19. Changes from revision 45

- From Astra's round 23: a flow mapping or list left open at a line's
  end keeps a block open until it closes, in the checker's normaliser
  and the fixture generator's alike, so a block written in flow form
  over several lines normalises whole; a comprehension whose
  projection is a text literal remembers it, so a computed property
  holding one compares, indexes and passes as an input like a list
  of such literals.

## 20. Changes from revision 44

- From Astra's round 22: `ordered_by` accepts a `returns` that is a
  conditional of lists, each branch ordered, and its expressions see
  the common entity; `OLD(x)` is seen through wherever the shape of
  `x` matters, so `OLD(order.days[0]) == NOW` reads like
  `order.days[0] == NOW`; the keys table names a `refuse` item's
  `when:` and `reason:`, so the registry holds every key.

## 21. Changes from revision 43

- From Astra's round 21: a slice, a join and a constant index apply to
  each branch of a conditional of written-out lists on its own, so
  with `values` computed as `[1, "x"] if flag else [1]`,
  `values[:1] == [1]`, `values + [] == values` and
  `values[0] + 1 == 2` pass, and `values[0]` is optional only when
  the position picked is.

## 22. Changes from revision 42

- From Astra's round 20: a conditional of two written-out lists keeps
  each branch's positions when they cannot be merged, so a computed
  property such as `[1, "x"] if flag else []` compares with itself
  and `[]` still fits every list; an element a constant index picks
  keeps its literal inside another written-out list, so
  `[days[0]]` compares and passes as an input like `days` itself,
  an optional value among them still standing only where `None`
  fits.

## 23. Changes from revision 41

- From Astra's round 19: a `None` picked out of a list by a constant
  index still stands only where `None` fits, so a required input
  refuses it; a list's positions remember a literal in each branch of
  a conditional, so a computed property such as
  `["2026-10-03" if flag else "2026-10-04"]` compares like the
  literals.

## 24. Changes from revision 40

- From Astra's round 18: a text literal's position in a list remembers
  that it may stand for a time, so a computed property's literals
  compare and pass as inputs like the literals themselves; an input
  argument picked out by a constant index is checked as written.

## 25. Changes from revision 39

- From Astra's round 17: a constant index gives the element as
  written, so a time literal picked out of a list still reads as a
  time; `approved_by` is a name, checked as one; an unknown role on a
  who-line is anchored at the `role` line.

## 26. Changes from revision 38

- From Astra's round 16: a negative whole-number index or bound
  (`-1`) keeps a list's known positions, as `list[-1]` promised; a
  constant slice has only the elements it keeps, so a list word or
  `in` over it sees the right types; a bad role-list item is named as
  written (`true`, `FALSE`).

## 27. Changes from revision 37

- From Astra's round 15: a snapshot passes the shape layer too, so a
  keyword or bad name, a wrong key or a duplicate given name inside a
  snapshot is `bad_snapshot`; a list keeps its known positions through
  a computed property, a constant index or slice and a `+`, so a
  mixed list compares with itself and `[1, "x"][:1] == [1]` stands; a
  key that is `True` or `False` is `bad_name`, as written.

## 28. Changes from revision 36

- From Astra's round 14: a snapshot's quoting and names are checked
  too, so an unquoted text or a quoted name in a snapshot is
  `bad_snapshot`; a step's `call` never sees `RESULT`, which belongs
  to the `then` items after a call; two written-out lists compare
  position by position, so `[id, approved] == ["FIX-001", False]`
  stands; `None` is no text for `in`; a key that fits no allowed
  name form is one `bad_name`, and the outcome message belongs to
  `then` alone.

## 29. Changes from revision 35

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

## 30. Changes from revision 34

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

## 31. Changes from revision 33

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

## 32. Changes from revision 32

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

## 33. Changes from revision 31

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

## 34. Changes from revision 30

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

## 35. Changes from revision 29

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

## 36. Changes from revision 28

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

## 37. Changes from revision 27

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

## 38. Changes from revision 26

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
