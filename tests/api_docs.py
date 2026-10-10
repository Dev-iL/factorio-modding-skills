"""Tiny hand-made API documents (api_version 6 shape) shared by the API tests.

Old -> new differences, each exercised by a test:
  - LuaControl.get_inventory changes its parameter type; LuaEntity inherits it (member found through the parent chain).
  - LuaMover.shift moves up to LuaControl when LuaMover gets LuaControl as a parent (MOVED, not REMOVED).
  - LuaGone is removed, LuaNew is added together with one method (the method must not be listed separately).
  - on_built_entity declares its data in a non-alphabetical order.
  - AssemblingMachinePrototype gains a property; CraftingMachinePrototype.energy_usage changes type (inherited by it).
"""

from __future__ import annotations

import copy
import json
from typing import cast

import httpx2
from _lib.apimodel import PrototypeDoc, RuntimeDoc


def _param(name: str, order: int, type_: object, optional: bool = False, description: str = "") -> dict[str, object]:
    return {"name": name, "order": order, "description": description, "type": type_, "optional": optional}


def runtime_old() -> RuntimeDoc:
    return cast(RuntimeDoc, {
        "application": "factorio",
        "application_version": "1.0.0",
        "api_version": 6,
        "stage": "runtime",
        "classes": [
            {
                "name": "LuaControl",
                "order": 0,
                "description": "Common base.",
                "abstract": True,
                "methods": [
                    {
                        "name": "get_inventory",
                        "order": 0,
                        "description": "Get an inventory belonging to this entity.",
                        "parameters": [_param("inventory", 0, "defines.inventory")],
                        "format": {"takes_table": False},
                        "return_values": [{"order": 0, "description": "The inventory or nil.", "type": "LuaInventory", "optional": True}],
                    }
                ],
                "attributes": [{"name": "health", "order": 1, "description": "Health.", "read_type": "float", "write_type": "float", "optional": False}],
                "operators": [],
            },
            {
                "name": "LuaEntity",
                "order": 1,
                "description": "An entity.",
                "parent": "LuaControl",
                "abstract": False,
                "methods": [
                    {
                        "name": "create_thing",
                        "order": 0,
                        "description": "Create a thing.",
                        "parameters": [_param("name", 1, "string", description="Which thing."), _param("amount", 0, "uint32", True), _param("force", 2, "string")],
                        "format": {"takes_table": True, "table_optional": False},
                        "return_values": [],
                    }
                ],
                "attributes": [],
                "operators": [],
            },
            {
                "name": "LuaMover",
                "order": 2,
                "description": "Has a method that later moves to LuaControl.",
                "abstract": False,
                "methods": [{"name": "shift", "order": 0, "description": "Shift.", "parameters": [], "format": {"takes_table": False}, "return_values": []}],
                "attributes": [],
                "operators": [],
            },
            {"name": "LuaGone", "order": 3, "description": "Removed later.", "abstract": False, "methods": [], "attributes": [], "operators": []},
        ],
        "events": [
            {
                "name": "on_built_entity",
                "order": 0,
                "description": "Called when player builds something.",
                "filter": "LuaPlayerBuiltEntityEventFilter",
                "data": [
                    _param("tick", 3, "MapTick", description="Tick."),
                    _param("entity", 0, "LuaEntity", description="The entity that was built."),
                    _param("player_index", 1, "uint32"),
                    _param("name", 2, "defines.events"),
                ],
            }
        ],
        "concepts": [
            {
                "name": "SimplePoint",
                "order": 0,
                "description": "A point.",
                "type": {"complex_type": "table", "parameters": [_param("y", 1, "double"), _param("x", 0, "double")]},
            },
            {"name": "Direction", "order": 1, "description": "Alias.", "type": {"complex_type": "union", "options": ["string", "nil"], "full_format": False}},
        ],
        "defines": [
            {
                "name": "inventory",
                "order": 0,
                "description": "",
                "values": [{"name": "furnace_source", "order": 1, "description": ""}, {"name": "chest", "order": 0, "description": "The chest."}],
            }
        ],
        "global_objects": [{"name": "game", "order": 0, "description": "The game.", "type": "LuaGameScript"}],
        "global_functions": [],
    })


