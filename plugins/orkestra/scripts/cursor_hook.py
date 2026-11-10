"""Cursor hook adaptörü: Cursor olayını Claude biçimine çevirip hook.py'yi çağırır, çıktıyı Cursor biçimine geri çevirir.

Kullanım (hooks/cursor-hooks.json): cursor_hook.py <cursorOlayAdı>   (stdin: Cursor JSON'u, BOM'lu olabilir)

hook.py değişmez; Cursor'a özgü tüm farklar burada toplanır:
- girdi: BOM, olay adı (camelCase → PascalCase), cwd (workspace_roots), araç adı (Shell → Bash), tool_output → tool_response
- çıktı: hookSpecificOutput → Cursor alanları (additional_context, permission, followup_message)
- salt okuma araçları ve ilgisiz PostToolUse çağrıları hook.py başlatılmadan geçilir (süre tasarrufu)
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cfg  # noqa: E402

OLAY_ESLEME = {
    "sessionStart": "SessionStart", "sessionEnd": "SessionEnd", "beforeSubmitPrompt": "UserPromptSubmit",
    "preToolUse": "PreToolUse", "postToolUse": "PostToolUse", "stop": "Stop",
    "subagentStart": "SubagentStart", "subagentStop": "SubagentStop",
}
ARAC_ESLEME = {"Shell": "Bash", "StrReplace": "Edit", "Delete": "Bash"}
SALT_OKUMA = {"Read", "Grep", "Glob", "LS", "SemanticSearch", "ReadLints", "TodoWrite"}
POST_ILGILI = {"Task", "Skill", "Agent", "Workflow"}


def _kok_dizin():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _yol_duzelt(y):
    """IDE workspace_roots'u başında bölü işaretiyle ('/<sürücü>:/...') verir; Windows yoluna çevirir."""
    if isinstance(y, str) and len(y) > 3 and y[0] == "/" and y[2] == ":":
        y = y[1:]
    return y


def girdi_donustur(cursor_olay, g):
    """Cursor payload'ını Claude hook girdisine çevirir."""
    c = dict(g)
    c.pop("user_email", None)  # kişisel veri: hook.py'ye, kanıta ve günlüklere geçmez
    c["hook_event_name"] = OLAY_ESLEME.get(cursor_olay, cursor_olay)
    kokler = g.get("workspace_roots")
    kokler = kokler if isinstance(kokler, list) else []
    proje = os.environ.get("CURSOR_PROJECT_DIR") or os.environ.get("CLAUDE_PROJECT_DIR") or (
        _yol_duzelt(kokler[0]) if kokler else "")
    if proje and not c.get("cwd"):
        c["cwd"] = proje
    # I-421: Cursor alt ajan türünü `subagent_type`, kimliğini `subagent_id` ile verir (cursor.com/docs/hooks);
    # hook.py rol tespiti (denetçi vb.) Claude'un `agent_type`/`agent_id` alanlarını okur. Araç çağrısı olaylarında
    # Cursor alt ajanı belirten alan göndermez; rol yalnız SubagentStart/SubagentStop'ta bilinir.
    if not c.get("agent_type") and isinstance(g.get("subagent_type"), str) and g.get("subagent_type"):
        c["agent_type"] = g["subagent_type"]
    if not c.get("agent_id") and isinstance(g.get("subagent_id"), str) and g.get("subagent_id"):
        c["agent_id"] = g["subagent_id"]
    ad = g.get("tool_name")
    if ad in ARAC_ESLEME:
        c["tool_name"] = ARAC_ESLEME[ad]
    ti = g.get("tool_input")
    if isinstance(ti, str):
        try:
            c["tool_input"] = json.loads(ti)
        except ValueError:
            c["tool_input"] = {"raw": ti}
    if "tool_output" in g and "tool_response" not in g:
        c["tool_response"] = g["tool_output"]
    return c


def atla(cursor_olay, g):
    """Hook.py'nin hiçbir şey yapmayacağı çağrılar (Claude eklentisindeki matcher'ların karşılığı)."""
    ad = g.get("tool_name")
    if cursor_olay == "preToolUse" and ad in SALT_OKUMA:
        return True
    if cursor_olay == "postToolUse" and ad not in POST_ILGILI:
        return True
    return False


