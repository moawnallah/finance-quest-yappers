"""Blockly side of the hard engine (docs/hard_engine.md, "Blockly"): block definitions and a
toolbox generated from a task's palette, and a converter between Blockly's JSON serialization
(`Blockly.serialization.workspaces.save`) and our program JSON (hard/dsl.py).

The app never builds the program format by hand: it loads `blocks` and `toolbox` from the
question, lets the user build, saves the workspace, and sends it as is. The backend converts
it here, then checks and scores the program.

Blockly block types are our block names with the prefix "fq_"; the root block is
"fq_every_month" with one statement input DO. Inputs and fields use upper-case names.
"""
from __future__ import annotations

import re

from .dsl import BLOCKS, VARS

PREFIX = "fq_"
ROOT = PREFIX + "every_month"
COLOURS = {"root": 45, "statement": 210, "condition": 120, "number": 230, "action": 290}
ACTIONS = ("save_to_buffer", "invest", "pay_debt", "sell_investments", "rebalance")

# Our slot name -> (Blockly arg type, Blockly name, type check)
SLOTS = {
    "if_else": {"if": ("input_value", "IF", "Boolean"), "then": ("input_statement", "THEN", None),
                "else": ("input_statement", "ELSE", None)},
    "compare": {"left": ("input_value", "LEFT", "Number"), "op": ("field_dropdown", "OP", None),
                "right": ("input_value", "RIGHT", "Number")},
    "and": {"a": ("input_value", "A", "Boolean"), "b": ("input_value", "B", "Boolean")},
    "or": {"a": ("input_value", "A", "Boolean"), "b": ("input_value", "B", "Boolean")},
    "not": {"a": ("input_value", "A", "Boolean")},
    "number": {"value": ("field_number", "VALUE", None)},
    "var": {"name": ("field_dropdown", "NAME", None)},
    "math": {"left": ("input_value", "LEFT", "Number"), "op": ("field_dropdown", "OP", None),
             "right": ("input_value", "RIGHT", "Number")},
    **{a: {"amount": ("input_value", "AMOUNT", "Number")} for a in ACTIONS if a != "rebalance"},
    "rebalance": {},
}


class ConversionError(ValueError):
    pass


# ---------------------------------------------------------------- definitions and toolbox

def _definition(block: str, allowed_vars: list[str]) -> dict:
    spec = BLOCKS[block]
    slots = re.findall(r"\{(\w+)\}", spec["text"])
    message, args = spec["text"], []
    for i, slot in enumerate(slots, start=1):
        kind, name, check = SLOTS[block][slot]
        message = message.replace("{" + slot + "}", f"%{i}", 1)
        arg = {"type": kind, "name": name}
        if check:
            arg["check"] = check
        if kind == "field_dropdown":
            options = spec["ops"] if block != "var" else {v: VARS[v] for v in allowed_vars}
            arg["options"] = [[label, key] for key, label in options.items()]
        if kind == "field_number":
            arg["value"] = 0
        args.append(arg)
    d = {"type": PREFIX + block, "message0": message, "args0": args, "inputsInline": block not in ("if_else",)}
    if spec["type"] == "condition":
        d.update(output="Boolean", colour=COLOURS["condition"])
    elif spec["type"] == "number":
        d.update(output="Number", colour=COLOURS["number"])
    else:
        d.update(previousStatement=None, nextStatement=None,
                 colour=COLOURS["action"] if block in ACTIONS else COLOURS["statement"])
    return d


def block_definitions(palette: list[str], allowed_vars: list[str]) -> list[dict]:
    """Blockly JSON block definitions (Blockly.common.defineBlocksWithJsonArray)."""
    root = {"type": ROOT, "message0": "Every month %1", "args0": [{"type": "input_statement", "name": "DO"}],
            "colour": COLOURS["root"], "deletable": False,
            "tooltip": "Your rule runs once at the start of every month."}
    blocks = [b for b in palette if b != "var"] + (["var"] if allowed_vars else [])
    return [root] + [_definition(b, allowed_vars) for b in blocks]


def toolbox(palette: list[str], allowed_vars: list[str]) -> dict:
    """A category toolbox; values get one ready-made block each, with the field preset."""
    groups = [("Rules", ["if_else"]), ("Conditions", ["compare", "and", "or", "not"]),
              ("Numbers", ["number", "math"]), ("Actions", list(ACTIONS))]
    contents = []
    for name, blocks in groups:
        items = [{"kind": "block", "type": PREFIX + b} for b in blocks if b in palette]
        if name == "Numbers":
            items += [{"kind": "block", "type": PREFIX + "var", "fields": {"NAME": v}} for v in allowed_vars]
        if items:
            contents.append({"kind": "category", "name": name, "contents": items})
    return {"kind": "categoryToolbox", "contents": contents}


