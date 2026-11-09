"""Refleks katmanı (ADR-0149): şema reddi, eşleşme, ezme kısıtı, hata yolu, kırpma ve hook girdisi."""
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BETIK = os.path.join(KOK, "scripts")
sys.path.insert(0, BETIK)
import refleks  # noqa: E402

GECERLI = {"ad": "deneme", "takma": ["dn"], "arguman": ["orkestra", "panel", "servis", "durum"], "salt_okur": True,
           "zaman_asimi": 8, "cikti_siniri": 4000}


def _tamam(stdout=b"merhaba", kod=0):
    return subprocess.CompletedProcess([], kod, stdout, b"")


class Sema(unittest.TestCase):
    def test_gecerli_kayit_gecer(self):
        self.assertEqual(refleks.dogrula(GECERLI), [])

    def test_salt_okur_olmayan_reddedilir(self):
        k = dict(GECERLI, salt_okur=False)
        self.assertTrue(refleks.dogrula(k))
        k.pop("salt_okur")
        self.assertTrue(refleks.dogrula(k))

    def test_izin_listesi_disi_yurutulebilir_reddedilir(self):
        self.assertTrue(refleks.dogrula(dict(GECERLI, arguman=["rm", "-rf", "x"])))

    def test_kabuk_metakarakteri_ve_yer_tutucu_reddedilir(self):
        for kotu in ("a;b", "a|b", "$(x)", "`x`", "a b", "{}", "{ad}", "a&b", "a>b", "a\nb"):
            self.assertTrue(refleks.dogrula(dict(GECERLI, arguman=["orkestra", kotu])), kotu)

    def test_zaman_asimi_ve_cikti_tavani(self):
        self.assertTrue(refleks.dogrula(dict(GECERLI, zaman_asimi=9)))
        self.assertTrue(refleks.dogrula(dict(GECERLI, cikti_siniri=4001)))

    def test_gercek_ayardaki_her_kayit_gecerli(self):
        d = json.load(open(refleks.AYAR, encoding="utf-8"))
        self.assertGreaterEqual(len(d["komutlar"]), 3)
        for k in d["komutlar"]:
            self.assertEqual(refleks.dogrula(k), [], k["ad"])


class Esleme(unittest.TestCase):
    def test_tam_eslesme_takma_ve_buyuk_harf(self):
        self.assertIs(refleks.esles("/ok deneme", "/ok", [GECERLI]), GECERLI)
        self.assertIs(refleks.esles("  /OK DN ", "/ok", [GECERLI]), GECERLI)

    def test_parametre_normal_mesaj_ve_bilinmeyen_eslesmez(self):
        for istem in ("/ok deneme fazla", "/ok", "/ok yok", "merhaba deneme", "ok deneme", "", "/ok deneme\n/ok dn"):
            self.assertIsNone(refleks.esles(istem, "/ok", [GECERLI]), istem)


