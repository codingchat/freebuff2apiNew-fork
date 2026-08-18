import unittest

from freebuff2api.tool_schema import normalize_tool_schemas


class ToolSchemaNormalizationTests(unittest.TestCase):
    def test_ref_resolution_and_nullable_simplification(self) -> None:
        payload = {
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "demo",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "x": {"$ref": "#/$defs/item"},
                            },
                            "$defs": {
                                "item": {
                                    "type": ["string", "null"],
                                    "nullable": True,
                                }
                            },
                        },
                    },
                }
            ]
        }
        normalize_tool_schemas(payload)
        params = payload["tools"][0]["function"]["parameters"]
        self.assertNotIn("$defs", params)
        self.assertNotIn("nullable", params)
        self.assertEqual(params["properties"]["x"]["type"], "string")

    def test_nullable_anyof_inlined(self) -> None:
        payload = {
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "demo",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "x": {
                                    "anyOf": [
                                        {"type": "null"},
                                        {"type": "integer"},
                                    ]
                                }
                            },
                        },
                    },
                }
            ]
        }
        normalize_tool_schemas(payload)
        x = payload["tools"][0]["function"]["parameters"]["properties"]["x"]
        self.assertEqual(x, {"type": "integer"})

    def test_enum_and_const_null_cleanup(self) -> None:
        payload = {
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "demo",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "x": {"enum": [None, "a", "a"]},
                                "y": {"const": None},
                            },
                        },
                    },
                }
            ]
        }
        normalize_tool_schemas(payload)
        props = payload["tools"][0]["function"]["parameters"]["properties"]
        self.assertEqual(props["x"]["enum"], ["a"])
        self.assertNotIn("const", props["y"])

    def test_missing_parameters_is_skipped(self) -> None:
        payload = {"tools": [{"type": "function", "function": {"name": "no_params"}}]}
        normalize_tool_schemas(payload)
        self.assertNotIn("parameters", payload["tools"][0]["function"])


if __name__ == "__main__":
    unittest.main()
