"""Ö3/Ö4 (I-020): okunacak belgelerde K-005 yazım anı kapısı ve K-003 Stop bağlantı kapısı, gölge ve ihlal modu.

Saf kurallar belge_bicim.py'de; kancalar geçici projede koşar (gerçek durum dizinine yazılmaz).
"""
import json
import os
import sys
import unittest
from unittest import mock

import test_cekirdek as TC

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(KOK, "scripts"))
import belge_bicim as BB  # noqa: E402

AYAR = BB.ayar_oku(None)

TEMIZ = """# Başlık

## Amaç

Kısa bir amaç cümlesi.

## Kararlar

- Birinci karar.
- İkinci karar.

**Neden:**

Tek etiket ayrı paragrafta.
"""

# 3. satır: iki etiket tek paragrafta; 5. satır: satır içi liste
IHLALLI = """# Başlık

**Amaç:** a **Neden:** b

Şunlar yapılacak: (a) bir, (b) iki, (c) üç.
"""


class Kurallar(unittest.TestCase):
    def tara(self, metin, ad="plan.md"):
        return BB.yazim_ihlalleri(metin, ad, AYAR)

    def test_temiz_metin_ihlalsiz(self):
        self.assertEqual(self.tara(TEMIZ), [])

    def test_coklu_etiket_ve_sikisik_liste_satir_numarasiyla(self):
        ih = self.tara(IHLALLI)
        self.assertEqual([(i["satir"], i["kural"]) for i in ih], [(3, "coklu_etiket"), (5, "sikisik_liste")])

    def test_noktalivirgul_ve_nokta_isareti_listesi(self):
        self.assertEqual(self.tara("a; b; c; d\n")[0]["kural"], "sikisik_liste")
        self.assertEqual(self.tara("x · y · z\n")[0]["kural"], "sikisik_liste")
        self.assertEqual(self.tara("tek; noktalı; virgül\n"), [])

    def test_uzun_paragraf_ve_todo_madde_siniri(self):
        uzun = "kelime " * 50  # 350 karakter
        self.assertEqual(self.tara(uzun)[0]["kural"], "uzun_paragraf")
        madde = "- " + "kelime " * 35  # ~245 karakter: paragraf sınırı altında, todo sınırı üstünde
        self.assertEqual(self.tara(madde, "plan.md"), [])
        self.assertEqual(self.tara(madde, "todo.md")[0]["kural"], "uzun_todo_madde")

    def test_kod_tablo_baslik_given_when_then_yok_sayilir(self):
        metin = ("## a; b; c\n\n| x ; y ; z | **A:** **B:** |\n|---|---|\n\n```\n**A:** **B:** a; b; c\n```\n\n"
                 "Given bir; When iki; Then üç; And dört\n")
        self.assertEqual(self.tara(metin), [])

    def test_satir_ici_kod_ve_baglanti_hedefi_sayilmaz(self):
        self.assertEqual(self.tara("Örnek `a; b; c` ve [x](<yol; ile; noktalı.md>) bağlantı.\n"), [])

    def test_bastirma_isareti(self):
        self.assertEqual(self.tara("a; b; c; d <!-- biçim-tamam -->\n"), [])

    def test_belge_adi_kalibi(self):
        k = AYAR["yazim_kapisi"]
        for ad in ("plan.md", "todo.md", "bulgu.md", "jira_onerisi.md", "rapor.md", "calisma_ozeti_20261016.md",
                   "a/b/rapor_20261016.md"):
            self.assertTrue(BB.belge_mi(ad, k), ad)
        for ad in ("README.md", "devir_ozeti.md", "plan.py", "planlama_notu.md", "sablonlar/plan.md",
                   ".claude/rules/orkestra_kurallari.md", "KURALLAR.md"):
            self.assertFalse(BB.belge_mi(ad, k), ad)

    def test_baglantisiz_belgeler(self):
        yol = os.path.join("C:\\", "p", "is1", "rapor.md")
        diger = os.path.join("C:\\", "p", "kod.py")
        self.assertEqual(BB.baglantisiz_belgeler([yol, diger], "bitti", AYAR), [yol.replace("\\", "/")])
        self.assertEqual(BB.baglantisiz_belgeler([yol], "rapor: [rapor.md](is1/rapor.md)", AYAR), [])
        self.assertEqual(BB.baglantisiz_belgeler([yol], "rapor: [r](<is 1/rapor.md>)", AYAR), [])
        self.assertEqual(BB.baglantisiz_belgeler([yol], "yalnız ad: rapor.md", AYAR), [yol.replace("\\", "/")])
        self.assertEqual(BB.baglantisiz_belgeler([yol, yol], "x", AYAR), [yol.replace("\\", "/")])  # tekrar yok

    # --- I-224 P9 (a): çok satırlı HTML yorumunun devam satırları sayılmaz
    def test_cok_satirli_yorum_icerigi_sayilmaz(self):
        metin = ("# B\n\n<!-- doldur: her satır ayrı:\n**A:** a **B:** b\nx · y · z ve a; b; c; d\n" + "kelime " * 50
                 + "\n-->\n\nTemiz paragraf.\n")
        self.assertEqual(self.tara(metin), [])
        # yorum kapandıktan sonraki ihlal yine yakalanır; satır numarası metnin kendisine göredir
        self.assertEqual([(i["satir"], i["kural"]) for i in self.tara("<!-- a\nb -->\n**A:** a **B:** b\n")],
                         [(3, "coklu_etiket")])
        # yorumdan önceki metin sayılır, yorum içi sayılmaz
        self.assertEqual([i["kural"] for i in self.tara("a; b; c; d <!-- not\n**A:** **B:**\n-->\n")], ["sikisik_liste"])
        self.assertEqual(self.tara("Metin <!-- a; b; c; d --> sonu.\n"), [])

    def test_yorum_icindeki_kod_citi_durumu_bozmaz(self):
        metin = "<!-- örnek:\n```markdown\n**A:** a **B:** b\n```\nson -->\n\n**A:** x **B:** y\n"
        self.assertEqual([(i["satir"], i["kural"]) for i in self.tara(metin)], [(7, "coklu_etiket")])

    def test_ozet_tum_ihlalleri_satir_satir_verir(self):
        """K2 (S1): 4 ihlalli metinde ileti 4 satır; her satırda satır numarası, kural ve ayrıntı."""
        metin = "**A:** a **B:** b\n\nx; y; z; w\n\n" + "kelime " * 50 + "\n\n**C:** c **D:** d\n"
        ih = self.tara(metin)
        self.assertEqual(len(ih), 4)
        ileti = BB.ozet_satiri("plan.md", ih)
        satirlar = ileti.split("\n")
        self.assertEqual(len(satirlar), 4)
        for s, i in zip(satirlar, ih):
            self.assertIn(f"satır {i['satir']} {i['kural']}: {i['ayrinti']}", s)
        self.assertTrue(satirlar[0].startswith("Orkestra biçim (K-005, gölge): plan.md, 4 ihlal: satır 1 coklu_etiket"))

    def test_ozet_en_cok_15_satir(self):
        ih = [{"satir": n, "kural": "uzun_paragraf", "ayrinti": "kısalt"} for n in range(1, 21)]
        satirlar = BB.ozet_satiri("plan.md", ih).split("\n")
        self.assertEqual(len(satirlar), 15)
        self.assertTrue(satirlar[-1].endswith("(+5 ihlal daha)"))

    def test_bozuk_ayar_varsayilana_duser(self):
        d = BB.ayar_oku("/yok/olan/dizin")
        self.assertEqual(BB.mod(d, "yazim_kapisi"), "ihlal")  # eklentinin gönderdiği ayar: ihlal (18.10.2026)
        self.assertEqual(BB.mod({"yazim_kapisi": {"mod": "saçma"}}, "yazim_kapisi"), "golge")


