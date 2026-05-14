# Исправление ошибки DOM mismatch / `$(...) is null`

Причина: после замены старой операторской панели на мастер запуска браузер мог использовать закешированный `/js/app.js` от предыдущей версии при новом `index.html`. Старый скрипт искал DOM-элементы старого интерфейса (`cards`, `blockers`, `operatorJobResult` и т.п.), которых в новом HTML уже нет, что приводило к ошибке `can't access property "innerHTML", $(...) is null`.

Что исправлено:

- добавлено версионирование frontend assets: `/js/app.js?v=operator-workflow-20260514-2`, `/css/styles.css?v=operator-workflow-20260514-2`;
- добавлен no-cache middleware для `/`, `.html`, `.js`, `.css` и `/api/operator*`;
- добавлены скрытые legacy DOM placeholders, чтобы один переходный запуск со старым JS не ломал экран;
- frontend `$()` теперь создает inert placeholder и пишет `console.error`, вместо падения всей панели;
- live/risk invariants не изменялись.

После обновления архива желательно открыть страницу с Ctrl+F5.
