"""Blockly side of the hard engine (docs/hard_engine.md, "Blockly"): block definitions and a
toolbox generated from a task's palette, and a converter between Blockly's JSON serialization
(`Blockly.serialization.workspaces.save`) and our program JSON (hard/dsl.py).

The app never builds the program format by hand: it loads `blocks` and `toolbox` from the
question, lets the user build, saves the workspace, and sends it as is. The backend converts
it here, then checks and scores the program.

Blockly block types are our block names with the prefix "fq_"; the root block is
"fq_every_month" with one statement input DO. Inputs and fields use upper-case names.

Own variables use Blockly's built-in variable blocks (the toolbox category with
`"custom": "VARIABLE"`, the same "Make a variable" button as Scratch): `variables_set`,
`math_change` and `variables_get`. They need Blockly's default blocks to be registered
(`import 'blockly'`, not only 'blockly/core'). Every number slot in the toolbox carries a typed
number (a shadow `fq_number`) that the user can overwrite or cover with another block.
"""
from __future__ import annotations

import re

from .dsl import BLOCKS, OWN_VAR_BLOCKS, VARS

PREFIX = "fq_"
ROOT = PREFIX + "every_month"
COLOURS = {"root": 45, "statement": 210, "condition": 120, "number": 230, "action": 290}
ACTIONS = ("save_to_buffer", "save_to_pot", "invest", "invest_in", "pay_debt", "sell_investments", "sell", "rebalance")
BUILTIN = {"variables_get", "variables_set", "math_change", "math_number"}  # Blockly's own blocks we accept

# Our slot name -> (Blockly arg type, Blockly name, type check)
SLOTS = {
    "if_else": {"if": ("input_value", "IF", "Boolean"), "then": ("input_statement", "THEN", None),
                "else": ("input_statement", "ELSE", None)},
    "if": {"if": ("input_value", "IF", "Boolean"), "then": ("input_statement", "THEN", None)},
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
    "invest_in": {"amount": ("input_value", "AMOUNT", "Number"), "asset": ("field_dropdown", "ASSET", None)},
    "sell": {"amount": ("input_value", "AMOUNT", "Number"), "asset": ("field_dropdown", "ASSET", None)},
    "rebalance": {},
}


class ConversionError(ValueError):
    pass


# ---------------------------------------------------------------- definitions and toolbox

def _definition(block: str, allowed_vars: list[str], assets: dict | None) -> dict:
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
            if block == "var":
                options = {v: VARS[v] for v in allowed_vars}
            elif slot == "asset":
                options = assets or {}
            else:
                options = spec["ops"]
            arg["options"] = [[label, key] for key, label in options.items()]
        if kind == "field_number":
            arg["value"] = 0
        args.append(arg)
    d = {"type": PREFIX + block, "message0": message, "args0": args, "inputsInline": block not in ("if_else", "if")}
    if spec["type"] == "condition":
        d.update(output="Boolean", colour=COLOURS["condition"])
    elif spec["type"] == "number":
        d.update(output="Number", colour=COLOURS["number"])
    else:
        d.update(previousStatement=None, nextStatement=None,
                 colour=COLOURS["action"] if block in ACTIONS else COLOURS["statement"])
    return d


def block_definitions(palette: list[str], allowed_vars: list[str], assets: dict | None = None) -> list[dict]:
    """Blockly JSON block definitions (Blockly.common.defineBlocksWithJsonArray). Own-variable
    blocks are Blockly's built-ins, so they are not defined here. assets: {key: label}."""
    root = {"type": ROOT, "message0": "Every month %1", "args0": [{"type": "input_statement", "name": "DO"}],
            "colour": COLOURS["root"], "deletable": False,
            "tooltip": "Your rule runs once at the start of every month."}
    blocks = [b for b in palette if b != "var" and b not in OWN_VAR_BLOCKS] + (["var"] if allowed_vars else [])
    return [root] + [_definition(b, allowed_vars, assets) for b in blocks]


