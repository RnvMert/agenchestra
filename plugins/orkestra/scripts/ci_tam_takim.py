#!/usr/bin/env python3
"""CI tam takım koşusu: test_paralel.py'yi çalıştırır, düşenleri bilinen-hata tabanıyla karşılaştırır.

Neden: tam takımda işletim sistemine bağlı eski hatalar var; hepsi düzelene kadar CI ya hep kırmızı kalır (yeni hata
gürültüde kaybolur) ya da hata yutulur. Bu betik tabanı kilitler (ratchet): taban dışı yeni düşen CI'yı kırar; tabandaki
bir test düzelince de kırar (satırı silmek gerekir), böylece taban yalnız küçülür.

Kullanım: ci_tam_takim.py [--taban DOSYA] [-- test_paralel argümanları]
Taban: satır başına bir pytest düğüm kimliği (`tests/x.py::Sinif::test`); `#` ile başlayan satır ve boş satır yok sayılır.
Varsayılan taban: tests/ci_taban_<linux|windows|macos>.txt. Çıkış: 0 taban dışı fark yok; 1 yeni düşen / eskimiş taban satırı /
koşucu sonuç üretmeden çıktı.
"""
import os
import subprocess
import sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def dusenler(cikti):
    """Koşucu çıktısından `FAILED <düğüm>` ve `ERROR <düğüm>` satırlarının düğüm kimlikleri."""
    sonuc = set()
    for satir in cikti.splitlines():
        for onek in ("FAILED ", "ERROR "):
            if satir.startswith(onek):
                dugum = satir[len(onek):].split(" - ", 1)[0].strip()
                if dugum:
                    sonuc.add(dugum.replace("\\", "/"))
    return sonuc


def taban_oku(yol):
    if not os.path.isfile(yol):
        return set()
    with open(yol, encoding="utf-8") as f:
        return {s.strip().replace("\\", "/") for s in f if s.strip() and not s.lstrip().startswith("#")}


def karsilastir(dusen, taban):
    """(yeni düşenler, tabanda olup artık geçenler) — ikisi de sıralı liste."""
    return sorted(dusen - taban), sorted(taban - dusen)


def varsayilan_taban():
    ad = "windows" if sys.platform.startswith("win") else "macos" if sys.platform == "darwin" else "linux"
    return os.path.join(KOK, "tests", f"ci_taban_{ad}.txt")


def main(argv):
    taban_yolu = varsayilan_taban()
    if "--taban" in argv:
        i = argv.index("--taban")
        taban_yolu = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    argv = [a for a in argv if a != "--"]
    p = subprocess.run([sys.executable, os.path.join(KOK, "scripts", "test_paralel.py")] + argv,
                       cwd=KOK, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                       errors="replace")
    print(p.stdout)
    if "=====" not in p.stdout:
        print("ci_tam_takim: koşucu özet satırı üretmedi (çıkış %d); sonuç yorumlanamaz." % p.returncode)
        return 1
    yeni, duzelen = karsilastir(dusenler(p.stdout), taban_oku(taban_yolu))
    if "zaman aşımı" in p.stdout.lower() and p.returncode not in (0, 1):
        print("ci_tam_takim: koşucu beklenmeyen çıkış verdi (%d)." % p.returncode)
        return 1
    if yeni:
        print("YENİ DÜŞEN (tabanda yok):")
        print("\n".join("  " + d for d in yeni))
    if duzelen:
        print("TABAN ESKİMİŞ (artık geçiyor; %s dosyasından sil):" % os.path.relpath(taban_yolu, KOK))
        print("\n".join("  " + d for d in duzelen))
    if not yeni and not duzelen:
        print("ci_tam_takim: düşenler tabanla aynı (%d bilinen hata)." % len(taban_oku(taban_yolu)))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
