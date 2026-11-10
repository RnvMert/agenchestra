"""I-433 (ORKESTRA-10, 11, 13): bağsız oturum retleri ve sohbetten doğan boş işler.

K1 proje dışı git worktree'sinde çalışan bağsız oturumda aynı depoya kabuk yazımı engellenmez; başka depo engellenir.
K2 `cd ...` ile başlayan komut/çıktı yapıştırması (soru_sinif 'yapistirma') iş açmaz.
K3 boş, eski, sohbet kaynaklı iş `orkestra bakim --sohbet --kapat --uygula` ile kapanır; elle açılan boş iş kalır.
K4 `orkestra bakim` bağsız oturum retlerini son 14 günde gunluk.jsonl'dan sayar (yalnız ölçüm).
"""
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_bagsiz_kabuk_yazimi import _Kabuk  # noqa: E402
from test_hook_yonlendirme import _Ortak  # noqa: E402
import test_cekirdek as TC  # noqa: E402

import is_kaydi  # noqa: E402
import is_onay  # noqa: E402
import soru_sinif  # noqa: E402

ANA = {"ajan_id": "ana", "ajan_tipi": "ana"}


def _git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


class K1ProjeDisiWorktree(_Kabuk):
    """Proje (durum klasörlü, git dışı) ayrı; oturum proje dışındaki bir deponun bağlı worktree'sinde çalışır."""

    def setUp(self):
        super().setUp()
        self.dis = tempfile.mkdtemp(prefix="ork_i433_")
        self.depo = os.path.join(self.dis, "depo")
        self.agac = os.path.join(self.dis, "depo-wt")
        self.baska = os.path.join(self.dis, "baska")
        for d in (self.depo, self.baska):
            os.makedirs(d)
            _git("init", "-q", cwd=d)
            _git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "ilk", cwd=d)
        _git("worktree", "add", "-q", "--detach", self.agac, cwd=self.depo)

    def tearDown(self):
        shutil.rmtree(self.dis, ignore_errors=True)
        super().tearDown()

    def yaz(self, hedef):
        return self.kabuk(f"echo x > {hedef.replace(os.sep, '/')}", cwd=self.agac)

    def test_ortak_dizin_ayni_depo(self):
        self.assertEqual(is_onay.git_ortak_dizin(os.path.join(self.agac, "yeni", "a.txt")),
                         is_onay.git_ortak_dizin(self.depo))
        self.assertNotEqual(is_onay.git_ortak_dizin(self.agac), is_onay.git_ortak_dizin(self.baska))
        self.assertIsNone(is_onay.git_ortak_dizin(self.proje))

    def test_ayni_depo_worktree_yazimi_engellenmez(self):
        self.kok_kurulum_dogrula()
        self.assertFalse(self.yaz(os.path.join(self.agac, "a.txt"))[0])
        self.assertFalse(self.yaz(os.path.join(self.depo, "b.txt"))[0])  # aynı deponun ana ağacı

    def test_baska_depo_engellenir(self):
        self.kok_kurulum_dogrula()
        deny, neden = self.yaz(os.path.join(self.baska, "c.txt"))
        self.assertTrue(deny)
        self.assertIn("kabuk komutu", neden)

    def test_proje_ici_hedef_hala_engellenir(self):
        self.assertTrue(self.yaz(self.kod())[0])

    def test_proje_icinden_calisan_oturum_degismez(self):
        self.assertTrue(self.kabuk(f"echo x > {os.path.join(self.agac, 'a.txt').replace(os.sep, '/')}")[0])


class K2Yapistirma(_Ortak):
    def idler(self):
        return {g["id"] for g in is_kaydi.is_liste(self.sd, "acik")}

    def test_sinif(self):
        for m in ("cd plugins/orkestra && python -m pytest -q", "PS C:\\Mert> git status\nOn branch main",
                  "$ ls -la", "Traceback (most recent call last):\n  File \"x.py\""):
            with self.subTest(m=m):
                self.assertEqual(soru_sinif.tur(m), "yapistirma")
                self.assertEqual(soru_sinif.bagli_tur(m), "devam")
        self.assertEqual(soru_sinif.tur("Şunu düzeltelim"), "is")
        self.assertEqual(soru_sinif.tur("# Başlık: raporu güncelleyelim"), "is")

    def test_cd_yapistirmasi_is_acmaz(self):
        once = self.idler()
        self.istek("cd C:/Mert/McD && orkestra is liste\nI-001 açık iş düzeltelim")
        self.assertEqual(self.idler(), once)
        self.assertFalse(self.oturum_json().get("is"))

    def test_is_istegi_acar_ve_sohbet_kaynagi_yazilir(self):
        once = self.idler()
        self.istek("Şunu düzeltelim")
        yeni = self.idler() - once
        self.assertEqual(len(yeni), 1)
        self.assertEqual(is_kaydi.is_al(self.sd, yeni.pop()).get("kaynak"), "sohbet")


