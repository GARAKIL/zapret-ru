# Zapret RU 1.3.0

[Скачать ZapretRU.exe](https://github.com/GARAKIL/zapret-ru/releases/download/v1.3.0/ZapretRU.exe) ·
[SHA256SUMS.txt](https://github.com/GARAKIL/zapret-ru/releases/download/v1.3.0/SHA256SUMS.txt)

**Свой движок. Один exe. Без winws и папки bin.**

- Режим **«Простой / Расширенный»**: большая кнопка, пинг и статистика на первом
  экране; профили и диагностика — по переключателю.
- Большой круглый переключатель защиты и плавные анимации.
- **Пинг** по минимальной задержке YouTube, Discord и Cloudflare.
- **7 профилей**, включая «Старт SNI» и «Конец SNI»; автоподбор проверяет все.
- SNI-split, HTTP Host split, QUIC → TCP.
- PyDivert и подписанный WinDivert64 включены в один exe; ничего не скачивается.
- Локальная статистика без телеметрии.
- 37 unit-тестов, CI, CodeQL и SHA-256.

## Быстрый старт

1. Скачайте `ZapretRU.exe`.
2. Запустите, разрешите UAC.
3. Нажмите «Включить защиту». Если сайт не открывается — «Подобрать стратегию».

## Важно

Абсолютных 100% на всех провайдерах не бывает: блокировки по IP, DNS, ECH и
UDP-протоколы требуют отдельных мер. Движок честно проверяет доступность и
показывает реальные задержки. WinDivert — сторонний драйвер под LGPL/GPL;
лицензии и исходники перечислены в `THIRD_PARTY_NOTICES.txt` и `licenses/`.

## Проверка файла

```powershell
Get-FileHash .\ZapretRU.exe -Algorithm SHA256
Get-Content .\SHA256SUMS.txt
```

Сборка не подписана сертификатом Authenticode, поэтому SmartScreen может
показать предупреждение. Проверяйте SHA-256 из этого же релиза.
