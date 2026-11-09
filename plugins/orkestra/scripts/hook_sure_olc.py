"""Hook duvar süresi için aralıklı A/B ölçümü (I-434).

Her turda değişkenler sırayla koşulur; böylece makine yükü dalgalanması tüm
değişkenleri aynı ölçüde etkiler. Çıktı: ortanca, p25, p75 (ms) ve mevcut giriş
ile ince giriş arasındaki eşleştirilmiş fark.

Kullanım (plugin kökünden):
    python scripts/hook_sure_olc.py PreToolUse --tur 15
"""
import argparse
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cfg  # noqa: E402

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ORNEK_YUK = {
    "session_id": "olcum-test",
    "hook_event_name": "PreToolUse",
    "tool_name": "Read",
    "tool_input": {"file_path": "x.txt"},
}


def ozet(degerler):
    """Ortanca, p25, p75 (ms)."""
    v = sorted(degerler)
    if not v:
        return {"n": 0, "ortanca": 0.0, "p25": 0.0, "p75": 0.0}
    n = len(v)
    return {"n": n, "ortanca": statistics.median(v), "p25": v[n // 4], "p75": v[(3 * n) // 4]}


def fark_ozeti(a, b):
    """a - b eşleştirilmiş fark (aynı tur sırası); ortanca ve p25."""
    f = [x - y for x, y in zip(a, b)]
    return ozet(f)


def degiskenler(kok, olay, onbellek_dizini):
    """Ad -> (komut, ortam). hook_giris.py yoksa ince giriş değişkenleri atlanır."""
    taban = dict(os.environ)
    taban["CLAUDE_PLUGIN_ROOT"] = kok
    taban["PYTHONDONTWRITEBYTECODE"] = "1"
    onbellekli = dict(taban)  # DONTWRITEBYTECODE açık kalır: hook_giris.py kendisi kapatır
    onbellekli["ORKESTRA_PYC"] = onbellek_dizini
    hook = os.path.join(kok, "scripts", "hook.py")
    giris = os.path.join(kok, "scripts", "hook_giris.py")
    d = {"mevcut": ([sys.executable, hook, olay], taban)}
    if os.path.exists(giris):
        d["ince_giris_onbellekli"] = ([sys.executable, giris, olay], onbellekli)
        kapali = dict(taban)
        kapali["ORKESTRA_PYC"] = "0"  # ayrıştırma: ince giriş, önbellek kapalı
        d["ince_giris_onbellek_kapali"] = ([sys.executable, giris, olay], kapali)
    d["bos_python"] = ([sys.executable, "-c", "pass"], taban)
    return d


def kos(komut, ortam, yuk_baytlari, cwd):
    t = time.perf_counter()
    subprocess.run(komut, env=ortam, input=yuk_baytlari, capture_output=True, cwd=cwd, **cfg.PENCERESIZ)
    return (time.perf_counter() - t) * 1000


def olc(kok, olay, tur, yuk, cwd, onbellek_dizini):
    d = degiskenler(kok, olay, onbellek_dizini)
    yb = json.dumps(yuk).encode("utf-8")
    for ad, (komut, ortam) in d.items():  # ısınma: önbellek yazılsın
        if ad != "bos_python":
            kos(komut, ortam, yb, cwd)
    sonuc = {ad: [] for ad in d}
    for _ in range(tur):
        for ad, (komut, ortam) in d.items():
            sonuc[ad].append(kos(komut, ortam, yb, cwd))
    return sonuc


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("olay", nargs="?", default="PreToolUse")
    ap.add_argument("--tur", type=int, default=15)
    ap.add_argument("--yuk", help="stdin JSON dosyası (varsayılan: örnek yük)")
    ap.add_argument("--cwd", default=os.getcwd())
    ap.add_argument("--json", action="store_true", help="sonucu JSON yaz")
    a = ap.parse_args(argv)
    if a.yuk:
        with open(a.yuk, encoding="utf-8") as f:
            yuk = json.load(f)
    else:
        yuk = dict(ORNEK_YUK, hook_event_name=a.olay, cwd=a.cwd)
    with tempfile.TemporaryDirectory(prefix="ork_pyc_") as pyc:
        s = olc(KOK, a.olay, a.tur, yuk, a.cwd, pyc)
    cikti = {ad: ozet(v) for ad, v in s.items()}
    if "mevcut" in s and "ince_giris_onbellekli" in s:
        cikti["fark_mevcut_eksi_ince"] = fark_ozeti(s["mevcut"], s["ince_giris_onbellekli"])
    if a.json:
        print(json.dumps(cikti, ensure_ascii=False, indent=2))
    else:
        for ad, o in cikti.items():
            print(f"{ad:26s} n={o['n']:3d} ortanca {o['ortanca']:6.0f}  p25 {o['p25']:6.0f}  p75 {o['p75']:6.0f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