def runtime_new() -> RuntimeDoc:
    doc = copy.deepcopy(runtime_old())
    doc["application_version"] = "2.0.0"
    classes = {c["name"]: c for c in doc["classes"]}
    classes["LuaControl"]["methods"][0]["parameters"][0]["type"] = "defines.inventory.kind"
    classes["LuaControl"]["methods"].append(
        {"name": "shift", "order": 1, "description": "Shift.", "parameters": [], "format": {"takes_table": False}, "return_values": []}
    )
    classes["LuaMover"]["parent"] = "LuaControl"
    classes["LuaMover"]["methods"] = []
    classes["LuaEntity"]["methods"].append(
        {"name": "explode", "order": 1, "description": "Boom.", "parameters": [], "format": {"takes_table": False}, "return_values": []}
    )
    doc["classes"] = [c for c in doc["classes"] if c["name"] != "LuaGone"] + [
        {
            "name": "LuaNew",
            "order": 4,
            "description": "New class.",
            "abstract": False,
            "methods": [{"name": "fresh", "order": 0, "description": "", "parameters": [], "format": {"takes_table": False}, "return_values": []}],
            "attributes": [],
            "operators": [],
        }
    ]
    return doc


def prototype_old() -> PrototypeDoc:
    return cast(PrototypeDoc, {
        "application": "factorio",
        "application_version": "1.0.0",
        "api_version": 6,
        "stage": "prototype",
        "prototypes": [
            {
                "name": "CraftingMachinePrototype",
                "order": 0,
                "description": "Base of crafting machines.",
                "abstract": True,
                "deprecated": False,
                "properties": [
                    {"name": "energy_usage", "order": 1, "description": "Energy per tick.", "override": False, "type": "Energy", "optional": False},
                    {"name": "crafting_speed", "order": 0, "description": "Speed.", "override": False, "type": "double", "optional": False},
                ],
            },
            {
                "name": "AssemblingMachinePrototype",
                "order": 1,
                "description": "An assembling machine.",
                "parent": "CraftingMachinePrototype",
                "abstract": False,
                "deprecated": False,
                "typename": "assembling-machine",
                "properties": [
                    {"name": "fixed_recipe", "order": 1, "description": "Preset recipe.", "override": False, "type": "RecipeID", "optional": True, "default": ""},
                    {"name": "circuit_connector", "order": 0, "description": "", "override": False, "type": "string", "optional": True},
                ],
            },
        ],
        "types": [{"name": "Energy", "order": 0, "description": "Energy string.", "abstract": False, "inline": False, "type": "string"}],
        "defines": [],
    })


def prototype_new() -> PrototypeDoc:
    doc = copy.deepcopy(prototype_old())
    doc["application_version"] = "2.0.0"
    protos = {p["name"]: p for p in doc["prototypes"]}
    protos["CraftingMachinePrototype"]["properties"][0]["type"] = {"complex_type": "union", "options": ["Energy", "double"], "full_format": False}
    protos["AssemblingMachinePrototype"]["properties"].append(
        {"name": "animation_random_start_frame", "order": 2, "description": "", "override": False, "type": "boolean", "optional": True, "default": False}
    )
    return doc


class FakeSite:
    """lua-api.factorio.com stand-in that serves documents by URL path and counts requests."""

    def __init__(self, documents: dict[str, bytes]) -> None:
        self.documents = documents
        self.requests: list[str] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request.url.path)
        body = self.documents.get(request.url.path)
        return httpx2.Response(404 if body is None else 200, content=body or b"")


def blob(document: object) -> bytes:
    return json.dumps(document).encode()


def site_with_versions() -> FakeSite:
    """Serves the old documents as 1.0.0 and the new ones as 2.0.0."""
    return FakeSite(
        {
            "/1.0.0/runtime-api.json": blob(runtime_old()),
            "/1.0.0/prototype-api.json": blob(prototype_old()),
            "/2.0.0/runtime-api.json": blob(runtime_new()),
            "/2.0.0/prototype-api.json": blob(prototype_new()),
        }
    )
