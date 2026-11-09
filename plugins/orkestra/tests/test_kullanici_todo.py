"""kullanici_todo: ekle/sil/liste, kimlik üretimi ve sınırlar (geçici durum klasörü)."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import kullanici_todo  # noqa: E402


class KullaniciTodoTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.sd = self.tmp.name

    def test_ekle_ardisik_kimlik_verir_ve_liste_ikisini_dondurur(self):
        ilk = kullanici_todo.ekle(self.sd, "ilk madde")
        ikinci = kullanici_todo.ekle(self.sd, "ikinci madde")
        self.assertEqual(ilk["id"], "K1")
        self.assertEqual(ikinci["id"], "K2")
        self.assertEqual([m["id"] for m in kullanici_todo.liste(self.sd)], ["K1", "K2"])

    def test_silinen_kimlik_maksimumun_altindaysa_yeniden_kullanilmaz(self):
        kullanici_todo.ekle(self.sd, "bir")
        kullanici_todo.ekle(self.sd, "iki")
        kullanici_todo.sil(self.sd, "K1")
        yeni = kullanici_todo.ekle(self.sd, "üç")
        self.assertEqual(yeni["id"], "K3")
        self.assertEqual([m["id"] for m in kullanici_todo.liste(self.sd)], ["K2", "K3"])

    def test_sil_olmayan_kimlikte_lookuperror_verir(self):
        with self.assertRaises(LookupError):
            kullanici_todo.sil(self.sd, "K99")

    def test_adet_siniri_asilinca_valueerror_verir(self):
        eski = kullanici_todo.ADET_MAKS
        kullanici_todo.ADET_MAKS = 3
        self.addCleanup(setattr, kullanici_todo, "ADET_MAKS", eski)
        for i in range(3):
            kullanici_todo.ekle(self.sd, f"madde {i}")
        with self.assertRaises(ValueError):
            kullanici_todo.ekle(self.sd, "fazla madde")
        self.assertEqual(len(kullanici_todo.liste(self.sd)), 3)

    def test_bos_metin_valueerror_verir(self):
        with self.assertRaises(ValueError):
            kullanici_todo.ekle(self.sd, "   ")


if __name__ == "__main__":
    unittest.main()
