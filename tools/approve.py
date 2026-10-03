"""Record the operator's yes to one story or one role or entity block as its
next version in the .edda.vc beside its file (reference section 10).

    python3 tools/approve.py NAME --by PERSON [--because TEXT]
        [--at "YYYY-MM-DD HH:MM"] [--dry-run] [--folder DIR]

The history is append-only: the new file is the old bytes followed by one
entry, checked on a copy of the folder before it is written, and written
through a temporary file and a rename. Who runs the script is not checked
here; a guard outside the language keeps the agent out of the history."""

import argparse
import datetime
import glob
import json
import os
import re
import shutil
import sys
import tempfile

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validate as E                                    # noqa: E402

SECTIONS = (("roles", "role"), ("entities", "entity"), ("stories", "story"))
SECTION_OF = {kind: section for section, kind in SECTIONS}


class Refused(Exception):
    pass


def find(folder, name):
    """(path, kind) of the file that declares name, looked up across the
    folder's .edda files as YAML, whether or not they check"""
    for path in sorted(glob.glob(f"{folder}/*.edda")):
        _, data = E.load(path)
        for section, kind in SECTIONS:
            if name in E.mapping(E.mapping(data).get(section)):
                return path, kind
    raise Refused(f"unknown name: {name}")


def refusals(path, P):
    """the refusals of a .edda file and of the .edda.vc beside it"""
    out = []
    for p in (path, path + ".vc"):
        if os.path.exists(p):
            src, shape, meaning, history, _ = E.check(p, P)
            out += [(os.path.basename(p),) + r for r in src + shape + meaning + history]
    return out


class Files:
    """the folder's .edda files, loaded once each"""

    def __init__(self, folder):
        self.folder, self.cache = folder, {}

    def get(self, stem):
        if stem not in self.cache:
            self.cache[stem] = E.load(f"{self.folder}/{stem}.edda")
        return self.cache[stem]

    def current(self, kind, name, P):
        """block.text, story.text: the block's normalised text now"""
        source, _ = self.get(P.file_of(kind, name))
        return E.block_text(source.text, source.line((SECTION_OF[kind], name)))


def story_blocks(sid, P, files):
    """story.blocks (section 11): its about entity; every entity in an input
    type phrase or a given; every entity a dot path in its expressions
    reaches; every role in as_a, a who-line, a given's roles: and on a may_*
    line of a collected entity; every role those include; each once, by file
    name, then file order"""
    stem = P.stories[sid]
    source, data = files.get(stem)
    st = data["stories"][sid]
    entities, roles = {st.get("about")}, {st.get("as_a")}
    for op in E.mapping(st.get("operations")).values():
        entities |= {E.phrase_entity(v) for v in E.mapping(op.get("inputs")).values() if isinstance(v, str)}
        roles |= {w.get("role") for w in E.listing(op.get("who")) if isinstance(w, dict)}
    for exm in E.mapping(st.get("examples")).values():
        for g in E.listing(exm.get("given")):
            for k in E.mapping(g):
                if k == "actor":
                    roles |= set(E.listing(E.mapping(g.get("with")).get("roles")))
                elif k != "with":
                    entities.add(k)
    E.REACHED.clear()
    list(E.walk_meaning({"stories": {sid: st}}, stem, P, source))   # the checker's own typing of every expression
    entities = (entities | E.REACHED) & set(P.entities)
    E.REACHED.clear()
    for e in entities:
        roles |= {r for rs in P.entities[e]["may"].values() for r in rs}
    roles = P.closure([r for r in roles if r in P.roles])
    return [(k, n) for k, n in P.block_order if n in (entities if k == "entity" else roles)]


def version(P, kind, name):
    """block.version, story.version: len(versions)"""
    return len(P.versions.get((kind, name), ()))


def decide(folder, name):
    """(path, kind, number, pins or None, text) for the next version of name,
    or Refused"""
    path, kind = find(folder, name)
    P = E.project_of(folder)
    if refusals(path, P):
        raise Refused("the file does not check")
    files = Files(folder)
    text = files.current(kind, name, P)
    entry = P.newest_entry.get((kind, name))
    if kind != "story":
        if E.approved(kind, text, entry):
            raise Refused("nothing to approve: the block matches its newest version")
        return path, kind, version(P, kind, name) + 1, None, text
    blocks = story_blocks(name, P, files)
    if any(not E.approved(k, files.current(k, n, P), P.newest_entry.get((k, n))) for k, n in blocks):
        raise Refused("approve its blocks first")
    if E.approved(kind, text, entry) and not E.pins_stale(entry, P):
        raise Refused("nothing to approve: the story matches its newest version and its pins are current")
    return path, kind, version(P, kind, name) + 1, [(k, n, version(P, k, n)) for k, n in blocks], text