class GuvenliDuzelt(unittest.TestCase):
    """I-224 P9 (b): yalnız anlamı değiştirmeyen dönüşümler; hepsi ya da hiçbiri; idempotent."""

    def duz(self, metin, ad="plan.md"):
        yeni, uyg = BB.guvenli_duzelt(metin, ad, AYAR)
        self.assertEqual(BB.guvenli_duzelt(yeni, ad, AYAR), (yeni, []), "idempotent değil")
        return yeni, [u["donusum"] for u in uyg]

    def test_etiket_ayirma(self):
        yeni, d = self.duz("# B\n\n**Amaç:** a **Neden:** b `**X:** y`\n")
        self.assertEqual(yeni, "# B\n\n**Amaç:** a\n\n**Neden:** b `**X:** y`\n")
        self.assertEqual(d, ["etiket_ayir"])
        self.assertEqual(BB.yazim_ihlalleri(yeni, "plan.md", AYAR), [])

    def test_bitisik_etiketli_alanlar_arasina_bos_satir(self):
        yeni, d = self.duz("**Amaç:** a\n**Neden:** b\n**Kanıt:** c\n")
        self.assertEqual(yeni, "**Amaç:** a\n\n**Neden:** b\n\n**Kanıt:** c\n")
        self.assertEqual(d, ["bos_satir", "bos_satir"])

    def test_nokta_ayiricili_liste_maddelere_bolunur(self):
        yeni, d = self.duz("Durum: I-1 · onay bekliyor · sıradaki: plan\nDevam.\n")
        self.assertEqual(yeni, "Durum:\n\n- I-1\n- onay bekliyor\n- sıradaki: plan\n\nDevam.\n")
        self.assertEqual(d, ["nokta_liste"])
        self.assertEqual(self.duz("a · b · c\n")[0], "- a\n- b\n- c\n")

    def test_belirsiz_ayirici_bolunmez(self):
        uzun = "x" * 130
        for metin in (f"a · {uzun} · c\n",  # madde çok uzun: cümle olabilir
                      "a · b · c·d\n"):  # boşluksuz '·' da var: ayırıcı kesin değil
            with self.subTest(metin=metin):
                self.assertEqual(self.duz(metin), (metin, []))

    # --- I-435 P1: sıkışık liste (`;`, (a)(b)) Write'ta madde satırlarına bölünür
    def test_noktali_virgul_listesi_maddelere_bolunur(self):
        yeni, d = self.duz("Kapsam: hook; CLI; panel; test\nDevam.\n")
        self.assertEqual(yeni, "Kapsam:\n\n- hook\n- CLI\n- panel\n- test\n\nDevam.\n")
        self.assertEqual(d, ["sikisik_liste"])
        self.assertEqual(self.duz("a; b; c; d\n")[0], "- a\n- b\n- c\n- d\n")
        self.assertEqual(self.duz("**Kapsam:** a; b; c; d\n")[0], "**Kapsam:**\n\n- a\n- b\n- c\n- d\n")
        self.assertEqual(self.duz("hook; CLI; panel\n"), ("hook; CLI; panel\n", []))  # iki ';' ihlal değil

    def test_harf_isaretli_liste_maddelere_bolunur(self):
        yeni, d = self.duz("Şunlar yapılacak: (a) bir, (b) iki ve (c) üç.\n")
        self.assertEqual(yeni, "Şunlar yapılacak:\n\n- (a) bir\n- (b) iki\n- (c) üç.\n")
        self.assertEqual(d, ["sikisik_liste"])
        self.assertEqual(self.duz("(1) bir; (2) iki\n")[0], "- (1) bir\n- (2) iki\n")

    def test_kod_araligindaki_noktali_virgul_bolunmez(self):
        self.assertEqual(self.duz("a; b; `c; d`; e\n")[0], "- a\n- b\n- `c; d`\n- e\n")

    def test_sikisik_liste_karisik_metinde_ihlal_sifir(self):
        """K1 (S1b): `;` ve (a)(b) satırları + etiket ihlali tek Write'ta giderilir; CRLF korunur."""
        metin = ("# Plan\r\n\r\n**Amaç:** a **Neden:** b\r\n\r\n"
                 "Adımlar: oku; yaz; sına; kaydet\r\n\r\nKarar: (a) eski kalır, (b) yeni eklenir.\r\n")
        self.assertGreaterEqual(len(BB.yazim_ihlalleri(metin, "plan.md", AYAR)), 3)
        yeni, d = self.duz(metin)
        self.assertEqual(BB.yazim_ihlalleri(yeni, "plan.md", AYAR), [])
        self.assertEqual(sorted(d), ["etiket_ayir", "sikisik_liste", "sikisik_liste"])
        self.assertNotIn("\n", yeni.replace("\r\n", ""))  # çıplak LF yok
        self.assertIn("- oku\r\n- yaz\r\n- sına\r\n- kaydet\r\n", yeni)
        self.assertIn("- (a) eski kalır\r\n- (b) yeni eklenir.\r\n", yeni)

    def test_sikisik_liste_belirsizse_orijinal_doner(self):
        """K3: ondalık, URL, tırnak/kod, foo(a)(b), sırasız işaret, cümle sınırı, korunan blok, uzun paragraf."""
        uzun = "kelime " * 50
        for metin in ("Oranlar 0;5 1;5 2;5 3;5\n",  # ondalık: boşluksuz ';'
                      "Bkz. https://x.example/a;b;c;d sonu.\n",  # URL içi ';'
                      'Komut "a; b; c; d" çalışır.\n',  # tırnak içi
                      "`a;b`;c;d;e\n",  # kod aralığı + boşluksuz ayırıcı
                      "Çağrı foo(a)(b) döner.\n",  # işlev çağrısı
                      "Not: (a) bir, (c) iki.\n",  # sırasız işaret
                      "a; b. Sonra c; d; e\n",  # madde içinde cümle sınırı
                      "Şunlar: (a) bir. Sonra (b) iki.\n",
                      "Seçim (a) ile (b) arasında yapılır.\n",  # ayraçsız işaretler: atıf, liste değil
                      "a; b; c;\n",  # boş son madde
                      "```\na; b; c; d\n(a) x (b) y\n```\n\n" + uzun + "\n",  # korunan blok + düzeltilemez ihlal
                      "Adımlar: oku; yaz; sına; kaydet\n\n" + uzun + "\n"):  # düzeltilebilir + uzun paragraf: hepsi ya da hiçbiri
            with self.subTest(metin=metin[:40]):
                self.assertEqual(self.duz(metin), (metin, []))

    def test_kod_citi_icindeki_sikisik_liste_dokunulmaz(self):
        cit = "```\na; b; c; d\n(a) x (b) y\n```\n\n"
        yeni, d = self.duz(cit + "Adımlar: oku; yaz; sına; kaydet\n")
        self.assertEqual(yeni, cit + "Adımlar:\n\n- oku\n- yaz\n- sına\n- kaydet\n")
        self.assertEqual(d, ["sikisik_liste"])

    def test_crlf_korunur(self):
        yeni, d = self.duz("**A:** a **B:** b\r\nson\r\n")
        self.assertEqual(yeni, "**A:** a\r\n\r\n**B:** b\r\nson\r\n")

    def test_kod_blogu_yorum_tablo_onbilgi_dokunulmaz(self):
        korunan = ("---\nbaslik: x\n---\n\n```\n**A:** a **B:** b\nx · y · z\n```\n\n<!-- **A:** a **B:** b\nx · y · z\n-->\n\n"
                   "| **A:** a **B:** b | x · y · z |\n|---|---|\n\n> alıntı\n\n")
        yeni, d = self.duz(korunan + "**A:** a **B:** b\n")
        self.assertEqual(yeni, korunan + "**A:** a\n\n**B:** b\n")
        self.assertEqual(d, ["etiket_ayir"])

    def test_anlamsal_ihlal_duzeltilmez_hepsi_ya_da_hicbiri(self):
        uzun = "kelime " * 50
        self.assertEqual(self.duz(uzun + "\n"), (uzun + "\n", []))
        todo = "- [ ] P1: " + "kelime " * 35 + "\n"
        self.assertEqual(self.duz(todo, "todo.md"), (todo, []))
        # düzeltilebilir ihlal + düzeltilemez ihlal: orijinal döner
        karma = "**A:** a **B:** b\n\n" + uzun + "\n"
        self.assertEqual(self.duz(karma), (karma, []))

    def test_temiz_ve_liste_maddesi_dokunulmaz(self):
        self.assertEqual(self.duz(TEMIZ), (TEMIZ, []))
        madde = "- **A:** a **B:** b\n"  # liste maddesini bölmek yapıyı değiştirir: ret kalır
        self.assertEqual(self.duz(madde), (madde, []))


