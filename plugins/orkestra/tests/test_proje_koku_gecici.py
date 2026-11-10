"""Proje kökü çözümü sistem geçici klasöründe durur (I-433).

Geçici kökte (tempfile.gettempdir) bir kez oluşmuş `.claude/orkestra`, altındaki her geçici klasörü o sahte projeye
bağlıyordu: yeni projede `baslat` yanlış kökü açıyor, testler TEMP'e göre kırılıyordu. Testler gerçek geçici kökü
değil, tempfile.tempdir'i geçici bir klasöre çevirerek aynı yapıyı kurar; gerçek geçici köke dokunulmaz.
"""
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import ork_lib as L  # noqa: E402


@pytest.fixture
def sahte_gecici(tmp_path, monkeypatch):
    kok = tmp_path / "Temp"
    (kok / ".claude" / "orkestra").mkdir(parents=True)  # geçici kökte artık kalmış durum klasörü
    monkeypatch.setattr(tempfile, "tempdir", str(kok))
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    return kok


def test_gecici_altindaki_yeni_klasor_gecici_koke_baglanmaz(sahte_gecici):
    yeni = sahte_gecici / "tmp_proje"
    yeni.mkdir()
    assert L.proje_dizini(str(yeni)) == str(yeni)
    assert L.proje_dizini(str(yeni), ortami_yoksay=True) == str(yeni)


def test_gecici_altindaki_gercek_proje_bulunur(sahte_gecici):
    proje = sahte_gecici / "p"
    (proje / ".claude" / "orkestra").mkdir(parents=True)
    alt = proje / "a" / "b"
    alt.mkdir(parents=True)
    assert L.proje_dizini(str(alt)) == str(proje)


def test_gecici_disinda_yukari_yuruyus_degismez(sahte_gecici, tmp_path):
    proje = tmp_path / "dis"
    (proje / ".claude" / "orkestra").mkdir(parents=True)
    alt = proje / "x"
    alt.mkdir()
    assert L.proje_dizini(str(alt)) == str(proje)
    assert L._gecici_sinir(str(alt)) is None
    assert L._gecici_sinir(str(sahte_gecici)) is None  # geçici kökün kendisi sınır dışı: açık istekle kullanılabilir
