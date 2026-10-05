#!/usr/bin/env python3
"""Write one .edda file as KDL by MAPPING.md, to make test inputs for the
trial. Not part of the trial itself.

    python3 trials/kdl/yaml2kdl.py FILE.edda > FILE.kdl"""
import os, re, sys
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tools"))
import validate  # noqa: E402  (its YAML 1.2 core loader)

TOKEN = re.compile(r'"(?:[^"\\]|\\.)*"|\S+')
NUMBER = re.compile(r"[+-]?[0-9]+(?:\.[0-9]+)?\Z")
NOT_IDENT = set('\\/(){};[]"#=')


def kdl_string(text):
    if "\n" not in text and ('"' in text or "\\" in text):
        hashes = "#"
        while '"' + hashes in text:
            hashes += "#"
        return f'{hashes}"{text}"{hashes}'
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t") + '"'


def word(token):
    """one plain YAML word as a KDL value"""
    if token.startswith('"'):
        return token
    if NUMBER.match(token):
        return token
    if (any(c in NOT_IDENT or c.isspace() for c in token) or token[0].isdigit()
            or token in ("true", "false", "null", "inf", "-inf", "nan")):
        return kdl_string(token)
    return token


def values(node):
    """a scalar node as KDL values: a quoted scalar one string, a plain one word by word"""
    if node.style == '"':
        return [kdl_string(node.value)]
    if node.style is not None:
        sys.exit(f"line {node.start_mark.line + 1}: only plain and double-quoted scalars are written")
    return [word(t) for t in TOKEN.findall(node.value)]


def name(k):
    return kdl_string(k.value) if k.style == '"' else k.value


def as_prop(v):
    return isinstance(v, yaml.ScalarNode) and len(values(v)) == 1


def emit(out, head, v, indent, props_ok):
    """one node: head (a key or -), then its value"""
    pad = "  " * indent
    if isinstance(v, yaml.ScalarNode):
        vals = values(v)
        out.append(pad + " ".join([head] + vals))
        return
    if isinstance(v, yaml.SequenceNode):
        out.append(pad + head + " {")
        for item in v.value:
            emit(out, "-", item, indent + 1, True)
        out.append(pad + "}")
        return
    pairs = v.value
    props = [(k, x) for k, x in pairs if props_ok and as_prop(x)]
    kids = [(k, x) for k, x in pairs if not (props_ok and as_prop(x))]
    line = " ".join([head] + [f"{name(k)}={values(x)[0]}" for k, x in props])
    if not kids:
        out.append(pad + line)
        return
    out.append(pad + line + " {")
    for k, x in kids:
        emit(out, name(k), x, indent + 1, x.flow_style if isinstance(x, yaml.MappingNode) else False)
    out.append(pad + "}")


def convert(text):
    root = yaml.compose(text, Loader=validate.Core)
    out = []
    for k, v in root.value:
        emit(out, name(k), v, 0, False)
        out.append("")
    return "\n".join(out).rstrip("\n") + "\n"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: yaml2kdl.py FILE.edda")
    sys.stdout.write(convert(open(sys.argv[1], encoding="utf-8").read()))
