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
- Without added latency the local API answers in under 50 ms, and the control build only
  fails at faster pacing (30 ms for PgDn); the proxy makes it fail at 50 ms and 150 ms too.

Conclusion: PR #9 fixed issue #6. No further change to `SegPanel.vue` was needed.

## Run the check yourself (one command)

Needs Docker Desktop running, Node 22, and the images this repository's compose file uses
already pulled or built once (`base:kraken6`, the nginx image, postgres, redis). Ports 8081
and 8082 must be free (or pick others with `--port` and `--proxy-port`). Everything runs in a
throwaway stack named `issue6`, published on 127.0.0.1 only; nothing touches an existing
deployment. The stack name is shared by every checkout: use `--project` to run two at once,
and note that `--down` removes the stack of that name whichever checkout started it.

1. **See the bug first** (editor built without PR #9), from the repository root:

   ```bash
   node front/tests/manual/fast-paging/check.js --bundle control
   ```

   The script creates `variables.env` from the example if needed, builds the control bundle
   (it reverse-applies PR #9's `SegPanel.vue` diff for the build and restores the file right
   after, also on Ctrl+C), starts the stack, seeds a 200-page document, and runs the latency proxy with a
   test panel added to the editor page. When it prints `Ready`, open the URL it shows,
   sign in as the `DJANGO_SU_NAME` account from `variables.env`, keep the Segmentation
   panel open, wait for the page image, and click **Full check** in the box at the bottom
   right. Expected: **FAIL**, with console errors, stale image sources and the
   `reading '0'` stack trace from `SegPanel.vue`.

2. **Check the fix** (current code). Press Ctrl+C to stop the proxy, then:

   ```bash
   node front/tests/manual/fast-paging/check.js --bundle main
   ```

   Reload the editor page and click **Full check** again. Expected: **PASS**: no console
   errors, no stale image sources, and the panel image, scale and overlay match the page
   shown after every run.

3. **Try it by hand** if you like: with the page open through the proxy (port 8082) and the
   browser's DevTools console visible, hold or hammer PgDn, or type page numbers into the
   page-number box and press Enter as fast as you can. No `refreshSegmenter` errors should
   appear, and the page that settles should show its own image and overlay.

4. **Clean up:**

   ```bash
   node front/tests/manual/fast-paging/check.js --down
   ```

Options: `--build` forces a rebuild (needed after switching branches: the script only checks
which of the two bundles `front/dist` holds, not whether it matches the code), `--project`, `--port`, `--proxy-port`, `--api-delay`
and `--media-delay` (ms ranges, defaults `120-300` and `100-400`) change the setup.

### What "Full check" does

The panel (`panel.js`) calls `driver.js`, which jumps to page 1, then dispatches 40 PgDn
keydowns at 50 ms intervals three times and 30 page-number entries at 50 ms once, waiting
3 s after each run. It hooks `console.error`, `window.onerror` and unhandled rejections,
counts `parts/load` commits, and flags any `src` set on the segmentation panel's image that
does not belong to the loaded part. PASS means zero console errors, zero stale sources, and
a correct settled state (image, scale and overlay line count) after each run.

## Pieces, for running them separately

- `compose.dev.yml`: override for the throwaway stack (pulled base image with `./app` and
  `./front/dist` mounted, nginx on port 8081 only). Used with the root `docker-compose.yml`.
- `seed.py`: creates the 200-page document (page n shows "PAGE n" and `5 + (n mod 7)` rules,
  with the same number of segmentation lines). Run with
  `docker exec -i <web> python manage.py shell < seed.py`.
- `latency-proxy.js`: `:8082 -> :8081` with delays on `/api/` and `/media/`; websockets
  tunnelled. Standalone it adds no panel.
- `driver.js`: can also be pasted into the browser console on an editor page, then
  `await window.__issue6.runPgDn(40, 50)` and `await window.__issue6.runNumberBox(30, 50)`.
- `panel.js`: the on-page PASS/FAIL box; only served by `check.js`'s proxy.
