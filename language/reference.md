# Edda: language reference

Draft, revision 24, 1 Oct 2026. Replaces revision 23 (kb:9378331).
Decisions behind it: kb:9378274, direction rounds 1 and 2. Everything
here is written so it can become `language/keywords.edda`: one entry
per word, each with what it means and why it exists.

## 1. The idea

- **Two levels.** Level 1 states: entities, statuses, who may do what,
  what an operation refuses and what is true after it, stories and
  examples. Level 2 does: ordered steps, in code or pseudocode. A step
  at level 1 is refused; a business rule at level 2 is refused.
- **Who writes, who reads.** An agent writes level 1 from the
  customer's words. A person reads the read view and approves. The
  agent builds level 2 and the code. The checker decides done.
- **One reading.** Every sentence has one shape from a closed list,
  over declared names. Anything else is refused. What the grammar
  cannot say goes in a `note:` and into the backlog; a new word
  arrives through the registry with a reason.
- **Checked, not trusted.** Names, links, versions and rules are
  checked against the code on every test run. Nothing the checker
  cannot read counts as a promise.

## 2. Files and layout

```
specs/
  glossary.edda      roles, and small entities with no stories
  epics.edda         one line per epic
  order.edda         entity order, then every story about orders
  order.edda.vc      approved copies of those stories, append-only
  order.links        level 2: business name -> code path, name map
  order.binding      level 2: how examples make, call and read entities
language/
  keywords.edda      the vocabulary; the checker refuses any other
  keywords.edda.vc   every addition approved with a reason
```

- **Placement.** A story lives in the file of the entity named by the
  first `ensure` line of its first operation. A part lives with its
  owner. The checker refuses a story in the wrong file; the agent
  never chooses.
- **Indentation.** Two spaces per level. A tab is refused.
- **Comments.** `#` ends a line with a comment. A story's id sits in
  its comment: `# FUL-005`. Comments carry no rules.
- **Continuation.** A line ending in a comma continues on the next,
  deeper line.
- **Names.** One snake_case word: `units_held`, `shop_user`. Declared
  once; an unknown name is refused. A business name may differ from
  the code's name; the links file maps them.
- **Reading a name.** `the order's status` reaches into an entity. Under
  an entity's own lines its properties are bare: `status`, not
  `it's status`.

## 3. Entities

```
entity order                                 # what a workshop buys
  shop: one shop
  workshop: one workshop
  lines: many order_line
  status: default incoming | delivered | removed
    may change: incoming to delivered, incoming to removed
    incoming: shop_user reads "Inkommande", workshop_user reads "Beställd"
  wanted_day, optional
  message, optional
  removed_by, optional
  removed_at, optional
  units_held: sum(line's units_held for line in lines)
  units_sent: sum(line's units_sent for line in lines)
  always units_sent is at most count(lines)
  may create: workshop_user
  may read:   shop_user whose shop is the order's shop
              workshop_user whose workshop is the order's workshop,
                while status is not removed
  may update: shop_user whose shop is the order's shop
  may delete: nobody

entity order_line, part of order
  article: one article
  units_held: default 0
  units_sent: default 0
```

| word | means | why |
|---|---|---|
| `entity <name>` | a kind of business object the system keeps | the glossary; every sentence is over declared entities |
| `role <name>` | a kind of person who uses the system | permissions and `who:` name roles; an example makes one person of a role |
| `<name>: one <entity>` | a property that holds one such entity | a relation with a count the checker reads |
| `<name>: many <entity>` | a property that holds any number | lists for comprehension and counts |
| `<name>, optional` | may be empty | `is set` and `is empty` can be asked |
| `<name>: default <value>` | the value when the entity is made | the industry word (SQL, JSON Schema, OpenAPI); an example need not state it |
| `a \| b \| c` | the only values a property may hold; the union bar of TypeScript and grammar notation; `default` before one of them marks the starting value | a status model the checker can follow; the read view says "one of" |
| `may change: a to b` | the only allowed status changes | an operation that breaks one fails; unreachable statuses are flagged |
| `<value>: <role> reads "<text>"` | the words a role sees for a value | the one piece of screen wording kept; the binding maps it |
| `<name>: <expression>` | a computed property; the short form of a read operation with no inputs beyond its entity | sentences can say `the order's units_held` |
| `part of <entity>` | this entity belongs to that one | placement: a story about a part lives with its owner; the frame rule reads the owner |
| `always <fact>` | holds for every entity of this kind, after every operation | an invariant the checker tests on the suite |
| `while <condition>, <fact>` | holds whenever the condition does | a state-bound invariant; EARS WHILE |

