"""Kayıtlı iş klasörünü silen/taşıyan kabuk komutu uyarısı (I-433, Jira ORKESTRA-20): PreToolUse kabuk kapısı.

Komut `rm`, `rmdir`, `rd`, `del`, `erase`, `unlink`, `Remove-Item`/`ri`, `mv`/`move`/`Move-Item` (yalnız kaynak),
`git worktree remove` ya da `git clean` (kuru koşu `-n` hariç) ile `isler.json`'daki bir işin `klasor` yolunu,
onun üst klasörünü ya da içindeki bir belgeyi hedefliyorsa uyarı üretir: hangi iş, hangi klasör, "iş belgeleri silinir".
Mod `ayarlar/is_klasoru_silme.json` (P-028: varsayılan `golge` = uyarı + gunluk.jsonl `kapi_golge`; `ihlal` = ret).
Proje ezmesi `.claude/orkestra/is_klasoru_silme.json`. Kapatma: ORKESTRA_KLASOR_SILME_KAPISI=0.
Sınır (en iyi çaba, kabuk_kilitli_yazma gibi): değişkenle/dolaylı kurulan yol, betik içi silme yakalanmaz; `cd` yalnız
aynı komuttaki düz `cd <yol>` ile izlenir. İş kaydı yoksa (bağsız proje) sessizdir; proje kökünde kayıtlı iş sayılmaz.
"""
from __future__ import annotations

import os
import re
import shlex

KAPI = "is_klasoru_silme"
GOSTERILEN_EN_COK = 3

_ON = re.compile(r"\b(?:rm|rmdir|rd|del|erase|unlink|Remove-Item|ri|mv|move|Move-Item|worktree|clean)\b", re.I)
_BOL = re.compile(r"&&|\|\||[;|\n]")
_SILEN = {"rm", "rmdir", "rd", "del", "erase", "unlink", "remove-item", "ri"}
_TASIYAN = {"mv", "move", "move-item", "mi"}
_PS_DEGERLI = {"-filter", "-include", "-exclude", "-destination", "-credential", "-stream"}
_GLOB = re.compile(r"[*?\[]")


def acik() -> bool:
    return os.environ.get("ORKESTRA_KLASOR_SILME_KAPISI", "").strip() != "0"


def _parcala(seg: str) -> list[str]:
    try:
        lex = shlex.shlex(seg, posix=False)
        lex.whitespace_split = True
        lex.commenters = ""
        toks = list(lex)
    except ValueError:
        toks = seg.split()
    return [t[1:-1] if len(t) >= 2 and t[0] == t[-1] and t[0] in "\"'" else t for t in toks]


def _yol(p: str, cwd: str) -> str | None:
    """Argümandan mutlak yol; glob varsa glob'dan önceki klasör. Değişkenli yol (`$X`, `%X%`) None."""
    if not p or "$" in p or "%" in p:
        return None
    p = os.path.expanduser(p)
    m = re.match(r"^/([a-zA-Z])(/|$)(.*)", p)
    if os.name == "nt" and m:  # MSYS biçimi (/c/ ile başlayan sürücü yolu)
        p = m.group(1).upper() + ":\\" + m.group(3)
    g = _GLOB.search(p)
    if g:
        p = p[:g.start()]
        p = p if p.endswith(("/", "\\")) else os.path.dirname(p)
        if not p:
            p = "."
    return os.path.abspath(os.path.join(cwd, p))


def _arguman_hedefleri(toks: list[str], tasiyan: bool) -> list[str]:
    args, bitti, atla = [], False, False
    for i, t in enumerate(toks):
        if atla:
            atla = False
            continue
        if bitti:
            args.append(t)
            continue
        if t == "--":
            bitti = True
            continue
        dusuk = t.lower()
        if dusuk in _PS_DEGERLI:
            atla = True
            continue
        if dusuk in ("-path", "-literalpath"):
            continue
        if t.startswith("-") or re.fullmatch(r"/[A-Za-z]", t):
            continue
        args.append(t)
    if tasiyan:
        has_dest = any(t.lower() == "-destination" for t in toks)
        if not has_dest:
            args = args[:-1]
    return args


