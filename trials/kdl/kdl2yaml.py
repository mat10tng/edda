#!/usr/bin/env python3
"""Translate one .kdl file, written by MAPPING.md, into the .edda YAML
text Edda's checker reads, with a line map: for each YAML line, the KDL
line it came from.

    python3 trials/kdl/kdl2yaml.py FILE.kdl          the YAML, on stdout
    python3 trials/kdl/kdl2yaml.py FILE.kdl --map    "yaml_line kdl_line" pairs

KDL is parsed by a small strict parser for the KDL v2 subset MAPPING.md
uses. A syntax error is `not_kdl`; valid KDL outside MAPPING.md is
`kdl_feature`. Either one stops the file: no YAML is made for it."""
import re, sys

NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*\Z")            # a key, a name, an id, an Edda word
PHRASE_WORD = re.compile(r"(?:[A-Za-z_][A-Za-z0-9_-]*,?|\|)\Z")   # a word of a type phrase
NUMBER = re.compile(r"[+-]?[0-9]+(?:\.[0-9]+)?\Z")
NOT_IDENT = set('\\/(){};[]"#=')
SPACES = set(" \t﻿         "
             "      　")
NEWLINES = set("\n\r\u0085\u000b\u000c  ")
ESCAPES = {'"': '"', "\\": "\\", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t", "s": " "}
KEYWORDS = {"#true": "True", "#false": "False", "#null": None, "#inf": None, "#-inf": None, "#nan": None}


class Problem(Exception):
    def __init__(self, rule, line, message):
        super().__init__(message)
        self.rule, self.line, self.message = rule, line, message


class Value:
    def __init__(self, kind, text, line):
        self.kind, self.text, self.line = kind, text, line     # kind: ident, string, number, keyword


class Node:
    def __init__(self, name, line):
        self.name, self.line = name, line      # name: a Value (ident or string)
        self.args, self.props, self.children = [], [], None


# --- the parser: KDL v2, the subset of MAPPING.md ---------------------------

class Parser:
    def __init__(self, text):
        self.s, self.i, self.line = text, 0, 1

    def fail(self, message, rule="not_kdl", line=None):
        raise Problem(rule, line or self.line, message)

    def peek(self, k=0):
        j = self.i + k
        return self.s[j] if j < len(self.s) else ""

    def advance(self, n=1):
        for _ in range(n):
            c = self.s[self.i]
            self.i += 1
            if c in NEWLINES and not (c == "\r" and self.peek() == "\n"):
                self.line += 1

    def block_comment(self):
        start, depth = self.line, 0
        while self.i < len(self.s):
            if self.s.startswith("/*", self.i):
                depth += 1
                self.advance(2)
            elif self.s.startswith("*/", self.i):
                depth -= 1
                self.advance(2)
                if depth == 0:
                    return
            else:
                self.advance()
        self.fail("a /* comment is never closed", line=start)

    def space(self):
        """skip spaces and /* */ comments on the line; true when any"""
        start = self.i
        while True:
            c = self.peek()
            if c in SPACES and c:
                self.advance()
            elif self.s.startswith("/*", self.i):
                self.block_comment()
            elif c == "\\":
                self.fail("a line continuation (\\) is outside MAPPING.md; write the node on one line",
                          rule="kdl_feature")
            else:
                return self.i > start

    def line_end(self):
        """skip a // comment and newlines, spaces and comments between nodes"""
        while True:
            self.space()
            if self.s.startswith("//", self.i):
                while self.peek() and self.peek() not in NEWLINES:
                    self.advance()
            elif self.peek() in NEWLINES and self.peek():
                self.advance()
            else:
                return

    def document(self):
        if self.peek() == "﻿":
            self.advance()
        nodes = self.nodes()
        if self.i < len(self.s):
            self.fail(f"unexpected {self.s[self.i]!r}")
        return nodes

    def nodes(self):
        out = []
        while True:
            self.line_end()
            if not self.peek() or self.peek() == "}":
                return out
            dashed = self.slashdash()
            node = self.node()
            if not dashed:
                out.append(node)

    def slashdash(self):
        if self.s.startswith("/-", self.i):
            self.advance(2)
            self.line_end()
            return True
        return False

    def node(self):
        if self.peek() == "(":
            self.fail("a type annotation is outside MAPPING.md", rule="kdl_feature")
        line = self.line
        name = self.value(as_name=True)
        node = Node(name, line)
        while True:
            spaced = self.space()
            c = self.peek()
            if not c or c in NEWLINES or c == ";" or c == "}" or self.s.startswith("//", self.i):
                if c == ";":
                    self.advance()
                return node
            if self.s.startswith("/-", self.i):
                self.advance(2)
                self.space()
                if self.peek() == "{":
                    self.children()
                else:
                    self.arg_or_prop()
                continue
            if c == "{":
                if node.children is not None:
                    self.fail("a node has one children block")
                node.children = self.children()
                continue
            if not spaced:
                self.fail(f"a space is needed before {c!r}")
            if node.children is not None:
                self.fail("arguments and properties come before the children block")
            item = self.arg_or_prop()
            if isinstance(item, tuple):
                node.props.append(item)
            else:
                node.args.append(item)

    def children(self):
        start = self.line
        self.advance()                          # {
        out = self.nodes()
        if self.peek() != "}":
            self.fail("a { block is never closed", line=start)
        self.advance()
        return out

    def arg_or_prop(self):
        if self.peek() == "(":
            self.fail("a type annotation is outside MAPPING.md", rule="kdl_feature")
        v = self.value()
        save = (self.i, self.line)
        self.space()
        if self.peek() == "=":
            if v.kind not in ("ident", "string"):
                self.fail("a property name is a word or a quoted string")
            self.advance()
            self.space()
            if self.peek() == "(":
                self.fail("a type annotation is outside MAPPING.md", rule="kdl_feature")
            return (v, self.value())
        self.i, self.line = save
        return v

    def value(self, as_name=False):
        c, line = self.peek(), self.line
        if c == '"':
            if self.s.startswith('"""', self.i):
                self.fail('a multi-line string (""") is outside MAPPING.md', rule="kdl_feature")
            return Value("string", self.quoted(), line)
        if c == "#":
            m = re.compile(r"#+").match(self.s, self.i)
            if self.s.startswith('"', m.end()):
                return Value("string", self.raw(len(m.group())), line)
            m = re.compile(r"#-?[A-Za-z]+").match(self.s, self.i)
            word = m.group() if m else "#"
            if word in KEYWORDS:
                if as_name:
                    self.fail(f"{word} cannot be a node name")
                self.advance(len(word))
                self.end_of_value()
                return Value("keyword", word, line)
            self.fail(f"unknown keyword {word}")
        if c.isdigit() or (c in "+-" and self.peek(1).isdigit()) or (c == "." and self.peek(1).isdigit()):
            m = re.compile(r"[+-]?0[xob][0-9A-Fa-f_]*|[+-]?[0-9][0-9_]*(\.[0-9_]*)?([eE][+-]?[0-9_]*)?").match(self.s, self.i)
            text = m.group() if m else c
            self.advance(len(text))
            self.end_of_value()
            if as_name:
                self.fail("a node name cannot be a number", line=line)
            if not NUMBER.match(text):
                if re.compile(r"[+-]?[0-9]+(\.[0-9]+)?([eE][+-]?[0-9]+)?\Z|[+-]?0[xob]").match(text) or "_" in text:
                    self.fail(f"the number {text} is outside MAPPING.md; write digits, with one . for a fraction",
                              rule="kdl_feature", line=line)
                self.fail(f"not a number: {text}", line=line)
            return Value("number", text, line)
        start = self.i
        while self.peek() and self.peek() not in NOT_IDENT and self.peek() not in SPACES \
                and self.peek() not in NEWLINES:
            self.advance()
        text = self.s[start:self.i]
        if not text:
            self.fail(f"unexpected {c!r}" if c else "unexpected end of file")
        if text in ("true", "false", "null", "inf", "-inf", "nan"):
            self.fail(f"{text} is not a bare word in KDL v2")
        if self.peek() in ('"', "#") and self.peek():
            self.fail(f"unexpected {self.peek()!r} after {text}")
        return Value("ident", text, line)

    def end_of_value(self):
        c = self.peek()
        if c and c not in SPACES and c not in NEWLINES and c not in ";}=" and not self.s.startswith("/", self.i):
            self.fail(f"unexpected {c!r}")

    def quoted(self):
        line = self.line
        self.advance()
        out = []
        while True:
            c = self.peek()
            if not c or c in NEWLINES:
                self.fail("a string is not closed on its line", line=line)
            self.advance()
            if c == '"':
                self.end_of_value()
                return "".join(out)
            if c != "\\":
                out.append(c)
                continue
            e = self.peek()
            if e in ESCAPES:
                out.append(ESCAPES[e])
                self.advance()
            elif e == "u":
                m = re.compile(r"u\{([0-9A-Fa-f]{1,6})\}").match(self.s, self.i)
                if not m:
                    self.fail("a \\u escape is \\u{hex}")
                out.append(chr(int(m.group(1), 16)))
                self.advance(len(m.group()))
            elif e in SPACES or e in NEWLINES:
                self.fail("a whitespace escape is outside MAPPING.md", rule="kdl_feature")
            else:
                self.fail(f"unknown escape \\{e}")

    def raw(self, hashes):
        line = self.line
        if self.s.startswith('"""', self.i + hashes):
            self.fail('a multi-line raw string is outside MAPPING.md', rule="kdl_feature")
        self.advance(hashes + 1)
        close = '"' + "#" * hashes
        start = self.i
        while not self.s.startswith(close, self.i):
            if not self.peek() or self.peek() in NEWLINES:
                self.fail("a raw string is not closed on its line", line=line)
            self.advance()
        text = self.s[start:self.i]
        self.advance(len(close))
        self.end_of_value()
        return text


# --- the translation: KDL nodes to Edda's YAML ------------------------------

def feature(line, message):
    raise Problem("kdl_feature", line, message)


def yaml_string(text):
    out = []
    for c in text:
        if c == "\\":
            out.append("\\\\")
        elif c == '"':
            out.append('\\"')
        elif c == "\n":
            out.append("\\n")
        elif c == "\t":
            out.append("\\t")
        elif ord(c) < 0x20 or ord(c) == 0x7f:
            out.append(f"\\x{ord(c):02x}")
        else:
            out.append(c)
    return '"' + "".join(out) + '"'


def scalar(v, phrase=False):
    """one KDL value as a YAML scalar: a word plain, a string double-quoted"""
    if v.kind == "string":
        return yaml_string(v.text)
    if v.kind == "number":
        return v.text
    if v.kind == "keyword":
        word = KEYWORDS[v.text]
        feature(v.line, f"{v.text} is outside MAPPING.md" + (f"; write {word}" if word else "; Edda has no such value"))
    if not (PHRASE_WORD if phrase else NAME).match(v.text):
        feature(v.line, f"the bare word {v.text} is outside MAPPING.md; quote it")
    return v.text


def key(v):
    if v.kind == "string":
        return yaml_string(v.text)
    if not NAME.match(v.text):
        feature(v.line, f"the key {v.text} is outside MAPPING.md; a key is a name, an id or a quoted title")
    return v.text


def node_value(node):
    """a node's value with no children: (scalar text) or None for a bare key"""
    if not node.args:
        return None
    if len(node.args) == 1:
        return scalar(node.args[0])
    return " ".join(scalar(a, phrase=True) for a in node.args)   # a type phrase, one plain line


def kind_of(node):
    if node.args and (node.props or node.children is not None):
        feature(node.line, "a node has either a value or properties and children, not both")
    if node.children is not None and not node.children:
        feature(node.line, "an empty { } block is outside MAPPING.md")
    if node.children:
        dashes = [c.name.kind == "ident" and c.name.text == "-" for c in node.children]
        if all(dashes):
            if node.props:
                feature(node.line, "a list (- children) cannot have properties")
            return "list"
        if any(dashes):
            feature(node.children[dashes.index(True)].line, "- items and keys cannot be mixed in one block")
        return "map"
    if node.props:
        return "flow"
    return "scalar"


class Emitter:
    def __init__(self):
        self.lines, self.map = [], []

    def put(self, indent, text, line):
        self.lines.append("  " * indent + text)
        self.map.append(line)

    def flow(self, node):
        return "{" + ", ".join(f"{key(k)}: {scalar(v)}" for k, v in node.props) + "}"

    def entry(self, node, indent):
        """a keyed node: key: value, or key: and its block"""
        k = key(node.name)
        kind = kind_of(node)
        if kind == "scalar":
            v = node_value(node)
            self.put(indent, f"{k}:" if v is None else f"{k}: {v}", node.line)
        elif kind == "flow":
            self.put(indent, f"{k}: {self.flow(node)}", node.line)
        else:
            self.put(indent, f"{k}:", node.line)
            self.body(node, kind, indent + 1)

    def body(self, node, kind, indent):
        if kind == "list":
            for item in node.children:
                self.item(item, indent)
        else:
            for pk, pv in node.props:
                self.put(indent, f"{key(pk)}: {scalar(pv)}", node.line)
            for child in node.children or []:
                self.entry(child, indent)

    def item(self, node, indent):
        """a - node: - value, - {flow}, or - first key and the rest under it"""
        kind = kind_of(node)
        if kind == "scalar":
            v = node_value(node)
            if v is None:
                feature(node.line, "an empty - item is outside MAPPING.md")
            self.put(indent, f"- {v}", node.line)
        elif kind == "flow":
            self.put(indent, f"- {self.flow(node)}", node.line)
        elif kind == "list":
            feature(node.line, "a list inside a list is outside MAPPING.md")
        else:
            start = len(self.lines)
            self.body(node, kind, indent + 1)
            first = self.lines[start]
            self.lines[start] = "  " * indent + "- " + first.lstrip(" ")


def translate(text):
    """(yaml text, line map, problems): the map's n-th entry is the KDL
    line of YAML line n + 1; on a problem the text is None"""
    try:
        nodes = Parser(text).document()
        e = Emitter()
        dashes = [n.name.kind == "ident" and n.name.text == "-" for n in nodes]
        if any(dashes) and not all(dashes):
            feature(nodes[dashes.index(True)].line, "- items and keys cannot be mixed at the top")
        for n in nodes:
            e.item(n, 0) if all(dashes) else e.entry(n, 0)
    except Problem as p:
        return None, [], [(p.rule, p.line, p.message)]
    return "\n".join(e.lines) + "\n", e.map, []


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or len(args) > 2 or (len(args) == 2 and args[1] != "--map"):
        sys.exit("usage: kdl2yaml.py FILE.kdl [--map]")
    out, line_map, problems = translate(open(args[0], encoding="utf-8").read())
    for rule, line, message in problems:
        print(f"{args[0]}: {line}: {rule}: {message}", file=sys.stderr)
    if problems:
        sys.exit(1)
    if len(args) == 2:
        for n, k in enumerate(line_map, 1):
            print(n, k)
    else:
        sys.stdout.write(out)
