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

The runner applies the spec's rules before it calls the binding: values
hold every with: value, a time as a datetime, a given name as the thing
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

import check as checker

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


# --- spec_file ---------------------------------------------------------------

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
    return Thing("spec_file", name=os.path.basename(path)[:-len(".edda")], text=text, _path=path)


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


ENTITIES = {"spec_file": make_spec_file}
OPERATIONS = {"check": check}
