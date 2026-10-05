"""The binding for Edda's own entities and operations (reference section 9).

A binding is the glue between a spec and the code it holds to: it makes
the things an example's given names, and it calls the code for an
operation. It holds no rule: permission, refusals and the facts after
are the spec's, and the runner (tools/run.py) checks them.

What a binding provides, the interface a binding in another stack
follows too:

  ENTITIES    entity name -> make(name, values, workdir): the given thing,
              an object whose attributes are the entity's properties
  make_actor  (name, roles, values) -> the given actor: name, roles and
              the properties of its roles
  OPERATIONS  operation name -> run(actor, *inputs, **optional_inputs):
              the operation's return, or raise Refused(reason)
  FUNCTIONS   optional: client function name -> f(*inputs): the client's
              real function, its inputs by position; edda run runs each
              function's example rows through it, never an example
              (reference section 4). Edda's own binding has none
  clock       optional: clock(now), called whenever the clock is set
              or moves, before anything is read at it (section 8), or
              None in an example that uses no time. Edda's own binding
              keeps it: approve and approve_block record it as approved_at

The runner applies the spec's rules before it calls the binding: values
hold every with: value, a time as a datetime with no zone (the business
zone's wall clock, as the clock's time is), a given name as the thing
made, and every stored property left out at its DEFAULT, [] for MANY,
None for OPTIONAL, or else an Unset (reference section 8); optional_inputs
holds every optional input, None when the call leaves it out (section 6).
A maker keeps the Unset on the thing, carrying it with
Thing(entity, values), or puts a value of its own there.

Unset is not unbound: reading an Unset raises UnsetRead at the read and
fails the example, so not even an identity test on it passes. That holds
for every ordinary way to a value: from a Thing by attribute or getattr,
and from its dict or the maker's values by key, get, pop, setdefault,
values(), items(), copy(), dict(x), {**x}, f(**x), x | y, update,
json.dumps, copy.copy or deepcopy (see Values). Any other use of an Unset
reached some other way raises too. An entity, operation or
property left out has no binding yet, and a story that needs it is not
run.
"""
import glob
import os
import shutil

import approve as approver
import check as checker
import view as viewer

FIXTURES = os.path.join(checker.ROOT, "fixtures")


class Refused(Exception):
    """the operation refused, with the reason it gave"""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


class NotBound(Exception):
    """a property or operation the binding does not provide yet"""


class UnsetRead(BaseException):
    """an Unset was used; what is "<x>.<property>". A BaseException, so
    bound code that catches Exception cannot swallow it; the runner's
    guards turn it into a failure of the example"""

    def __init__(self, what):
        super().__init__(f"{what} is unset")
        self.what = what


class Unset:
    """the value of a required stored property the given leaves out
    (reference section 8), "<x>.<property>": there, but any use of it
    (comparison, ordering, truth test, arithmetic, hashing, string
    conversion, iteration, attribute access) raises UnsetRead"""

    __slots__ = ("_what",)

    def __init__(self, what):
        object.__setattr__(self, "_what", what)

    def _poison(self, *args, **kwargs):
        raise UnsetRead(object.__getattribute__(self, "_what"))

    __getattr__ = __setattr__ = __delattr__ = _poison
    __eq__ = __ne__ = __lt__ = __le__ = __gt__ = __ge__ = _poison
    __bool__ = __len__ = __hash__ = __iter__ = __contains__ = _poison
    __getitem__ = __setitem__ = __call__ = _poison
    __str__ = __repr__ = __format__ = __bytes__ = __fspath__ = _poison
    __int__ = __float__ = __index__ = __complex__ = __round__ = _poison
    __neg__ = __pos__ = __abs__ = __invert__ = _poison


for _op in ("add", "sub", "mul", "truediv", "floordiv", "mod", "pow", "matmul",
            "and", "or", "xor", "lshift", "rshift", "divmod"):
    for _f in (f"__{_op}__", f"__r{_op}__", f"__i{_op}__"):
        setattr(Unset, _f, Unset._poison)     # arithmetic, each side and in place
del _op, _f


def unset_read(v):
    """v, or UnsetRead when v is an Unset: a read of an unset value fails
    at the read, so even an identity test (is None) on it cannot pass"""
    if type(v) is Unset:
        raise UnsetRead(object.__getattribute__(v, "_what"))
    return v


