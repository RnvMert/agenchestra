# ADR-0175: İzin ezmesi varsayılanla birleşir, proje kökü taraması geçici kökte durur, belge içeren worktree silinmez

**Durum:** Kabul edildi

**Tarih:** 2026-11-10

**Bağlam:**

- Jira ORKESTRA kartları I-433 işinde kodla ve McD günlüğüyle doğrulandı (isler.json, gunluk.jsonl, 09.11.2026 23:55 ve 10.11.2026).
- `izin_politikasi.ayar_yukle` ezmeyi `cfg.update` ile uyguluyordu; ezmedeki tek bir üst düzey alan varsayılandaki GitHub ve veritabanı koruma girişlerini komple siliyordu (ORKESTRA-14).
- `dal_temizle.agaclar_temizle` belge içeren worktree'yi denetlemeden kaldırıyordu; McD isler.json'daki 431 işin 112'sinin klasörü silinmiş worktree yolunda kaldı (ORKESTRA-3, 18).
- `ork_lib.proje_dizini` yukarı doğru `.claude/orkestra` ararken geçici dizindeki bir stray klasörü proje sayıyordu; temiz olmayan makinede test takımı ~1240 hata verdi (ORKESTRA-4).
- `jsonl_ekle` kayda proje kökü yazmıyordu; 1165 `kural_ihlal` kaydının hiçbirinde kök alanı yoktu (ORKESTRA-19).

**Karar:**

- Ezme alan türüne göre birleşir: sözlükler özyinelemeli, listeler varsayılan + ezme (tekrarsız), tekil alanlar ezmedeki değerle değişir. Listeyi tümüyle değiştirmek için ezmede `"degistir": ["alan"]` yazılır. `mcp: []` artık varsayılanı silmez.
- `agaclar_temizle` worktree içindeki iş belgesi (isler.json `klasor` alanı ya da `is.json` içeren klasör) `main`'de güvende değilse worktree'yi silmez, belge yollarını atlanan kayda ve `worktree_temizle` olayına yazar.
- Proje kökü taraması başlangıç yolu TEMP altındaysa TEMP kökünde durur; TEMP dışı davranış değişmez.
- `jsonl_ekle` günlük yolundan çıkardığı proje kökünü `kok` olarak yazar, başka kökün kaydını reddeder (`KokUyusmazligi`); mevcut satırlar değişmez.

**Seçenekler:**

- Seçilen: alan türüne göre birleştirme. Neden: koruma girişleri sessizce düşmez, tam değiştirme açık ve kayıtlı kalır.
- Elenen: ezmeyi olduğu gibi bırakıp belgeye uyarı yazmak. Neden elendi: kapı olmayan uyarı korumayı düşüren yapılandırmayı engellemez.
- Seçilen: belge güvenli değilse worktree'yi silmemek. Neden: sessiz belge kaybı geri alınamaz.
- Elenen: belge klasörünü her zaman ana projeye taşımak. Neden elendi: iş klasörü oturum köküne göre çözülür (ADR-0033), kök taşınırsa bağlantılar bozulur.
- Elenen: test için TEMP'i her seferinde ortam değişkeniyle ayırmak. Neden elendi: kaynak çözümleyici yanlış kökü seçmeye devam eder.

**Sonuçlar:**

- Ezmede `mcp: []` yazan projeler artık varsayılan korumaları yeniden alır; eski davranışı isteyen `degistir` yazar (`test_standart_izin.py` yeni sözleşmeye uyarlandı).
- Silinmeyen worktree'ler birikebilir; `orkestra git denetim` ve atlanan listesi bunları gösterir.
- Başka projenin `kural_ihlal` kaydı artık hata verir; çağıranlar `KokUyusmazligi` yakalamalıdır.

**İlgili:** ADR-0033, ADR-0050, I-433, Jira ORKESTRA-3, 4, 14, 18, 19.