# ---------------------------------------------------------------- workspace -> program

def _child(block: dict, name: str) -> dict | None:
    inp = (block.get("inputs") or {}).get(name) or {}
    return inp.get("block") or inp.get("shadow")


def _type(block: dict) -> str:
    t = block.get("type", "")
    if not t.startswith(PREFIX):
        raise ConversionError(f"unknown block type {t!r}")
    return t[len(PREFIX):]


def _value(block: dict | None, where: str) -> dict:
    if block is None:
        raise ConversionError(f"{where}: an empty slot; put a block in it")
    b, fields = _type(block), block.get("fields") or {}
    if b == "number":
        return {"block": "number", "value": fields.get("VALUE", 0)}
    if b == "var":
        return {"block": "var", "name": fields.get("NAME")}
    if b in ("math", "compare"):
        return {"block": b, "op": fields.get("OP"), "left": _value(_child(block, "LEFT"), f"{where}.left"),
                "right": _value(_child(block, "RIGHT"), f"{where}.right")}
    if b in ("and", "or"):
        return {"block": b, "args": [_value(_child(block, "A"), f"{where}.a"), _value(_child(block, "B"), f"{where}.b")]}
    if b == "not":
        return {"block": "not", "arg": _value(_child(block, "A"), f"{where}.a")}
    raise ConversionError(f"{where}: {b!r} cannot go in a value slot")


def _statements(block: dict | None, where: str) -> list[dict]:
    out, i = [], 0
    while block is not None:
        b = _type(block)
        w = f"{where}[{i}]"
        if b == "if_else":
            out.append({"block": "if_else", "if": _value(_child(block, "IF"), w + ".if"),
                        "then": _statements(_child(block, "THEN"), w + ".then"),
                        "else": _statements(_child(block, "ELSE"), w + ".else")})
        elif b == "rebalance":
            out.append({"block": "rebalance"})
        elif b in ACTIONS:
            out.append({"block": b, "amount": _value(_child(block, "AMOUNT"), w + ".amount")})
        else:
            raise ConversionError(f"{w}: {b!r} is not a statement")
        block = ((block.get("next") or {}).get("block"))
        i += 1
    return out


def workspace_to_program(workspace: dict) -> dict:
    """Blockly workspace JSON -> our program. Loose blocks outside the root are ignored, as in
    Blockly itself; exactly one root is required."""
    top = ((workspace.get("blocks") or {}).get("blocks")) or []
    roots = [b for b in top if b.get("type") == ROOT]
    if len(roots) != 1:
        raise ConversionError(f"the workspace needs exactly one 'Every month' block, found {len(roots)}")
    return {"every_month": _statements(_child(roots[0], "DO"), "every_month")}


# ---------------------------------------------------------------- program -> workspace

def _to_value(n: dict) -> dict:
    b = n["block"]
    if b == "number":
        return {"type": PREFIX + "number", "fields": {"VALUE": n["value"]}}
    if b == "var":
        return {"type": PREFIX + "var", "fields": {"NAME": n["name"]}}
    if b in ("math", "compare"):
        return {"type": PREFIX + b, "fields": {"OP": n["op"]},
                "inputs": {"LEFT": {"block": _to_value(n["left"])}, "RIGHT": {"block": _to_value(n["right"])}}}
    if b in ("and", "or"):
        return {"type": PREFIX + b, "inputs": {"A": {"block": _to_value(n["args"][0])}, "B": {"block": _to_value(n["args"][1])}}}
    return {"type": PREFIX + "not", "inputs": {"A": {"block": _to_value(n["arg"])}}}


def _to_chain(nodes: list[dict]) -> dict | None:
    head = None
    for n in reversed(nodes):
        if n["block"] == "if_else":
            blk = {"type": PREFIX + "if_else", "inputs": {"IF": {"block": _to_value(n["if"])}}}
            for key, name in (("then", "THEN"), ("else", "ELSE")):
                chain = _to_chain(n.get(key, []))
                if chain:
                    blk["inputs"][name] = {"block": chain}
        elif n["block"] == "rebalance":
            blk = {"type": PREFIX + "rebalance"}
        else:
            blk = {"type": PREFIX + n["block"], "inputs": {"AMOUNT": {"block": _to_value(n["amount"])}}}
        if head:
            blk["next"] = {"block": head}
        head = blk
    return head


def program_to_workspace(program: dict) -> dict:
    """Our program -> Blockly workspace JSON (starter program, reference solution in the reveal)."""
    root = {"type": ROOT, "x": 20, "y": 20}
    chain = _to_chain(program.get("every_month", []))
    if chain:
        root["inputs"] = {"DO": {"block": chain}}
    return {"blocks": {"languageVersion": 0, "blocks": [root]}}
