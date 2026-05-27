Use the API tests as the lower layer, then add browser-level tests for the HTML pages.

For the HTML/API interaction, I’d test with a real browser runner such as Playwright or Selenium:

- Start the Flask/Django/FastAPI app in test mode.
- Open the actual HTML pages in a browser.
- Fill forms, click buttons, submit data, navigate pages.
- Assert both the visible UI result and the backend effect.
- Cover key flows: create parking record, update status, search/list, delete/cancel, validation errors, and empty states.

A typical structure would be:

```text
tests/
  test_api_*.py          # direct API/unit tests
  test_pages_*.py        # browser tests against HTML pages
```

For the database, don’t use your real development or production database. Use an isolated test database that is reset for every test or test session.

Good options:

- SQLite in-memory database for fast tests, if your app supports it.
- A temporary SQLite file per test run.
- A dedicated test database, e.g. `parkinglot_test`, recreated before tests.
- Transactions with rollback after each test, if your framework supports it cleanly.

The important rule is: browser tests should hit the same test database as the app server, but that database should contain only controlled test data. Seed it at the start of each test, run the UI interaction, assert the result, then clean it up.

In short: API tests prove endpoints work; browser tests prove the pages actually call those endpoints correctly. Use a disposable test database so the UI tests are realistic without risking real data.