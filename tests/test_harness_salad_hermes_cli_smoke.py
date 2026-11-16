import tempfile
import unittest
from pathlib import Path
from scripts.harness_salad_hermes_cli_smoke import run_cli


class HermesSaladCliSmokeTests(unittest.TestCase):
    def test_cli_subprocess_contract(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp)
            binary=base/"fake-hermes"
            binary.write_text("#!/bin/sh\necho 46\n")
            binary.chmod(0o700)
            result=run_cli(str(binary),base,base,"test","nonsecret",timeout=5)
            self.assertEqual(result["exit"],0)
            self.assertEqual(result["stdout"],"46")

    def test_redacts_credential_if_child_leaks_it(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp)
            binary=base/"fake-hermes"
            binary.write_text("#!/bin/sh\necho test-private-token\n")
            binary.chmod(0o700)
            result=run_cli(str(binary),base,base,"test","test-private-token",timeout=5)
            self.assertEqual(result["stdout"],"[REDACTED]")


if __name__=="__main__":
    unittest.main()
