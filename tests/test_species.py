"""Validate species/species_list.json against the species file contract. No network."""
import json, re, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIST = ROOT / "species" / "species_list.json"
TIERS = {"recorded", "nearby", "unexpected", "unknown"}
REQUIRED = {"aphia_id", "gbif_key", "scientific_name", "common_names", "aliases",
            "group", "flags", "ns_status_tier", "id_notes", "sources"}
OPTIONAL = {"rank"}


class SpeciesContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(LIST.read_text(encoding="utf-8"))

    def test_is_nonempty_list(self):
        self.assertIsInstance(self.data, list)
        self.assertGreater(len(self.data), 0)

    def test_records(self):
        for r in self.data:
            n = r.get("scientific_name")
            self.assertEqual(set(r) - OPTIONAL, REQUIRED, n)
            for k in ("aphia_id", "gbif_key"):
                self.assertTrue(r[k] is None or (isinstance(r[k], int) and not isinstance(r[k], bool)), n)
            self.assertIsInstance(n, str); self.assertTrue(n.strip())
            for k in ("common_names", "aliases"):
                self.assertIsInstance(r[k], list, n)
                self.assertTrue(all(isinstance(x, str) for x in r[k]), n)
            self.assertIsInstance(r["group"], str); self.assertTrue(r["group"])
            self.assertEqual(set(r["flags"]), {"at_risk", "invasive", "range_expander"}, n)
            self.assertTrue(all(isinstance(v, bool) for v in r["flags"].values()), n)
            self.assertIn(r["ns_status_tier"], TIERS, n)
            self.assertIsInstance(r["id_notes"], str)
            if "rank" in r:
                self.assertIsInstance(r["rank"], str)
            self.assertIsInstance(r["sources"], list)
            for s in r["sources"]:
                self.assertEqual(set(s), {"name", "retrieved"}, n)
                self.assertRegex(s["retrieved"], r"^\d{4}-\d{2}-\d{2}$")

    def test_no_duplicate_names(self):
        names = [r["scientific_name"].lower() for r in self.data]
        self.assertEqual(len(names), len(set(names)))

    def test_no_em_dashes(self):
        self.assertNotIn("—", LIST.read_text(encoding="utf-8"))

    def test_required_content(self):
        names = {r["scientific_name"] for r in self.data}
        self.assertIn("Pseudopleuronectes americanus", names)  # winter flounder
        groups = {r["group"] for r in self.data}
        self.assertIn("Invertebrate", groups)
        commons = {c for r in self.data for c in r["common_names"]}
        for c in ("Unknown fish", "Crab, unidentified", "Flatfish, unidentified", "Shrimp, unidentified"):
            self.assertIn(c, commons)

    def test_known_ids_if_resolved(self):
        known = {"Gadus morhua": 126436, "Anguilla rostrata": 158562, "Centropristis striata": 159348}
        for r in self.data:
            if r["scientific_name"] in known and r["aphia_id"] is not None:
                self.assertEqual(r["aphia_id"], known[r["scientific_name"]])

    def test_manifest(self):
        m = json.loads((ROOT / "species" / "species_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(m["total"], len(self.data))
        self.assertIn("unresolved", m)
        self.assertTrue((ROOT / "species" / m["versioned_file"]).exists())


if __name__ == "__main__":
    unittest.main()
