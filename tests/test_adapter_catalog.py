import json
import unittest
from pathlib import Path

class AdapterCatalogTests(unittest.TestCase):
    def test_catalog_cannot_self_approve(self):
        data=json.loads((Path(__file__).resolve().parents[1]/'adapters/catalog.json').read_text())
        self.assertEqual(data['schema_version'],1)
        seen=set()
        for item in data['adapters']:
            self.assertNotIn(item['id'],seen)
            seen.add(item['id'])
            self.assertIn(item['status'],{'proposed','evaluation','verified','approved','deprecated','revoked'})
            self.assertIn(item['origin'],{'internal','external-integration'})
            if item['status']=='approved':
                self.assertIsNotNone(item['approved_version'])
                self.assertIsNotNone(item['evidence'])
