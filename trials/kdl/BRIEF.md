# Brief: KDL trial harness (task 2562, step A)

## Goal

Build a small harness so the same Edda checker can judge a spec
written in KDL, for a trial that compares YAML and KDL as Edda's
skeleton. Nothing in the product changes.

## Where

Repository ~/Documents/Git/edda, branch `bootstrap` (its only
branch; edits on it are the project's way of working). Base commit
58167df. Write only under `trials/kdl/`. Do not touch `tools/`,
`language/`, `specs/` or `fixtures/`. Do not commit; the chair
commits.

## Read first

- `README.md`
- `language/reference.md` sections 1 to 8 (the language)
- `tools/validate.py`: `Source`, `load`, `check`, `project_of`, and
  the `__main__` block (how a folder is checked and printed)
- `fixtures/inventory_autopart/*.edda` (a whole small spec)

## What to build

1. `trials/kdl/MAPPING.md`: how every Edda construct is written in
   KDL version 2 (https://kdl.dev, spec v2.0.0). One rule per
   construct: a mapping key with a scalar, a mapping with children,
   a list of scalars, a list of mappings (use `-` as the node name
   for list items, the KDL convention), flow maps on one line (node
   properties), quoted free text and expressions (use KDL v2 raw
   strings `#"..."#` where a string holds `"`), example titles as
   quoted node names, `True`/`False`/`DONE` and type phrases. End
   with the reference's `order` example (sections 3 to 8) written in
   KDL, complete. Keep it short; it is what a trial writer reads.

2. `trials/kdl/kdl2yaml.py`: reads a `.kdl` file and writes the
   equivalent `.edda` YAML text in Edda's subset (two-space indent,
   double-quoted free text and expressions, plain names), plus a
   line map: for each YAML line, the KDL line it came from. Parse
   KDL with your own small strict parser for the KDL v2 subset that
   MAPPING.md uses (nodes, string/raw-string/number/#true/#false/
   #null arguments, properties, children blocks, `//` and `/* */`
   comments, `/-` slashdash). No third-party packages. A KDL syntax
   error is reported as rule `not_kdl` at its KDL line. A KDL
   construct outside MAPPING.md is `kdl_feature`.

3. `trials/kdl/check.py FOLDER --format yaml|kdl`: checks one folder
   with Edda's own checker. For `yaml`, run validate's
   `project_of` and `check` on the folder's `.edda` files. For `kdl`,
   translate each `.kdl` to `.edda` in a temp folder, run the same,
   and map every problem's line back to the `.kdl` line. Print
   problems as validate does (`file: line: rule: message`). Append
   every run to `FOLDER/runs.log`, one JSON line per run: time,
   format, files, and the list of problems (rule, file, line). Exit
   0 when clean, 1 otherwise.

4. `trials/kdl/yaml2kdl.py`: the other direction, used only to make
   test inputs.

## Checks you must run

- `yaml2kdl` on each `fixtures/inventory_autopart/*.edda`, then
  `check.py --format kdl` on that KDL: zero problems, the same as
  `check.py --format yaml` on the fixture folder.
- Three broken KDL files you write (a syntax error, an unknown key,
  an unknown name in an expression): each problem is reported at the
  right `.kdl` line.
- `python3 tools/validate.py` still exits 0 and its output is
  unchanged (you did not touch it).

## Report

What you built, the exact commands and outputs of the checks above,
anything in KDL that maps awkwardly (with an example), and a full
self-review of the diff. Plain English, short.
