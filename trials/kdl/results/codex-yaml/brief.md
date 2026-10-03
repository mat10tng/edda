# Brief: write an Edda spec from a customer's words (YAML trial)

You are an agent who writes Edda specs. Edda is a small language for
saying what a system must do; a checker refuses what it cannot check.
This is a timed trial: write the spec, run the checker, fix what it
reports, and repeat until it reports nothing.

## Your role

You are the implementer for this trial, launched directly by the chair
through `kb seats run`; this launch is your authority. You are not a
chair: do not look up Plans, claims, launch receipts or KB context,
and do not dispatch anyone. Read the files named below and write files
only in your folder. Nothing in the repository is changed.

## Your folder

Work only in `/private/tmp/claude-501/-Users-tuan-Documents-Git-edda/ea07cc1a-8fba-4ceb-98f3-802aec7bf0fa/scratchpad/trial/codex-yaml`. Write your files there and nowhere else.
Do not edit `runs.log` there; the checker writes it.

## Read

- `/Users/tuan/Documents/Git/edda/README.md`
- `/Users/tuan/Documents/Git/edda/language/reference.md`, sections 1
  to 8 (the language) and section 11's list of rules

- `/private/tmp/claude-501/-Users-tuan-Documents-Git-edda/ea07cc1a-8fba-4ceb-98f3-802aec7bf0fa/scratchpad/trial/codex-yaml/customer.md`: what the customer said.

Do not open `fixtures/`, `specs/` or `trials/kdl/results/` in the
repository: write from the customer's words and the reference only.

## Write

Write `.edda` files: `glossary.edda`, `part.edda`, `fulfillment.edda`.

One file per entity, as reference section 2 says, plus the project
file for roles and the epic. Each story's examples cover its normal
case and each refusal the customer named.

## Check

After writing, and after every fix, run:

    python3 /Users/tuan/Documents/Git/edda/trials/kdl/check.py /private/tmp/claude-501/-Users-tuan-Documents-Git-edda/ea07cc1a-8fba-4ceb-98f3-802aec7bf0fa/scratchpad/trial/codex-yaml --format yaml

Fix every problem it prints. Stop when it prints none, or after 15
runs. Do not change the checker or work around it.

## Report

Your files' names, how many check runs you needed, and in a few
lines what was hard to get right. Plain English.
