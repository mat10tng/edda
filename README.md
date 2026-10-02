# Edda

Edda is a small language for saying what a system must do, in plain
sentences over declared names, and a checker that holds the code to it.

A story is the unit: who wants what and why, the operations it needs
(who may ask, when the system refuses and why, what is true after),
and examples. The business reads it; the checker refuses anything it
cannot check; the code carries a link to the story and its version.

Edda is written by coding agents from a customer's words and read and
approved by a person. It exists because an agent that writes both the
spec and the code will make them agree unless something outside the
agent checks them.

Edda is not a new method. It is BDD's examples, DDD's shared vocabulary
and invariants, and Design by Contract, with enforcement: a closed
grammar, checked names, links and versions tied to the code, and a
person's approval as the only way a rule changes.

The decisions behind the language live in the knowledge base
(project `edda`); this repository holds the language, the checker and
Edda's own stories.

## Layout

```
language/   reference.md    the language reference, revision 24
            keywords.edda   the vocabulary, one entry per keyword
specs/      *.edda          Edda's own stories, one file per entity
            *.edda.vc       approved copies, append-only (none yet)
fixtures/   <name>/*.edda   one folder per fixture: a whole spec, checked
                            under its own file name, one deliberate
                            problem each; the examples name the folder
```

Nothing is built yet.
