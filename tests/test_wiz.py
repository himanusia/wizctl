import io
import json
import os
import sys
import unittest
from contextlib import redirect_stdout
from tempfile import TemporaryDirectory
from unittest.mock import patch

import wiz


class WizRegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.cache_path = os.path.join(self.tmp.name, "lights.json")
        self.cache_patch = patch.object(wiz, "CACHE_FILE", self.cache_path)
        self.cache_patch.start()

    def tearDown(self):
        self.cache_patch.stop()
        self.tmp.cleanup()

    def test_migrates_legacy_ip_cache_to_numbered_registry(self):
        with open(self.cache_path, "w") as handle:
            json.dump(
                {
                    "lights": [
                        {"ip": "192.0.2.51", "name": "desk"},
                        {"ip": "192.0.2.50", "name": None},
                    ]
                },
                handle,
            )

        state = wiz.load_state()

        self.assertEqual([light["id"] for light in state["lights"]], ["1", "2"])
        self.assertEqual(state["lights"][0]["ip"], "192.0.2.50")
        self.assertEqual(state["lights"][1]["name"], "desk")
        self.assertEqual(state["next_id"], 3)

    def test_registration_response_extracts_mac_uid(self):
        packet = json.dumps(
            {"method": "registration", "result": {"mac": "AA:BB:CC:DD:EE:FF"}}
        ).encode("utf-8")

        self.assertEqual(
            wiz.parse_discovery_packet(packet),
            {"uid": "mac:aabbccddeeff"},
        )

    def test_mac_keeps_same_id_when_ip_changes(self):
        state = wiz.empty_state()
        first = wiz.merge_discovered(
            state,
            [{"ip": "192.0.2.50", "mac": "AA:BB:CC:DD:EE:FF"}],
        )[0]
        second = wiz.merge_discovered(
            state,
            [{"ip": "192.0.2.99", "mac": "aabbccddeeff"}],
        )[0]

        self.assertEqual(first["id"], second["id"])
        self.assertEqual(second["ip"], "192.0.2.99")
        self.assertEqual(second["uid"], "mac:aabbccddeeff")
        self.assertEqual(len(state["lights"]), 1)

    def test_different_mac_at_reused_ip_does_not_inherit_old_identity(self):
        state = wiz.empty_state()
        old = wiz.merge_discovered(
            state,
            [{"ip": "192.0.2.50", "mac": "AA:AA:AA:AA:AA:AA"}],
        )[0]
        old["name"] = "desk"
        new = wiz.merge_discovered(
            state,
            [{"ip": "192.0.2.50", "mac": "BB:BB:BB:BB:BB:BB"}],
        )[0]

        self.assertNotEqual(new["id"], old["id"])
        self.assertEqual(old["uid"], "mac:aaaaaaaaaaaa")
        self.assertEqual(old["name"], "desk")
        self.assertIsNone(old["ip"])
        self.assertEqual(new["uid"], "mac:bbbbbbbbbbbb")
        self.assertIsNone(new["name"])
        self.assertEqual(new["ip"], "192.0.2.50")
        self.assertEqual(len(state["lights"]), 2)

    def test_offline_conflict_record_round_trips_without_string_none(self):
        state = wiz.empty_state()
        old = wiz.merge_discovered(
            state,
            [{"ip": "192.0.2.50", "mac": "AA:AA:AA:AA:AA:AA"}],
        )[0]
        old["name"] = "desk"
        wiz.merge_discovered(
            state,
            [{"ip": "192.0.2.50", "mac": "BB:BB:BB:BB:BB:BB"}],
        )
        wiz.save_state(state)

        loaded = wiz.load_state()
        old_loaded = next(
            light for light in loaded["lights"]
            if light["uid"] == "mac:aaaaaaaaaaaa"
        )
        self.assertIsNone(old_loaded["ip"])
        self.assertEqual(old_loaded["last_ip"], "192.0.2.50")

    def test_offline_record_never_sends_command_to_stale_ip(self):
        record = {
            "id": "1",
            "uid": "mac:aaaaaaaaaaaa",
            "ip": None,
            "last_ip": "192.0.2.50",
            "name": "desk",
        }
        with patch.object(wiz, "get_pilot") as get_pilot:
            output = io.StringIO()
            with redirect_stdout(output):
                result = wiz.apply(record, None)

        self.assertFalse(result)
        get_pilot.assert_not_called()
        self.assertIn("no current IP", output.getvalue())

    def test_resolves_numeric_id_name_and_ip(self):
        state = {
            "version": 2,
            "next_id": 3,
            "ignored": [],
            "lights": [
                {"id": "1", "uid": "mac:111111111111", "ip": "192.0.2.50", "name": "desk"},
                {"id": "2", "uid": "mac:222222222222", "ip": "192.0.2.51", "name": "bedroom"},
            ],
        }

        _, target = wiz.split_target("on", ["@2"])
        by_id = wiz.resolve_targets(state, target)
        _, target = wiz.split_target("on", ["desk"])
        by_name = wiz.resolve_targets(state, target)
        _, target = wiz.split_target("on", ["192.0.2.51"])
        by_ip = wiz.resolve_targets(state, target)
        _, brightness_target = wiz.split_target("40", ["desk"])

        self.assertEqual(by_id[0]["id"], "2")
        self.assertEqual(by_name[0]["id"], "1")
        self.assertEqual(by_ip[0]["id"], "2")
        self.assertEqual(brightness_target, "desk")

    def test_empty_explicit_target_is_rejected(self):
        state = {
            "version": 2,
            "next_id": 1,
            "ignored": [],
            "lights": [],
        }

        with self.assertRaises(SystemExit):
            wiz.split_target("off", ["@"])
        with self.assertRaises(SystemExit):
            wiz.resolve_targets(state, " ")

    def test_quoted_empty_forget_target_is_rejected_without_deleting(self):
        state = {
            "version": 2,
            "next_id": 2,
            "ignored": [],
            "lights": [
                {"id": "1", "uid": "mac:111111111111", "ip": "192.0.2.50", "name": "desk"},
            ],
        }
        wiz.save_state(state)

        with patch.object(sys, "argv", ["wiz", "forget", ""]):
            with self.assertRaises(SystemExit):
                wiz.main()

        saved = wiz.load_state()
        self.assertEqual(len(saved["lights"]), 1)
        self.assertEqual(saved["lights"][0]["name"], "desk")

    def test_forget_by_id_persists_ignored_uid(self):
        state = {
            "version": 2,
            "next_id": 2,
            "ignored": [],
            "lights": [
                {"id": "1", "uid": "mac:111111111111", "ip": "192.0.2.50", "name": "desk"},
            ],
        }
        wiz.save_state(state)

        args, target = wiz.split_target("forget", ["@1"])
        self.assertEqual(args, [])
        wiz.cmd_forget(state, wiz.resolve_targets(state, target))
        saved = wiz.load_state()

        self.assertEqual(saved["lights"], [])
        self.assertEqual(saved["ignored"], ["mac:111111111111"])

    def test_normal_discovery_skips_forgotten_device_until_re_adopted(self):
        state = {
            "version": 2,
            "next_id": 2,
            "ignored": ["mac:111111111111"],
            "lights": [],
        }
        discovered = [{"ip": "192.0.2.50", "mac": "11:11:11:11:11:11"}]

        tracked = wiz.merge_discovered(state, discovered)
        self.assertEqual(tracked, [])
        self.assertEqual(state["lights"], [])

        tracked = wiz.merge_discovered(state, discovered, include_ignored=True)
        self.assertEqual([light["id"] for light in tracked], ["2"])
        self.assertEqual(state["ignored"], [])

    def test_bare_status_refreshes_discovery_before_listing(self):
        response = {"ip": "192.0.2.50", "mac": "AA:BB:CC:DD:EE:FF"}
        with patch.object(wiz, "discover", return_value=[response]) as discover:
            with patch.object(wiz, "get_pilot", return_value={"state": True, "dimming": 80}):
                with patch.object(sys, "argv", ["wiz"]):
                    output = io.StringIO()
                    with redirect_stdout(output):
                        result = wiz.main()

        discover.assert_called_once_with()
        self.assertEqual(result, 0)
        self.assertIn("[1]", output.getvalue())
        self.assertIn("192.0.2.50", output.getvalue())

    def test_rgb_accepts_hash_hex_example(self):
        self.assertEqual(
            wiz.build_params("rgb", ["#ff8800"]),
            {"r": 255, "g": 136, "b": 0, "state": True},
        )

    def test_named_color_preset_builds_rgb_params(self):
        self.assertEqual(
            wiz.build_params("preset", ["orange"]),
            {"r": 255, "g": 136, "b": 0, "state": True},
        )
        self.assertEqual(
            wiz.build_params("color", ["blue"]),
            {"r": 0, "g": 102, "b": 255, "state": True},
        )

    def test_named_ambience_builds_scene_params(self):
        self.assertEqual(
            wiz.build_params("ambience", ["Ocean"]),
            {"sceneId": 1, "state": True},
        )
        self.assertEqual(
            wiz.build_params("scene", ["35"]),
            {"sceneId": 35, "state": True},
        )

    def test_preset_help_lists_default_and_color_presets(self):
        with patch.object(sys, "argv", ["wiz", "preset"]):
            output = io.StringIO()
            with redirect_stdout(output):
                result = wiz.main()

        self.assertEqual(result, 0)
        self.assertIn("night", output.getvalue())
        self.assertIn("orange", output.getvalue())
        self.assertIn("#ff8800", output.getvalue())

    def test_ambience_help_lists_ids_and_names(self):
        with patch.object(sys, "argv", ["wiz", "ambience"]):
            output = io.StringIO()
            with redirect_stdout(output):
                result = wiz.main()

        self.assertEqual(result, 0)
        self.assertIn("1", output.getvalue())
        self.assertIn("Ocean", output.getvalue())
        self.assertIn("35", output.getvalue())
        self.assertIn("Alarm", output.getvalue())
        self.assertIn("1000", output.getvalue())
        self.assertIn("Rhythm", output.getvalue())
        self.assertIn("256", output.getvalue())
        self.assertIn("Custom Mode 1", output.getvalue())

    def test_version_is_exposed_by_cli(self):
        with patch.object(sys, "argv", ["wiz", "--version"]):
            output = io.StringIO()
            with redirect_stdout(output):
                result = wiz.main()

        self.assertEqual(result, 0)
        self.assertEqual(output.getvalue().strip(), "wiz 0.5.0")


if __name__ == "__main__":
    unittest.main()