class K3K4Bakim(unittest.TestCase):
    setUp = TC.Cekirdek.setUp
    tearDown = TC.Cekirdek.tearDown
    cli = TC.Cekirdek.cli

    def bakim(self, *args):
        r = self.cli("bakim", "--json", *args, **ANA)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return json.loads(r.stdout)

    def is_ac(self, ad, kaynak=None, eski_saat=72):
        klasor = os.path.join(self.proje, "isler", ad)
        k = is_kaydi.is_ac(self.sd, "İş " + ad, klasor)
        if kaynak:
            is_kaydi._degistir(self.sd, k["id"], lambda x: x.__setitem__("kaynak", kaynak))
        merkez = os.path.join(self.sd, "isler.json")
        with open(merkez, encoding="utf-8") as f:
            d = json.load(f)
        d["isler"][k["id"]]["olusturma"] = (datetime.datetime.now().astimezone()
                                           - datetime.timedelta(hours=eski_saat)).isoformat(timespec="seconds")
        with open(merkez, "w", encoding="utf-8") as f:
            json.dump(d, f)
        return k["id"]

    def durum(self, i):
        with open(os.path.join(self.sd, "isler.json"), encoding="utf-8") as f:
            return json.load(f)["isler"][i]["durum"]

    def test_k3_sohbet_kaynakli_bos_is_kapanir_elle_acilan_kalir(self):
        sohbet = self.is_ac("001-sohbet", kaynak="sohbet")
        eski = self.is_ac("002-eski-kayit")  # kaynak alanı yok; atif.jsonl ilk bağlanması hook
        elle = self.is_ac("003-elle")
        taze = self.is_ac("004-taze", kaynak="sohbet", eski_saat=1)
        with open(os.path.join(self.sd, "atif.jsonl"), "w", encoding="utf-8") as f:
            f.write(json.dumps({"zaman": "2026-11-01T10:00:00+03:00", "is": eski, "kaynak": "hook-otomatik-baglama"}) + "\n")
            f.write(json.dumps({"zaman": "2026-11-01T10:00:00+03:00", "is": elle, "kaynak": "cli-is-baglama"}) + "\n")
        kuru = self.bakim("--sohbet", "--bos-saat", "48")
        self.assertEqual(sorted(g["id"] for g in kuru["bos_isler"]), sorted([sohbet, eski]))
        r = self.bakim("--uygula", "--kapat", "--sohbet", "--bos-saat", "48")
        self.assertEqual(sorted(r["kapatilan_is"]), sorted([sohbet, eski]))
        self.assertEqual([self.durum(i) for i in (sohbet, eski, elle, taze)], ["kapandi", "kapandi", "acik", "acik"])

    def test_k4_son_14_gun_bagsiz_retleri_sayilir(self):
        simdi = datetime.datetime.now().astimezone()
        satirlar = [
            {"zaman": simdi.isoformat(timespec="seconds"), "tur": "kapi_golge", "kapi": "bagsiz_otomatik_bagla"},
            {"zaman": (simdi - datetime.timedelta(days=3)).isoformat(timespec="seconds"), "tur": "kapi_golge",
             "kapi": "bagsiz_otomatik_bagla"},
            {"zaman": (simdi - datetime.timedelta(days=2)).isoformat(timespec="seconds"), "tur": "kapi_ret", "kapi": "bagsiz_kabuk"},
            {"zaman": (simdi - datetime.timedelta(days=30)).isoformat(timespec="seconds"), "tur": "kapi_ret", "kapi": "bagsiz_kabuk"},
            {"zaman": simdi.isoformat(timespec="seconds"), "tur": "kapi_golge", "kapi": "baska_kapi"},
        ]
        os.makedirs(self.sd, exist_ok=True)
        with open(os.path.join(self.sd, "gunluk.jsonl"), "a", encoding="utf-8") as f:
            f.writelines(json.dumps(s) + "\n" for s in satirlar)
        b = self.bakim()["bagsiz_olcum"]
        self.assertEqual((b["gun"], b["otomatik_bagla_golge"], b["kabuk_ret"]), (14, 2, 1))
        r = self.cli("bakim", **ANA)
        self.assertIn("bağsız oturum retleri (son 14 gün", r.stdout)
        self.assertIn("otomatik bağlama gölge 2", r.stdout)


if __name__ == "__main__":
    unittest.main()