class Values(dict):
    """the values a maker gets and a thing's own dict. Every ordinary way
    to a value in it reads through [key], which raises UnsetRead for an
    Unset: get, pop, popitem, setdefault, values(), items(), copy(),
    dict(x), {**x}, f(**x), x | y, update, json.dumps, copy.copy and
    deepcopy. A copy or listing reads every value, so it raises if any is
    unset. Names alone (iteration, keys(), in, len) hand out no value.
    The Unset stays in it, so a maker can carry it onto the thing with
    Thing(entity, values)"""

    def __getitem__(self, key):
        return unset_read(dict.__getitem__(self, key))

    def __iter__(self):     # a dict subclass with its own __iter__ is copied
        return dict.__iter__(self)   # by keys and [key], never raw (CPython)

    def get(self, key, default=None):
        return self[key] if key in self else default

    def pop(self, key, *default):
        return unset_read(dict.pop(self, key, *default))

    def popitem(self):
        key, v = dict.popitem(self)
        return key, unset_read(v)

    def setdefault(self, key, default=None):
        if key not in self:
            self[key] = default
        return self[key]

    def values(self):
        return [self[k] for k in self]

    def items(self):
        return [(k, self[k]) for k in self]

    def copy(self):
        return Values(self)


class Thing:
    """a given or a returned entity, or an actor; equal only to itself
    (reference section 6, equality of entities). Reading an unset property
    raises UnsetRead, by attribute or through its dict.

    Thing(entity, values, **more): values, the Values a maker gets, are
    carried onto the thing as they are, an Unset staying unset and
    unread; this is the one way to carry an Unset, since passing values
    as **values reads them all"""

    def __init__(self, entity, carried=None, /, **values):
        d = Values(_entity=entity)
        if carried is not None:
            dict.update(d, dict.items(carried))     # raw: an Unset is carried, not read
        dict.update(d, values)
        object.__setattr__(self, "__dict__", d)

    def __getattribute__(self, name):
        return unset_read(object.__getattribute__(self, name))

    def __getattr__(self, name):
        if name.startswith("__"):   # a Python protocol (copy's __deepcopy__), not a property
            raise AttributeError(name)
        raise NotBound(f"{self._entity}.{name}")

    def __repr__(self):
        shown = ", ".join(f"{k}={v!r}" for k, v in self.__dict__.items() if not k.startswith("_"))
        return f"{self._entity}({shown})"


def make_actor(name, roles, values):
    return Thing("actor", values, name=name, roles=list(roles))


# --- the clock -----------------------------------------------------------------

NOW = [None]    # the clock's time in the example being run, as the runner tells it


def clock(now):
    """the runner tells the binding the time (reference section 9):
    approve and approve_block record it as approved_at"""
    NOW[0] = now


# --- spec_file ---------------------------------------------------------------

def own(thing):
    """a thing's own dict, raw"""
    return object.__getattribute__(thing, "__dict__")


class Files:
    """a spec_file's .edda and .edda.vc as they are on disk now: the
    checker's reading of each and its project, read again whenever either
    file changed (an approval appends to the history), the model made at
    the first read of it"""

    def __init__(self, path):
        self.path, self.folder = path, os.path.dirname(path)
        self.source, self.data = checker.load(path)
        _, entries = checker.load(path + ".vc") if os.path.exists(path + ".vc") else (None, [])
        self.entries = [e for e in entries if isinstance(e, dict)] if isinstance(entries, list) else []
        self.P = checker.project_of(self.folder)
        self._model = None

    @staticmethod
    def key(path):
        """the bytes of the .edda and the .edda.vc, None for one not there"""
        out = []
        for p in (path, path + ".vc"):
            if os.path.exists(p):
                with open(p, "rb") as f:
                    out.append(f.read())
            else:
                out.append(None)
        return tuple(out)

    def model(self):
        """the checker's model of the folder; a folder that does not check has none"""
        if self._model is None:
            if checker.refused(self.folder):
                raise ValueError(f"{os.path.basename(self.path)} does not check, so it has no model")
            self._model = checker.model_of(self.folder)
        return self._model

    def block_text(self, section, name):
        """block.text, story.text: the normalised text of the block now"""
        return checker.block_text(self.source.text, self.source.line((section, name)))


