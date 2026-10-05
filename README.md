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
language/   reference.md    the language reference, revision 66
            schema.json     the keys of .edda, JSON Schema 2020-12
            vc-schema.json  the keys of .edda.vc
            keywords.yaml   the registry: every key, expression form,
                            fixed name, checker rule and sentence kind,
                            with what it means, why, and where it is
                            from; plain YAML, not a spec
specs/      *.edda          Edda's own stories, YAML, one file per entity
            *.edda.vc       approved versions, append-only; the blocks
                            so far, the stories still drafts
            glossary.links  the code target, the naming rule and the
                            tools the link check reads
            edda.yaml       optional settings: generated_cases, off
                            when absent; Edda's own specs have none
            *.links         per entity, the operations whose function
                            does not follow the rule
fixtures/   <name>/*.edda   one folder per fixture: a whole spec, checked
                            under its own file name, one deliberate
                            problem or one history each; the examples
                            name the folder
            <name>/*.edda.vc  the fixture's history, when it has one
            <name>/*.links, code.py  a fixture of the link layer
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
                            --graph one status life graph as text;
                            then the links: every operation to the one
                            function that does it, every marker to its
                            story's version, covered code no story
                            reaches flagged
            analyse.py      the analyser, called by check.py: four
                            flags read from the spec alone (a refusal
                            that can never be given, ensures that
                            cannot both hold, an ensure that cannot
                            fail, a change may_change does not allow)
            approve.py      the operator's approval of one story or
                            block, appended to its .edda.vc
            view.py         the read view: each story as plain
                            sentences, rendered from the JSON model,
                            notes grey, questions and drifted pairs
                            marked; --lines gives each one's line
            edda_binding.py the binding for Edda's own spec_file,
                            problem, check, story, version, sentence,
                            view and view_at: makes the givens from
                            fixture copies in a temporary folder and
                            calls the real checker and the read view;
                            no rules of its own
            run.py          the runner: every example through the
                            binding, every call held to its
                            operation's rules (refusals, ensure with
                            OLD, always, the frame rule), reported per
                            example and per story (examples passed,
                            failing, not run and why); generated
                            cases when edda.yaml turns them on
            generate.py     generated cases: random worlds and steps
                            from the glossary, every call held to its
                            rules, a failure shrunk and printed as an
                            example; needs Hypothesis
            requirements.txt  Hypothesis, needed only for generated
                            cases
            test_run.py     a checker broken on purpose must fail
                            EDDA-001; the real one passes it; each
                            broken rule fails its example
            test_generate.py  generated cases: an edge-value break
                            found and shrunk, a seed replayed, the
                            runner without Hypothesis
            test_model.py   the JSON model and the status life graph:
                            deterministic, every story and operation,
                            each expression's ast read back
            test_view.py    the read view: every sentence kind on a
                            small spec, every expression form in words,
                            EDDA-007 through the runner
            test_links.py   the link layer: Edda's own links, each link
                            fixture, each rule and the reach rule
            test_analyse.py the analyser: each flag raised, a near miss
                            not, a condition too complex skipped
```

A `.edda` file is YAML 1.2 in a strict subset: structure in keys, logic
in quoted Python expressions limited to a whitelist, names in
snake_case. Tell your editor the extension is YAML and point it at
`language/schema.json`.

Built so far: a partial checker, the approve command, and the running
of examples for the stories whose operations have a binding (Edda's
own `check`, `notes`, `view` and `view_at`: EDDA-001, EDDA-002,
EDDA-003 and EDDA-007),
each call held to its operation's rules, the JSON model of a spec, and
the read view, and the links from every operation to the code that
does it; the other bindings are not
there yet. `python3 tools/check.py` needs
PyYAML and jsonschema.
`python3 tools/run.py [--project DIR] [--seed N] [STORY ...]` runs
the examples (reference section 9): exit 0 when no story failed, 1
when one failed, 3 when Edda itself failed. A project whose
`edda.yaml` holds `generated_cases: {on: true, runs: 100, steps: 20}`
also gets generated cases, which need
`python3 -m pip install -r tools/requirements.txt`; `--seed N`
replays a failure.
`python3 tools/check.py --model [DIR]` prints the JSON model of a
project that checks, and `python3 tools/check.py --graph
ENTITY.PROPERTY [DIR]` its status life graph (reference section 9).
`python3 tools/view.py [--lines] [DIR] [STORY ...]` prints each story
as plain sentences (reference section 12).
`python3 tools/test_run.py` shows the runner catches a broken checker
and a bound operation that breaks a rule of its spec.
`python3 tools/test_links.py` holds the link layer to its rules
(reference sections 9 and 11).
`python3 tools/approve.py NAME --by OPERATOR [--because TEXT] [--dry-run]`
records an approval (reference section 10).
