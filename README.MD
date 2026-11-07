## Python и проверка контейнера

Для локальной разработки и контейнера используется Python 3.12 (`.python-version`).
Создайте отдельное виртуальное окружение и установите `requirements.txt`.
Dockerfile использует Debian Bookworm. `.env`, ключи и резервные копии исключены
из контекста сборки; настройки передаются при запуске, а не встраиваются в образ.

Проверка без подключения к рабочим БД и без SMTP:

```sh
docker build -t culta-backend:check .
docker run --rm --network none culta-backend:check python -m pip check
docker run --rm --network none culta-backend:check python -m pytest tests -q
docker run --rm --network none culta-backend:check python -c 'import tests.conftest; from main import app; from fastapi.testclient import TestClient; c=TestClient(app); assert c.get("/openapi.json").status_code == 200'
```

Интеграционные тесты PostgreSQL запускаются отдельно по `tests/README.md`.

## Автоматические проверки

Workflow `.github/workflows/backend-checks.yml` запускается для pull request,
push в `main`/`master` и вручную через GitHub Actions. Используется Python 3.12.
Одна задача проверяет зависимости и весь набор тестов с отдельной PostgreSQL 16,
вторая собирает Dockerfile и проверяет запуск API в контейнере без сети.
Тестовые настройки задаются в `tests/conftest.py`, секреты рабочего окружения
не требуются. JUnit-отчёт сохраняется на 14 дней, в том числе при падении тестов.
Workflow начнёт работать после попадания файла в GitHub; локальная проверка
не подтверждает успешный удалённый запуск Actions.

## Проверка восстановления локальной базы

Из корня backend, в его Python-окружении:

```sh
python -B scripts/verify_local_restore.py
```

Скрипт предназначен только для локального Podman `culta-clean`, контейнера
`main_db` и БД `main_db` на `127.0.0.1:5431`. Другие адреса отклоняются.
Он создаёт свежий дамп и контрольные суммы из одного read-only снимка PostgreSQL,
восстанавливает данные в отдельном контейнере с временным хранилищем без
опубликованных портов, сравнивает все таблицы и количество объектов схемы.
Затем собирает текущий backend и проверяет миграции и запуск API. Рабочая БД
не изменяется. Временный контейнер удаляется по завершении, включая ошибки.
При принудительном завершении процесса нужно проверить оставшиеся контейнеры
с префиксом `culta-restore-check-` и меткой `culta.restore-drill`.

Дамп и `report.json` сохраняются в каталоге `backups/culta-restore-drill-*`
текущей локальной рабочей области Codex (путь указан в скрипте). Файлы доступны
только владельцу; дамп содержит пользовательские данные и не должен попадать
в Git. Успех подтверждают `complete`, `data_verified`, `migrations_verified`,
`api_startup_verified` и `temporary_container_removed` в отчёте.
Размер исходной БД ограничен 256 МиБ, временное хранилище — 1 ГиБ.

Проверка 28.10.2026: 25 таблиц совпали, схема `a44c28e62026`, миграции и API
проверены. Это проверка восстановления данных и схемы: глобальные роли,
исходные права доступа, S3 и секреты приложения в неё не входят.
28.10.2026 проверена загрузка в приватный S3-бакет `culta-db-backups`:
скачанный архив совпал по размеру и SHA-256. Локальная автоматизация Codex
`culta-s3` включена ежедневно в 03:00 по Москве, с уведомлением при ошибке.
Для неё должны работать компьютер, Codex и Podman. Серверное расписание
пока не настроено; успешный ручной запуск не подтверждает ночной запуск.

## Резервные копии: подготовка автоматического запуска

`python -B scripts/backup_database.py` создаёт и полностью декодирует новый
локальный дамп `main_db`, сохраняет SHA-256 и результат в `last_run.json`.
Параллельный запуск не создаёт вторую копию. По умолчанию сохраняются последние
14 проверенных локальных копий, минимум две; повреждённые, незавершённые и
посторонние каталоги автоматически не удаляются. При ошибке создания или
загрузки старые копии не удаляются. Проверка декодирования не заменяет
периодический полный прогон восстановления описанным выше скриптом.

