"""Kural özeti: her oturumda yüklenen kural dosyası kısa kalır (I-363). Tam metin JSON ve KURALLAR.md'de durur."""
import os
import re
import sys
import tempfile
import unittest
from unittest import mock

AD = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AD, "..", "scripts"))
import onay  # noqa: E402

TOKEN = re.compile(r"ORKESTRA_[A-Z_]+")
MD_ENCOK_BAYT = 20000  # eklenti kuralları + yükleme satırı; proje kuralları dışında


KAYNAK = os.path.join(AD, "..", "kurallar", "eklenti_kurallari.json")


def setUpModule():
    global _env
    _env = mock.patch.dict(os.environ, {"ORKESTRA_EKLENTI_KURALLARI": KAYNAK})
    _env.start()


def tearDownModule():
    _env.stop()


def ozet_ihlalleri(liste):
    """Yüklenen etkin kurallarda eksik, uzun ya da belirteci kaybeden özetleri döner."""
    out = []
    for r in liste:
        if r.get("durum") != "etkin" or r.get("yukle") == "hook":
            continue
        o = r.get("ozet") or ""
        if not o:
            out.append((r["id"], "eksik"))
        if len(o) > onay.OZET_ENCOK:
            out.append((r["id"], "uzun"))
        out += [(r["id"], t) for t in set(TOKEN.findall(r["metin"])) if t not in o]
    return out


def etkin_yuklenen():
    return [r for r in onay._eklenti_oku() if r.get("durum") == "etkin" and r.get("yukle") != "hook"]


class KuralOzet(unittest.TestCase):
    def test_ozetler_kisa_eksiksiz_ve_belirtec_koruyor(self):
        self.assertEqual(ozet_ihlalleri(onay._eklenti_oku()), [])

    def test_uretilen_md_ozeti_yazar_tam_metni_degil(self):
        with tempfile.TemporaryDirectory() as sd:
            md = onay._kural_dosya_metni(sd)
        r = etkin_yuklenen()[0]
        self.assertIn(r["ozet"].split(".")[0], md)
        self.assertNotIn(r["metin"], md)
        self.assertIn(f"({r['id']}, ", md, "kural_farki sonekini (ID, tarih) korumalı")

    def test_ozetsiz_kural_tam_metinle_yazilir(self):
        kural = {"id": "T-001", "metin": "tam metin", "durum": "etkin", "olusturma": "2026-11-02"}
        with mock.patch.object(onay, "_eklenti_oku", return_value=[kural]), tempfile.TemporaryDirectory() as sd:
            md = onay._kural_dosya_metni(sd)
        self.assertIn("- tam metin (T-001, 2026-11-02)", md)

    def test_ihlal_vakalari_yakalanir(self):
        taban = {"id": "T-002", "metin": "m ORKESTRA_X=0 kapatır", "durum": "etkin"}
        self.assertEqual(ozet_ihlalleri([dict(taban, ozet="x" * (onay.OZET_ENCOK + 1))])[0], ("T-002", "uzun"))
        self.assertIn(("T-002", "eksik"), ozet_ihlalleri([taban]))
        self.assertIn(("T-002", "ORKESTRA_X"), ozet_ihlalleri([dict(taban, ozet="kısa")]))

    def test_uretilen_md_bayt_siniri(self):
        with tempfile.TemporaryDirectory() as sd:
            md = onay._kural_dosya_metni(sd)
        self.assertLessEqual(len(md.encode("utf-8")), MD_ENCOK_BAYT)


class YazimdaOzet(unittest.TestCase):
    """Özet yazım anında belirlenir (I-433: P-061 CLI ile özetsiz eklendi, md'ye tam metin girdi)."""

    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.sd = os.path.join(self.t.name, "proje", ".claude", "orkestra")
        os.makedirs(self.sd)
        self.env = mock.patch.dict(os.environ, {"ORKESTRA_EKLENTI_KURALLARI": os.path.join(self.t.name, "depo.json")})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.t.cleanup()

    def test_uzun_ozetsiz_eklenti_kurali_reddedilir_ozetle_kabul(self):
        uzun = "kural " * 100 + "ORKESTRA_DENEME kapatır."
        with self.assertRaises(ValueError):
            onay.kural_ekle(self.sd, uzun, "", katman="plugin")
        with self.assertRaises(ValueError):  # belirteç kaybolursa
            onay.kural_ekle(self.sd, uzun, "", katman="plugin", ozet="kısa özet")
        r = onay.kural_ekle(self.sd, uzun, "", katman="plugin", ozet="Kısa özet. ORKESTRA_DENEME kapatır.")
        self.assertEqual(ozet_ihlalleri(onay._eklenti_oku()), [])
        self.assertEqual(r["ozet"], "Kısa özet. ORKESTRA_DENEME kapatır.")

    def test_kisa_kural_ozeti_metindir_duzenleme_ozeti_yeniler(self):
        r = onay.kural_ekle(self.sd, "Kısa kural", "", katman="plugin")
        self.assertEqual(r["ozet"], "Kısa kural")
        onay.kural_duzenle(self.sd, r["id"], "Yeni kısa kural")
        self.assertEqual(ozet_ihlalleri(onay._eklenti_oku()), [])
        self.assertEqual(onay._eklenti_oku()[0]["ozet"], "Yeni kısa kural")
        with self.assertRaises(ValueError):
            onay.kural_duzenle(self.sd, r["id"], "uzun " * 100)
        self.assertEqual(onay._eklenti_oku()[0]["metin"], "Yeni kısa kural")

    def test_projeden_tasinan_uzun_kural_ozet_ister(self):
        r = onay.kural_ekle(self.sd, "uzun " * 100, "")
        self.assertNotIn("ozet", r)
        with self.assertRaises(ValueError):
            onay.kural_tasi(self.sd, r["id"], "plugin")
        t = onay.kural_tasi(self.sd, r["id"], "plugin", ozet="Kısa özet")
        self.assertEqual((t["katman"], t["ozet"]), ("plugin", "Kısa özet"))


if __name__ == "__main__":
    unittest.main()