class Kancalar(unittest.TestCase):
    setUp = TC.Cekirdek.setUp
    tearDown = TC.Cekirdek.tearDown
    cli = TC.Cekirdek.cli
    hook = TC.Cekirdek.hook
    karar = TC.Cekirdek.karar
    kart = TC.Cekirdek.kart

    def gunluk(self):
        yol = os.path.join(self.sd, "gunluk.jsonl")
        if not os.path.exists(yol):
            return []
        with open(yol, encoding="utf-8") as f:
            return [json.loads(s) for s in f if s.strip()]

    def ihlaller(self, kural):
        return [g for g in self.gunluk() if g.get("tur") == "kural_ihlal" and g.get("kural") == kural]

    def ayar_yaz(self, **kapilar):
        with open(os.path.join(self.sd, "belge_bicim.json"), "w", encoding="utf-8") as f:
            json.dump({k: {"mod": v} for k, v in kapilar.items()}, f)

    def yaz(self, ad, icerik, arac="Write", alan="content"):
        return self.hook("PreToolUse", {"tool_name": arac, "tool_input": {"file_path": os.path.join(self.proje, ad), alan: icerik}})

    def stop(self, yanit, dokunulan):
        satirlar = [{"type": "assistant", "timestamp": "2026-10-16T10:00:00Z",
                     "message": {"model": "claude-opus-5-5", "usage": {"input_tokens": 1, "output_tokens": 1},
                                 "content": [{"type": "tool_use", "name": "Write", "input": {"file_path": os.path.join(self.proje, d)}}
                                             for d in dokunulan]}}]
        with open(self.ana_tr, "w", encoding="utf-8", newline="\n") as f:
            for s in satirlar:
                f.write(json.dumps(s) + chr(10))
        return self.hook("Stop", {"last_assistant_message": yanit})

    # --- Ö4 yazım anı
    def test_golge_yazimi_engellemez_kayit_ve_uyari_dusurur(self):
        self.ayar_yaz(yazim_kapisi="golge")
        c = self.yaz("is1/plan.md", IHLALLI)
        self.assertIsNone(self.karar(c))
        self.assertIn("K-005", c["hookSpecificOutput"]["additionalContext"])
        self.assertIn("satır 3 coklu_etiket", c["hookSpecificOutput"]["additionalContext"])
        k = self.ihlaller("belge_bicim")
        self.assertEqual(len(k), 1, k)
        self.assertEqual((k[0]["mod"], k[0]["dosya"], k[0]["adet"]), ("golge", "is1/plan.md", 2))

    def test_temiz_ve_belge_olmayan_dosya_sessiz(self):
        # Biçim kapısı sessizliği sınanır; yazım anı bağlamı (ADR-0111) ayrı mekanizma, kendi testinde.
        with mock.patch.dict(os.environ, {"ORKESTRA_URETIM_ENJEKSIYON": "0"}):
            self.assertEqual(self.yaz("is1/plan.md", TEMIZ), {})
        self.assertEqual(self.yaz("is1/notlar.md", IHLALLI), {})
        self.assertEqual(self.yaz("kod.py", "a; b; c; d"), {})
        self.assertEqual(self.ihlaller("belge_bicim"), [])

    def test_edit_ve_multiedit_parcasi_taranir(self):
        self.ayar_yaz(yazim_kapisi="golge")
        c = self.yaz("is1/todo.md", "a; b; c; d", arac="Edit", alan="new_string")
        self.assertIn("sikisik_liste", c["hookSpecificOutput"]["additionalContext"])
        c = self.hook("PreToolUse", {"tool_name": "MultiEdit", "tool_input": {
            "file_path": os.path.join(self.proje, "is1/rapor.md"), "edits": [{"old_string": "x", "new_string": "a; b; c; d"}]}})
        self.assertIn("sikisik_liste", c["hookSpecificOutput"]["additionalContext"])

    def test_ihlal_modunda_yazim_reddedilir_bastirma_gecer(self):
        self.ayar_yaz(yazim_kapisi="ihlal")
        # IHLALLI tek başına güvenli düzeltmeyle geçer (I-435 P1); uzun paragraf eklenince düzeltilemez, ret kalır
        c = self.yaz("is1/plan.md", IHLALLI + "\n" + "kelime " * 50 + "\n")
        self.assertEqual(self.karar(c), "deny")
        neden = c["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("satır 3 coklu_etiket", neden)
        self.assertIn("satır 5 sikisik_liste", neden)  # tüm ihlaller tek seferde
        self.assertIn("satır 7 uzun_paragraf", neden)
        self.assertEqual(self.yaz("is1/plan.md", "a; b; c; d <!-- biçim-tamam -->\n"), {})
        self.assertEqual(self.ihlaller("belge_bicim")[0]["mod"], "ihlal")

    def test_biçim_kapisi_kilitli_test_kapisini_atlamaz(self):
        """Gölge uyarısı gec() çıkışına taşınır; sonraki ret kapıları (ana ajan alan kapısı) yine çalışır."""
        k = self.kart("--yazma", "is1/**")
        self.assertTrue(k)
        r = self.cli("kart", "durum", k, "isleniyor")
        self.assertEqual(r.returncode, 0, r.stderr)
        c = self.yaz("is1/plan.md", IHLALLI)
        self.assertEqual(self.karar(c), "deny", c)

    # --- I-224 P9 (c): Write'ta güvenli düzeltme updatedInput ile
    DUZELIR = "# B\n\n**Amaç:** a **Neden:** b\n"

    def test_write_duzeltilebilir_icerik_updatedinput_ile_yazilir(self):
        self.ayar_yaz(yazim_kapisi="ihlal")
        yol = os.path.join(self.proje, "is1/plan.md")
        c = self.hook("PreToolUse", {"tool_name": "Write", "permission_mode": "acceptEdits",
                                     "tool_input": {"file_path": yol, "content": self.DUZELIR}})
        ho = c["hookSpecificOutput"]
        self.assertEqual(ho["permissionDecision"], "allow", c)
        self.assertEqual(ho["updatedInput"], {"file_path": yol, "content": "# B\n\n**Amaç:** a\n\n**Neden:** b\n"})
        self.assertIn("biçim düzeltildi (K-005): 1 dönüşüm", ho["additionalContext"])
        self.assertEqual(self.ihlaller("belge_bicim"), [])  # ret sayılmaz
        self.assertEqual([g["donusum_adet"] for g in self.gunluk() if g.get("tur") == "belge_duzeltme"], [1])

    def test_varsayilan_kipte_duzeltme_kullaniciya_sorulur(self):
        """İzin yükseltmesi yok: düzenlemeyi sormadan yapmayan kipte düzeltilmiş girdi ask ile gösterilir."""
        self.ayar_yaz(yazim_kapisi="ihlal")
        c = self.yaz("is1/plan.md", self.DUZELIR)
        self.assertEqual(self.karar(c), "ask", c)
        self.assertIn("updatedInput", c["hookSpecificOutput"])

    def test_duzeltilemez_icerik_reddedilir(self):
        self.ayar_yaz(yazim_kapisi="ihlal")
        c = self.yaz("is1/plan.md", self.DUZELIR + "\n" + "kelime " * 50 + "\n")
        self.assertEqual(self.karar(c), "deny", c)
        self.assertNotIn("updatedInput", c["hookSpecificOutput"])

    def test_edit_ve_multiedit_duzeltilmez_ret_kalir(self):
        self.ayar_yaz(yazim_kapisi="ihlal")
        c = self.yaz("is1/plan.md", "**Amaç:** a **Neden:** b", arac="Edit", alan="new_string")
        self.assertEqual(self.karar(c), "deny", c)
        self.assertNotIn("updatedInput", c["hookSpecificOutput"])

    def test_golge_modda_duzeltme_yok(self):
        self.ayar_yaz(yazim_kapisi="golge")
        c = self.yaz("is1/plan.md", self.DUZELIR)
        self.assertNotIn("updatedInput", c.get("hookSpecificOutput") or {})

    def test_kapatilinca_eski_ret_davranisi(self):
        self.ayar_yaz(yazim_kapisi="ihlal")
        with open(os.path.join(self.sd, "belge_duzelt.json"), "w", encoding="utf-8") as f:
            json.dump({"mod": "kapali"}, f)
        c = self.yaz("is1/plan.md", self.DUZELIR)
        self.assertEqual(self.karar(c), "deny", c)
        self.assertIn("satır 3 coklu_etiket", c["hookSpecificOutput"]["permissionDecisionReason"])
        os.remove(os.path.join(self.sd, "belge_duzelt.json"))
        eski = os.environ.get("ORKESTRA_BELGE_DUZELT")
        os.environ["ORKESTRA_BELGE_DUZELT"] = "0"
        try:
            c = self.yaz("is1/plan.md", self.DUZELIR)
        finally:
            if eski is None:
                os.environ.pop("ORKESTRA_BELGE_DUZELT", None)
            else:
                os.environ["ORKESTRA_BELGE_DUZELT"] = eski
        self.assertEqual(self.karar(c), "deny", c)
        self.assertNotIn("updatedInput", c["hookSpecificOutput"])

    # --- Ö3 Stop
    def test_stop_golge_baglantisiz_belgeyi_kaydeder_bloklamaz(self):
        self.ayar_yaz(baglanti_kapisi="golge")
        c = self.stop("bitti", ["is1/rapor.md", "kod.py"])
        self.assertNotEqual(c.get("decision"), "block", c)
        k = self.ihlaller("belge_baglantisi_yok")
        self.assertEqual(len(k), 1, k)
        self.assertEqual((k[0]["mod"], k[0]["dosyalar"], k[0]["adet"]), ("golge", ["is1/rapor.md"], 1))

    def test_stop_baglantili_yanit_kayit_dusurmez(self):
        self.stop("rapor: [rapor.md](is1/rapor.md)", ["is1/rapor.md"])
        self.assertEqual(self.ihlaller("belge_baglantisi_yok"), [])

    def test_stop_ihlal_modunda_hook_gosterir_bloklamaz(self):
        self.ayar_yaz(baglanti_kapisi="ihlal")
        c = self.stop("bitti", ["is1/rapor.md"])
        self.assertNotEqual(c.get("decision"), "block", c)
        self.assertIn("rapor.md", c["systemMessage"])
        self.assertIn("(is1/rapor.md)", c["systemMessage"])

    def test_stop_belge_olmayan_dosya_ihlal_sayilmaz(self):
        self.stop("bitti", ["scripts/kod.py", "README.md", "is1/devir_ozeti.md"])
        self.assertEqual(self.ihlaller("belge_baglantisi_yok"), [])


if __name__ == "__main__":
    unittest.main()
