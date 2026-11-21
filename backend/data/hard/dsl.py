"""The block language of hard tasks: a JSON program (what Blockly exports), checked and compiled
into a policy for the simulation core. User programs are interpreted, never executed as code.

Program:   {"every_month": [statement, ...]}
Statement: {"block": "if_else", "if": <condition>, "then": [...], "else": [...]}
           {"block": <action>, "amount": <number>}          action in sim.ACTIONS
Number:    {"block": "number", "value": 3}
           {"block": "var", "name": "buffer_months"}
           {"block": "math", "op": "*" | "+" | "-" | "min", "left": <number>, "right": <number>}
Condition: {"block": "compare", "op": "<" | ">", "left": <number>, "right": <number>}
           {"block": "and" | "or", "args": [<condition>, <condition>]}
           {"block": "not", "arg": <condition>}
"""
from __future__ import annotations

from sim import ACTIONS

VARS = {
    "cash": "money left this month",
    "shortfall": "money missing this month",
    "buffer_months": "months my buffer covers",
    "buffer": "my buffer",
    "costs": "my essential costs",
    "card_debt": "my card debt",
    "invested": "my investments",
    "employed": "I have a job (1 = yes, 0 = no)",
    "month": "the month number",
    "shares_weight": "the share of shares in my investments (0 to 1)",
    "drift": "how far my mix is from its target (0 to 1)",
    "drawdown": "how far my investments are below their peak (0 to 1)",
    "months_since_rebalance": "months since I last rebalanced",
}

# Sentence templates for the app (Blockly toolbox). {x} marks an input slot.
BLOCKS = {
    "if_else": {"type": "statement", "text": "If {if} then {then} otherwise {else}"},
    "compare": {"type": "condition", "text": "{left} {op} {right}", "ops": {"<": "is less than", ">": "is more than"}},
    "and": {"type": "condition", "text": "{a} and {b}"},
    "or": {"type": "condition", "text": "{a} or {b}"},
    "not": {"type": "condition", "text": "not {a}"},
    "number": {"type": "number", "text": "{value}"},
    "var": {"type": "number", "text": "{name}"},
    "math": {"type": "number", "text": "{left} {op} {right}",
             "ops": {"*": "times", "+": "plus", "-": "minus", "min": "but at most"}},
    "save_to_buffer": {"type": "statement", "text": "Put {amount} PLN into my buffer"},
    "invest": {"type": "statement", "text": "Invest {amount} PLN in a broad share fund"},
    "pay_debt": {"type": "statement", "text": "Pay {amount} PLN off my card"},
    "sell_investments": {"type": "statement", "text": "Sell {amount} PLN of my investments"},
    "rebalance": {"type": "statement", "text": "Rebalance back to my target mix"},
}
assert set(ACTIONS) <= set(BLOCKS)


def check(program, palette: list[str], allowed_vars: list[str], max_blocks: int, max_depth: int) -> list[str]:
    """Return the problems with a program; empty means it can run."""
    errors: list[str] = []
    count = 0

    def block(node, where):
        nonlocal count
        if not isinstance(node, dict) or "block" not in node:
            errors.append(f"{where}: not a block")
            return None
        count += 1
        b = node["block"]
        if b not in BLOCKS:
            errors.append(f"{where}: unknown block {b!r}")
            return None
        if b != "var" and b not in palette:
            errors.append(f"{where}: block {b!r} is not available in this task")
        return b

    def number(node, where, depth):
        b = block(node, where)
        if b is None:
            return
        if b == "number":
            if not isinstance(node.get("value"), (int, float)) or isinstance(node.get("value"), bool):
                errors.append(f"{where}: number needs a value")
        elif b == "var":
            if node.get("name") not in allowed_vars:
                errors.append(f"{where}: value {node.get('name')!r} is not available in this task")
        elif b == "math":
            if node.get("op") not in BLOCKS["math"]["ops"]:
                errors.append(f"{where}: unknown operation {node.get('op')!r}")
            number(node.get("left"), where + ".left", depth + 1)
            number(node.get("right"), where + ".right", depth + 1)
        else:
            errors.append(f"{where}: {b!r} is not a number")

    def condition(node, where, depth):
        b = block(node, where)
        if b is None:
            return
        if b == "compare":
            if node.get("op") not in BLOCKS["compare"]["ops"]:
                errors.append(f"{where}: unknown comparison {node.get('op')!r}")
            number(node.get("left"), where + ".left", depth + 1)
            number(node.get("right"), where + ".right", depth + 1)
        elif b in ("and", "or"):
            args = node.get("args")
            if not isinstance(args, list) or len(args) != 2:
                errors.append(f"{where}: {b} needs two conditions")
            else:
                for i, a in enumerate(args):
                    condition(a, f"{where}.args[{i}]", depth + 1)
        elif b == "not":
            condition(node.get("arg"), where + ".arg", depth + 1)
        else:
            errors.append(f"{where}: {b!r} is not a condition")

    def statements(nodes, where, depth):
        if depth > max_depth:
            errors.append(f"{where}: nested deeper than {max_depth}")
            return
        if not isinstance(nodes, list):
            errors.append(f"{where}: must be a list of blocks")
            return
        for i, node in enumerate(nodes):
            w = f"{where}[{i}]"
            b = block(node, w)
            if b == "if_else":
                condition(node.get("if"), w + ".if", depth + 1)
                statements(node.get("then", []), w + ".then", depth + 1)
                statements(node.get("else", []), w + ".else", depth + 1)
            elif b == "rebalance":
                pass
            elif b in ACTIONS:
                number(node.get("amount"), w + ".amount", depth + 1)
            elif b is not None:
                errors.append(f"{w}: {b!r} is not a statement")

    if not isinstance(program, dict) or not isinstance(program.get("every_month"), list):
        return ["the program must be {\"every_month\": [...]}"]
    statements(program["every_month"], "every_month", 1)
    if count > max_blocks:
        errors.append(f"the program uses {count} blocks; the limit is {max_blocks}")
    return errors


def compile_program(program: dict):
    """A checked program -> policy(ctx) returning [(action, amount), ...]."""

    def num(n, ctx):
        b = n["block"]
        if b == "number":
            return float(n["value"])
        if b == "var":
            return float(ctx[n["name"]])
        left, right = num(n["left"], ctx), num(n["right"], ctx)
        return {"*": left * right, "+": left + right, "-": left - right, "min": min(left, right)}[n["op"]]

    def cond(n, ctx):
        b = n["block"]
        if b == "compare":
            left, right = num(n["left"], ctx), num(n["right"], ctx)
            return left < right if n["op"] == "<" else left > right
        if b == "and":
            return cond(n["args"][0], ctx) and cond(n["args"][1], ctx)
        if b == "or":
            return cond(n["args"][0], ctx) or cond(n["args"][1], ctx)
        return not cond(n["arg"], ctx)

    def run(nodes, ctx, out):
        for n in nodes:
            if n["block"] == "if_else":
                run(n["then"] if cond(n["if"], ctx) else n.get("else", []), ctx, out)
            elif n["block"] == "rebalance":
                out.append(("rebalance", 0.0))
            else:
                out.append((n["block"], num(n["amount"], ctx)))
        return out

    return lambda ctx: run(program["every_month"], ctx, [])
