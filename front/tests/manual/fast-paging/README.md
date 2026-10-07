# Fast paging in the editor: segmentation panel race (issue #6)

Manual, browser-driven check for
[issue #6](https://github.com/SimpleTreeDa/escriptorium-ui/issues/6):
paging quickly through a document with the segmentation panel open used to log

```
TypeError: Cannot read properties of undefined (reading '0')
    at refreshSegmenter (front/vue/components/SegPanel.vue)
```

[PR #9](https://github.com/SimpleTreeDa/escriptorium-ui/pull/9) targeted the error. This
folder holds the harness that was used to confirm the fix held on `main`, and the results.
It is not part of `npm test` (nothing here is a `*.test.mjs`): the race needs a real browser,
a real backend and network latency.

## Result (2026-10-07)

Both bundles were served by the same local stack, same database, same latency proxy.
Keystrokes were dispatched every 50 ms. "Control" is `main` at 2f7d4311 with only PR #9's
`SegPanel.vue` diff reverse-applied, so the fix is the single variable.

| Build | Run | Page changes | `reading '0'` throws from SegPanel | Old page's image set as source |
|---|---|---|---|---|
| control (#9 reverted) | PgDn ×40 | 7 | 10 | 6 |
| control (#9 reverted) | PgDn ×40 | 7 | 12 | 6 |
| control (#9 reverted) | PgDn ×40 | 7 | 12 | 6 |
| control (#9 reverted) | page-number box ×30 | 4 | 6 | 3 |
| main 2f7d4311 | PgDn ×40, 3 rounds | 7 + 7 + 7 | 0 | 0 |
| main 2f7d4311 | page-number box ×30 | 3 | 0 | 0 |

- On the control build the throw is `this.$store.state.parts.image.size[0]` inside the
  `Vue.nextTick` callback of `refreshSegmenter`. Vue logs each throw twice in a development
  bundle (a `[Vue warn]` line and the error object), so the console shows about twice these
  numbers.
- On `main` nothing was logged. After every run the panel image matched the loaded part, the
  segmenter scale equalled `naturalWidth / parts.image.size[0]`, and the number of overlay
  lines matched the page shown.
- PgDn presses are ignored while a page is loading (`parts/loadPart` returns early), which is
  why 40 presses give 7 page changes. The page-number box is removed from the DOM while a page
  loads, so only 3–4 of 30 Enter presses at 50 ms reach it.
- Without added latency the local API answers in under 50 ms and the race does not happen.

Conclusion: PR #9 fixed issue #6. No further change to `SegPanel.vue` was needed.

## How to run it again

Everything below runs against a throwaway stack; nothing touches an existing deployment.

1. **Stack.** Copy `variables.env_example` to `variables.env` and set
   `CSRF_TRUSTED_ORIGINS=http://127.0.0.1:8081,http://127.0.0.1:8082`. Build the bundle
   (`cd front && npm ci && npm run build`; the development build keeps readable stack traces),
   then from the repository root:

   ```bash
   docker compose -p issue6 -f docker-compose.yml -f front/tests/manual/fast-paging/compose.dev.yml up -d --no-build db redis web channelserver nginx
   ```

   `compose.dev.yml` runs the pulled `base:kraken6` image with `./app` and `./front/dist`
   mounted and publishes nginx on port 8081 only. After rebuilding the bundle, re-run
   `docker exec issue6-web-1 python manage.py collectstatic --no-input`.

2. **Data.** Seed one 200-page document (generated PNGs with a page number and
   `5 + (n mod 7)` rules, plus the same number of segmentation lines):

   ```bash
   docker exec -i issue6-web-1 python manage.py shell < front/tests/manual/fast-paging/seed.py
   ```

   It prints the editor URL. The `admin` account from `variables.env` is used and switched to
   the new UI.

3. **Latency.** Start the proxy, then browse through it:

   ```bash
   node front/tests/manual/fast-paging/latency-proxy.js
   ```

   Defaults: `/api/` delayed 120–300 ms, `/media/` 100–400 ms, websockets tunnelled.
   Override with `API_DELAY=150-250 MEDIA_DELAY=...`. Open
   `http://127.0.0.1:8082/document/<doc>/part/<part>/edit/` with the segmentation panel open.

4. **Drive and measure.** Paste `driver.js` into the browser console, then:

   ```js
   await window.__issue6.runPgDn(40, 50)
   await window.__issue6.runNumberBox(30, 50, 200)
   ```

   Each run returns the counts in the table above plus the settled-state checks. The driver
   hooks `console.error`, `window.onerror` and unhandled rejections, counts `parts/load`
   commits, and flags any `src` set on the segmentation panel's image that does not belong to
   the loaded part.

5. **Control build.** `git show 4773072b -- front/vue/components/SegPanel.vue | git apply -R`,
   rebuild, `collectstatic`, reload, repeat step 4. Restore with
   `git checkout -- front/vue/components/SegPanel.vue`.

Tear down with `docker compose -p issue6 down -v`.