class SpecFile(Thing):
    """a spec_file: a fixture folder copied to the work folder. Its blocks,
    stories and versions are read from the files on disk at each read,
    each one thing for as long as the example runs, so a story or a
    version read again is the same thing (entities are equal only to
    themselves)"""

    def files(self):
        """the files as they are now (Files)"""
        d = own(self)
        key = Files.key(self._path)
        if dict.get(d, "_files_key") != key:
            dict.__setitem__(d, "_files", Files(self._path))
            dict.__setitem__(d, "_files_key", key)
        return dict.__getitem__(d, "_files")

    def made(self, key, make):
        """the one thing for key, made at the first read"""
        things = dict.setdefault(own(self), "_made", {})
        if key not in things:
            things[key] = make()
        return things[key]

    def block(self, kind, name):
        """the block of this file of that kind and name"""
        return self.made(("block", kind, name), lambda: Block("block", file=self, kind=kind, name=name))

    @property
    def blocks(self):
        """spec_file.blocks: the role and entity blocks, in file order"""
        data = checker.mapping(self.files().data)
        return [self.block(kind, name) for section, kind in (("roles", "role"), ("entities", "entity"))
                for name in checker.mapping(data.get(section))]

    @property
    def stories(self):
        """spec_file.stories, in file order, read from the file as YAML,
        whether or not it checks"""
        data = checker.mapping(self.files().data)
        return [self.made(("story", sid), lambda sid=sid: Story("story", file=self, id=sid))
                for sid in checker.mapping(data.get("stories"))]

    @property
    def notes(self):
        """spec_file.notes: the checker's notes of this one file, in file order"""
        return sorted(notes_of([self]), key=lambda n: n.line)

    def versions(self):
        """history.versions: every version in the .edda.vc, oldest first;
        a version, never changed once approved, is one thing by its place
        in the history"""
        out = []
        for i, e in enumerate(self.files().entries):
            kind = checker.vc_kind(e)
            out.append(self.made(("version", i, kind, e.get(kind), e.get("number")),
                                 lambda e=e, kind=kind: make_version(self, kind, e)))
        return out


def make_version(file, kind, e):
    """a version of the history from its entry e: its stored properties as
    written, approved_at as a time"""
    at = e.get("approved_at")
    pins = [Pin("pin", _file=file, kind=checker.vc_kind(p), name=p.get(checker.vc_kind(p)), number=p.get("number"))
            for p in checker.listing(e.get("pins")) if isinstance(p, dict)]
    return Version("version", number=e.get("number"), approved_at=checker.parse_time(at) or at,
                   approved_by=e.get("approved_by"), because=e.get("because"), text=e.get("text"), pins=pins,
                   _file=file, _kind=kind, _name=e.get(kind), _entry=e)


class History(Thing):
    """the .edda.vc beside a spec_file; text, the file as it is"""

    @property
    def versions(self):
        return self._file.versions()


def vc_text(path):
    """history.text: the .edda.vc beside path as it is, "" when there is none"""
    if not os.path.exists(path + ".vc"):
        return ""
    with open(path + ".vc") as f:
        return f.read()


def make_spec_file(name, values, workdir):
    """a fixture folder copied to workdir; its one .edda is the spec file"""
    folder = os.path.join(workdir, name)
    shutil.copytree(os.path.join(FIXTURES, values["fixture"]), folder)
    files = glob.glob(f"{folder}/*.edda")
    if len(files) != 1:
        raise ValueError(f"fixture {values['fixture']} holds {len(files)} .edda files, not one")
    path = files[0]
    with open(path) as f:
        text = f.read()
    file = SpecFile("spec_file", name=os.path.basename(path)[:-len(".edda")], text=text, _path=path)
    dict.__setitem__(own(file), "history", History("history", text=vc_text(path), _file=file))
    return file


def sentences(found):
    """the renderer's sentences as sentence things"""
    return [Thing("sentence", **s) for s in found]


class Versioned(Thing):
    """what a block and a story share: their versions in the history, and
    the newest one"""

    def entry(self):
        """the newest version as the history holds it, or None"""
        return dict.__getitem__(own(self.versions[-1]), "_entry") if self.versions else None

    @property
    def version(self):
        """len(versions), as the spec computes it"""
        return len(self.versions)


class Block(Versioned):
    """a role or entity block of a spec_file"""

    @property
    def text(self):
        return self.file.files().block_text(checker.SECTION[self.kind], self.name)

    @property
    def versions(self):
        return [v for v in self.file.versions() if (v._kind, v._name) == (self.kind, self.name)]

    @property
    def approved(self):
        return checker.approved(self.kind, self.text, self.entry())


