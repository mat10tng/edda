#!/usr/bin/env python3
"""Validate every .edda and .edda.vc file against the revision 26 schemas
and the YAML subset; report which fixtures the schema catches."""
import glob, json, os, re, sys
import yaml
from jsonschema import Draft202012Validator

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
schema = json.load(open(f"{ROOT}/language/schema.json"))
vc_schema = json.load(open(f"{ROOT}/language/vc-schema.json"))
Draft202012Validator.check_schema(schema)
Draft202012Validator.check_schema(vc_schema)
V = Draft202012Validator(schema)
VC = Draft202012Validator(vc_schema)


class Strict(yaml.SafeLoader):
    pass


def no_dup(loader, node, deep=False):
    seen = set()
    for k, _ in node.value:
        key = loader.construct_object(k, deep=deep)
        if key in seen:
            raise yaml.constructor.ConstructorError(None, None, f"duplicate key {key!r}", k.start_mark)
        seen.add(key)
    return yaml.SafeLoader.construct_mapping(loader, node, deep)


Strict.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, no_dup)


def source_problems(text):
    out = []
    if "\t" in text:
        out.append("tab")
    if re.search(r"(^|\s)[&*][A-Za-z]", text, re.M):
        out.append("anchor/alias")
    if re.search(r"^\s*<<:", text, re.M):
        out.append("merge key")
    if re.search(r"^%|(^|\s)!", text, re.M):
        out.append("tag/directive")
    if text.count("\n---") or text.startswith("---"):
        out.append("second document")
    return out


def check(path):
    text = open(path).read()
    src = source_problems(text)
    try:
        data = yaml.load(text, Loader=Strict)
    except Exception as e:
        return src, [f"yaml: {str(e).splitlines()[0]}"]
    v = VC if path.endswith(".vc") else V
    errs = sorted(v.iter_errors(data), key=lambda e: list(e.absolute_path))
    return src, [f"{'/'.join(map(str, e.absolute_path))}: {e.message[:90]}" for e in errs]


ok = True
for path in sorted(glob.glob(f"{ROOT}/specs/*.edda") + glob.glob(f"{ROOT}/specs/*.edda.vc")):
    src, errs = check(path)
    print(os.path.relpath(path, ROOT), "OK" if not (src or errs) else "")
    for e in src + errs:
        ok = False
        print("   ", e)

print()
print("fixtures: which the source/schema layer catches")
for folder in sorted(os.listdir(f"{ROOT}/fixtures")):
    for path in sorted(glob.glob(f"{ROOT}/fixtures/{folder}/*")):
        src, errs = check(path)
        tag = "caught" if (src or errs) else "passes"
        print(f"  {folder}/{os.path.basename(path)}: {tag}")
        for e in src + errs:
            print("     ", e)
sys.exit(0 if ok else 1)
