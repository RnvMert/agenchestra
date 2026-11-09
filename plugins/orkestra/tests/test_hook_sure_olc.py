import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import hook_sure_olc as O  # noqa: E402


class HookSureOlcTest(unittest.TestCase):
    def test_ozet_ortanca_ve_ceyrekler(self):
        o = O.ozet([10, 20, 30, 40])
        self.assertEqual(o["n"], 4)
        self.assertEqual(o["ortanca"], 25)
        self.assertEqual(o["p25"], 20)
        self.assertEqual(o["p75"], 40)

    def test_ozet_bos(self):
        self.assertEqual(O.ozet([])["n"], 0)

    def test_fark_eslestirilmis(self):
        f = O.fark_ozeti([100, 110, 120, 130], [60, 60, 60, 60])
        self.assertEqual(f["ortanca"], 55)
        self.assertGreater(f["p25"], 0)

    def test_degiskenler_giris_yoksa_atlanir(self):
        import tempfile
        with tempfile.TemporaryDirectory() as k:
            os.makedirs(os.path.join(k, "scripts"))
            d = O.degiskenler(k, "PreToolUse", "pyc")
            self.assertEqual(list(d), ["mevcut", "bos_python"])
            self.assertEqual(d["mevcut"][1]["PYTHONDONTWRITEBYTECODE"], "1")

    def test_degiskenler_giris_varsa_onbellek_ayarli(self):
        import tempfile
        with tempfile.TemporaryDirectory() as k:
            os.makedirs(os.path.join(k, "scripts"))
            open(os.path.join(k, "scripts", "hook_giris.py"), "w").close()
            d = O.degiskenler(k, "PreToolUse", "pycdizin")
            env = d["ince_giris_onbellekli"][1]
            self.assertEqual(env["PYTHONDONTWRITEBYTECODE"], "1")
            self.assertEqual(env["ORKESTRA_PYC"], "pycdizin")
            self.assertEqual(d["ince_giris_onbellek_kapali"][1]["ORKESTRA_PYC"], "0")


if __name__ == "__main__":
    unittest.main()