def cikti_donustur(cursor_olay, claude):
    """hook.py çıktısını (Claude JSON'u ya da None) Cursor çıktısına çevirir."""
    if not claude or not isinstance(claude, dict):
        return {}
    ho = claude.get("hookSpecificOutput")
    ho = ho if isinstance(ho, dict) else {}
    ek = ho.get("additionalContext") or claude.get("additional_context")
    if cursor_olay == "sessionStart":
        return {"additional_context": ek} if ek else {}
    if cursor_olay == "beforeSubmitPrompt":
        o = {"continue": claude.get("continue", True)}
        if ek:
            o["additional_context"] = ek
        return o
    if cursor_olay == "preToolUse":
        karar = ho.get("permissionDecision")
        o = {}
        if karar:
            if karar == "ask" and os.environ.get("ORKESTRA_CURSOR_ASK", "deny") == "deny":
                karar = "deny"  # Cursor 'ask' kararını uygulamıyor (019 ölçümü); güvenli taraf: reddet
                neden = (ho.get("permissionDecisionReason") or "") + " (Cursor onay sormaz; kullanıcıya sor, onaylarsa kendisi çalıştırsın.)"
            else:
                neden = ho.get("permissionDecisionReason") or ""
            o["permission"] = karar
            if neden:
                o["user_message"] = neden
                o["agent_message"] = neden
        if ho.get("updatedInput") is not None:
            o["updated_input"] = ho["updatedInput"]
        if ek and "agent_message" not in o:
            o["agent_message"] = ek
        return o
    if cursor_olay == "postToolUse":
        return {"additional_context": ek} if ek else {}
    if cursor_olay == "stop":
        if claude.get("decision") == "block" or ho.get("decision") == "block":
            return {"followup_message": str(claude.get("reason") or ho.get("reason") or "")}
        return {}
    return {}


def komutu_yeniden_yaz(komut, onek):
    """Tırnak dışında, komut konumundaki (başta ya da ; & | ( satırsonu sonrası) çıplak `orkestra` sözcüğünü `onek` ile değiştirir.
    Tırnak içindeki metne, argümanlara ve `xorkestra` gibi sözcüklere dokunmaz."""
    cikti, i, n, tirnak, konum = [], 0, len(komut), None, True
    while i < n:
        c = komut[i]
        if tirnak:
            cikti.append(c)
            if c == "\\" and tirnak == '"' and i + 1 < n:
                cikti.append(komut[i + 1])
                i += 1
            elif c == tirnak:
                tirnak = None
            i += 1
            continue
        if c in "'\"":
            tirnak, konum = c, False
        elif c in ";&|(\n":
            konum = True
        elif not c.isspace():
            if konum and komut.startswith("orkestra", i) and (i + 8 >= n or komut[i + 8].isspace() or komut[i + 8] in ";&|)"):
                cikti.append(onek)
                i += 8
                konum = False
                continue
            konum = False
        cikti.append(c)
        i += 1
    return "".join(cikti)


def cli_onegi():
    """Kabuğa bağımlı olmayan çağrı: PowerShell, cmd ve bash'te aynı çalışır; PATH'te `orkestra` komutu aranmaz."""
    betik = os.path.join(_kok_dizin(), "scripts", "orkestra.py").replace("\\", "/")
    return f'python "{betik}"'


def kabuk_komutu_duzelt(g, cikti):
    """Cursor Shell'inde `orkestra` komutu PATH'te değildir (Claude Code eklenti bin klasörünü yalnız kendi Bash'ine ekler).
    preToolUse'ta komut, eklentinin kendi CLI betiğine açık yolla yeniden yazılır (updated_input, 08.11.2026'da Cursor CLI'de
    tek başına ve permission ile birlikte uygulandığı ölçüldü). Reddedilen komuta dokunulmaz; ORKESTRA_CURSOR_KOMUT_YAZ=0 kapatır."""
    if os.environ.get("ORKESTRA_CURSOR_KOMUT_YAZ") == "0" or g.get("tool_name") != "Shell" or cikti.get("permission") == "deny":
        return cikti
    taban = g.get("tool_input") if isinstance(g.get("tool_input"), dict) else {}
    taban = dict(taban)
    if isinstance(cikti.get("updated_input"), dict):
        taban.update(cikti["updated_input"])
    komut = taban.get("command")
    if not isinstance(komut, str) or "orkestra" not in komut:
        return cikti
    yeni = komutu_yeniden_yaz(komut, cli_onegi())
    if yeni == komut:
        return cikti
    taban["command"] = yeni
    sonuc = dict(cikti)
    sonuc["updated_input"] = taban
    return sonuc


def _hook_py():
    return os.environ.get("ORKESTRA_CURSOR_HOOK_PY") or os.path.join(_kok_dizin(), "scripts", "hook.py")


