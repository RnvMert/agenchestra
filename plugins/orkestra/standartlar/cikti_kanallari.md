# Çıktı kanalları

Hook kanalı sayısı: 4 (hook.py taramasından üretilir; elle düzenlenmez).
Model kanalı sayısı: 3.

## Hook kanalları

### additionalContext

- **Alıcı:** model
- **Düğme:** hayır
- **hook.py'de geçiş:** 8
- **Not:** Modele bağlam; kullanıcı görmez. Model cümleyi kendi sözleriyle yazar, biçim güvenilmez.

### systemMessage

- **Alıcı:** kullanıcı
- **Düğme:** hayır
- **hook.py'de geçiş:** 13
- **Not:** Kullanıcıya doğrudan sabit metin; model araya girmez. Düğme taşıyamaz.

### decision block

- **Alıcı:** model
- **Düğme:** hayır
- **hook.py'de geçiş:** 10
- **Not:** Turu zorla sürdürür; reason modele gider.

### permissionDecision

- **Alıcı:** araç çağrısı
- **Düğme:** hayır
- **hook.py'de geçiş:** 3
- **Not:** allow, deny ya da ask; ask kullanıcıya onay sordurur (düğmeyi uygulama çizer).

## Model kanalları

### düz metin

- **Alıcı:** kullanıcı
- **Düğme:** hayır
- **Not:** Serbest yanıt; biçim modele bağlı.

### düğmeli seçim

- **Alıcı:** kullanıcı
- **Düğme:** evet
- **Not:** wrap_up actions ya da AskUserQuestion; yalnız model çağırabilir.

### dosya gönderimi

- **Alıcı:** kullanıcı
- **Düğme:** hayır
- **Not:** SendUserFile; belge içeriği sohbete yazılmaz.

## Kural

- Kullanıcıya dönük uyarı sabit `systemMessage` ile gider; seçim gerekiyorsa model düğmeyle sunar (ADR-0157).
- Düğmenin çıkması modelde zorlanmaz, yalnız `additionalContext` yönergesiyle istenir.