def _with_typed_numbers(block: str) -> dict:
    """A toolbox entry whose number slots hold a typed number (like Scratch's white oval)."""
    entry = {"kind": "block", "type": PREFIX + block}
    numbers = {name: {"shadow": {"type": PREFIX + "number", "fields": {"VALUE": 0}}}
               for kind, name, check in SLOTS[block].values() if kind == "input_value" and check == "Number"}
    if numbers:
        entry["inputs"] = numbers
    return entry


def toolbox(palette: list[str], allowed_vars: list[str]) -> dict:
    """A category toolbox; values get one ready-made block each, with the field preset."""
    groups = [("Rules", ["if", "if_else"]), ("Conditions", ["compare", "and", "or", "not"]),
              ("Numbers", ["number", "math"]), ("Money moves", list(ACTIONS))]
    contents = []
    for name, blocks in groups:
        items = [_with_typed_numbers(b) for b in blocks if b in palette]
        if name == "Numbers":
            items += [{"kind": "block", "type": PREFIX + "var", "fields": {"NAME": v}} for v in allowed_vars]
        if items:
            contents.append({"kind": "category", "name": name, "contents": items})
        if name == "Numbers" and any(b in palette for b in OWN_VAR_BLOCKS):
            contents.append({"kind": "category", "name": "My variables", "custom": "VARIABLE"})
    return {"kind": "categoryToolbox", "contents": contents}


# ---------------------------------------------------------------- workspace -> program

def _child(block: dict, name: str) -> dict | None:
    inp = (block.get("inputs") or {}).get(name) or {}
    return inp.get("block") or inp.get("shadow")


def _type(block: dict) -> str:
    t = block.get("type", "")
    if t in BUILTIN:
        return t
    if not t.startswith(PREFIX):
        raise ConversionError(f"unknown block type {t!r}")
    return t[len(PREFIX):]


def _var_name(block: dict, names: dict, where: str) -> str:
    """Blockly stores a variable field as {"id": ...} (newer versions) or as the name itself."""
    field = (block.get("fields") or {}).get("VAR")
    if isinstance(field, dict):
        name = field.get("name") or names.get(field.get("id"))
    else:
        name = field
    if not name:
        raise ConversionError(f"{where}: a variable block without a variable")
    return name


def _value(block: dict | None, where: str, names: dict) -> dict:
    if block is None:
        raise ConversionError(f"{where}: an empty slot; put a block in it")
    b, fields = _type(block), block.get("fields") or {}
    if b == "number":
        return {"block": "number", "value": fields.get("VALUE", 0)}
    if b == "math_number":
        return {"block": "number", "value": fields.get("NUM", 0)}
    if b == "var":
        return {"block": "var", "name": fields.get("NAME")}
    if b == "variables_get":
        return {"block": "my_var", "name": _var_name(block, names, where)}
    if b in ("math", "compare"):
        return {"block": b, "op": fields.get("OP"), "left": _value(_child(block, "LEFT"), f"{where}.left", names),
                "right": _value(_child(block, "RIGHT"), f"{where}.right", names)}
    if b in ("and", "or"):
        return {"block": b, "args": [_value(_child(block, "A"), f"{where}.a", names),
                                     _value(_child(block, "B"), f"{where}.b", names)]}
    if b == "not":
        return {"block": "not", "arg": _value(_child(block, "A"), f"{where}.a", names)}
    raise ConversionError(f"{where}: {b!r} cannot go in a value slot")


