"""ret_nedeni: kök eşlemesi ve hook ret sınıfı (saf fonksiyonlar)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import ret_nedeni  # noqa: E402

BILINEN_KOKLER = {"kart", "basamak", "ortam", "dikkat"}


class KokTest(unittest.TestCase):
    def test_bilinen_nedenler_koke_eslenir(self):
        self.assertEqual(ret_nedeni.kok("kriter-belirsiz"), "kart")
        self.assertEqual(ret_nedeni.kok("ortam"), "ortam")

    def test_none_sayi_ve_bilinmeyen_siniflanmamis_doner(self):
        for deger in (None, 42, "boyle-bir-neden-yok"):
            with self.subTest(deger=deger):
                self.assertEqual(ret_nedeni.kok(deger), "siniflanmamis")


class RetSinifiTest(unittest.TestCase):
    def test_bilinen_kapi_sinifa_eslenir(self):
        self.assertEqual(ret_nedeni.ret_sinifi("K-003"), "R1")

    def test_bosluk_kirpilir(self):
        self.assertEqual(ret_nedeni.ret_sinifi("  P-016 "), "R6")

    def test_none_ve_bilinmeyen_kapi_siniflanmamis_doner(self):
        for deger in (None, "P-999"):
            with self.subTest(deger=deger):
                self.assertEqual(ret_nedeni.ret_sinifi(deger), "siniflanmamis")


class TabloButunluguTest(unittest.TestCase):
    def test_kapi_sinif_degerleri_ret_siniflarinda_tanimli(self):
        for kapi, sinif in ret_nedeni.KAPI_SINIF.items():
            with self.subTest(kapi=kapi):
                self.assertIn(sinif, ret_nedeni.RET_SINIFLARI)

    def test_kok_degerleri_bilinen_sinif_ve_anahtarlar_nedenlerle_ayni(self):
        self.assertTrue(set(ret_nedeni.KOK.values()) <= BILINEN_KOKLER)
        self.assertEqual(set(ret_nedeni.KOK), set(ret_nedeni.NEDENLER))


if __name__ == "__main__":
    unittest.main()