def _oturum_isareti(sohbet, cursor_olay):
    """Cursor `sessionStart`ı bazen ilk `beforeSubmitPrompt`tan SONRA gönderir (08-10.11.2026 Cursor günlüklerinde 15 sohbetin 5'i).
    Oturum bağlamı (bağlı iş, kurallar yolu) ilk istemde eksik kalmasın diye sohbet başına tek işaret tutulur.
    Dönüş: 'normal' (sıra doğru ya da sohbet kimliği yok), 'onden' (istem sessionStart'tan önce geldi: bağlamı şimdi üret),
    'gec' (sessionStart istemden sonra geldi: bağlam zaten verildi, atla). ORKESTRA_CURSOR_OTURUM_ISARET=0 kapatır."""
    if os.environ.get("ORKESTRA_CURSOR_OTURUM_ISARET") == "0" or not isinstance(sohbet, str) or not sohbet:
        return "normal"
    yol = os.path.join(_tekil_dizin(), "sohbet_" + hashlib.sha1(sohbet.encode("utf-8")).hexdigest()[:20] + ".isaret")
    try:
        os.makedirs(os.path.dirname(yol), exist_ok=True)
        try:
            fd = os.open(yol, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            with open(yol, encoding="utf-8") as f:
                ilk = f.read().strip()
            return "gec" if (cursor_olay == "sessionStart" and ilk == "beforeSubmitPrompt") else "normal"
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(cursor_olay)
    except OSError:
        return "normal"
    return "onden" if cursor_olay == "beforeSubmitPrompt" else "normal"


def _oturum_baglami(g, env):
    """İlk istemde, gelmemiş sessionStart'ın bağlamını hook.py SessionStart ile üretir (hata olursa boş)."""
    try:
        girdi = girdi_donustur("sessionStart", dict(g, hook_event_name="sessionStart"))
        p = subprocess.run([sys.executable, _hook_py(), girdi["hook_event_name"]], input=json.dumps(girdi).encode("utf-8"),
                           capture_output=True, env=env, **cfg.PENCERESIZ)
        claude = json.loads(p.stdout.decode("utf-8", "replace").strip() or "null")
        return cikti_donustur("sessionStart", claude).get("additional_context") or ""
    except (OSError, ValueError, subprocess.SubprocessError):
        return ""


def calistir(cursor_olay, ham):
    """Dönüş: (stdout_metni, çıkış_kodu, stderr_metni)."""
    try:
        g = json.loads(ham.decode("utf-8-sig") or "{}")
    except ValueError:
        return "{}", 0, ""
    if not isinstance(g, dict):  # stop aborted/error olaylarında gövde null/dizi gelebilir
        return "{}", 0, ""
    if atla(cursor_olay, g):
        return "{}", 0, ""
    claude_girdi = girdi_donustur(cursor_olay, g)
    env = dict(os.environ)
    env.setdefault("CLAUDE_PLUGIN_ROOT", _kok_dizin())
    if claude_girdi.get("cwd"):
        env.setdefault("CLAUDE_PROJECT_DIR", claude_girdi["cwd"])
    gec_baglam = ""
    if cursor_olay in ("sessionStart", "beforeSubmitPrompt"):
        durum = _oturum_isareti(g.get("conversation_id"), cursor_olay)
        if durum == "gec":
            return "{}", 0, ""  # bu sohbetin oturum bağlamı ilk istemde zaten verildi
        if durum == "onden":
            gec_baglam = _oturum_baglami(g, env)
    p = subprocess.run([sys.executable, _hook_py(), claude_girdi["hook_event_name"]],
                       input=json.dumps(claude_girdi).encode("utf-8"), capture_output=True, env=env, **cfg.PENCERESIZ)
    cikis = p.stdout.decode("utf-8", "replace").strip()
    try:
        claude = json.loads(cikis) if cikis else None
    except ValueError:
        claude = None
    cikti = cikti_donustur(cursor_olay, claude)
    if gec_baglam:
        ek = cikti.get("additional_context")
        cikti["additional_context"] = gec_baglam + ("\n" + ek if ek else "")
    if cursor_olay == "preToolUse":
        cikti = kabuk_komutu_duzelt(dict(g, tool_input=claude_girdi.get("tool_input")), cikti)  # girdi_donustur dizgiyi sözlüğe çevirmişti
    return json.dumps(cikti, ensure_ascii=False), p.returncode, p.stderr.decode("utf-8", "replace")


TEKIL_BEKLEME_SN = 8.0   # cursor-hooks.json zaman aşımı 10 sn; bekleyen kopya ondan önce bırakır
TEKIL_TAZE_SN = 15.0     # bu süreden eski kilit kardeş değil, aynı yükün yeni olayıdır
TEKIL_OMUR_SN = 600


def _tekil_dizin():
    return os.environ.get("ORKESTRA_CURSOR_TEKIL_DIZIN") or os.path.join(tempfile.gettempdir(), "orkestra_cursor_tekil")


def tekil(cursor_olay, ham, calistir_fn=None):
    """Aynı Cursor olayını birden çok Orkestra kopyası işlemez (tek uçuş).

    Neden: Cursor aynı hook olayını, yüklü her eklenti kopyası için ayrı süreçle paralel çalıştırır. 08.11.2026 ölçümü:
    yerel Cursor kopyası, Claude eklenti önbelleği ve proje hook'u aynı preToolUse'a birlikte yanıt verdi (sessionStart,
    postToolUse, sessionEnd de ikişer kez); hook'lar birbirinin çıktısını görmez ve çakışan updated_input uygulanmadı.
    Kopyalar defteri ve kapıları çift yazıyordu. Aynı yükü alan ilk süreç sahiptir ve hook.py'yi bir kez çalıştırır;
    diğerleri sahibin çıktısını aynen yazar, böylece Cursor hangisinin yanıtını alırsa alsın sonuç aynıdır.
    Bu korumayı taşımayan eski kopyaları etkilemez (doktor onları bayat kopya olarak bildirir). ORKESTRA_CURSOR_TEKIL=0 kapatır."""
    calistir_fn = calistir_fn or calistir
    if os.environ.get("ORKESTRA_CURSOR_TEKIL") == "0":
        return calistir_fn(cursor_olay, ham)
    try:
        g = json.loads(ham.decode("utf-8-sig") or "{}")
    except ValueError:
        g = None
    if not isinstance(g, dict) or atla(cursor_olay, g):
        return calistir_fn(cursor_olay, ham)
    dizin = _tekil_dizin()
    anahtar = hashlib.sha1(cursor_olay.encode("utf-8") + b"\0" + ham).hexdigest()
    kilit, sonuc = os.path.join(dizin, anahtar + ".kilit"), os.path.join(dizin, anahtar + ".json")
    try:
        os.makedirs(dizin, exist_ok=True)
        if _kilit_eski(kilit):  # önceki aynı yükün kalıntısı: yeni olaydır, tekrar sayılmaz
            _sil(sonuc)
            _sil(kilit)
        fd = os.open(kilit, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
        sahip = True
    except FileExistsError:
        sahip = False
    except OSError:
        return calistir_fn(cursor_olay, ham)
    if sahip:
        try:
            _eskileri_temizle(dizin)
            cikti = calistir_fn(cursor_olay, ham)
        except BaseException:
            _sil(kilit)  # bekleyenler kendi başına çalışsın
            raise
        gecici = sonuc + ".%d.tmp" % os.getpid()
        try:
            with open(gecici, "w", encoding="utf-8") as f:
                json.dump(list(cikti), f, ensure_ascii=False)
            os.replace(gecici, sonuc)
        except OSError:
            _sil(gecici)
        return cikti
    bitis = time.monotonic() + TEKIL_BEKLEME_SN
    while time.monotonic() < bitis:
        try:
            with open(sonuc, encoding="utf-8") as f:
                metin, kod, _hata = json.load(f)
            return metin, kod, ""
        except (OSError, ValueError):
            if not os.path.exists(kilit):
                break  # sahip hata ile bıraktı
            time.sleep(0.03)
    return calistir_fn(cursor_olay, ham)  # sahip takıldı ya da öldü: kopya kendi çalışır


def _kilit_eski(kilit):
    """Kardeş kopyalar aynı olaya milisaniyeler içinde gelir; TEKIL_TAZE_SN'den eski kilit aynı yükün yeni bir olayıdır."""
    try:
        return time.time() - os.path.getmtime(kilit) > TEKIL_TAZE_SN
    except OSError:
        return False


def _sil(yol):
    try:
        os.remove(yol)
    except OSError:
        pass


def _eskileri_temizle(dizin):
    sinir = time.time() - TEKIL_OMUR_SN
    try:
        for ad in os.listdir(dizin):
            yol = os.path.join(dizin, ad)
            if os.path.getmtime(yol) < sinir:
                _sil(yol)
    except OSError:
        pass


def main():
    cursor_olay = sys.argv[1] if len(sys.argv) > 1 else ""
    ham = sys.stdin.buffer.read()
    metin, kod, hata = tekil(cursor_olay, ham)
    gunluk = os.environ.get("ORKESTRA_CURSOR_DEBUG")  # tanı: hangi olay geldi, ne döndü (dosya yolu)
    if gunluk:
        try:
            try:
                yeni_komut = (json.loads(metin).get("updated_input") or {}).get("command")  # kısaltılan 'cikti' bunu kesebilir
            except (ValueError, AttributeError):
                yeni_komut = None
            with open(gunluk, "a", encoding="utf-8") as f:
                f.write(json.dumps({"olay": cursor_olay, "kod": kod, "cikti": metin[:300], "yeni_komut": yeni_komut, "hata": hata[-300:],
                                    "kok": os.environ.get("CURSOR_PLUGIN_ROOT"), "cwd": os.getcwd()}, ensure_ascii=False) + "\n")
        except OSError:
            pass
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hata:
        sys.stderr.write(hata)
    sys.stdout.write(metin)
    sys.exit(kod)


if __name__ == "__main__":
    main()
