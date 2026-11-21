"""A readable text form of hard-task programs, for the app's code panel.

The engine runs the JSON block program (dsl.py). This module turns text like

    # every month
    if buffer_months < 2:
        save_to_buffer(cash)
    else:
        save_to_pot((next_bill - pot) / months_to_next_bill)

into that program, and a program back into text. The text is parsed, never executed: it only
ever becomes blocks, which dsl.check() then validates as before.

Statements (one per line, blocks indented by 4 spaces):
    if <condition>:   elif <condition>:   else:
    <action>(<amount>)              save_to_buffer, save_to_pot, pay_debt, invest, sell_investments
    <action>(<amount>, <asset>)     invest_in, sell
    rebalance()
    name = <number>                 set an own variable (set_var)
    name += <number>  name -= <number>   change an own variable (change_var)
Numbers: 12, 0.5, 12_000, built-in values (cash, buffer_months, ...), own variables,
    + - * / and parentheses, min(a, b), max(a, b), and a leading minus.
Conditions: <number> < <number>, <number> > <number>, and, or, not, parentheses.
"""
from __future__ import annotations

import re

from .dsl import VARS
from sim import ACTIONS, ASSET_ACTIONS

INDENT = 4
_TOKEN = re.compile(r"\s*(?:(\d[\d_]*(?:\.\d+)?|\.\d+)|([A-Za-z_][A-Za-z0-9_]*)|(\+=|-=|<=|>=|==|!=|[()+\-*/<>=,:]))")


class TextError(ValueError):
    """The code could not be read. The message names the line."""


def _tokens(src: str, line_no: int) -> list[tuple[str, str]]:
    out, pos = [], 0
    src = src.rstrip()
    while pos < len(src):
        m = _TOKEN.match(src, pos)
        if not m or m.end() == pos:
            raise TextError(f"line {line_no}: I can't read {src[pos:].strip()[:20]!r}")
        num, name, op = m.groups()
        out.append(("num", num) if num else ("name", name) if name else ("op", op))
        pos = m.end()
    return out


class _Line:
    """Recursive-descent parser over one line's tokens."""

    def __init__(self, toks, line_no: int, builtins: set[str]):
        self.t, self.i, self.n, self.builtins = toks, 0, line_no, builtins

    def peek(self, k: int = 0):
        j = self.i + k
        return self.t[j] if j < len(self.t) else (None, None)

    def take(self, value: str | None = None):
        kind, v = self.peek()
        if kind is None or (value is not None and v != value):
            want = f"{value!r}" if value else "more"
            raise TextError(f"line {self.n}: expected {want}" + (f", found {v!r}" if v else " at the end of the line"))
        self.i += 1
        return kind, v

    def done(self):
        if self.i != len(self.t):
            raise TextError(f"line {self.n}: unexpected {self.t[self.i][1]!r}")

    # numbers: sum -> product -> unary -> atom
    def number(self) -> dict:
        left = self.product()
        while self.peek()[1] in ("+", "-"):
            op = self.take()[1]
            left = {"block": "math", "op": op, "left": left, "right": self.product()}
        return left

    def product(self) -> dict:
        left = self.unary()
        while self.peek()[1] in ("*", "/"):
            op = self.take()[1]
            left = {"block": "math", "op": op, "left": left, "right": self.unary()}
        return left

    def unary(self) -> dict:
        if self.peek()[1] == "-":
            self.take()
            inner = self.unary()
            if inner["block"] == "number":
                return {"block": "number", "value": -inner["value"]}
            return {"block": "math", "op": "-", "left": {"block": "number", "value": 0}, "right": inner}
        return self.atom()

    def atom(self) -> dict:
        kind, v = self.peek()
        if kind == "num":
            self.take()
            x = float(v.replace("_", ""))
            return {"block": "number", "value": int(x) if x.is_integer() else x}
        if v == "(":
            self.take("(")
            x = self.number()
            self.take(")")
            return x
        if kind == "name":
            self.take()
            if v in ("min", "max") and self.peek()[1] == "(":
                self.take("(")
                a = self.number()
                self.take(",")
                b = self.number()
                self.take(")")
                return {"block": "math", "op": v, "left": a, "right": b}
            if v in self.builtins:
                return {"block": "var", "name": v}
            if v in VARS:
                raise TextError(f"line {self.n}: {v!r} is not available in this task")
            return {"block": "my_var", "name": v}
        raise TextError(f"line {self.n}: expected a number" + (f", found {v!r}" if v else ""))

    # conditions: or -> and -> not -> comparison
    def condition(self) -> dict:
        left = self.conj()
        while self.peek()[1] == "or":
            self.take()
            left = {"block": "or", "args": [left, self.conj()]}
        return left

    def conj(self) -> dict:
        left = self.negation()
        while self.peek()[1] == "and":
            self.take()
            left = {"block": "and", "args": [left, self.negation()]}
        return left

    def negation(self) -> dict:
        if self.peek()[1] == "not":
            self.take()
            return {"block": "not", "arg": self.negation()}
        # a parenthesised condition, or a parenthesised number that starts a comparison
        if self.peek()[1] == "(":
            save = self.i
            self.take("(")
            try:
                c = self.condition()
                self.take(")")
                if self.peek()[1] not in ("<", ">", "<=", ">=", "==", "!=", "+", "-", "*", "/"):
                    return c
            except TextError:
                pass
            self.i = save
        left = self.number()
        op = self.peek()[1]
        if op in ("<=", ">=", "==", "!="):
            raise TextError(f"line {self.n}: only < and > can compare numbers here")
        if op not in ("<", ">"):
            raise TextError(f"line {self.n}: expected < or > after the number")
        self.take()
        return {"block": "compare", "op": op, "left": left, "right": self.number()}


