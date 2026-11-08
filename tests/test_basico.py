"""Verificações rápidas que rodam no CI (não acessam a API do SC2 Pulse)."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "coletor"))

from sc2pulse import SC2Pulse, _race_from_team, format_matchup  # noqa: E402


class ConfigTest(unittest.TestCase):
    def setUp(self):
        self.cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))

    def test_times(self):
        self.assertTrue(self.cfg["times"])
        ids = [c["id"] for t in self.cfg["times"] for c in t["clas"]]
        self.assertEqual(len(ids), len(set(ids)), "um clã aparece em dois times")
        for t in self.cfg["times"]:
            self.assertTrue(t["nome"])
            for c in t["clas"]:
                self.assertIsInstance(c["id"], int)

    def test_divisoes(self):
        for d in self.cfg["divisoes"]:
            limites = [v["mmr_max"] for v in d["vagas"]]
            self.assertTrue(all(isinstance(x, int) and x > 0 for x in limites), d["nome"])

    def test_meu_time_existe(self):
        if self.cfg.get("meu_time"):
            self.assertIn(self.cfg["meu_time"], [t["nome"] for t in self.cfg["times"]])


class HelpersTest(unittest.TestCase):
    def test_legacy_uids(self):
        self.assertEqual(SC2Pulse.legacy_uids(1, 123)[0], "201-0-1-1.123.1")
        self.assertEqual(len(SC2Pulse.legacy_uids(1, 123)), 4)

    def test_race_from_team(self):
        self.assertEqual(_race_from_team({"team": {"legacyUid": "201-0-1-1.123.3"}}), "Z")
        self.assertIsNone(_race_from_team({"team": {}}))

    def test_format_matchup(self):
        self.assertEqual(format_matchup({"W": 3, "L": 1}), "3-1 (75%)")
        self.assertEqual(format_matchup({"W": 0, "L": 0}), "-")


if __name__ == "__main__":
    unittest.main()
