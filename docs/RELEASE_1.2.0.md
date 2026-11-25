# Zapret RU 1.2.0

[Скачать ZapretRU.exe](https://github.com/GARAKIL/zapret-ru/releases/download/v1.2.0/ZapretRU.exe) ·
[SHA256SUMS.txt](https://github.com/GARAKIL/zapret-ru/releases/download/v1.2.0/SHA256SUMS.txt)

**Собственный движок. Один exe. Без winws и папки bin.**

- Встроенный WinDivert-движок: SNI-split, HTTP Host split, QUIC → TCP.
- Большое окно 1120×800 с рабочими кнопками свернуть / развернуть / закрыть.
- Новый тёмный iOS-интерфейс: скругления, градиенты, анимации, минимум кнопок.
- Автоподбор профилей по YouTube, Discord и Cloudflare.
- Горячее применение списков и локальная статистика без телеметрии.
- PyDivert и подписанный WinDivert64 включены в один exe; ничего не скачивается.
- 36 unit-тестов, CI, CodeQL и SHA-256.

## Быстрый старт

1. Скачайте `ZapretRU.exe`.
2. Запустите, разрешите UAC.
3. Нажмите «Включить защиту». Если сайт не открывается — нажмите автоподбор.

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
