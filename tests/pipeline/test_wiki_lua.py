import math

import pytest

from app.pipeline.sources import wiki_lua
from app.pipeline.sources.wiki_lua import LuaError, parse_module


def test_reads_the_module_subset() -> None:
    text = """return {
    \t["AX-52"] = {
    \t\tAttacks = { { AttackName = "Normal", FireRate = 10, Damage = { Puncture = 40 } } },
    \t\tFireRate = math.huge, -- comment
    \t\tIsSilent = false,
    \t\tUsers = { },
    \t\tRatio = -0.5e1;
    \t},
    }"""
    data = parse_module(text)
    weapon = data["AX-52"]
    assert weapon["Attacks"] == [
        {"AttackName": "Normal", "FireRate": 10, "Damage": {"Puncture": 40}}
    ]
    assert weapon["FireRate"] == math.inf
    assert weapon["IsSilent"] is False
    assert weapon["Users"] == []
    assert weapon["Ratio"] == -5.0


@pytest.mark.parametrize(
    "text,message",
    [
        ("{ a = 1 }", "return"),
        ("return { a = f(1) }", "unsupported syntax"),
        ("return { a = f }", "unexpected"),
        ('return { a = "x\\"y" }', "unsupported syntax"),
        ("return { a = 'x' }", "unsupported syntax"),
        ("return { a = 1, a = 2 }", "duplicate key"),
        ("return { a = 1, 2 }", "mixes named"),
        ("return { [1] = 2 }", "unsupported table key"),
        ("return { a = 1 } x", "after the returned table"),
        ("return { a = 1", "expected"),
        ("return {\n--[[\nA = 1,\n]]\nB = 2 }", "unsupported syntax"),
    ],
)
def test_rejects_anything_else(text: str, message: str) -> None:
    with pytest.raises(LuaError, match=message):
        parse_module(text)


def test_depth_and_size_are_capped(monkeypatch: pytest.MonkeyPatch) -> None:
    deep = "return " + "{ " * (wiki_lua.MAX_DEPTH + 1) + "}" * (wiki_lua.MAX_DEPTH + 1)
    with pytest.raises(LuaError, match="nested deeper"):
        parse_module(deep)
    monkeypatch.setattr(wiki_lua, "MAX_BYTES", 10)
    with pytest.raises(LuaError, match="larger than"):
        parse_module("return { a = 1 }")
