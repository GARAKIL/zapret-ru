# Zapret RU 1.1.0

[Скачать ZapretRU.exe](https://github.com/GARAKIL/zapret-ru/releases/download/v1.1.0/ZapretRU.exe) ·
[SHA256SUMS.txt](https://github.com/GARAKIL/zapret-ru/releases/download/v1.1.0/SHA256SUMS.txt)

Zapret RU — локальный Windows-лаунчер для оригинального
[bol-van/zapret](https://github.com/bol-van/zapret). Помогает настроить
desync-обход DPI/ТСПУ для YouTube, Discord, Cloudflare и других сервисов, не
превращаясь в VPN и не заворачивая трафик через чужие серверы.

## Состав

- Исходный код лаунчера и UI.
- Пресеты `presets.json`.
- Базовые списки доменов.
- Автоподбор стратегии.
- Локальная статистика без телеметрии.
- Скрипты сборки и CI.

## Важно

Бинарники `winws.exe`, WinDivert, `cygwin1.dll` и `.bin`-фейки **не входят** в
репозиторий. Их нужно взять из официального дистрибутива zapret. Лаунчер не
скачивает их сам.

Ни один клиентский обход DPI не может гарантировать 100% результат на всех
провайдерах: ТСПУ меняются, часть блокировок делается по IP и протоколам.
Используйте встроенную диагностику и автоподбор, чтобы найти рабочую стратегию
для своего подключения.

## Проверка файла

```powershell
Get-FileHash .\ZapretRU.exe -Algorithm SHA256
Get-Content .\SHA256SUMS.txt
```

Хэш должен совпасть с `SHA256SUMS.txt` из этого же релиза. Сборка не подписана
сертификатом Authenticode, поэтому SmartScreen может показать предупреждение.

## Лицензия

MIT. Оригинальный zapret распространяется отдельно под своей лицензией.