## 4. Permissions

| word | means | why |
|---|---|---|
| `may create: <who>` | who may make one | the standard CRUD verbs, so the matrix entity x verb x role is mechanical |
| `may read: <who>` | who may see one | replaces `hidden from`; a `while` on it hides in a state |
| `may update: <who>` | who may change one | the default `who:` of a changing operation |
| `may delete: <who>` | who may remove one for good | most entities say `nobody`; removal is usually an update |
| `<role> whose <condition>` | the role, narrowed to people for whom the condition holds | ownership: `shop_user whose shop is the order's shop` |
| `, while <condition>` | only while the condition holds on the entity | hides a removed order from the workshop |
| `nobody` | no one | default deny made explicit |
| `the actor` | the person asking now | refusals, outcomes and `whose` can name the asker |

Anything not listed is refused. One line that allows is enough.

## 5. Stories

```
epic the workshop orders from the shop                     # ORD

story remove orders from the list                          # FUL-005
  as a shop_user
  i want to remove an order that was never sent
  so that the list shows only live orders
  epic: ORD
  tags: ordering, shop
  note: the shop asked for undo; no rule yet
  question: may a removed order be restored?
  ...operations and examples...
```

| word | means | why |
|---|---|---|
| `epic <sentence> # <id>` | one sentence of intent, no rules; done when its stories are | one level above the story, nothing deeper |
| `story <sentence> # <id>` | who wants what and why; the unit of done, review, version and delivery | the todo list and the delivery are lists of stories |
| `as a <role>` | the role the story serves; must be declared | the one checked part of the sentence; the read view groups by role |
| `i want <text>` | the want, free text | stored and shown; nothing runs on it |
| `so that <text>` | the reason, free text | same |
| `epic: <id>` | which epic this story belongs to | grouping; a label, changeable without a new version |
| `tags: a, b` | any labels | grouping and search across epics |
| `note: <text>` | something the grammar cannot say; the checker ignores it, the read view shows it in grey | nothing the customer said is lost; repeated notes are the evidence for a new word |
| `question: <text>` | something undecided | a warning on the story, never a block |

The acceptance criteria of a story are its operations' contracts and
its examples. There is no separate list.

## 6. Operations

```
operation remove(order)
  who: a shop_user whose shop is the order's shop
  if the order's status is removed,
    refuse: "the order is already removed"
  if the order's units_sent is more than 0,
    refuse: "the order has been sent and cannot be removed"
  when remove succeeds, ensure:
    the order's status is removed
    the order's removed_by is the actor
    the order's removed_at is now
    the order's units_held is 0
  also changes: the order's history

operation open_orders(shop) returns
  [order for order in shop's orders if order's status is incoming]
```

| word | means | why |
|---|---|---|
| `operation <name>(<inputs>)` | one thing an actor can ask for; the anchor the code carries | states what right is, is testable, and is where spec and code meet |
| `who: <who>` | who may ask; optional | overrides the entity's `may update`, `may create` or `may read` |
| `if <condition>,` + `refuse: "<reason>"` | when asked and the condition holds, nothing changes and this reason is given | preconditions with a reason tests can match; EARS IF/THEN |
| `when <name> succeeds, ensure:` + facts | what is true after; one fact per line | postconditions; EARS WHEN/SHALL |
| `returns <expression>` | what a read operation gives back | one word for reads and writes; `returns` or `ensure`, never both |
| `also changes: <entity's property>` | a change the frame rule should allow without an `ensure` line | the frame rule reads everything else as unchanged |

- **Order of checks.** Permission first, then refusals in the order
  written, then the operation. The first refusal that holds is the
  reason given.
