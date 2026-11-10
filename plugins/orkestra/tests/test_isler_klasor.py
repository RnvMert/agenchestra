"""I-435 P2 (S2): `is ac` iş klasörünü oturum kökünden türetir.

`--klasor` isteğe bağlıdır: verilmezse oturum kökü altında sıradaki NNN-tarih-slug açılır; worktree oturumunda kök
dışı `--klasor` reddedilmez, kök altına çevrilir; `..` ile kaçış kök dışına çıkamaz. Her test tempfile altında kendi
git deposunu kurar; CLI `ic_kos` ile süreç içinde koşar.
`python -m pytest plugins/orkestra/tests/test_isler_klasor.py`
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI = os.path.join(KOK, "scripts", "orkestra.py")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(KOK, "scripts"))
import ic_kos  # noqa: E402
import ork_lib as L  # noqa: E402

_TEMIZ = ("CLAUDE_PROJECT_DIR", L.DURUM_YEREL_ORTAM, "ORKESTRA_IS_KLASOR_KOK")
_NNN = re.compile(r"^\d{3}-\d{8}-")


def git(cwd, *args):
    r = subprocess.run(["git", "-C", cwd] + list(args), capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        raise AssertionError(f"git {' '.join(args)}: {r.stderr or r.stdout}")
    return r.stdout


def n(yol):
    return os.path.normcase(os.path.realpath(yol)).replace("\\", "/").rstrip("/")


def altinda(yol, kok):
    return (n(yol) + "/").startswith(n(kok) + "/") and n(yol) != n(kok)


class IsAcKlasorTuretme(unittest.TestCase):
    def setUp(self):
        self.taban = os.path.realpath(tempfile.mkdtemp(prefix="ork_iak_"))
        self.ana = os.path.join(self.taban, "depo")
        os.makedirs(os.path.join(self.ana, ".claude", "orkestra"))
        git(self.ana, "init", "-q", "-b", "main")
        git(self.ana, "config", "user.name", "Test")
        git(self.ana, "config", "user.email", "test@example.invalid")
        with open(os.path.join(self.ana, ".gitignore"), "w", encoding="utf-8", newline="\n") as f:
            f.write(".claude/orkestra/\n.claude/worktrees/\n")
        with open(os.path.join(self.ana, "a.txt"), "w", encoding="utf-8", newline="\n") as f:
            f.write("bir\n")
        git(self.ana, "add", ".")
        git(self.ana, "commit", "-q", "-m", "ilk")
        self.wt = os.path.join(self.ana, ".claude", "worktrees", "oturum-ef34ab")
        git(self.ana, "worktree", "add", "-q", "-b", "claude/oturum-ef34ab", self.wt)
        shutil.copytree(os.path.join(self.ana, ".claude", "orkestra"), os.path.join(self.wt, ".claude", "orkestra"))

    def tearDown(self):
        subprocess.run(["git", "-C", self.ana, "worktree", "remove", "--force", self.wt], capture_output=True)
        shutil.rmtree(self.taban, ignore_errors=True)

    def kos(self, args, cwd, env_ek=None):
        env = dict(os.environ, CLAUDE_CODE_SESSION_ID="iak-oturum", PYTHONUTF8="1")
        for k in _TEMIZ:
            env.pop(k, None)
        env.update(env_ek or {})
        return ic_kos.kos([CLI] + list(args), cwd=cwd, env=env)

    def is_klasoru(self, r):
        self.assertEqual(r.returncode, 0, r.stderr)
        is_id = r.stdout.strip().splitlines()[-1]
        sd = os.path.join(self.ana, ".claude", "orkestra")
        with open(os.path.join(sd, "isler.json"), encoding="utf-8") as f:
            veri = json.load(f)
        isler = veri.get("isler", veri) if isinstance(veri, dict) else veri
        kayit = isler[is_id] if isinstance(isler, dict) else next(i for i in isler if i.get("id") == is_id)
        return kayit["klasor"]

    # ------------------------------------------------------------------ K1
    def test_klasorsuz_is_ac_worktree_oturum_koku_altinda(self):
        r = self.kos(["is", "ac", "Başlık"], self.wt)
        klasor = self.is_klasoru(r)
        self.assertEqual(n(os.path.dirname(klasor)), n(self.wt))
        self.assertRegex(os.path.basename(klasor), _NNN)
        self.assertTrue(os.path.isdir(klasor))
        self.assertIn("iş klasörü:", r.stderr)

    def test_klasorsuz_is_ac_ana_agacta_proje_koku_altinda(self):
        r = self.kos(["is", "ac", "Başlık"], self.ana)
        klasor = self.is_klasoru(r)
        self.assertEqual(n(os.path.dirname(klasor)), n(self.ana))
        self.assertRegex(os.path.basename(klasor), _NNN)

    def test_ardisik_klasorsuz_isler_sirali_numara_alir(self):
        a = os.path.basename(self.is_klasoru(self.kos(["is", "ac", "Birinci"], self.wt)))
        b = os.path.basename(self.is_klasoru(self.kos(["is", "ac", "İkinci"], self.wt)))
        self.assertLess(a[:3], b[:3])

    # ------------------------------------------------------------------ K1b eşleme (baglam.json)
    def esleme_yaz(self, projeler):
        with open(os.path.join(self.ana, ".claude", "orkestra", "baglam.json"), "w", encoding="utf-8") as f:
            json.dump({"surum": 1, "projeler": projeler, "surec_deseni": r"^\d{2}_", "gorev_deseni": r"^\d{3}-",
                       "haric": ["98_calisma"]}, f)

    def test_eslemede_is_yoksa_ilk_proje_altinda(self):
        self.esleme_yaz(["RNV", "Claude_Orkestrasyon"])
        klasor = self.is_klasoru(self.kos(["is", "ac", "Başlık"], self.wt))
        self.assertEqual(n(os.path.dirname(klasor)), n(os.path.join(self.wt, "RNV")))
        self.assertRegex(os.path.basename(klasor), _NNN)

    def test_eslemede_son_isin_ust_klasoru_kullanilir(self):
        self.esleme_yaz(["RNV", "Claude_Orkestrasyon"])
        ilk = os.path.join(self.wt, "Claude_Orkestrasyon", "200-20261110-onceki")
        self.assertEqual(n(self.is_klasoru(self.kos(["is", "ac", "Önceki", "--klasor", ilk], self.wt))), n(ilk))
        klasor = self.is_klasoru(self.kos(["is", "ac", "Sonraki"], self.wt))
        self.assertEqual(n(os.path.dirname(klasor)), n(os.path.join(self.wt, "Claude_Orkestrasyon")))
        self.assertRegex(os.path.basename(klasor), r"^201-")

    def test_eslemede_ana_agactaki_is_oturum_kokune_tasinir(self):
        self.esleme_yaz(["RNV"])
        ilk = os.path.join(self.ana, "RNV", "01_surec", "010-20261110-ana")
        self.is_klasoru(self.kos(["is", "ac", "Ana", "--klasor", ilk], self.ana))
        klasor = self.is_klasoru(self.kos(["is", "ac", "Oturum"], self.wt))
        self.assertEqual(n(os.path.dirname(klasor)), n(os.path.join(self.wt, "RNV", "01_surec")))

    def test_eslenmemis_ya_da_haric_klasordeki_is_yok_sayilir(self):
        self.esleme_yaz(["RNV"])
        for yol in (os.path.join(self.wt, "Baska", "001-20261110-x"),
                    os.path.join(self.wt, "RNV", "98_calisma", "002-20261110-y")):
            self.is_klasoru(self.kos(["is", "ac", "X", "--klasor", yol], self.wt))
        klasor = self.is_klasoru(self.kos(["is", "ac", "Yeni"], self.wt))
        self.assertEqual(n(os.path.dirname(klasor)), n(os.path.join(self.wt, "RNV")))

    # ------------------------------------------------------------------ K2
    def test_kok_disi_klasor_kok_altina_cevrilir(self):
        dis = os.path.join(self.ana, "Claude_Orkestrasyon", "002-20261110-dis")
        r = self.kos(["is", "ac", "Dış", "--klasor", dis], self.wt)
        klasor = self.is_klasoru(r)
        self.assertEqual(n(klasor), n(os.path.join(self.wt, "Claude_Orkestrasyon", "002-20261110-dis")))
        self.assertFalse(os.path.exists(dis))
        self.assertIn("oturum kökü altına çevrildi", r.stderr)
        self.assertNotIn("oturum kökü dışında:", r.stderr)  # eski ret iletisi yok

    def test_proje_disi_klasor_son_bileseniyle_kok_altina(self):
        dis = os.path.join(self.taban, "baska_yer", "003-20261110-uzak")
        r = self.kos(["is", "ac", "Uzak", "--klasor", dis], self.wt)
        klasor = self.is_klasoru(r)
        self.assertEqual(n(klasor), n(os.path.join(self.wt, "003-20261110-uzak")))
        self.assertFalse(os.path.exists(dis))

    def test_kok_icindeki_klasor_degismez(self):
        ic = os.path.join(self.wt, "Claude_Orkestrasyon", "004-20261110-ic")
        r = self.kos(["is", "ac", "İç", "--klasor", ic], self.wt)
        self.assertEqual(n(self.is_klasoru(r)), n(ic))
        self.assertNotIn("çevrildi", r.stderr)

    def test_ortamla_cevirme_kapanir(self):
        dis = os.path.join(self.ana, "Claude_Orkestrasyon", "005-20261110-dis")
        r = self.kos(["is", "ac", "Dış", "--klasor", dis], self.wt, {"ORKESTRA_IS_KLASOR_KOK": "0"})
        self.assertEqual(n(self.is_klasoru(r)), n(dis))

    # ------------------------------------------------------------------ K3
    def test_noktali_kacis_kok_disina_cikamaz(self):
        for i, yol in enumerate(("../../006-20261110-kacis", os.path.join(self.wt, "..", "..", "..", "007-20261110-kacis"),
                                 os.path.join(self.wt, "Claude_Orkestrasyon", "..", "..", "..", "008-20261110-kacis"))):
            with self.subTest(yol=yol):
                r = self.kos(["is", "ac", f"Kaçış {i}", "--klasor", yol], self.wt)
                klasor = self.is_klasoru(r)
                self.assertTrue(altinda(klasor, self.wt), klasor)
                self.assertNotIn("..", os.path.relpath(klasor, self.wt).split(os.sep))

    def test_kokun_kendisine_cevrilen_yol_sirali_klasor_alir(self):
        r = self.kos(["is", "ac", "Kök", "--klasor", os.path.join(self.ana, ".claude", "worktrees", "oturum-ef34ab", "..")],
                     self.wt)
        klasor = self.is_klasoru(r)
        self.assertEqual(n(os.path.dirname(klasor)), n(self.wt))
        self.assertRegex(os.path.basename(klasor), _NNN)


if __name__ == "__main__":
    unittest.main()