def _statements(block: dict | None, where: str, names: dict) -> list[dict]:
    out, i = [], 0
    while block is not None:
        b = _type(block)
        w = f"{where}[{i}]"
        if b in ("if_else", "if"):
            node = {"block": b, "if": _value(_child(block, "IF"), w + ".if", names),
                    "then": _statements(_child(block, "THEN"), w + ".then", names)}
            if b == "if_else":
                node["else"] = _statements(_child(block, "ELSE"), w + ".else", names)
            out.append(node)
        elif b in ("variables_set", "math_change"):
            out.append({"block": "set_var" if b == "variables_set" else "change_var",
                        "name": _var_name(block, names, w),
                        "value": _value(_child(block, "VALUE" if b == "variables_set" else "DELTA"), w + ".value", names)})
        elif b == "rebalance":
            out.append({"block": "rebalance"})
        elif b in ("invest_in", "sell"):
            out.append({"block": b, "amount": _value(_child(block, "AMOUNT"), w + ".amount", names),
                        "asset": (block.get("fields") or {}).get("ASSET")})
        elif b in ACTIONS:
            out.append({"block": b, "amount": _value(_child(block, "AMOUNT"), w + ".amount", names)})
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
    names = {v.get("id"): v.get("name") for v in workspace.get("variables") or []}
    return {"every_month": _statements(_child(roots[0], "DO"), "every_month", names)}


# ---------------------------------------------------------------- program -> workspace

def _var_field(name: str) -> dict:
    return {"VAR": {"id": "v_" + name}}


def _to_value(n: dict) -> dict:
    b = n["block"]
    if b == "number":
        return {"type": PREFIX + "number", "fields": {"VALUE": n["value"]}}
    if b == "var":
        return {"type": PREFIX + "var", "fields": {"NAME": n["name"]}}
    if b == "my_var":
        return {"type": "variables_get", "fields": _var_field(n["name"])}
    if b in ("math", "compare"):
        return {"type": PREFIX + b, "fields": {"OP": n["op"]},
                "inputs": {"LEFT": {"block": _to_value(n["left"])}, "RIGHT": {"block": _to_value(n["right"])}}}
    if b in ("and", "or"):
        return {"type": PREFIX + b, "inputs": {"A": {"block": _to_value(n["args"][0])}, "B": {"block": _to_value(n["args"][1])}}}
    return {"type": PREFIX + "not", "inputs": {"A": {"block": _to_value(n["arg"])}}}


def _to_chain(nodes: list[dict], own: set) -> dict | None:
    head = None
    for n in reversed(nodes):
        b = n["block"]
        if b in ("if_else", "if"):
            blk = {"type": PREFIX + b, "inputs": {"IF": {"block": _to_value(n["if"])}}}
            for key, name in (("then", "THEN"), ("else", "ELSE")):
                chain = _to_chain(n.get(key, []), own)
                if chain:
                    blk["inputs"][name] = {"block": chain}
        elif b in ("set_var", "change_var"):
            own.add(n["name"])
            blk = {"type": "variables_set" if b == "set_var" else "math_change", "fields": _var_field(n["name"]),
                   "inputs": {("VALUE" if b == "set_var" else "DELTA"): {"block": _to_value(n["value"])}}}
        elif b == "rebalance":
            blk = {"type": PREFIX + "rebalance"}
        else:
            blk = {"type": PREFIX + b, "inputs": {"AMOUNT": {"block": _to_value(n["amount"])}}}
            if b in ("invest_in", "sell"):
                blk["fields"] = {"ASSET": n["asset"]}
        if head:
            blk["next"] = {"block": head}
        head = blk
    return head


def _own_names(n) -> set:
    if isinstance(n, dict):
        found = {n["name"]} if n.get("block") in OWN_VAR_BLOCKS else set()
        return found.union(*(_own_names(v) for v in n.values()))
    if isinstance(n, list):
        return set().union(*(_own_names(v) for v in n)) if n else set()
    return set()


def program_to_workspace(program: dict) -> dict:
    """Our program -> Blockly workspace JSON (starter program, reference solution in the reveal)."""
    root = {"type": ROOT, "x": 20, "y": 20}
    chain = _to_chain(program.get("every_month", []), set())
    if chain:
        root["inputs"] = {"DO": {"block": chain}}
    ws = {"blocks": {"languageVersion": 0, "blocks": [root]}}
    names = sorted(_own_names(program))
    if names:
        ws["variables"] = [{"name": name, "id": "v_" + name} for name in names]
    return ws
