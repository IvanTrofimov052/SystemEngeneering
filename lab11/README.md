# Selenium UI тесты для lab5

Эти тесты покрывают основные UI-сценарии Social Network MVP (lab5):
- регистрация / вход / выход
- создание поста и удаление
- лайк поста и добавление комментария

## Требования

1) Запустите приложение lab5:

```bash
cd ../lab5
source .venv/bin/activate
uvicorn app.main:app --reload
```

2) Установите зависимости тестов (из lab11):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3) Убедитесь, что установлен Google Chrome и chromedriver доступен в PATH,
   либо задайте путь в `CHROMEDRIVER_PATH`.

## Запуск тестов

```bash
pytest -q
```

### Опциональные переменные окружения

- `BASE_URL` (по умолчанию: `http://127.0.0.1:8000`)
- `HEADLESS` (по умолчанию: `1`; поставьте `0`, чтобы видеть браузер)
- `BROWSER` (по умолчанию: `chrome`)
- `CHROMEDRIVER_PATH` (опционально; путь к chromedriver)