def hedefler(komut: str, cwd: str) -> list[str]:
    """Komutun sildiği/taşıdığı (kaynak) yolların mutlak biçimleri."""
    if not komut or not _ON.search(komut):
        return []
    out: list[str] = []
    for seg in _BOL.split(komut):
        toks = _parcala(seg.strip().lstrip("({").strip())
        while toks and re.match(r"^[A-Za-z_]\w*=", toks[0]):
            toks = toks[1:]
        if toks and toks[0] in ("sudo", "command", "&"):
            toks = toks[1:]
        if not toks:
            continue
        ad = os.path.basename(toks[0].replace("\\", "/")).lower()
        ad = ad[:-4] if ad.endswith(".exe") else ad
        if ad in ("cd", "set-location", "pushd") and len(toks) > 1:
            y = _yol(toks[1], cwd)
            if y:
                cwd = y
            continue
        if ad == "cmd" and len(toks) > 2 and toks[1].lower() in ("/c", "/k"):
            toks = toks[2:]
            ad = toks[0].lower()
        args: list[str] = []
        if ad in _SILEN:
            args = _arguman_hedefleri(toks[1:], False)
        elif ad in _TASIYAN:
            args = _arguman_hedefleri(toks[1:], True)
        elif ad == "git":
            rest, gcwd = toks[1:], cwd
            while len(rest) >= 2 and rest[0] == "-C":
                gcwd = _yol(rest[1], gcwd) or gcwd
                rest = rest[2:]
            if len(rest) >= 2 and rest[0] == "worktree" and rest[1] == "remove":
                args = [a for a in rest[2:] if not a.startswith("-")]
                cwd_git = gcwd
            elif rest and rest[0] == "clean" and not any(a == "--dry-run" or re.fullmatch(r"-[a-zA-Z]*n[a-zA-Z]*", a)
                                                          for a in rest[1:]):
                yollar = rest[rest.index("--") + 1:] if "--" in rest else [a for a in rest[1:] if not a.startswith("-")]
                args = yollar or ["."]
                cwd_git = gcwd
            else:
                continue
            out += [y for y in (_yol(a, cwd_git) for a in args) if y]
            continue
        else:
            continue
        out += [y for y in (_yol(a, cwd) for a in args) if y]
    return out


def _iliski(hedef: str, klasor: str) -> str | None:
    h, k = os.path.normcase(os.path.normpath(hedef)), os.path.normcase(os.path.normpath(klasor))
    if h == k:
        return "klasörün kendisi"
    if k.startswith(h.rstrip("\\/") + os.sep):
        return "üst klasörü"
    if h.startswith(k + os.sep):
        return "içindeki belge"
    return None


def eslesmeler(sd: str, komut: str, cwd: str, proje: str | None = None) -> list[tuple[str, str, str]]:
    """[(iş kimliği, klasör, ilişki)]; kayıt yoksa ya da eşleşme yoksa boş."""
    hed = hedefler(komut, cwd)
    if not hed:
        return []
    import is_kaydi
    isler = is_kaydi.merkez_isler(sd)
    if not isler:
        return []
    kok = os.path.normcase(os.path.normpath(proje)) if proje else None
    out = []
    for i in is_kaydi.is_sirala(isler):
        klasor = str((isler[i] or {}).get("klasor") or "")
        if not klasor or (kok and os.path.normcase(os.path.normpath(klasor)) == kok):
            continue
        for h in hed:
            r = _iliski(h, klasor)
            if r:
                out.append((i, klasor, r))
                break
    return out


def denetle(sd: str, komut: str, cwd: str | None, proje: str | None = None) -> tuple[str, str]:
    """(karar, ileti): 'ret' | 'golge' | ''. Hata kapıyı bozmaz (serbest)."""
    try:
        if not acik() or not sd:
            return "", ""
        e = eslesmeler(sd, komut, cwd or os.getcwd(), proje)
        if not e:
            return "", ""
        parca = "; ".join(f"{i} ({k}, {r})" for i, k, r in e[:GOSTERILEN_EN_COK])
        if len(e) > GOSTERILEN_EN_COK:
            parca += f"; +{len(e) - GOSTERILEN_EN_COK} iş"
        neden = f"kayıtlı iş klasörü siliniyor/taşınıyor: {parca}"
        ileti = (f"{neden}. İş belgeleri silinir (is.json, mevcut durum, plan, todo, çalışma özeti); iş kaydı yetim kalır. "
                 "Klasör gerçekten gidecekse önce kullanıcıya sor; temizlikte arşive taşı (_arsiv/<proje>/…).")
        import kapi_mod
        yer = proje or cwd or os.getcwd()
        if kapi_mod.mod(KAPI, yer) == "ihlal":
            kapi_mod.ret_kaydet(yer, KAPI, neden)
            return "ret", ileti
        kapi_mod.kaydet(yer, KAPI, neden)
        return "golge", f"orkestra (gölge, {KAPI}): {ileti}"
    except Exception:
        return "", ""
