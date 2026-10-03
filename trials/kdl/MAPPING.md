# Edda in KDL: the mapping

A trial only. Edda's skeleton is YAML (`language/reference.md`). This
file says how to write the same spec in KDL version 2 (kdl.dev, spec
2.0.0) so that `check.py --format kdl` can translate it to YAML and run
Edda's own checker on it. Every rule of the reference still holds; only
the way the structure is written changes.

## The rules

One KDL node is one YAML key. A node is a name, then values or
properties, then an optional `{ }` block of child nodes. One node per
line; `;` ends a node early, so short blocks fit on one line.

| Edda (YAML) | KDL | rule |
|---|---|---|
| `about: order` | `about order` | a key with a scalar: the node's one value |
| `is: "a stocked part"` | `is "a stocked part"` | free text and expressions are quoted strings |
| `properties:` + keys under it | `properties { code TEXT }` | a mapping: child nodes in a `{ }` block |
| `tags: [ordering, shop]` | `tags { - ordering; - shop }` | a list: child nodes named `-`, one per item |
| `- when: "..."` `reason: "..."` | `- when="..." reason="..."` | a list of mappings: `-` nodes with properties |
| `who: [{role: buyer}]` | `who { - role=buyer }` | the same, one line |
| `inputs: {p: part, qty: INTEGER}` | `inputs p=part qty=INTEGER` | a flow map: properties on the node, written order kept |
| a mapping with a list in it | `with name="Main" { parts { - widget } }` | scalars as properties, the rest in the block |
| `"Ta bort frees stock":` | `"Ta bort frees stock" { ... }` | an example title: a quoted node name |
| `when: "x.name == \"a\""` | `when #"x.name == "a""#` | a string holding `"`: a raw string `#"..."#` |
| `stock: DEFAULT 0` | `stock DEFAULT 0` | a type phrase: its words as bare values, joined by one space |
| `lines: MANY line, IN ORDER` | `lines MANY line, IN ORDER` | the same; `,` and `\|` are part of the words |
| `because: "TEXT, OPTIONAL"` | `because="TEXT, OPTIONAL"` | a type phrase as one property value is quoted, as in YAML flow |
| `True`, `False`, `DONE` | `True`, `False`, `DONE` | Edda's words, bare; never KDL's `#true`, `#false`, `#null` |
| `quantity: 3`, `x: -1.5` | `quantity 3`, `x=-1.5` | numbers: digits, a sign, one `.` |

The quoting rule carries over: a bare word in KDL is a plain YAML value
and a quoted string is a double-quoted one. So names, ids, numbers,
`True`, `False`, `DONE` and type-phrase words are bare, and free text,
expressions, example titles and quoted times are strings, exactly where
the reference wants them. A bare word is letters, digits, `_` and `-`,
starting with a letter or `_`.

A node has either one value (or a type phrase's words), or properties
and a block, never both. A block holds only `-` nodes (a list) or only
named nodes (a mapping). Comments are `//`, `/* */` and `/-` (drops the
next node, value, property or block); like YAML comments they carry no
rules.

## Outside the mapping

Valid KDL that the mapping does not use is `kdl_feature`, at its line:
type annotations `(t)`, `#true` `#false` `#null` `#inf` `#nan`,
multi-line strings `"""`, line continuation `\`, whitespace escapes,
hex, octal, binary, exponent and `_` numbers, an empty `{ }`, an empty
`-`, a list inside a list, a node with both a value and a block, and a
bare word that is not a name. Invalid KDL is `not_kdl`. Either one
stops that file before Edda's checker reads it.

## The reference's example (sections 3 to 8)

```kdl
roles {
  shop_user {
    is "a person at a shop who orders from the workshop"
    has shop=shop
  }
  admin {
    is "a person who runs the system"
    includes { - shop_user }
  }
  agent {
    is "a program that writes .edda files"
  }
}

entities {
  order {
    is "what a workshop buys"
    properties {
      shop shop
      workshop workshop
      lines MANY order_line, IN ORDER
      status DEFAULT incoming | delivered | removed
      wanted_day TIME, OPTIONAL
      message TEXT, OPTIONAL
      units_held computed="sum(line.units_held for line in lines)"
      units_sent computed="sum(line.units_sent for line in lines)"
    }
    may_change { status { incoming { - delivered; - removed } } }
    wording { status { incoming shop_user="Inkommande" workshop_user="Beställd" } }
    always { - "units_sent <= len(lines)" }
    while { - when="status == removed" holds="units_held == 0" }
    may_create { - role=workshop_user }
    may_read {
      - role=shop_user when="ACTOR.shop == order.shop"
      - role=workshop_user when="ACTOR.workshop == order.workshop and order.status != removed"
      - role=admin
    }
    may_update { - role=shop_user when="ACTOR.shop == order.shop"; - role=admin }
  }

  order_line {
    is "one article on an order"
    part_of order
    properties {
      article article
      units_held DEFAULT 0
      units_sent DEFAULT 0
    }
  }
}

epics {
  ORD "the workshop orders from the shop"
}

stories {
  FUL-005 {
    story "remove orders from the list"
    about order
    as_a shop_user
    i_want "to remove an order that was never sent"
    so_that "the list shows only live orders"
    epic ORD
    tags { - ordering; - shop }
    notes { - "the shop asked for undo; no rule yet" }
    questions { - "may a removed order be restored?" }
    rules {
      - rule="a removed order gives its held stock back" {
          shown_by { - "Ta bort frees held stock" }
        }
    }
    operations {
      remove {
        is "takes an unsent order off the list and frees its held stock"
        inputs order=order because="TEXT, OPTIONAL"
        who { - role=shop_user when="ACTOR.shop == order.shop" }
        refuse {
          - when="order.status == removed" reason="the order is already removed"
          - when="order.units_sent > 0" reason="the order has been sent and cannot be removed"
        }
        ensure {
          - "order.status == removed"
          - "order.removed_by == ACTOR.name"
          - "order.removed_at == NOW"
          - fact="order.units_held == 0" means="the held stock goes back to the shelf"
        }
        also_changes { - "order.history" }
        notes { - "the shop calls this Ta bort" }
      }

      open_orders {
        is "lists the orders a shop still waits for"
        inputs shop=shop
        who { - role=shop_user when="ACTOR.shop == shop" }
        returns "[order for order in shop.orders if order.status == incoming]"
        ordered_by { - "order.wanted_day"; - "order.id" }
      }
    }
    examples {
      "Ta bort frees held stock" {
        given {
          - actor=erik {
              with shop=butik { roles { - shop_user } }
            }
          - order_line=held {
              with units_held=3 units_sent=0
            }
          - order=purchase {
              with shop=butik status=incoming { lines { - held } }
            }
        }
        steps {
          - {
              when actor=erik call="remove(purchase)" at="2026-10-03 10:00"
              then {
                - DONE
                - "purchase.status == removed"
                - "held.units_held == 0"
              }
            }
          - {
              when actor=erik call="remove(purchase)"
              then { - refused="the order is already removed" }
            }
        }
        notes { - "erik is the shop's buyer" }
      }
    }
  }
}
```