- **Frame rule.** After an operation, every property of every declared
  entity that is not named in `ensure` or `also changes` is unchanged.
  Undeclared data is not checked.
- **One at a time.** Operations have the results they would have if
  run one at a time.
- **Steps are level 2.** A line that says how (set, then, call) is
  refused here.

## 7. Conditions and values

| form | means |
|---|---|
| `x is v`, `x is not v` | equal, not equal |
| `x is more than v`, `x is less than v` | number or time comparison |
| `x is at least v`, `x is at most v` | inclusive comparison |
| `x is before v`, `x is after v` | time comparison in words |
| `x is longer than N characters` | text length |
| `x is set`, `x is empty` | an optional property has, or has no, value |
| `x in [a, b]` | membership, Python order |
| `a and b`, `a or b`, `not a` | combined; `not` first; brackets when mixed |
| `the <entity>'s <property>` | reach into an entity; chains allowed: `the order's shop's name` |
| `[x for x in list if condition]` | a filtered list, Python order |
| `sum(e for x in list)`, `count(list)`, `min`, `max`, `any`, `all` | the six list words |
| `now`, `today` | the time or day the operation runs, business zone, no offset |
| `the actor` | the person asking |
| `"text"`, `3`, `500 characters`, `2026-10-03 10:00` | literals |

