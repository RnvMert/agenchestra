"""I-433 (ORKESTRA-19, 20): kayıt tutarlılığı.

K1 `jsonl_ekle` kural_ihlal kaydına günlüğün proje kökünü `kok` alanı olarak yazar; başka proje köklü kayıt reddedilir.
K2 `orkestra is ac ... --kart ORKESTRA-1` is.json ve isler.json'a `kart` alanını yazar; geçersiz anahtar reddedilir.
K3 aynı üst klasörde iki iş aynı NNN önekini alamaz: merkez kayıtta (silinmiş worktree / birleşmemiş dal) kullanılan
   numara da dolu sayılır; mevcut klasörlerin adı değişmez.
K4 hook yönergesindeki "Güncel konu" eski niyet kaydı değil, bu mesajdan önceki son kullanıcı mesajıdır.
Hepsi geçici dizinlerde koşar; gerçek proje durumuna dokunmaz.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

TESTS = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(TESTS), "scripts")
sys.path.insert(0, TESTS)
sys.path.insert(0, SCRIPTS)
import ic_kos  # noqa: E402  (CLI'yi süreç içinde koşar)
import is_kaydi  # noqa: E402
import niyet  # noqa: E402
import ork_lib as L  # noqa: E402
from test_hook_yonlendirme import OTURUM, _Ortak  # noqa: E402

ORK = os.path.join(SCRIPTS, "orkestra.py")


def _satirlar(yol):
    with open(yol, encoding="utf-8") as f:
        return [json.loads(s) for s in f if s.strip()]


class K1KuralIhlalKoku(unittest.TestCase):
    def setUp(self):
        self.dis = tempfile.mkdtemp(prefix="ork_i433_k1_")
        self.proje = os.path.join(self.dis, "proje")
        self.baska = os.path.join(self.dis, "baska")
        self.sd = os.path.join(self.proje, ".claude", "orkestra")
        os.makedirs(self.sd)
        os.makedirs(os.path.join(self.baska, ".claude", "orkestra"))
        self.gunluk = os.path.join(self.sd, "gunluk.jsonl")

    def tearDown(self):
        shutil.rmtree(self.dis, ignore_errors=True)

    def test_yeni_kural_ihlal_kok_tasir(self):
        L.jsonl_ekle(self.gunluk, {"zaman": L.simdi(), "tur": "kural_ihlal", "kural": "x"})
        L.jsonl_toplu_ekle(self.gunluk, [{"tur": "kural_ihlal", "kural": "y"}])
        kayitlar = _satirlar(self.gunluk)
        self.assertEqual(len(kayitlar), 2)
        for k in kayitlar:
            self.assertEqual(os.path.normcase(k["kok"]), os.path.normcase(os.path.abspath(self.proje)))

    def test_baska_proje_koklu_kayit_reddedilir(self):
        with self.assertRaises(L.KokUyusmazligi):
            L.jsonl_ekle(self.gunluk, {"tur": "kural_ihlal", "kural": "x", "kok": self.baska})
        with self.assertRaises(L.KokUyusmazligi):
            L.jsonl_toplu_ekle(self.gunluk, [{"tur": "kural_ihlal", "kok": self.baska}])
        self.assertFalse(os.path.exists(self.gunluk))  # hiçbir satır yazılmadı

    def test_ayni_proje_ve_alt_klasor_kabul(self):
        alt = os.path.join(self.proje, ".claude", "worktrees", "oturum1")
        L.jsonl_ekle(self.gunluk, {"tur": "kural_ihlal", "kok": self.proje})
        L.jsonl_ekle(self.gunluk, {"tur": "kural_ihlal", "kok": alt})
        self.assertEqual(len(_satirlar(self.gunluk)), 2)

    def test_diger_turlere_ve_mevcut_satirlara_dokunulmaz(self):
        with open(self.gunluk, "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps({"tur": "kural_ihlal", "kural": "eski"}) + "\n")
        L.jsonl_ekle(self.gunluk, {"tur": "istek", "uzunluk": 3})
        eski, istek = _satirlar(self.gunluk)
        self.assertNotIn("kok", eski)
        self.assertNotIn("kok", istek)

    def test_proje_disi_gunluk_degismez(self):
        yol = os.path.join(self.dis, "serbest.jsonl")
        L.jsonl_ekle(yol, {"tur": "kural_ihlal", "kok": self.baska})
        self.assertEqual(_satirlar(yol)[0]["kok"], self.baska)


class _Cli(unittest.TestCase):
    def setUp(self):
        self.proje = tempfile.mkdtemp(prefix="ork_i433_cli_")
        self.sd = os.path.join(self.proje, ".claude", "orkestra")
        os.makedirs(self.sd)
        self.env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}

    def tearDown(self):
        shutil.rmtree(self.proje, ignore_errors=True)

    def cli(self, *args):
        return ic_kos.kos([ORK, *args], cwd=self.proje, env=self.env)


class K2KartAlani(_Cli):
    def test_kart_alani_dolar(self):
        r = self.cli("is", "ac", "jira isi", "--klasor", "Surec/001-a", "--kart", "ORKESTRA-1")
        self.assertEqual(r.returncode, 0, r.stderr)
        is_id = r.stdout.strip().splitlines()[-1]
        kayit = is_kaydi.is_al(self.sd, is_id)
        self.assertEqual(kayit["kart"], ["ORKESTRA-1"])
        with open(os.path.join(self.sd, "isler.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["isler"][is_id]["kart"], ["ORKESTRA-1"])

    def test_birden_cok_kart_tekrar_ve_virgul(self):
        r = self.cli("is", "ac", "iki kart", "--klasor", "Surec/002-b", "--kart", "orkestra-19,ORKESTRA-20",
                     "--kart", "ORKESTRA-19")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(is_kaydi.is_al(self.sd, r.stdout.strip().splitlines()[-1])["kart"], ["ORKESTRA-19", "ORKESTRA-20"])

    def test_kartsiz_is_alan_tasimaz(self):
        r = self.cli("is", "ac", "kartsiz", "--klasor", "Surec/003-c")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("kart", is_kaydi.is_al(self.sd, r.stdout.strip().splitlines()[-1]))

    def test_gecersiz_kart_reddedilir_klasor_acilmaz(self):
        r = self.cli("is", "ac", "bozuk", "--klasor", "Surec/004-d", "--kart", "orkestra 1")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("geçersiz kart anahtarı", r.stderr + r.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.proje, "Surec", "004-d")))


class K3OnekTekilligi(_Cli):
    def _kayitli_is(self, klasor, baslik="silinmis worktree isi"):
        """Merkezde kayıtlı ama klasörü diskte olmayan iş (silinmiş worktree / birleşmemiş dal)."""
        yol = os.path.join(self.sd, "isler.json")
        veri = {"sayac": 1, "isler": {"I-001": {"klasor": klasor, "baslik": baslik, "durum": "kapandi",
                                                 "olusturma": L.simdi()}}}
        with open(yol, "w", encoding="utf-8") as f:
            json.dump(veri, f)

    def test_silinmis_worktreedeki_numara_dolu(self):
        os.makedirs(os.path.join(self.proje, "Surec", "004-x"))
        self._kayitli_is(os.path.join(self.proje, ".claude", "worktrees", "silindi", "Surec", "005-eski"))
        r = self.cli("is", "ac", "yeni", "--klasor", "Surec/005-yeni")
        self.assertEqual(r.returncode, 0, r.stderr)
        klasor = is_kaydi.is_al(self.sd, r.stdout.strip().splitlines()[-1])["klasor"]
        self.assertTrue(os.path.basename(klasor).startswith("006-"), klasor)
        self.assertTrue(os.path.isdir(os.path.join(self.proje, "Surec", "004-x")))  # mevcut ad değişmedi

    def test_sonraki_numara_merkez_kaydini_sayar(self):
        self._kayitli_is(os.path.join(self.proje, ".claude", "worktrees", "w", "Surec", "009-eski"))
        ad = is_kaydi.klasor_ayir(self.sd, os.path.join(self.proje, "Surec"), "baslik", tarih="20261110")
        self.assertEqual(ad, "010-20261110-baslik")

    def test_iki_is_ayni_onek_almaz(self):
        r1 = self.cli("is", "ac", "bir", "--klasor", "Surec/007-bir")
        r2 = self.cli("is", "ac", "iki", "--klasor", "Surec/007-iki")
        self.assertEqual((r1.returncode, r2.returncode), (0, 0), r1.stderr + r2.stderr)
        k1 = is_kaydi.is_al(self.sd, r1.stdout.strip().splitlines()[-1])["klasor"]
        k2 = is_kaydi.is_al(self.sd, r2.stdout.strip().splitlines()[-1])["klasor"]
        self.assertEqual(os.path.basename(k1), "007-bir")
        self.assertNotEqual(os.path.basename(k2)[:3], "007")

    def test_baska_ust_klasor_etkilemez(self):
        self._kayitli_is(os.path.join(self.proje, "Baska", "005-eski"))
        self.assertEqual(is_kaydi.klasor_ayir(self.sd, os.path.join(self.proje, "Surec"), "x", tercih="005-yeni"),
                         "005-yeni")


class K4GuncelKonu(_Ortak):
    def setUp(self):
        super().setUp()
        self.fatura = self.is_ac("fatura raporlama ekranı", "fatura")
        self.baglan(self.fatura)
        niyet.olay(OTURUM, self.proje, "niyet", ne="eski niyet konusu veritabani yedegi", neden="eski",
                   **{"is": self.fatura["id"]})

    def _konu(self, metin):
        m = self.istek(metin)
        self.assertIn("ZORUNLU", m)
        bas = m.index('Güncel konu: "') + len('Güncel konu: "')
        return m[bas:m.index('"', bas)]

    def test_guncel_konu_son_kullanici_mesaji(self):
        # oturumun ilk mesajı: önceki mesaj yok, kayıtlı niyet gösterilir
        self.assertEqual(self._konu("kuantum gitar akorlarını öğrenmek istiyorum"), "eski niyet konusu veritabani yedegi")
        # ikinci mesaj: güncel konu bir önceki kullanıcı mesajıdır, eski niyet değil
        konu = self._konu("uzay teleskobu lensini parlatmak istiyorum")
        self.assertEqual(konu, "kuantum gitar akorlarını öğrenmek istiyorum")
        self.assertEqual(self._konu("bahçedeki domatesleri sulamak istiyorum"), "uzay teleskobu lensini parlatmak istiyorum")


if __name__ == "__main__":
    unittest.main()