def entry_text(kind, name, number, at, by, because, pins, text):
    """one .edda.vc entry in the layout of the existing ones"""
    out = [f"- {kind}: {name}", f"  number: {number}", f'  approved_at: "{at}"', f"  approved_by: {by}"]
    if because is not None:
        out.append(f"  because: {json.dumps(because, ensure_ascii=False)}")
    if pins is not None:
        out.append("  pins: [" + ", ".join(f"{{{k}: {n}, number: {v}}}" for k, n, v in pins) + "]")
    out.append("  text: |")
    out += ["    " + line if line else "" for line in text.split("\n")[:-1]]
    return "\n".join(out) + "\n"


def try_on_copy(folder, path, kind, name, new_bytes, old_entries):
    """check the would-be folder: no refusal in the file or its history, the
    old entries kept and one added, its text the block's or story's text, a
    story's pins its blocks at their versions in story.blocks order, and the
    block or story then approved (and its pins current); raises Refused with
    the reason otherwise"""
    with tempfile.TemporaryDirectory(prefix="edda-approve-") as tmp:
        for p in glob.glob(f"{folder}/*.edda") + glob.glob(f"{folder}/*.edda.vc"):
            shutil.copy2(p, tmp)
        copy = os.path.join(tmp, os.path.basename(path))
        with open(copy + ".vc", "wb") as f:
            f.write(new_bytes)
        P = E.project_of(tmp)
        problems = refusals(copy, P)
        if problems:
            file, rule, line, msg = problems[0]
            raise Refused(f"the new history would not check: {file} {line}: {rule}: {msg}")
        entries = yaml.load(new_bytes.decode(), Loader=E.Core)
        if entries[:-1] != old_entries or len(entries) != len(old_entries) + 1:
            raise Refused("the new history would not keep the old entries")
        entry = P.newest_entry.get((kind, name))
        if entry != entries[-1]:
            raise Refused("the new entry is not the newest version")
        files = Files(tmp)
        if entry.get("text") != files.current(kind, name, P):
            raise Refused(f"the new entry's text is not the {kind}'s text")
        if kind == "story":
            pins = [{k: n, "number": version(P, k, n)} for k, n in story_blocks(name, P, files)]
            if entry.get("pins") != pins:
                raise Refused("the new entry's pins are not the story's blocks at their versions")
        if not E.approved(kind, files.current(kind, name, P), entry) or kind == "story" and E.pins_stale(entry, P):
            raise Refused(f"the {kind} would not be approved by the new entry")


def write_atomic(vc, old_bytes, new_bytes):
    """replace vc by new_bytes through a temporary file in the same folder,
    unless vc changed since old_bytes were read"""
    current = open(vc, "rb").read() if os.path.exists(vc) else b""
    if current != old_bytes:
        raise Refused("the history changed while approving; nothing written")
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(vc) or ".", prefix=".approve-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(new_bytes)
            f.flush()
            os.fsync(f.fileno())
        if os.path.exists(vc):
            shutil.copymode(vc, tmp)
        else:
            umask = os.umask(0)
            os.umask(umask)
            os.chmod(tmp, 0o666 & ~umask)
        os.replace(tmp, vc)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def main(argv=None):
    ap = argparse.ArgumentParser(description="Append the operator's approval of a story or block to its .edda.vc.")
    ap.add_argument("name", metavar="NAME", help="a story id (ABC-123) or a role or entity name")
    ap.add_argument("--by", required=True, help="the operator's name; becomes approved_by")
    ap.add_argument("--because", help="one line of why; left out when not given")
    ap.add_argument("--at", help='"YYYY-MM-DD HH:MM"; default now, local time')
    ap.add_argument("--dry-run", action="store_true", help="print the entry; write nothing")
    ap.add_argument("--folder", default=os.path.join(E.ROOT, "specs"), help="the project folder (default specs/)")
    a = ap.parse_args(argv)
    try:
        if not re.fullmatch(E.NAME, a.by) or a.by in E.PY_KEYWORDS:
            raise Refused(f"not a name: {a.by}")
        at = a.at if a.at is not None else datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        try:
            ok = re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}", at) and datetime.datetime.strptime(at, "%Y-%m-%d %H:%M")
        except ValueError:
            ok = False
        if not ok:
            raise Refused(f'not a time "YYYY-MM-DD HH:MM": {at}')
        folder = os.path.abspath(a.folder)
        path, kind, number, pins, text = decide(folder, a.name)
        entry = entry_text(kind, a.name, number, at, a.by, a.because, pins, text)
        vc = path + ".vc"
        old_bytes = open(vc, "rb").read() if os.path.exists(vc) else b""
        old_entries = (yaml.load(old_bytes.decode(), Loader=E.Core) or []) if old_bytes else []
        sep = b"" if not old_bytes or old_bytes.endswith(b"\n") else b"\n"
        new_bytes = old_bytes + sep + entry.encode()
        try_on_copy(folder, path, kind, a.name, new_bytes, old_entries)
        if a.dry_run:
            sys.stdout.write(entry)
            return 0
        write_atomic(vc, old_bytes, new_bytes)
        sys.stdout.write(entry)
        print(f"appended {kind} {a.name} version {number} to {vc}")
        return 0
    except Refused as r:
        print(r, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