class Story(Versioned):
    """a story of a spec_file"""

    @property
    def text(self):
        return self.file.files().block_text("stories", self.id)

    @property
    def body_text(self):
        return checker.body_text(self.text)

    @property
    def versions(self):
        return [v for v in self.file.versions() if (v._kind, v._name) == ("story", self.id)]

    @property
    def approved(self):
        return checker.approved("story", self.text, self.entry())

    @property
    def pins_stale(self):
        """check.py's reading: a pin of the newest version older than its block's newest version"""
        newest = self.entry()
        return newest is not None and checker.pins_stale(newest, self.file.files().P)

    @property
    def blocks(self):
        """story.blocks, as approve.py works them out"""
        files = self.file.files()
        return [self.file.block(k, n) for k, n in approver.story_blocks(self.id, files.P, approver.Files(files.folder))]

    @property
    def changes(self):
        """story.changes: the checker's walk from the newest version's text,
        none when there is no version, to the text now"""
        newest = self.entry()
        return [Thing("change", kind=k, line=line, sentence=s)
                for k, line, s in checker.changes(newest["text"] if newest else "", self.text)]

    @property
    def sentences(self):
        """the read view of the story in the model of the file now"""
        model = self.file.files().model()
        st = next(s for s in model["stories"] if s["id"] == self.id)
        return sentences(viewer.story_sentences(st, model["operations"], model["entities"], model["roles"],
                                                model["functions"]))


class Version(Thing):
    """one version in a history"""

    @property
    def body_text(self):
        return checker.body_text(self.text)

    @property
    def sentences(self):
        """the read view of a story's version, from the model of the file now"""
        model = self._file.files().model()
        st = next(s for s in model["stories"] if s["id"] == self._name)
        return sentences(viewer.version_sentences(next(v for v in st["versions"] if v["number"] == self.number)))


class Pin(Thing):
    """one block version a story version was approved against"""

    @property
    def block(self):
        return self._file.block(self.kind, self.name)


def notes_of(files):
    """the checker's notes of several spec files as note things, each with
    its spec_file"""
    by_path = {f._path: f for f in files}
    return [Thing("note", file=by_path[n["path"]], story_id=n["story_id"], line=n["line"], text=n["text"])
            for n in checker.notes([f._path for f in files])]


def problems_of(path):
    """the real checker over one .edda and the .edda.vc beside it"""
    P = checker.project_of(os.path.dirname(path))
    out = []
    for p in (path, path + ".vc"):
        if not os.path.exists(p):
            continue
        src, shape, meaning, history, flags = checker.check(p, P)
        for kind, found in (("refused", src + shape + meaning + history), ("flagged", flags)):
            out += [Thing("problem", kind=kind, rule=rule, file_name=os.path.basename(p), line=line, message=msg)
                    for rule, line, msg in found]
    return out


# --- operations --------------------------------------------------------------

def check(actor, file):
    return problems_of(file._path)


def view(actor, story):
    return story.sentences


def notes(actor, files):
    """check.py's notes; a file that does not check has none, which the
    spec gives as its refusal"""
    try:
        return notes_of(files)
    except ValueError:
        raise Refused("a file does not check")


# EDDA-007@0
def view_at(actor, story, number):
    if number < 1 or number > len(story.versions):
        raise Refused("no such version")
    return story.versions[number - 1].sentences


def diff(actor, story):
    return story.changes


def approve_story(actor, story, because=None):
    record(actor, story.file, story.id, because)


def approve_block(actor, block, because=None):
    record(actor, block.file, block.name, because)


def record(actor, file, name, because):
    """approve.py's approve of the story or block called name, in the
    copied folder, by the actor, at the clock's time; its refusal as the
    reason it gives. The history then holds the file as written"""
    if NOW[0] is None:
        raise ValueError("an approval needs the clock, and the example has none")
    try:
        approver.approve(os.path.dirname(file._path), name, NOW[0].strftime("%Y-%m-%d %H:%M"), actor.name,
                         because, dry_run=False)
    except approver.Refused as r:
        raise Refused(str(r))
    dict.__setitem__(own(file.history), "text", vc_text(file._path))


ENTITIES = {"spec_file": make_spec_file}
# VALUES, optional, for generated cases (tools/generate.py): entity name ->
# {key: [values]}, the values a maker takes where the types cannot say. An
# entity named here is generated from these keys alone, as an example gives
# it, and its maker fills in the rest: a spec_file from a fixture folder
# holding one .edda, as make_spec_file needs.
VALUES = {"spec_file": {"fixture": sorted(f for f in os.listdir(FIXTURES)
                                          if len(glob.glob(os.path.join(FIXTURES, f, "*.edda"))) == 1)}}
OPERATIONS = {"check": check, "view": view, "view_at": view_at, "notes": notes,
              "approve": approve_story, "diff": diff, "approve_block": approve_block}
FUNCTIONS = {}      # Edda's own spec declares no client function