class Yukleme(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.ayar = os.path.join(self.t.name, "refleks.json")
        self.sd = os.path.join(self.t.name, "sd")
        os.makedirs(self.sd)
        json.dump({"mod": "acik", "on_ek": "/ok", "komutlar": [GECERLI, dict(GECERLI, ad="kotu", salt_okur=False)]},
                  open(self.ayar, "w", encoding="utf-8"))

    def tearDown(self):
        self.t.cleanup()

    def test_gecersiz_kayit_atlanir(self):
        mod, _, k = refleks.yukle(None, self.ayar)
        self.assertEqual((mod, [x["ad"] for x in k]), ("acik", ["deneme"]))

    def test_bozuk_ayar_kapali_sayilir(self):
        open(self.ayar, "w").write("{bozuk")
        self.assertEqual(refleks.yukle(None, self.ayar)[0], "kapali")

    def test_proje_ezmesi_yalniz_kapatir(self):
        ekleme = dict(GECERLI, ad="yeni")
        json.dump({"komutlar": [ekleme], "mod": "acik"}, open(os.path.join(self.sd, "refleks.json"), "w"))
        self.assertEqual([x["ad"] for x in refleks.yukle(self.sd, self.ayar)[2]], ["deneme"])
        json.dump({"kapat": ["deneme"]}, open(os.path.join(self.sd, "refleks.json"), "w"))
        self.assertEqual(refleks.yukle(self.sd, self.ayar)[2], [])
        json.dump({"mod": "kapali"}, open(os.path.join(self.sd, "refleks.json"), "w"))
        self.assertEqual(refleks.yukle(self.sd, self.ayar)[0], "kapali")


class Yurutme(unittest.TestCase):
    def test_zaman_asimi_none_doner(self):
        with mock.patch.object(refleks.subprocess, "run", side_effect=subprocess.TimeoutExpired("x", 8)):
            self.assertIsNone(refleks.calistir(GECERLI))

    def test_hata_kodu_none_doner(self):
        with mock.patch.object(refleks.subprocess, "run", return_value=_tamam(b"cikti", 1)):
            self.assertIsNone(refleks.calistir(GECERLI))

    def test_kabuksuz_ve_arguman_listesiyle_calisir(self):
        with mock.patch.object(refleks.subprocess, "run", return_value=_tamam()) as r:
            self.assertEqual(refleks.calistir(GECERLI), "merhaba")
        self.assertFalse(r.call_args.kwargs["shell"])
        self.assertEqual(r.call_args.args[0][2:], ["panel", "servis", "durum"])
        self.assertLessEqual(r.call_args.kwargs["timeout"], 8)

    def test_gecersiz_kayit_calismaz(self):
        with mock.patch.object(refleks.subprocess, "run") as r:
            self.assertIsNone(refleks.calistir(dict(GECERLI, salt_okur=False)))
        r.assert_not_called()

    def test_cikti_kirpilir(self):
        with mock.patch.object(refleks.subprocess, "run", return_value=_tamam(b"a" * 9000)):
            c = refleks.calistir(GECERLI)
        self.assertLessEqual(len(c), 4000 + 30)
        self.assertTrue(c.endswith("(kırpıldı)"))


class Denetle(unittest.TestCase):
    def test_iz_yazilir_ve_blok_doner(self):
        with tempfile.TemporaryDirectory() as proje:
            sd = os.path.join(proje, ".claude", "orkestra")
            os.makedirs(sd)
            with mock.patch.object(refleks, "calistir", return_value="sonuc"):
                r = refleks.denetle("/ok panel", proje)
            self.assertEqual(r, {"decision": "block", "reason": "sonuc"})
            satir = json.loads(open(os.path.join(sd, "refleks.jsonl"), encoding="utf-8").read().splitlines()[0])
            self.assertEqual(satir["komut"], "panel")
            self.assertIn("ms", satir)

    def test_calistirma_basarisizsa_none(self):
        with mock.patch.object(refleks, "calistir", return_value=None):
            self.assertIsNone(refleks.denetle("/ok panel", None))

    def test_kapatma_bayragi(self):
        with mock.patch.dict(os.environ, {"ORKESTRA_REFLEKS": "0"}), mock.patch.object(refleks, "calistir", return_value="x"):
            self.assertIsNone(refleks.denetle("/ok panel", None))


class HookGirdisi(unittest.TestCase):
    def _kos(self, girdi, env=None):
        e = dict(os.environ, PYTHONUTF8="1")
        e.update(env or {})
        return subprocess.run([sys.executable, os.path.join(BETIK, "refleks_hook.py")], input=girdi, capture_output=True, text=True, env=e, timeout=30)

    def test_on_eksiz_istemde_cikti_bos_kod_sifir(self):
        for g in (json.dumps({"prompt": "merhaba", "cwd": "."}), json.dumps({"prompt": "/ok yok", "cwd": "."}), "{bozuk", ""):
            r = self._kos(g)
            self.assertEqual((r.returncode, r.stdout), (0, ""), g)

    def test_kapatma_bayragi_hook(self):
        r = self._kos(json.dumps({"prompt": "/ok panel", "cwd": "."}), {"ORKESTRA_REFLEKS": "0"})
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_ice_aktarma_zincirinde_hook_py_yok(self):
        kod = ("import sys; sys.path.insert(0, %r); import refleks_hook, refleks; "
               "print('hook' in sys.modules, 'ork_lib' in sys.modules)" % BETIK)
        r = subprocess.run([sys.executable, "-c", kod], capture_output=True, text=True, timeout=30)
        self.assertEqual(r.stdout.strip(), "False False", r.stderr)

    def test_hooks_json_refleks_girdisini_kaydeder(self):
        d = json.load(open(os.path.join(KOK, "hooks", "hooks.json"), encoding="utf-8"))
        komutlar = [h["command"] for g in d["hooks"]["UserPromptSubmit"] for h in g["hooks"]]
        self.assertTrue(any("refleks_hook.py" in c for c in komutlar))
        self.assertTrue(any(("hook_giris.py\" UserPromptSubmit" in c or "hook.py\" UserPromptSubmit" in c) for c in komutlar))


if __name__ == "__main__":
    unittest.main()
