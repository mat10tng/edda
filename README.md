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
language/   reference.md    the language reference, revision 62
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
                            changed lines; --model prints the
                            JSON model of a project that checks,
                            --graph one status life graph as text
            approve.py      the operator's approval of one story or
                            block, appended to its .edda.vc
            edda_binding.py the binding for Edda's own spec_file,
                            problem and check: makes the givens from
                            fixture copies in a temporary folder and
                            calls the real checker; no rules of its own
            run.py          the runner: every example through the
                            binding, every call held to its
                            operation's rules (refusals, ensure with
                            OLD, always, the frame rule), reported per
                            example and per story (examples passed,
                            failing, not run and why)
            test_run.py     a checker broken on purpose must fail
                            EDDA-001; the real one passes it; each
                            broken rule fails its example
            test_model.py   the JSON model and the status life graph:
                            deterministic, every story and operation,
                            each expression's ast read back
```

A `.edda` file is YAML 1.2 in a strict subset: structure in keys, logic
in quoted Python expressions limited to a whitelist, names in
snake_case. Tell your editor the extension is YAML and point it at
`language/schema.json`.

Built so far: a partial checker, the approve command, and the running
of examples for the stories whose operations have a binding (Edda's
own `check`: EDDA-001 and EDDA-002), each call held to its
operation's rules, and the JSON model of a spec; links and the other
bindings are not there yet. `python3 tools/check.py` needs
PyYAML and jsonschema.
`python3 tools/run.py [--project DIR] [STORY ...]` runs the examples
(reference section 9): exit 0 when no story failed, 1 when one failed,
3 when Edda itself failed.
`python3 tools/check.py --model [DIR]` prints the JSON model of a
project that checks, and `python3 tools/check.py --graph
ENTITY.PROPERTY [DIR]` its status life graph (reference section 9).
`python3 tools/test_run.py` shows the runner catches a broken checker
and a bound operation that breaks a rule of its spec.
`python3 tools/approve.py NAME --by OPERATOR [--because TEXT] [--dry-run]`
records an approval (reference section 10).