Для внешнего хранения заполните в `.env` отдельные `BACKUP_S3_*` поля из
`.env.backup.example` и используйте `python -B scripts/backup_database.py --upload`.
Нужен приватный отдельный бакет и ключ с доступом PutObject/GetObject к префиксу
`culta/main_db/`. Ключи изображений автоматически не подставляются. После
загрузки объект скачивается потоком и проверяется по размеру и SHA-256.
Это создаёт дополнительный исходящий трафик хранилища. При включённом upload
локальная ротация касается только копий с подтверждённой внешней загрузкой.
Удаление объектов из S3 скрипт не выполняет; срок хранения бакета настраивается
отдельно.

Локальный путь по умолчанию — `backups/scheduled` рабочей области Codex,
можно задать `--directory` или `BACKUP_DIRECTORY` (аргумент имеет приоритет).
Без дополнительных настроек используется локальный Podman `culta-clean`.
Для сервера доступны `BACKUP_CONTAINER_COMMAND` (например, `docker`),
`BACKUP_DB_CONTAINER`, `BACKUP_DB_USER`, `BACKUP_DB_NAME`. Команда разбирается
в аргументы без shell; пароли в неё помещать нельзя. На сервере задайте
отдельный каталог `BACKUP_DIRECTORY`, доступный только владельцу, установите
Python-зависимости проекта и проверьте ручной запуск с `--upload` перед
включением расписания. Нужны доступ к контейнеру PostgreSQL и отдельные
`BACKUP_S3_*` настройки. Скрипт сам не устанавливает серверный планировщик.

Для поднятия сервисов баз для локальной разработки нужно запустить команду:

```
make up
```

Для накатывания миграций, если файла alembic.ini ещё нет, нужно запустить в терминале команду:

```
alembic init migrations
```

После этого будет создана папка с миграциями и конфигурационный файл для алембика.

- В alembic.ini нужно задать адрес базы данных, в которую будем катать миграции.
- Дальше идём в папку с миграциями и открываем env.py, там вносим изменения в блок, где написано

```
from myapp import mymodel
```

- Дальше вводим: ```alembic revision --autogenerate -m "comment"``` - делается при любых изменениях моделей
- Будет создана миграция
- Дальше вводим: ```alembic upgrade heads```

Для того, чтобы во время тестов нормально генерировались миграции нужно:
- сначала попробовать запустить тесты обычным образом. с первого раза все должно упасть
- если после падения в папке tests создались алембиковские файлы, то нужно прописать туда данные по миграхам
- если они не создались, то зайти из консоли в папку test и вызвать вручную команды на миграции, чтобы файлы появились
### Product edit concurrency

Product reads include `version` (starts at 1). Send that version in
`PATCH /product_card/update_by_id` or `PUT /navigation_editor/products`
when updating an existing product. Each accepted update increments it.
Creating a product does not require a version.

Missing version returns 428; a stale version returns 409 with
`detail.code=product_version_conflict`. Reload explicitly and review the
changes before retrying; never automatically retry with a newer version.
The legacy `PUT /navigation_editor/items` endpoint requires
`product_version` when it also edits an existing product.
Apply migration `d30c18e62026` before running this code. Older API clients
must pass the read version before attempting product updates.
### Публикация меню (№32)

`screen`, `container`, `item` имеют `is_active` и `is_visible` (по умолчанию `true`).
Редактор `/navigation_editor` возвращает все элементы, включая скрытые. `/canvas`
сохраняет флаги атомарно с версией экрана. Отсутствующие флаги не меняют существующие значения.
Публичные GET навигации возвращают 404 для скрытых/неактивных элементов и их потомков;
вложенные списки и список экранов компании фильтруются. Это публикация меню,
а не запрет продажи товара сотрудником: карточки и история заказов сохраняются.
`ProductCard.is_used` вычисляется по наличию размещений, в том числе скрытых.
### Проверка токена (№33)

