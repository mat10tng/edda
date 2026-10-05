"""Record the operator's yes to one story or one role or entity block as its
next version in the .edda.vc beside its file (reference section 10).

    python3 tools/approve.py NAME --by OPERATOR [--because TEXT]
        [--at "YYYY-MM-DD HH:MM"] [--dry-run] [--root DIR] [--folder DIR]

The history is append-only: the new file is the old bytes followed by one
version (the version alone when the history has none), checked on a copy
of the folder before it is written, and written through a temporary file
and a rename. One approval at a time per folder: a lock on the folder is
held from the first read to the rename, everything is computed from one
reading of the folder's files, and nothing is written if any of them
changed meanwhile. With edda.yaml or a root in play, every file read and
the folder written resolve inside the root (outside_root); the temporary
file and the rename are made in the folder the lock holds open, so a
symlink swapped in after the check is never followed. Who runs the script is not checked here; a guard
outside the language keeps the agent out of the history. An approval
refused exits 1; an --by, --because or --at that is not well formed is
a usage error and exits 2 (reference section 13). The edda command runs
this as edda approve; with --json it fills a result."""

import argparse
import datetime
import fcntl
import glob
import os
import re
import secrets
import stat
import sys
import tempfile

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check as E                                       # noqa: E402

SECTIONS = (("roles", "role"), ("entities", "entity"), ("stories", "story"))
SECTION_OF = {kind: section for section, kind in SECTIONS}


class Refused(Exception):
    pass


def outside(path, real):
    return Refused(f"{os.path.relpath(path)}: outside_root: {os.path.basename(path)} "
                   f"resolves outside the project root: {real}")


def read_folder(folder, guard=None):
    """{file name: bytes} of the folder's .edda and .edda.vc files, each
    read only inside guard when given"""
    out = {}
    for p in sorted(glob.glob(f"{folder}/*.edda") + glob.glob(f"{folder}/*.edda.vc")):
        try:
            f = open(p, "rb") if guard is None else os.fdopen(E.open_inside(guard, p), "rb")
        except E.Outside as o:
            raise outside(p, o.args[0])
        with f:
            out[os.path.basename(p)] = f.read()
    return out


