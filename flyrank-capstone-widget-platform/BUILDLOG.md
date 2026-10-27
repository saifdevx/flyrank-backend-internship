# BUILDLOG: how AI was used on this project

## What the AI did (Claude, one working session)
- Read the capstone brief and produced the first complete version of this project: migrations, the three layers,
  the widget JavaScript, the rate limiter, the geo fallback chain, the background worker, the tests, and the docs.
- Wrote the automated tests, then ran them. It also ran the server over real HTTP with curl (preflight, cross-origin
  submit, dashboard, worker email) and loaded `widget.js` in a simulated browser (jsdom).

## Where the AI was wrong, and how it was caught
1. **HEAD requests returned 405** on `/widget.js` and `/widgets/{id}/config`. All 21 tests passed at that point, but a live
   `curl -I` smoke test exposed it. Fixed by allowing HEAD on those routes and adding `test_head_requests_work_on_public_assets`.
2. **A passing test suite proves little by itself.** To check the tests can fail, the AI deliberately broke the code twice
   (removed the tenant check; disabled the honeypot) and confirmed the matching tests failed.
3. **Not verified by the AI:** real CORS enforcement in a real browser (jsdom does not enforce CORS), and the real geo
   providers (`GEO_MODE=real`), because the AI's sandbox had no access to them.

## What I did myself
- [x] I set the project up in my own virtual environment and ran the full automated test suite on my machine.
- [x] I generated `EVIDENCE.md` with `python scripts/fill_evidence.py`: all 15 requirement groups passed.
- [ ] I ran the customer-site page in a real browser and checked the Network tab. (Not done.)
- [ ] I ran `GEO_MODE=real` once. (Not done; the geo fallback is proven only with the mock providers.)
- Changes I made to the AI's code: none so far. I ran it as provided.
- Decision: I am keeping the capstone as a subfolder of my existing internship repository. The brief recommends a
  separate repository, so I am asking the FlyRank team in the capstone Q&A whether this is acceptable.
- Not done: I did not capture screenshots. The evidence is the pasted test output instead.

## Lines I can explain
1. `allowed, retry = rate_limit.limiter.consume(...)` in `routes/public.py`: each visitor IP has a bucket of 10 tokens
   that refills at one per second, and every submission spends one. When the bucket is empty the API answers 429
   immediately, before doing any real work, so a flood is rejected cheaply and the server stays up.
2. `WHERE id = ? AND tenant_id = ?` in `repositories.get_widget_for_tenant`: the database only returns a widget if it
   belongs to the tenant making the request. If tenant B asks for tenant A's widget, nothing is found and the API
   answers 404, so isolation is enforced in the query itself.
3. `repo.insert_submission(...)` then `repo.enqueue_job(...)` inside one `with db.session()` in `services.submit`: the saved
   submission and its "send email" job are committed together or not at all. The email is sent later by the worker, so
   if it fails the submission is already safely stored.
4. `except sqlite3.IntegrityError: return "duplicate"` in `services.submit`: the database allows each idempotency key
   only once per widget. If two retries of the same submission arrive at the same moment, one is stored and the other
   is rejected by the database, and the code reports "already received" instead of crashing.