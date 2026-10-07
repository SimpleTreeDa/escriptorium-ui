/* eslint-env browser */
// Fast-paging driver (see README.md). Two ways to use it:
//
// 1. check.js adds it to the editor page together with panel.js; the panel's buttons call
//    window.__issue6Install() and the run functions below.
// 2. Paste the whole file into the console of an open editor page (segmentation panel
//    visible), then:
//      await window.__issue6.runPgDn(40, 50)            // 40 PgDn presses, one every 50 ms
//      await window.__issue6.runNumberBox(30, 50)       // 30 page numbers + Enter, every 50 ms
//
// Each run waits 3 s to settle and returns error counts, page changes, stale image sources
// and the settled-state checks.
(() => {
    const install = () => {
        const rootEl = document.querySelector("#editor");
        const root = rootEl && rootEl.__vue__;
        if (!root) throw new Error("This is not an editor page (no #editor Vue root).");
        const store = root.$store;
        const findSeg = (vm) => (
            vm.segmenter && vm.refreshSegmenter ? vm : vm.$children.map(findSeg).find(Boolean)
        );
        const S = window.__issue6 = window.__issue6 || {
            errors: [], pageChanges: 0, staleSrc: [], srcChanges: 0, dispatched: 0,
            hooked: false, hasSeg: false,
        };
        const partImageUrls = (img) => [
            img.uri,
            img.thumbnails && img.thumbnails.large,
            img.thumbnails && img.thumbnails.display,
        ].filter(Boolean);
        const srcBelongsTo = (src, img) => (
            partImageUrls(img).some((u) => src.includes(u.split("?")[0]))
        );

        if (!S.hooked) {
            S.hooked = true;
            const record = (kind, err) => {
                const stack = String((err && err.stack) || err || "");
                const message = String((err && err.message) || err || "");
                S.errors.push({
                    t: performance.now(), kind, message, stack,
                    inRefresh: /refreshSegmenter/.test(stack),
                    inSegPanel: /SegPanel/.test(stack),
                    reading0: /reading '0'/.test(message) || /reading '0'/.test(stack),
                });
            };
            const origError = console.error.bind(console);
            console.error = (...args) => {
                args.forEach((a) => record("console.error", a));
                origError(...args);
            };
            window.addEventListener("error", (e) => record("window.error", e.error || e.message));
            window.addEventListener("unhandledrejection", (e) => (
                record("unhandledrejection", e.reason)
            ));
            store.subscribe((m) => {
                if (m.type === "parts/load" && m.payload && m.payload.image) S.pageChanges++;
            });
        }

        // The segmentation panel only exists once a page is loaded, so attach to it lazily.
        // Any src set on its <img> while the store holds another part (or none) is stale.
        if (!S.hasSeg) {
            const seg = findSeg(root);
            if (seg) {
                S.hasSeg = true;
                new MutationObserver(() => {
                    const src = seg.$img.getAttribute("src");
                    if (!src) return;
                    S.srcChanges++;
                    const ok = store.state.parts.loaded
                        && srcBelongsTo(src, store.state.parts.image || {});
                    if (!ok) {
                        S.staleSrc.push({
                            t: performance.now(), src,
                            part: store.state.parts.pk, loaded: store.state.parts.loaded,
                        });
                    }
                }).observe(seg.$img, { attributes: true, attributeFilter: ["src"] });
            }
        }

        const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
        const keydown = (target, key, keyCode) => {
            target.dispatchEvent(new KeyboardEvent("keydown", {
                key, code: key, keyCode, which: keyCode, bubbles: true, cancelable: true,
            }));
        };
        const start = (run) => ({
            run, before: S.errors.length, pc: S.pageChanges, stale: S.staleSrc.length,
            startOrder: store.state.parts.order,
        });
        const pageCount = () => store.state.document.partsCount || 200;

        // load page `order` (0-based) and wait for it, so runs start from a known place
        S.goToOrder = async (order = 0) => {
            if (store.state.parts.loaded && store.state.parts.order === order) return;
            store.dispatch("parts/loadPartByOrder", order);
            for (let i = 0; i < 100; i++) {
                await sleep(100);
                if (store.state.parts.loaded && store.state.parts.order === order) break;
            }
            await sleep(1500);
        };

        S.runPgDn = async (n = 40, ms = 50) => {
            const ctx = start(`PgDn x${n} @${ms}ms`);
            for (let i = 0; i < n; i++) {
                keydown(document, "PageDown", 34);
                S.dispatched++;
                await sleep(ms);
            }
            await sleep(3000);
            return S.summary(ctx);
        };

        S.runNumberBox = async (n = 30, ms = 50, maxPage = pageCount()) => {
            const ctx = start(`number box x${n} @${ms}ms`);
            let typed = 0;
            let skipped = 0;
            for (let i = 0; i < n; i++) {
                // the box is removed from the DOM while a page loads
                const input = document.querySelector(".element-switcher input[type=number]");
                if (input) {
                    const page = 1 + Math.floor(Math.random() * maxPage);
                    input.value = String(page);
                    keydown(input, "Enter", 13);
                    typed++;
                    S.lastTyped = page;
                } else {
                    skipped++;
                }
                await sleep(ms);
            }
            await sleep(3000);
            return S.summary({ ...ctx, typed, skipped, lastTyped: S.lastTyped });
        };

        S.summary = (ctx) => {
            const seg = findSeg(root);
            const errs = S.errors.slice(ctx.before);
            const p = store.state.parts;
            const img = p.image || {};
            const src = seg && seg.$img.getAttribute("src");
            const sample = errs.find((e) => e.inSegPanel) || errs[0];
            return {
                ...ctx,
                errors: errs.length,
                // the error objects whose stack is in SegPanel.vue: one per throw
                segPanelThrows: errs.filter((e) => e.inSegPanel).length,
                reading0Errors: errs.filter((e) => e.reading0).length,
                otherErrors: errs.filter((e) => !e.inSegPanel && !e.reading0)
                    .map((e) => e.message.slice(0, 160)),
                sampleStack: sample && sample.stack.split("\n").slice(0, 4),
                pageChanges: S.pageChanges - ctx.pc,
                staleSrc: S.staleSrc.length - ctx.stale,
                settled: {
                    loaded: p.loaded, order: p.order, pk: p.pk,
                    imgMatchesPart: !!src && srcBelongsTo(src, img),
                    scaleOk: !!seg && seg.$img.naturalWidth > 0 && !!img.size
                        && Math.abs(seg.segmenter.scale
                            - seg.$img.naturalWidth / img.size[0]) < 1e-9,
                    scale: seg && seg.segmenter.scale,
                    overlayLines: seg && seg.segmenter.lines.length,
                    storeLines: store.state.lines.all.length,
                    // pages seeded by seed.py have 5 + (order % 7) lines; null otherwise
                    expectedLines: p.loaded && S.seededDocument ? 5 + (p.order % 7) : null,
                },
            };
        };
        S.seededDocument = /Fast paging test/.test(store.state.document.name || "");
        return S;
    };

    window.__issue6Install = install;
    // pasted into the console (no <script> element): install right away
    return document.currentScript ? undefined : install();
})();
