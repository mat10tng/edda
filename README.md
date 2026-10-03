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
language/   reference.md    the language reference, revision 54
            schema.json     the keys of .edda, JSON Schema 2020-12
            vc-schema.json  the keys of .edda.vc
            keywords.yaml   the registry: every key, expression form,
                            style rule, fixed name, checker rule and
                            sentence kind, with what it means, why, and
                            where it is from; plain YAML, not a spec
specs/      *.edda          Edda's own stories, YAML, one file per entity
            *.edda.vc       approved versions, append-only; the blocks
                            so far, the stories still drafts
fixtures/   <name>/*.edda   one folder per fixture: a whole spec, checked
                            under its own file name, one deliberate
                            problem or one history each; the examples
                            name the folder
            <name>/*.edda.vc  the fixture's history, when it has one
tools/      gen_fixtures.py the fixtures, generated from one clean spec;
                            prints the lines and counts the stories assert
            gen_keywords.py the registry, generated from the reference
            validate.py     every file through the source, shape and
                            meaning layers: the YAML 1.2 subset, the
                            quoting rule, both schemas mapped to rule
                            names and lines, the type-phrase grammar,
                            names resolved across a folder, the Python
                            expression whitelist with types from
                            literals and declarations, operation
                            signatures, ordering, the style rule under
                            its equivalences, and the version sequence
                            of a history
```

A `.edda` file is YAML 1.2 in a strict subset: structure in keys, logic
in quoted Python expressions limited to a whitelist, names in
snake_case. Tell your editor the extension is YAML and point it at
`language/schema.json`.

Nothing is built beyond the validator, which is a partial checker:
the running of the examples is not there yet.
`python3 tools/validate.py` needs PyYAML and jsonschema.
