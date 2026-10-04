# Edda

Edda is a small language for saying what a system must do, in plain
sentences over declared names, and a checker that holds the code to it.

A story is the unit: who wants what and why, the operations it needs
(who may ask, when the system refuses and why, what is true after),
and examples. The business reads it; the checker refuses anything it
cannot check; the code carries a link to the story and its version.

Edda is written by coding agents from a customer's words and read and
approved by the operator, a person. It exists because an agent that
writes both the spec and the code will make them agree unless something
outside the agent checks them.

Edda is not a new method. It is BDD's examples, DDD's shared vocabulary
and invariants, and Design by Contract, with enforcement: a closed
grammar, checked names, links and versions tied to the code, and the
operator's approval as the only way an approved story or block changes.

The decisions behind the language live in the knowledge base
(project `edda`); this repository holds the language, the checker and
Edda's own stories.

## Layout

```
language/   reference.md    the language reference, revision 58
            schema.json     the keys of .edda, JSON Schema 2020-12
            vc-schema.json  the keys of .edda.vc
            keywords.yaml   the registry: every key, expression form,
                            fixed name, checker rule and sentence kind,
                            with what it means, why, and where it is
                            from; plain YAML, not a spec
specs/      *.edda          Edda's own stories, YAML, one file per entity
            *.edda.vc       approved versions, append-only; the blocks
                            so far, the stories still drafts
fixtures/   <name>/*.edda   one folder per fixture: a whole spec, checked
                            under its own file name, one deliberate
                            problem or one history each; the examples
                            name the folder
            <name>/*.edda.vc  the fixture's history, when it has one
tools/      gen_fixtures.py the fixtures, generated from one clean spec;
                            prints the lines and counts the stories
                            assert; it replaces fixtures/, so restore
                            the hand-made folders after running it
            gen_keywords.py the registry, generated from the reference
            check.py        the checker: every file through the four
                            layers (source, shape, meaning, history and
                            flags): the YAML 1.2 subset, the quoting
                            rule, both schemas mapped to rule names and
                            lines, the type-phrase grammar, names
                            resolved across a folder, the Python
                            expression whitelist with types from
                            literals and declarations, operation
                            signatures, ordering, the version sequence
                            of a history, and the flags; under a file
                            that checks, each block and story as draft
                            or approved with its version, and a story's
                            changed lines
            approve.py      the operator's approval of one story or
                            block, appended to its .edda.vc
```

A `.edda` file is YAML 1.2 in a strict subset: structure in keys, logic
in quoted Python expressions limited to a whitelist, names in
snake_case. Tell your editor the extension is YAML and point it at
`language/schema.json`.

Nothing is built beyond a partial checker and the approve command; the
running of the examples is not there yet. `python3 tools/check.py`
needs PyYAML and jsonschema.
`python3 tools/approve.py NAME --by OPERATOR [--because TEXT] [--dry-run]`
records an approval (reference section 10).
