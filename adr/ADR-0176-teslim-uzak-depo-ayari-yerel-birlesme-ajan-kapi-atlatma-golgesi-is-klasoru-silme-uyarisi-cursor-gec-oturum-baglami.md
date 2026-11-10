# ADR-0176: Teslim kapısı uzak depo adını ayardan alır, yerel birleşme yolu, ajan kapı atlatma ve kayıtlı iş klasörü silme uyarıları gölgede başlar, Cursor geç sessionStart bağlamı ilk istemde verilir

**Durum:** Kabul edildi

**Tarih:** 2026-11-10

**Bağlam:**

- Jira ORKESTRA-9 ve 12: teslim kapısı uzak depo adını `origin` olarak koduna gömüyordu; `origin`'i olmayan depoda kapı çalışmıyor, ajanın kapıyı `--ozetsiz` ya da `ORKESTRA_*_KAPISI=0` ile atlaması engellenmiyordu. Bekleyen iş için hatırlatma metni kapının atlanabileceğini düşündürüyordu.
- Jira ORKESTRA-20: McD `isler.json` kayıtlarının bir kısmı silinmiş klasörü gösteriyor; kayıtlı bir iş klasörünün kabukla silinmesi uyarısız geçiyordu (ADR-0175 yalnız worktree temizliğini kapsıyor).
- Cursor 019 todo satır 65: Cursor günlüklerinde 15 sohbetin 5'inde `sessionStart` ilk `beforeSubmitPrompt`'tan sonra geliyor (08-10.11.2026); ilk istem bağsız, kurallar yolsuz çalışıyordu.
- Yeni kontroller P-028 gereği önce gölge modda açılır.

**Karar:**

- `ayarlar/teslim.json` `uzak_depo` (varsayılan `origin`) ekler; kapı bu uzak depoya bakar, uzak depo yoksa susar. Proje ezmesi anahtar bazında birleşir.
- `orkestra is kapat --yerel-birlesme <commit>`: commit ana dalın atasıysa (`git merge-base --is-ancestor`) kanıt `teslim.yerel_birlesme` alanına yazılır, kapanışta yeniden doğrulanır. Özet ve ADR kapıları çalışmaya devam eder. Ajan kimliğiyle çağrı her modda reddedilir.
- Yeni kapı `kapi_atlatma` (gölge): ajan kabuğunda `--ozetsiz` ve `ORKESTRA_*_KAPISI=0` türü atamalar uyarı + `kapi_golge` olarak kaydedilir; ihlal modunda reddedilir. Kapatma: `ORKESTRA_KAPI_ATLATMA_KAPISI=0`.
- Yeni kapı `is_klasoru_silme` (gölge): `rm`, `rmdir`, `del`, `Remove-Item`, `mv`, `git worktree remove`, `git clean` komutları `isler.json`'daki bir iş klasörünü, üstünü ya da içindeki belgeyi hedefliyorsa uyarı + `kapi_golge`; ihlalde ret. Değişkenli yol yakalanmaz (en iyi çaba). Kapatma: `ORKESTRA_KLASOR_SILME_KAPISI=0`.
- Bekleyen teslim `is.json` `bekliyor` alanıyla işaretlenir; hatırlatma "kullanıcı kararını bekle" der, kapıyı atlamayı önermez.
- `cursor_hook.py`: sohbet kimliği başına işaret dosyası tutulur. İstem `sessionStart`'tan önce gelirse SessionStart bağlamı ilk istemde üretilir, geç gelen `sessionStart` atlanır. Kapatma: `ORKESTRA_CURSOR_OTURUM_ISARET=0`.

**Seçenekler:**

- Seçilen: yeni kapılar gölgede. Neden: P-028; yanlış pozitif ölçülmeden engel konmaz.
- Elenen: doğrudan ihlal modu. Neden elendi: ajanın test komutlarındaki `ORKESTRA_X_KAPISI=0 pytest …` gibi meşru kullanımlar da yakalanıyor; ölçüm yok.
- Seçilen: `--yerel-birlesme` kanıtı git ataması ile doğrulanır. Neden: uzak depo olmayan projede teslim kapısı çalışmaz kalmasın.
- Elenen: kapıyı `origin`'i olmayan projede tümüyle kapatmak. Neden elendi: kapanış güvencesi o projede tamamen düşer.
- Elenen: Cursor'da bağlamı ilk istemden sonra eklemek. Neden elendi: ilk tur bağlamsız kalır.

**Sonuçlar:**

- Meşru `ORKESTRA_*_KAPISI=0` kullanımı gölge kayda düşer; ihlale geçmeden önce `orkestra is rapor` ile ölçülmelidir.
- `izin_ver` bekleyen gölge uyarısını `additionalContext` olarak taşır; izinli tüm orkestra komutlarında görünür.
- Cursor ilk istemde ek bir hook süreci çalıştırır (yalnız sessionStart gecikmesinde).
- Gölge kapıların hiçbiri bu kararla ihlale alınmadı (ORKESTRA-5 ölçümü: P-028 ölçütü hiçbirinde sağlanmıyor).

**İlgili:** ADR-0175, P-028, I-433, Jira ORKESTRA-5, 9, 12, 20, Cursor 019 todo satır 65.
