ZAPRET RU — папка движка
========================

Сюда нужно скопировать файлы из оригинального zapret для Windows (bol-van).
Приложение не скачивает их автоматически.

Обязательные файлы:
  winws.exe
  WinDivert.dll
  WinDivert64.sys
  cygwin1.dll

Рекомендуемые файлы фейковых пакетов:
  quic_initial_www_google_com.bin
  tls_clienthello_www_google_com.bin
  ACTIVE_DISCORD_UDP.bin
  ACTIVE_GAME_UDP.bin

Откуда взять:
  1. https://github.com/bol-van/zapret
  2. https://github.com/bol-van/zapret-win-bundle
  3. или из проверенной сборки zapret для Windows

Скопируйте сюда весь каталог bin из архива zapret, чтобы вместе с winws.exe
лежали WinDivert.dll, WinDivert64.sys, cygwin1.dll и .bin-файлы.
Архитектура: Windows 10/11 x64.

Если каких-то .bin-файлов нет, лаунчер всё равно запустится: приложение
пропустит соответствующие параметры, и zapret использует встроенные фейки.
Полный комплект .bin обычно даёт более стабильный результат.

ВАЖНО:
- WinDivert и winws.exe являются сторонними компонентами zapret (bol-van).
- Используйте только официальные источники: сборки из случайных архивов
  могут содержать вредоносный код.
- Не запускайте второй winws.exe параллельно с этим приложением.
