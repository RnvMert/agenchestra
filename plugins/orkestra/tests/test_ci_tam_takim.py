"""ci_tam_takim: koşucu çıktısından düşenleri ayıklama ve tabanla karşılaştırma (saf fonksiyonlar)."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import ci_tam_takim  # noqa: E402

CIKTI = """tests/test_a.py ...
FAILED tests/test_a.py::A::test_bir - AssertionError: 1 != 2
ERROR tests/test_b.py - ImportError: yok
FAILED tests\\test_c.py::test_uc
===== 3 dosya, 2 düşen, 0 süre aşan, 1.0 s (-n 4) =====
"""


class DusenlerTest(unittest.TestCase):
    def test_failed_ve_error_satirlari_dugum_kimligine_indirgenir(self):
        self.assertEqual(
            ci_tam_takim.dusenler(CIKTI),
            {"tests/test_a.py::A::test_bir", "tests/test_b.py", "tests/test_c.py::test_uc"},
        )

    def test_dusen_yoksa_bos_kume(self):
        self.assertEqual(ci_tam_takim.dusenler("tests/test_a.py ...\n===== 1 dosya, 0 düşen ====="), set())


class KarsilastirTest(unittest.TestCase):
    def test_yeni_ve_duzelen_ayri_listelenir(self):
        yeni, duzelen = ci_tam_takim.karsilastir({"a", "b"}, {"b", "c"})
        self.assertEqual(yeni, ["a"])
        self.assertEqual(duzelen, ["c"])

    def test_esit_kume_fark_vermez(self):
        self.assertEqual(ci_tam_takim.karsilastir({"a"}, {"a"}), ([], []))


class TabanOkuTest(unittest.TestCase):
    def test_yorum_bos_satir_ve_ters_egik_cizgi(self):
        with tempfile.TemporaryDirectory() as d:
            yol = os.path.join(d, "taban.txt")
            with open(yol, "w", encoding="utf-8") as f:
                f.write("# yorum\n\ntests\\x.py::T::t\n  tests/y.py::u  \n")
            self.assertEqual(ci_tam_takim.taban_oku(yol), {"tests/x.py::T::t", "tests/y.py::u"})

    def test_olmayan_dosya_bos_taban(self):
        self.assertEqual(ci_tam_takim.taban_oku(os.path.join(tempfile.gettempdir(), "yok_taban_dosyasi.txt")), set())


if __name__ == "__main__":
    unittest.main()
