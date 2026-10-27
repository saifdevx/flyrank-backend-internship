# BUILDLOG: how AI was used on this project

> Honesty is graded, perfection is not. Edit this file so it describes what actually happened for YOU.

## What the AI did (Claude, one working session)
- Read the capstone brief and produced the first complete version of this repository: migrations, the three layers,
  the widget JavaScript, the rate limiter, the geo fallback chain, the background worker, the tests, and the docs.
- Wrote the 22 tests, then ran them. It also ran the server over real HTTP with curl (preflight, cross-origin submit,
  dashboard, worker email) and loaded `widget.js` in a simulated browser (jsdom).

## Where the AI was wrong, and how it was caught
1. **HEAD requests returned 405** on `/widget.js` and `/widgets/{id}/config`. All 21 tests passed, but a live `curl -I`
   smoke test exposed it. Fixed by allowing HEAD on those routes and adding `test_head_requests_work_on_public_assets`.
2. **A passing test suite proves little by itself.** To check the tests can fail, the AI deliberately broke the code twice
   (removed the tenant check; disabled the honeypot) and confirmed the matching tests failed.
3. **Not verified by the AI:** real CORS enforcement in a real browser (jsdom does not enforce CORS), and the real geo
   providers (`GEO_MODE=real`), because the sandbox had no access to them. Both are for me to check.

## What I did myself
> Fill this in truthfully. Examples: which files I read line by line, what I ran, what I changed, what I broke and fixed.

- [ ] I read and can explain `app/services.py` (`submit`), `app/rate_limit.py`, `app/cors.py`, `app/jobs.py`.
- [ ] I ran the server and the customer-site page in a real browser and checked the Network tab.
- [ ] I ran `GEO_MODE=real` once and noted what happened.
- [ ] Changes I made: ...

## Lines I can explain (the evaluator will pick 2-3)
Write one plain sentence for each, in your own words:
1. `allowed, retry = rate_limit.limiter.consume(...)` in `routes/public.py`: ...
2. `WHERE id = ? AND tenant_id = ?` in `repositories.get_widget_for_tenant`: ...
3. `repo.insert_submission(...)` then `repo.enqueue_job(...)` inside one `with db.session()` in `services.submit`: ...
4. `except sqlite3.IntegrityError: return "duplicate"` in `services.submit`: ...