def to_program(code: str, builtins: list[str] | None = None, assets: list[str] | None = None) -> dict:
    """Code text -> {"every_month": [...]}. Raises TextError with the line number."""
    vars_ok = set(builtins if builtins is not None else VARS)
    lines = []
    for n, raw in enumerate(code.replace("\t", " " * INDENT).splitlines(), 1):
        body = raw.split("#", 1)[0].rstrip()
        if not body.strip():
            continue
        spaces = len(body) - len(body.lstrip(" "))
        if spaces % INDENT:
            raise TextError(f"line {n}: indent blocks by {INDENT} spaces")
        lines.append((n, spaces // INDENT, body.strip()))

    pos = 0

    def block(level: int) -> list[dict]:
        nonlocal pos
        out: list[dict] = []
        while pos < len(lines):
            n, lvl, text = lines[pos]
            if lvl < level:
                break
            if lvl > level:
                raise TextError(f"line {n}: unexpected indent")
            if text.startswith(("elif ", "else")):
                raise TextError(f"line {n}: {text.split()[0]!r} without an 'if' above it")
            pos += 1
            out.append(statement(n, level, text))
        return out

    def body_of(n: int, level: int) -> list[dict]:
        if pos >= len(lines) or lines[pos][1] <= level:
            raise TextError(f"line {n}: the block after ':' is empty; indent at least one line under it")
        return block(level + 1)

    def if_chain(n: int, level: int, text: str, keyword: str) -> dict:
        nonlocal pos
        p = _Line(_tokens(text[len(keyword):], n), n, vars_ok)
        if not text.endswith(":"):
            raise TextError(f"line {n}: end the line with ':'")
        p.t = p.t[:-1]
        cond = p.condition()
        p.done()
        then = body_of(n, level)
        if pos < len(lines) and lines[pos][1] == level:
            n2, _, t2 = lines[pos]
            if t2.startswith("elif "):
                pos += 1
                return {"block": "if_else", "if": cond, "then": then, "else": [if_chain(n2, level, t2, "elif")]}
            if re.fullmatch(r"else\s*:", t2):
                pos += 1
                return {"block": "if_else", "if": cond, "then": then, "else": body_of(n2, level)}
        return {"block": "if", "if": cond, "then": then}

    def statement(n: int, level: int, text: str) -> dict:
        if text.startswith("if "):
            return if_chain(n, level, text, "if")
        toks = _tokens(text, n)
        p = _Line(toks, n, vars_ok)
        kind, name = p.take()
        if kind != "name":
            raise TextError(f"line {n}: a line starts with an action, a variable or 'if'")
        nxt = p.peek()[1]
        if nxt in ("=", "+=", "-="):
            if name in VARS:
                raise TextError(f"line {n}: {name!r} is a built-in value; you can't change it")
            p.take()
            value = p.number()
            p.done()
            if nxt == "=":
                return {"block": "set_var", "name": name, "value": value}
            if nxt == "-=":
                value = ({"block": "number", "value": -value["value"]} if value["block"] == "number"
                         else {"block": "math", "op": "-", "left": {"block": "number", "value": 0}, "right": value})
            return {"block": "change_var", "name": name, "value": value}
        if nxt != "(":
            raise TextError(f"line {n}: {name!r} is not an action; actions look like save_to_buffer(cash)")
        if name not in ACTIONS:
            raise TextError(f"line {n}: unknown action {name!r}")
        p.take("(")
        if name == "rebalance":
            p.take(")")
            p.done()
            return {"block": "rebalance"}
        amount = p.number()
        node = {"block": name, "amount": amount}
        if name in ASSET_ACTIONS:
            p.take(",")
            k, asset = p.take()
            if k != "name":
                raise TextError(f"line {n}: name the asset, for example {name}(cash, {(assets or ['shares'])[0]})")
            if assets is not None and asset not in assets:
                raise TextError(f"line {n}: asset {asset!r} is not in this task (use {', '.join(assets)})")
            node["asset"] = asset
        p.take(")")
        p.done()
        return node

    program = block(0)
    if pos != len(lines):
        raise TextError(f"line {lines[pos][0]}: unexpected indent")
    return {"every_month": program}


_PREC = {"+": 1, "-": 1, "*": 2, "/": 2}


def _num(n: dict, parent: int = 0) -> str:
    b = n["block"]
    if b == "number":
        v = n["value"]
        return str(int(v)) if float(v).is_integer() else str(v)
    if b in ("var", "my_var"):
        return n["name"]
    op = n["op"]
    if op in ("min", "max"):
        return f"{op}({_num(n['left'])}, {_num(n['right'])})"
    p = _PREC[op]
    s = f"{_num(n['left'], p)} {op} {_num(n['right'], p + (1 if op in '-/' else 0))}"
    return f"({s})" if p < parent else s


def _cond(n: dict, parent: int = 0) -> str:
    b = n["block"]
    if b == "compare":
        return f"{_num(n['left'])} {n['op']} {_num(n['right'])}"
    if b == "not":
        return f"not {_cond(n['arg'], 3)}"
    p = 1 if b == "or" else 2
    s = f"{_cond(n['args'][0], p)} {b} {_cond(n['args'][1], p + 1)}"
    return f"({s})" if p < parent else s


def to_text(program: dict | None) -> str:
    """{"every_month": [...]} -> code text (the inverse of to_program)."""
    out: list[str] = []

    def stmts(nodes, level):
        pad = " " * (INDENT * level)
        for n in nodes:
            b = n["block"]
            if b in ("if", "if_else"):
                out.append(f"{pad}if {_cond(n['if'])}:")
                stmts(n["then"], level + 1)
                rest = n.get("else") if b == "if_else" else None
                while rest and len(rest) == 1 and rest[0]["block"] in ("if", "if_else"):
                    e = rest[0]
                    out.append(f"{pad}elif {_cond(e['if'])}:")
                    stmts(e["then"], level + 1)
                    rest = e.get("else") if e["block"] == "if_else" else None
                if rest:
                    out.append(f"{pad}else:")
                    stmts(rest, level + 1)
            elif b == "set_var":
                out.append(f"{pad}{n['name']} = {_num(n['value'])}")
            elif b == "change_var":
                out.append(f"{pad}{n['name']} += {_num(n['value'])}")
            elif b == "rebalance":
                out.append(f"{pad}rebalance()")
            elif b in ASSET_ACTIONS:
                out.append(f"{pad}{b}({_num(n['amount'])}, {n['asset']})")
            else:
                out.append(f"{pad}{b}({_num(n['amount'])})")

    stmts((program or {}).get("every_month") or [], 0)
    return "\n".join(out) + ("\n" if out else "")