`GET /login/token/status` с `Authorization: Bearer <access_token>` возвращает
`valid`, `user_id`, `expires_at` (UTC) и `expires_in` (оставшиеся целые секунды).
Ответ не кешируется и не продлевает токен. Неверный/истёкший токен или отсутствие
`exp` дают 401; неподтверждённый, заблокированный или удалённый аккаунт — 403
согласно общей политике авторизации. Проверка не гарантирует валидность будущего
запроса: каждый защищённый запрос проходит авторизацию самостоятельно.
### Обновление сессий (№34)

`POST /login/session` принимает JSON `email`, `password` и возвращает access token
и одноразовый `refresh_token`. `POST /login/refresh` принимает `refresh_token`,
возвращает новую пару; старый refresh token необходимо заменить атомарно.
`POST /login/logout` с текущим refresh token отзывает сессию обновления.
Срок refresh-сессии фиксирован: 30 дней, максимум 500 ротаций, затем новый вход.
В БД сохраняются только хеши refresh-токенов. Повторное применение уже заменённого
токена отзывает всю refresh-сессию. Клиент обязан сериализовать refresh-запросы,
в том числе между вкладками, и не повторять их автоматически после потери ответа.
Смена пароля или недоступность аккаунта запрещает дальнейшее обновление.
Новые access-токены имеют `sid`, действуют 15 минут и проверяют состояние сессии
при каждом защищённом HTTP-запросе. Logout и отзыв сессии блокируют их немедленно.
WebSocket проверяет сессию перед командами и при периодической проверке доступа.
Legacy-токены без `sid` сохраняют прежнее поведение до истечения своего `exp`.
`GET /login/sessions` показывает собственные активные сессии без секретов;
`DELETE /login/sessions/{session_id}` завершает выбранную собственную сессию. UI использует `/login/session`, Yandex callback также выдаёт refresh-сессию.
Старый `/login/token` сохранён без refresh для совместимости.
При 401 UI обновляет токен и повторяет исходный запрос один раз. Web Locks
сериализует обновления между вкладками. Если Web Locks недоступен или ответ
обновления потерян, нужен повторный вход. Токены хранятся в localStorage
(как ранее access token); это требует строгой защиты от XSS. Старым сессиям
нужен один повторный вход для получения refresh token.
Перед публикацией использовать HTTPS; refresh-токены не помещать в URL/логи.

### Вход через Google

В Google Cloud создайте OAuth client типа Web application и зарегистрируйте
точный redirect URI `http://localhost:3000/auth/google/callback` для локальной разработки.
Скопируйте переменные из `auth/GOOGLE.env.example` в backend `.env`, заполните
client ID и client secret, затем перезапустите backend. Не помещайте secret в UI.
Локально открывайте UI через `localhost`, с API на `localhost:8000`: смешивание
`127.0.0.1` и `localhost` нарушает передачу SameSite cookie OAuth-потока.
На сервере нужны HTTPS, зарегистрированный production callback и same-site API/UI.
Для OAuth-приложения в режиме Testing добавьте разрешённых тестовых пользователей.

POST `/login/auth/google/start` создаёт 10-минутный поток с HttpOnly cookie,
state, nonce и PKCE. POST `/login/auth/google/callback` проверяет код и подпись
Google ID-токена и выдаёт обычную refresh-сессию приложения. Новый пользователь
получает статус `confirmed` только при `email_verified=true`.
Совпадение email с существующим аккаунтом возвращает 409: автоматическое
объединение аккаунтов отключено. Для такого аккаунта используйте прежний способ входа.

### Telegram OIDC

Backend environment: TELEGRAM_CLIENT_ID, TELEGRAM_CLIENT_SECRET (OAuth secret,
not Bot API token), TELEGRAM_REDIRECT_URI. Register the exact callback in
BotFather → Login Widget → OpenID Connect. Default signing algorithm: RS256.
The login uses openid/profile only, state, nonce and PKCE, plus HttpOnly flow cookie.
No phone/email is requested or inferred; accounts are keyed by Telegram subject.
No automatic linking to existing accounts or super-admin grants occur.
Migration a37c20e62026 permits NULL email. New sessions carry a UUID uid claim;
legacy email-subject tokens remain accepted until expiry.
Local testing currently reaches Telegram but HTTP localhost callback returned
'redirect_uri required'; production requires registered HTTPS callback and same-site UI/API.
