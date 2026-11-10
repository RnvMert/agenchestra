"""Ajanın kapanış kapılarını atlatması (I-433, Jira ORKESTRA-12): PreToolUse kabuk kapısı.

Ajanın kabuğunda (Bash/PowerShell; ana ve alt ajan) şu komutlar kapı atlatma sayılır:
- `orkestra is kapat … --ozetsiz …`: özet ve ADR kapılarını atlar; yalnız kullanıcı kendi terminalinde kullanır.
- `ORKESTRA_<AD>_KAPISI=0` (ve `off`, `false`, `no`, `hayır`, `kapali` eşdeğerleri) ataması: komut konumunda
  (`X=0 cmd`, `export`, `set`, `env`, `declare -x`) ya da PowerShell `$env:` biçiminde.
Mod `ayarlar/kapi_atlatma.json` (P-028: varsayılan `golge`; proje ezmesi `.claude/orkestra/kapi_atlatma.json`):
golge = uyarı + gunluk.jsonl `kapi_golge`, engel yok; ihlal = ret + `kapi_ret`.
`orkestra is kapat … --yerel-birlesme` ajan kabuğunda moddan bağımsız reddedilir (yeni seçenek, yalnız kullanıcı terminali).
Kapatma: ORKESTRA_KAPI_ATLATMA_KAPISI=0 (kullanıcı ortamı; ajanın ataması kapının kendisine takılır).
Sınır (en iyi çaba): değişkenle kurulan komut, betik dosyası içindeki atama, `os.environ[...]` yakalanmaz.
"""
from __future__ import annotations

import os
import re

KAPI = "kapi_atlatma"

_ORK = r"""(?:[^\s"';&|]*[\\/])?orkestra(?:\.py|\.cmd)?["']?"""
_OZETSIZ = re.compile(_ORK + r"""\s+(?:--\S+\s+)*is\s+kapat\b[^\n;&|]*?\s--ozetsiz(?=[\s=]|$)""", re.I)
_YEREL = re.compile(_ORK + r"""\s+(?:--\S+\s+)*is\s+kapat\b[^\n;&|]*?\s--yerel-birlesme(?=[\s=]|$)""", re.I)
_KAPALI_DEGER = r"""["']?(?:0|off|false|no|hay[ıi]r|kapal[ıi])["']?(?![\w])"""
_ATAMA = re.compile(
    r"""(?:(?:^|[;&|(\n{])\s*(?:(?:export|set|env|declare\s+-x|typeset\s+-x)\s+(?:-\S+\s+)*)?(?:[A-Za-z_]\w*=\S*\s+)*["']?"""
    r"""|\$env:)"""
    r"""(?P<ad>ORKESTRA_[A-Z0-9_]+_KAPISI)["']?\s*=\s*""" + _KAPALI_DEGER, re.I)


def acik() -> bool:
    return os.environ.get("ORKESTRA_KAPI_ATLATMA_KAPISI", "").strip() != "0"


def _govde(komut: str) -> str:
    """Veri heredoc gövdeleri atılmış komut metni (izin politikasıyla aynı)."""
    try:
        import izin_politikasi
        return izin_politikasi.komut_govdesi(komut)
    except Exception:
        return komut or ""


def _tirnaksiz(metin: str) -> str:
    """Tırnaklı argümanlar veridir: içerikleri boşaltılır (program yolundaki tırnak korunur)."""
    yol_acik = re.sub(r'["\']([^"\']*orkestra(?:\.py|\.cmd))["\']', lambda m: m.group(1).replace(" ", "_"), metin)
    return re.sub(r'"(?:\\.|[^"\\])*"|\'[^\']*\'', '""', yol_acik)


def bulgular(komut: str) -> list[str]:
    """Komuttaki kapı atlatma girişimleri (kısa açıklama listesi); yoksa boş."""
    if not komut or ("ozetsiz" not in komut and "KAPISI" not in komut.upper()):
        return []
    govde = _govde(komut)
    out = []
    if _OZETSIZ.search(_tirnaksiz(govde)):
        out.append("`orkestra is kapat --ozetsiz`")
    for m in _ATAMA.finditer(govde):
        ad = m.group("ad").upper()
        if f"{ad}=0" not in out:
            out.append(f"{ad}=0")
    return out


def yerel_birlesme_mi(komut: str) -> bool:
    return bool(komut) and "yerel-birlesme" in komut and bool(_YEREL.search(_tirnaksiz(_govde(komut))))


RET_SONU = ("Kapı yalnız kullanıcı tarafından atlanır: gerekiyorsa kullanıcıya bildir, kullanıcı komutu kendi terminalinde "
            "çalıştırır. Ajan kapının istediğini yapar (özet, ADR, PR) ya da işi açık bırakır.")


def denetle(komut: str, cwd: str | None) -> tuple[str, str]:
    """(karar, ileti): karar 'ret' | 'golge' | ''. Hata kapıyı bozmaz (serbest)."""
    try:
        if yerel_birlesme_mi(komut):
            return "ret", ("`orkestra is kapat --yerel-birlesme` ajan oturumunda kullanılamaz (I-433): commit'in ana dalda "
                           "olduğunu kullanıcı kendi terminalinde doğrulatır. " + RET_SONU)
        if not acik():
            return "", ""
        b = bulgular(komut)
        if not b:
            return "", ""
        import kapi_mod
        neden = "kapı atlatma: " + ", ".join(b)
        yer = cwd or os.getcwd()
        if kapi_mod.mod(KAPI, yer) == "ihlal":
            kapi_mod.ret_kaydet(yer, KAPI, neden)
            return "ret", f"{neden} ajan tarafından kullanılamaz (I-433). " + RET_SONU
        kapi_mod.kaydet(yer, KAPI, neden)
        return "golge", (f"orkestra (gölge, {KAPI}): {neden} ajan tarafından kullanılmamalı; kapıyı yalnız kullanıcı kendi "
                         "terminalinde atlar. İhlal modunda bu komut reddedilir.")
    except Exception:
        return "", ""
