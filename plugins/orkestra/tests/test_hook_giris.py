import os
import subprocess
import sys
import tempfile
import unittest

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GIRIS = os.path.join(KOK, "scripts", "hook_giris.py")
sys.path.insert(0, os.path.join(KOK, "scripts"))
import hook_giris as G  # noqa: E402


class HookGirisTest(unittest.TestCase):
    def setUp(self):
        self._eski = (sys.pycache_prefix, sys.dont_write_bytecode, os.environ.get("ORKESTRA_PYC"))

    def tearDown(self):
        sys.pycache_prefix, sys.dont_write_bytecode = self._eski[0], self._eski[1]
        if self._eski[2] is None:
            os.environ.pop("ORKESTRA_PYC", None)
        else:
            os.environ["ORKESTRA_PYC"] = self._eski[2]

    def test_onbellek_ac_dizini_ayarlar_ve_yazimi_acar(self):
        sys.dont_write_bytecode = True
        os.environ["ORKESTRA_PYC"] = "ozel_dizin"
        self.assertEqual(G.onbellek_ac(), "ozel_dizin")
        self.assertEqual(sys.pycache_prefix, "ozel_dizin")
        self.assertFalse(sys.dont_write_bytecode)

    def test_onbellek_sifir_kapali_birakir(self):
        sys.dont_write_bytecode = True
        os.environ["ORKESTRA_PYC"] = "0"
        self.assertIsNone(G.onbellek_ac())
        self.assertTrue(sys.dont_write_bytecode)

    def test_varsayilan_dizin_kullanici_duzeyinde(self):
        os.environ.pop("ORKESTRA_PYC", None)
        yol = G.onbellek_ac()
        self.assertTrue(yol.startswith(os.path.expanduser("~")))
        self.assertTrue(yol.endswith(os.path.join(".orkestra", "pyc")))

    def test_bilinmeyen_olay_hook_py_ile_ayni_cikis0_ve_bos_stdout(self):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", ORKESTRA_PYC=tempfile.mkdtemp(prefix="ork_pyc_"))
        r = []
        for betik in ("hook.py", "hook_giris.py"):
            p = subprocess.run([sys.executable, os.path.join(KOK, "scripts", betik), "OlmayanOlay"],
                               input=b"{}", capture_output=True, env=env)
            r.append((p.returncode, p.stdout))
        self.assertEqual(r[0], r[1])
        self.assertEqual(r[0][0], 0)

    def test_pyc_onbellek_dizinine_yazilir(self):
        d = tempfile.mkdtemp(prefix="ork_pyc_")
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", ORKESTRA_PYC=d)
        subprocess.run([sys.executable, GIRIS, "OlmayanOlay"], input=b"{}", capture_output=True, env=env)
        pyc = [f for _, _, fs in os.walk(d) for f in fs if f.startswith("hook.") and f.endswith(".pyc")]
        self.assertTrue(pyc, "hook modülü için .pyc yazılmalı")


if __name__ == "__main__":
    unittest.main()
