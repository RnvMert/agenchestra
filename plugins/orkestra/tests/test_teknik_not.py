"""teknik_not.dogrula: işçi is-bitti teknik not doğrulaması (saf fonksiyon)."""
import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import teknik_not  # noqa: E402

GECERLI = {
    "yaklasim": "Doğrulama saf fonksiyon olarak yazıldı ve ayrı modülde tutuldu.",
    "neden_bu_yol": "Hook ve CLI aynı kuralı paylaşsın diye tek yerde durması gerekiyordu.",
    "alternatifler": [{"secenek": "Hook içinde satır içi doğrulama", "neden_elendi": "Test edilemez ve tekrarlanır."}],
    "entegrasyon": ["is_bitti → teknik_not.dogrula: not şemasını denetler"],
    "riskler": ["Şema genişlerse sınırlar güncellenmeli"],
}


def _kopya(**degisim):
    nesne = copy.deepcopy(GECERLI)
    nesne.update(degisim)
    return nesne


class DogrulaTest(unittest.TestCase):
    def test_gecerli_not_tamam_doner(self):
        self.assertEqual(teknik_not.dogrula(GECERLI), (True, []))

    def test_bos_listeler_gecerli(self):
        tamam, hatalar = teknik_not.dogrula(_kopya(alternatifler=[], entegrasyon=[], riskler=[]))
        self.assertTrue(tamam)
        self.assertEqual(hatalar, [])

    def test_nesne_olmayan_girdi_reddedilir(self):
        for girdi in (None, "metin", ["liste"], 42):
            with self.subTest(girdi=girdi):
                tamam, hatalar = teknik_not.dogrula(girdi)
                self.assertFalse(tamam)
                self.assertEqual(len(hatalar), 1)

    def test_eksik_anahtar_alan_adiyla_bildirilir(self):
        nesne = _kopya()
        del nesne["yaklasim"]
        tamam, hatalar = teknik_not.dogrula(nesne)
        self.assertFalse(tamam)
        self.assertTrue(any(h.startswith("yaklasim") for h in hatalar))

    def test_kisa_metin_reddedilir(self):
        tamam, hatalar = teknik_not.dogrula(_kopya(yaklasim="çok kısa"))
        self.assertFalse(tamam)
        self.assertTrue(any(h.startswith("yaklasim") and "20-400" in h for h in hatalar))

    def test_uzun_metin_reddedilir(self):
        tamam, hatalar = teknik_not.dogrula(_kopya(neden_bu_yol="x" * 401))
        self.assertFalse(tamam)
        self.assertTrue(any(h.startswith("neden_bu_yol") and "20-400" in h for h in hatalar))

    def test_sinir_uzunluklari_kabul_edilir(self):
        for uzunluk in (20, 400):
            with self.subTest(uzunluk=uzunluk):
                tamam, _ = teknik_not.dogrula(_kopya(yaklasim="x" * uzunluk))
                self.assertTrue(tamam)

    def test_liste_olmayan_riskler_reddedilir(self):
        tamam, hatalar = teknik_not.dogrula(_kopya(riskler="liste değil"))
        self.assertFalse(tamam)
        self.assertTrue(any(h.startswith("riskler") and "liste" in h for h in hatalar))

    def test_alternatif_kaydinda_eksik_alan_indeksle_bildirilir(self):
        nesne = _kopya(alternatifler=[
            {"secenek": "iyi", "neden_elendi": "iyi neden"},
            {"secenek": "yalnız seçenek var"},
        ])
        tamam, hatalar = teknik_not.dogrula(nesne)
        self.assertFalse(tamam)
        self.assertIn("alternatifler[1].neden_elendi: dolu metin olmalı", hatalar)
        self.assertFalse(any(h.startswith("alternatifler[0]") for h in hatalar))


if __name__ == "__main__":
    unittest.main()
