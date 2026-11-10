"""I-433 (Jira ORKESTRA-20): kayıtlı iş klasörünü silen/taşıyan kabuk komutu PreToolUse'ta uyarı üretir (gölge: uyarı +
kapi_golge; ihlal: ret); kayıtsız klasör ve bağsız (isler.json yok) proje sessiz kalır. CLI ve hook süreç içinde."""
import json
import os
import shutil
import sys
import tempfile
import unittest

import test_cekirdek as TC

sys.path.insert(0, os.path.join(TC.KOK, "scripts"))
import is_klasoru_silme as S  # noqa: E402


class KlasorSilme(unittest.TestCase):
    setUp_ = TC.Cekirdek.setUp
    tearDown = TC.Cekirdek.tearDown
    cli = TC.Cekirdek.cli
    hook = TC.Cekirdek.hook
    karar = TC.Cekirdek.karar

    def setUp(self):
        self.setUp_()
        self.klasor = os.path.join(self.proje, "isler", "001-deneme")
        r = self.cli("is", "ac", "Silme denemesi", "--klasor", self.klasor)
        self.assertEqual(r.returncode, 0, r.stderr)
        os.makedirs(os.path.join(self.proje, "baska"), exist_ok=True)

    def pre(self, komut, arac="Bash"):
        return self.hook("PreToolUse", {"tool_name": arac, "tool_input": {"command": komut}})

    def ek(self, o):
        return (o.get("hookSpecificOutput") or {}).get("additionalContext", "")

    def golge(self):
        yol = os.path.join(self.sd, "gunluk.jsonl")
        if not os.path.exists(yol):
            return []
        with open(yol, encoding="utf-8") as f:
            return [o for o in (json.loads(s) for s in f if s.strip())
                    if o.get("tur") == "kapi_golge" and o.get("kapi") == "is_klasoru_silme"]

    def test_kayitli_klasore_rm_uyari_verir(self):
        for komut in ("rm -rf isler/001-deneme", "rm -rf isler", "rm isler/001-deneme/plan.md",
                      "git worktree remove isler/001-deneme", "mv isler/001-deneme /tmp/x", "rmdir /s /q isler\\001-deneme",
                      "cd isler && rm -rf 001-deneme", "rm -rf isler/001-deneme/*"):
            with self.subTest(komut=komut):
                o = self.pre(komut)
                self.assertNotEqual(self.karar(o), "deny", o)
                self.assertIn("I-001", self.ek(o))
                self.assertIn("İş belgeleri silinir", self.ek(o))
        o = self.pre("Remove-Item -Recurse -Force isler/001-deneme", arac="PowerShell")
        self.assertIn("I-001", self.ek(o))
        self.assertTrue(self.golge())

    def test_kayitsiz_klasore_uyari_vermez(self):
        for komut in ("rm -rf baska", "rm -rf isler/002-yok", "mv baska isler/001-deneme/ic", "ls isler/001-deneme",
                      "git clean -n", "cat isler/001-deneme/plan.md"):
            with self.subTest(komut=komut):
                self.assertNotIn("is_klasoru_silme", self.ek(self.pre(komut)))
        self.assertEqual(self.golge(), [])

    def test_ihlal_modunda_reddeder(self):
        with open(os.path.join(self.sd, "is_klasoru_silme.json"), "w", encoding="utf-8") as f:
            json.dump({"mod": "ihlal"}, f)
        o = self.pre("rm -rf isler/001-deneme")
        self.assertEqual(self.karar(o), "deny", o)
        self.assertIn("I-001", o["hookSpecificOutput"]["permissionDecisionReason"])
        self.assertNotEqual(self.karar(self.pre("rm -rf baska")), "deny")

    def test_bagsiz_projede_sessiz(self):
        os.remove(os.path.join(self.sd, "isler.json"))
        o = self.pre("rm -rf isler/001-deneme")
        self.assertNotIn("is_klasoru_silme", self.ek(o))
        self.assertEqual(self.golge(), [])


class Hedefler(unittest.TestCase):
    def setUp(self):
        self.kok = tempfile.mkdtemp(prefix="ork_i433_silme_")
        self.addCleanup(shutil.rmtree, self.kok, True)

    def h(self, komut):
        return [os.path.relpath(y, self.kok).replace("\\", "/") for y in S.hedefler(komut, self.kok)]

    def test_hedef_cikarma(self):
        self.assertEqual(self.h("rm -rf a b"), ["a", "b"])
        self.assertEqual(self.h("mv a b c"), ["a", "b"])
        self.assertEqual(self.h("Move-Item -Path a -Destination b"), ["a"])
        self.assertEqual(self.h("git -C d worktree remove --force w"), ["d/w"])
        self.assertEqual(self.h("git clean -fdx"), ["."])
        self.assertEqual(self.h("git clean -fd -- x"), ["x"])
        self.assertEqual(self.h("git clean -nd"), [])
        self.assertEqual(self.h("rm -rf $HOME/x"), [])
        self.assertEqual(self.h("echo rm a"), [])


if __name__ == "__main__":
    unittest.main()
