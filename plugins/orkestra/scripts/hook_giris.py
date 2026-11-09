"""Hook giriş noktası (I-434): bayt kodu önbelleğini açıp hook.py'yi modül olarak çalıştırır.

hook.py betik (`__main__`) olarak çalışınca bayt kodu önbelleğe alınmaz ve her olayda
yeniden derlenir. Burada önbellek dizini (sys.pycache_prefix) ayarlanır, bayt kodu
yazımı açılır ve hook modül olarak içe aktarılır; sonraki olaylar derlenmiş kodu okur.
ORKESTRA_PYC: önbellek dizinini değiştirir; "0" önbelleği kapalı bırakır.
Çıktı ve davranış hook.py ile aynıdır (hook.main()).
"""
import os
import sys


def onbellek_ac():
    yol = os.environ.get("ORKESTRA_PYC", "")
    if yol == "0":
        return None
    if not yol:
        yol = os.path.join(os.path.expanduser("~"), ".orkestra", "pyc")
    sys.pycache_prefix = yol
    sys.dont_write_bytecode = False
    return yol


def calistir():
    onbellek_ac()
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    import hook
    hook.main()


if __name__ == "__main__":
    calistir()
