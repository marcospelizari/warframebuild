"""Strict reader for the Lua table literals in saved wiki data modules (`return { ... }`).

Covers only the subset those pages use: tables with `name =`, `["name"] =` and positional
entries, single- or double-quoted strings (escapes \\n \\" \\' \\\\ only), numbers,
true/false/nil, `math.huge` and `--` line comments; block comments (`--[[ ]]`) and anything
else fail. The text is untrusted (S5): no code is evaluated, input size and nesting depth
are capped and the token pattern is linear.
"""

import math
import re
from typing import Any

MAX_BYTES = 8 * 1024 * 1024
MAX_DEPTH = 32

_TOKEN = re.compile(
    r"""
    (?P<space>\s+|--(?!\[=*\[)[^\n]*)
  | (?P<string>"(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*')
  | (?P<number>-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)
  | (?P<huge>math\.huge)
  | (?P<name>[A-Za-z_]\w*)
  | (?P<punct>[{}\[\]=,;])
    """,
    re.VERBOSE,
)
_KEYWORDS = {"true": True, "false": False, "nil": None}
_ESCAPES = {"n": "\n", '"': '"', "'": "'", "\\": "\\"}
_ESCAPE = re.compile(r"\\(.)")


class LuaError(ValueError):
    pass


def parse_module(text: str, *, lua_rules: bool = False) -> Any:
    """Value of a module that is `return <table>`. A repeated key or a table mixing named and
    positional entries fails, unless `lua_rules`: then Lua's own rules apply (last duplicate
    wins, positional entries keyed 1, 2, ...); the enemy modules carry a few such slips."""
    if len(text.encode()) > MAX_BYTES:
        raise LuaError(f"module larger than {MAX_BYTES} bytes")
    tokens = _tokens(text)
    if not tokens or tokens[0] != ("name", "return"):
        raise LuaError("module does not start with `return`")
    parser = _Parser(tokens, 1, lua_rules)
    value = parser.value(0)
    if parser.pos != len(tokens):
        raise LuaError(f"unexpected {tokens[parser.pos][1]!r} after the returned table")
    return value


def _tokens(text: str) -> list[tuple[str, str]]:
    out = []
    pos = 0
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if m is None:
            line = text.count("\n", 0, pos) + 1
            raise LuaError(f"line {line}: unsupported syntax {text[pos : pos + 20]!r}")
        kind = m.lastgroup
        assert kind is not None
        if kind != "space":
            out.append((kind, m.group()))
        pos = m.end()
    return out


class _Parser:
    def __init__(self, tokens: list[tuple[str, str]], pos: int, lua_rules: bool = False) -> None:
        self.tokens = tokens
        self.pos = pos
        self.lua_rules = lua_rules

    def peek(self, offset: int = 0) -> tuple[str, str]:
        i = self.pos + offset
        return self.tokens[i] if i < len(self.tokens) else ("end", "")

    def take(self, text: str) -> None:
        if self.peek()[1] != text:
            raise LuaError(f"expected {text!r}, got {self.peek()[1]!r}")
        self.pos += 1

    def value(self, depth: int) -> Any:
        kind, text = self.peek()
        self.pos += 1
        if kind == "string":
            return _unquote(text)
        if kind == "number":
            return float(text) if any(c in text for c in ".eE") else int(text)
        if kind == "huge":
            return math.inf
        if kind == "name" and text in _KEYWORDS:
            return _KEYWORDS[text]
        if text == "{":
            return self.table(depth + 1)
        raise LuaError(f"unexpected {text!r}")

    def table(self, depth: int) -> dict[Any, Any] | list[Any]:
        if depth > MAX_DEPTH:
            raise LuaError(f"tables nested deeper than {MAX_DEPTH}")
        named: dict[str, Any] = {}
        items: list[Any] = []
        while self.peek()[1] != "}":
            kind, text = self.peek()
            if kind == "name" and self.peek(1)[1] == "=":
                key = text
                self.pos += 2
            elif text == "[":
                self.pos += 1
                k_kind, k_text = self.peek()
                if k_kind != "string":
                    raise LuaError(f"unsupported table key {k_text!r}")
                key = _unquote(k_text)
                self.pos += 1
                self.take("]")
                self.take("=")
            else:
                items.append(self.value(depth))
                self._separator()
                continue
            if key in named and not self.lua_rules:
                raise LuaError(f"duplicate key {key!r}")
            named[key] = self.value(depth)
            self._separator()
        self.take("}")
        if named and items:
            if not self.lua_rules:
                raise LuaError("table mixes named and positional entries")
            return {**dict(enumerate(items, 1)), **named}
        return items if items or not named else named

    def _separator(self) -> None:
        if self.peek()[1] in (",", ";"):
            self.pos += 1
        elif self.peek()[1] != "}":
            raise LuaError(f"expected ',' or '}}', got {self.peek()[1]!r}")


def _unquote(token: str) -> str:
    def escape(m: re.Match[str]) -> str:
        if m.group(1) not in _ESCAPES:
            raise LuaError(f"unsupported escape {m.group()!r}")
        return _ESCAPES[m.group(1)]

    return _ESCAPE.sub(escape, token[1:-1])