Nothing else. Percent, rounding, money and date arithmetic are in the
backlog (#2494).

## 8. Examples

```
example Ta bort frees held stock
  given shop_user erik with shop butik
        order_line held with units_held 3, units_sent 0
        order purchase with shop butik, status incoming, lines [held]
  when  erik asks remove(purchase) at 2026-10-03 10:00
  then  done
        purchase's status is removed
        held's units_held is 0

example a sent order cannot be removed
  given shop_user erik with shop butik
        order_line gone with units_held 0, units_sent 2
        order purchase with shop butik, status incoming, lines [gone]
  when  erik asks remove(purchase)
  then  refused: "the order has been sent and cannot be removed"
        purchase's status is incoming
```

| word | means | why |
|---|---|---|
| `example <sentence>` | one concrete run; a test | the examples are the acceptance criteria that run |
| `given <entity> <name> with <property> <value>, ...` | make an entity and name it; items align in one column | names declared here are used below; no glue is written |
| `when <actor> asks <operation>(<args>) [at <time>]` | the request; time optional | one fixed shape so the checker finds actor and operation |
| `then done` + facts | the operation succeeded and these facts hold | postcondition check, plus the frame rule |
| `then refused: "<reason>"` + facts | the operation refused with this reason; facts unchanged | the same word as the operation's `refuse:`; tests match the spec's reason; the binding maps app wording |
| several `when`/`then` pairs | a flow in one example | place, then remove |

Examples use only declared names, so one small binding per name runs
every example; nothing is written per sentence.

## 9. Level 2: links and binding

```
order.links
  order        -> backend/app/models/orm.py:Order
  order.status -> Order.status
    incoming  = new, accepted, being_prepared, partly_sent
    delivered = completed
    removed   = cancelled
  remove       -> backend/app/services/fulfilment/cancel.py:cancel_order

in the code, on cancel_order:
  # FUL-005@3

order.binding
  order:       make(**fields) -> Order row; read(name)
  shop_user:   make(shop) -> Account with role 'store'
  remove:      call(actor, order) -> POST /api/store/orders/{id}/cancel
  reason "the order is already removed" -> app text "Ordern är redan borttagen"
```

- The links file holds every path and the business-to-code name map.
  Level 1 and the read view never show a path.
- The code comment carries story and version, so the link resolves
  both ways. Code with no comment is flagged as code with no story; a
  comment with no story is an error; `@3` against a story at v4 is
  "code behind the spec"; `@4` against v3 is "unapproved version".
- The binding is written once per entity, role and operation by the
  agent, and grows only when the glossary grows.

## 10. Versions and approval

```
order.edda.vc

=== FUL-005 v3  approved 2026-10-01 by tuan
because: the shop asked that sent orders cannot be removed
story remove orders from the list                          # FUL-005
  ...the whole story as approved...
=== FUL-005 v2  approved 2026-09-28 by tuan
...
```

- `.edda` is current; the agent edits it. `.edda.vc` is append-only;
  only the person's `edda approve` writes it, and the agent is denied
  by the same guard that protects a primary branch.
- **Draft.** A story whose operations or examples differ from its
  newest block. Labels (epic, tags, notes, question, the sentence)
  change freely and are stored at the next approval.
- **What changed** is computed between two versions as added, changed
  and removed sentences; never written by hand. `because:` is the
  person's one line, optional.
- The read view at a version is built from the block, so a customer's
  document for a delivery is exact. A milestone in the Plan is a list
  of story versions.
- Git keeps the history of both files. There is no other version
  store; where git is absent the same model applies.

## 11. The registry

```
language/keywords.edda

keyword asks
  means:   the actor sends the request named next
  why:     one fixed verb lets the checker find the actor and the
           operation in every example
  example: when erik asks remove(purchase) at 2026-10-03 10:00
  since:   v1
```

- The vocabulary is this file. A word in keyword position that is not
  in it is refused.
- Both views show `means` and `why` on hover, from this file.
- A new word is added like a rule: drafted by the agent when a
  `note:` repeats, approved by the person with a `because:` in
  `keywords.edda.vc`. No word exists without a stated need.

## 12. What the checker does

- **Refuses:** a sentence not in the grammar; an unknown name or
  keyword; a name declared twice; a status not in its `|` list; a change
  not in `may change`; a step at level 1; a business rule at level 2;
  `returns` and `ensure` on one operation; a story in the wrong file;
  a tab.
- **Flags:** a status nothing reaches; code with no story; a story
  with no example; a `question:` on a done story; code behind the
  spec or at an unapproved version.
- **Collects:** every `note:` into one view grouped by wording, so a
  repeating kind shows itself.
- **Done.** A story is done when, at its approved version: it is not
  a draft; every example passes; the rule checks pass on the whole
  suite for its operations; every link resolves both ways. The checker
  computes it; the agent never marks it. An open question is a
  warning.
- **Runs, test only.** Examples through the binding; refusals,
  ensures, always/while rules and the frame rule wrapped round the
  linked operation for every test in the suite. Never in production.

## 13. Views

- **Read view.** Generated from checked lines, never edited: EARS
  sentences in story order (IF ... refuse; WHEN ... succeeds, ensure;
  WHILE; always), grouped by epic, tag or role on request; notes in
  grey; ids hidden; hover shows each keyword's meaning and reason.
- **Write view.** The `.edda` file with syntax colour: keywords blue,
  refuse red, ensure green, names purple, values teal, strings amber,
  comments grey.
- **Diff view.** Two versions as added, changed and removed sentences.

## 14. Not in this revision

Qualities and infrastructure (#2487), time-triggered operations
(#2486), screens beyond `reads` (#2488), timing and concurrency
(#2489), generated cases (#2490), the analyser (#2491), drafting from
existing code (#2492), story to Plan tasks (#2493), richer
calculations (#2494), tooling (#2495). Revision 23's containers,
components, due lines, other systems with contracts, and the
infrastructure log are parked under #2487 and #2486.

## 15. Changes from revision 23

- `command` and `x.verb` headers become `operation name(inputs)`;
  steps leave level 1; `refuse if:` becomes one `if ..., refuse:` per
  refusal; outcomes become `when ... succeeds, ensure:`.
- `person` and `permissions` rows become `role` and CRUD lines on the
  entity; `hidden from` dropped; enum values under a property become
  `a | b | c`; `= value` becomes `default value`.
- Dots become `'s`; symbols become words (`is more than`); the six list
  words and the comprehension form replace `every`/`some`; examples end
  `then done` or `then refused: "<reason>"`.
- Stories, epics, tags, notes and questions added; `part` headers and
  sections dropped; one file per entity by rule.
- Refs `[S12]` become `# FUL-005@3` with a version; `.edda.vc` and
  approval added; the keyword registry added.
- Containers, components, due lines and other systems parked.