def materialise(files, folder):
    """write a reading's files into an empty folder"""
    for name, data in files.items():
        with open(os.path.join(folder, name), "wb") as f:
            f.write(data)


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
    line of a collected entity; each once, by file name, then file order"""
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
    roles = {r for r in roles if r in P.roles}
    return [(k, n) for k, n in P.block_order if n in (entities if k == "entity" else roles)]


def blocks_not_approved(blocks, P, files):
    """the blocks of story.blocks that have no version or are drafts"""
    return [(k, n) for k, n in blocks if not E.approved(k, files.current(k, n, P), P.newest_version.get((k, n)))]


def version(P, kind, name):
    """block.version, story.version: len(versions)"""
    return len(P.versions.get((kind, name), ()))


def decide(folder, name, clock=None):
    """(path, kind, number, pins or None, text) for the next version of name,
    or Refused; clock as for check.project_of"""
    path, kind = find(folder, name)
    P = E.project_of(folder, clock=clock)
    if refusals(path, P):
        raise Refused("the file does not check")
    files = Files(folder)
    text = files.current(kind, name, P)
    newest = P.newest_version.get((kind, name))
    if kind != "story":
        if E.approved(kind, text, newest):
            raise Refused("nothing to approve: the block matches its newest version")
        return path, kind, version(P, kind, name) + 1, None, text
    blocks = story_blocks(name, P, files)
    if blocks_not_approved(blocks, P, files):
        raise Refused("approve its blocks first")
    if E.approved(kind, text, newest) and not E.pins_stale(newest, P):
        raise Refused("nothing to approve: the story matches its newest version and its pins are current")
    return path, kind, version(P, kind, name) + 1, [(k, n, version(P, k, n)) for k, n in blocks], text


def is_one_line(text):
    """no character str.splitlines() splits on (\\n, \\r, U+0085, U+2028 ...)"""
    return "".join(text.splitlines()) == text


def quoted(text):
    """text as a YAML double-quoted scalar that reads back as text: a
    printable character as itself, any other as an escape"""
    out = []
    for c in text:
        o = ord(c)
        if c in '"\\':
            out.append("\\" + c)
        elif 0x20 <= o <= 0x7e or 0xa0 <= o <= 0xd7ff and o not in (0x2028, 0x2029) or 0xe000 <= o <= 0xfffd and o != 0xfeff \
                or 0x10000 <= o <= 0x10ffff:
            out.append(c)
        else:
            out.append(f"\\x{o:02x}" if o <= 0xff else f"\\u{o:04x}")
    return '"' + "".join(out) + '"'


def version_text(kind, name, number, at, by, because, pins, text):
    """one .edda.vc version in the layout of the existing ones"""
    out = [f"- {kind}: {name}", f"  number: {number}", f"  approved_at: {quoted(at)}", f"  approved_by: {by}"]
    if because is not None:
        out.append(f"  because: {quoted(because)}")
    if pins is not None:
        out.append("  pins: [" + ", ".join(f"{{{k}: {n}, number: {v}}}" for k, n, v in pins) + "]")
    out.append("  text: |")
    out += ["    " + line if line else "" for line in text.split("\n")[:-1]]
    return "\n".join(out) + "\n"


def try_on_copy(reading, path, kind, name, number, at, by, because, new_bytes, old_versions, clock=None):
    """check the would-be folder, built from the reading: no refusal in the
    file or its history; the old versions kept and one added; its name,
    number, approved_at, approved_by and because the ones given, its text
    the block's or story's text; for a story every block of story.blocks
    approved and pinned at its version, in story.blocks order; and the
    block or story then approved (and its pins current); raises Refused
    with the reason otherwise; clock, the project's, as for
    check.project_of"""
    with tempfile.TemporaryDirectory(prefix="edda-approve-") as tmp:
        materialise(reading, tmp)
        copy = os.path.join(tmp, os.path.basename(path))
        with open(copy + ".vc", "wb") as f:
            f.write(new_bytes)
        P = E.project_of(tmp, clock=clock)
        problems = refusals(copy, P)
        if problems:
            file, rule, line, msg = problems[0]
            raise Refused(f"the new history would not check: {file} {line}: {rule}: {msg}")
        versions = yaml.load(new_bytes.decode(), Loader=E.Core)
        if versions[:-1] != old_versions or len(versions) != len(old_versions) + 1:
            raise Refused("the new history would not keep the old versions")
        new = P.newest_version.get((kind, name))
        if new != versions[-1]:
            raise Refused("the new version is not the newest one")
        given = {kind: name, "number": number, "approved_at": at, "approved_by": by}
        if because is not None:
            given["because"] = because
        if {k: new.get(k) for k in given} != given or because is None and "because" in new:
            raise Refused("the new version would not read back as given")
        files = Files(tmp)
        if new.get("text") != files.current(kind, name, P):
            raise Refused(f"the new version's text is not the {kind}'s text")
        if kind == "story":
            blocks = story_blocks(name, P, files)
            if blocks_not_approved(blocks, P, files):
                raise Refused("approve its blocks first")
            if new.get("pins") != [{k: n, "number": version(P, k, n)} for k, n in blocks]:
                raise Refused("the new version's pins are not the story's blocks at their versions")
        if not E.approved(kind, files.current(kind, name, P), new) or kind == "story" and E.pins_stale(new, P):
            raise Refused(f"the {kind} would not be approved by the new version")


def write_atomic(folder, reading, vc, new_bytes, held, guard=None):
    """replace vc by new_bytes through a temporary file in the same folder,
    unless a file of the folder changed since the reading; held, the folder
    held open (the lock): the temporary file is created there, never
    through a symlink, and renamed there, a rename replacing a symlink
    named vc rather than writing where it points"""
    if read_folder(folder, guard) != reading:
        raise Refused("the folder changed while approving; nothing written")
    name, tmp = os.path.basename(vc), f".approve-{secrets.token_hex(6)}.tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=held)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(new_bytes)
            f.flush()
            os.fsync(f.fileno())
            try:
                mode = stat.S_IMODE(os.stat(name, dir_fd=held).st_mode)
            except FileNotFoundError:
                umask = os.umask(0)
                os.umask(umask)
                mode = 0o666 & ~umask
            os.fchmod(f.fileno(), mode)
        os.replace(tmp, name, src_dir_fd=held, dst_dir_fd=held)
    except BaseException:
        try:
            os.remove(tmp, dir_fd=held)
        except FileNotFoundError:
            pass
        raise


# EDDA-005@0
# EDDA-008@0
def approve(folder, name, at, by, because, dry_run, guard=None, clock=None):
    """the approval, under the folder's lock and on one reading; returns
    (the new version's text, kind, number, vc); guard, the root the folder
    and its files must resolve inside, or None (settings.Settings.guard);
    clock, the project's (clock_start, zone), else read from the edda.yaml
    of guard, or of the folder above folder: the copies checked here
    live elsewhere"""
    if not os.path.isdir(folder):
        raise Refused(f"not a folder: {folder}")
    if clock is None:
        import settings
        clock = settings.clock_at(guard if guard is not None else os.path.dirname(os.path.abspath(folder)))
    try:                                      # the folder itself is the lock: no file to leave behind
        lock = os.open(folder, os.O_RDONLY) if guard is None else E.open_inside(guard, folder, os.O_RDONLY | os.O_DIRECTORY)
    except E.Outside as o:
        raise outside(folder, o.args[0])
    try:
        fcntl.flock(lock, fcntl.LOCK_EX)
        reading = read_folder(folder, guard)
        with tempfile.TemporaryDirectory(prefix="edda-reading-") as tmp:
            materialise(reading, tmp)
            path, kind, number, pins, text = decide(tmp, name, clock)
        path = os.path.join(folder, os.path.basename(path))
        new = version_text(kind, name, number, at, by, because, pins, text)
        vc = path + ".vc"
        old_bytes = reading.get(os.path.basename(vc), b"")
        old_versions = (yaml.load(old_bytes.decode(), Loader=E.Core) or []) if old_bytes else []
        if not old_versions:
            new_bytes = new.encode()
        else:
            new_bytes = old_bytes + (b"" if old_bytes.endswith(b"\n") else b"\n") + new.encode()
        try_on_copy(reading, path, kind, name, number, at, by, because, new_bytes, old_versions, clock)
        if not dry_run:
            write_atomic(folder, reading, vc, new_bytes, lock, guard)
        return new, kind, number, vc
    finally:
        os.close(lock)


def main(argv=None, result=None):
    ap = argparse.ArgumentParser(description="Append the operator's approval of a story or block to its .edda.vc.")
    ap.add_argument("name", metavar="NAME", help="a story id (ABC-123) or a role or entity name")
    ap.add_argument("--by", required=True, metavar="OPERATOR", help="the operator's name; becomes approved_by")
    ap.add_argument("--because", help="one line of why; left out when not given")
    ap.add_argument("--at", help='"YYYY-MM-DD HH:MM"; default now, in the host\'s local time (the business zone)')
    ap.add_argument("--dry-run", action="store_true", help="print the new version; write nothing")
    ap.add_argument("--root", help="the project: the folder holding edda.yaml and the spec folder")
    ap.add_argument("--folder", help="the spec folder (default the one edda.yaml names, specs/); "
                                     "given with --root, the two name one root")
    a = ap.parse_args(argv)
    import settings     # edda.yaml: the spec folder and the pin (section 9)
    usage = settings.not_there([a.root, a.folder])
    if usage:
        print(usage, file=sys.stderr)
        if result is not None:
            result["refused"] = usage
        return 2
    project, code = settings.open_project(a.root, a.folder, sys.stderr)
    if project is None:
        return code
    at = a.at if a.at is not None else datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    try:
        ok = re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}", at) and datetime.datetime.strptime(at, "%Y-%m-%d %H:%M")
    except ValueError:
        ok = False
    usage = (f"not a name: {a.by}" if not re.fullmatch(E.NAME, a.by) or a.by in E.PY_KEYWORDS
             else "because is one line" if a.because is not None and not is_one_line(a.because)
             else None if ok else f'not a time "YYYY-MM-DD HH:MM": {at}')
    if usage is not None:       # the options, not the approval: a usage error
        print(usage, file=sys.stderr)
        if result is not None:
            result["refused"] = usage
        return 2
    try:
        new, kind, number, vc = approve(project.folder, a.name, at, a.by, a.because, a.dry_run, project.guard,
                                        project.clock)
        if result is not None:      # with --json, the fields say what is printed here
            result.update(name=a.name, kind=kind, number=number, history=os.path.relpath(vc),
                          version=new, written=not a.dry_run, refused=None)
            return 0
        sys.stdout.write(new)
        if not a.dry_run:
            print(f"appended {kind} {a.name} v{number} to {vc}")
        return 0
    except Refused as r:
        print(r, file=sys.stderr)
        if result is not None:
            result.update(name=a.name, refused=str(r))
        return 1


if __name__ == "__main__":
    import edda     # the one command: its exit codes and --json (section 13)
    sys.exit(edda.main(["approve", *sys.argv[1:]]))
