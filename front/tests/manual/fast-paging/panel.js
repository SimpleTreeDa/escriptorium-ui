/* eslint-env browser */
// Test panel that check.js's proxy adds to editor pages (see README.md). It runs the
// driver (driver.js) and shows PASS or FAIL. Never loaded in normal use of the app.
(() => {
    const style = document.createElement("style");
    style.textContent = `
#fast-paging-panel { position: fixed; right: 16px; bottom: 16px; z-index: 100000;
  width: 380px; max-height: 60vh; overflow: auto; background: #fff; color: #111;
  border: 1px solid #888; border-radius: 6px; box-shadow: 0 2px 12px rgba(0,0,0,.3);
  font: 13px/1.4 system-ui, sans-serif; padding: 10px; }
#fast-paging-panel button { margin: 6px 6px 0 0; padding: 4px 10px; font: inherit;
  cursor: pointer; }
#fast-paging-panel pre { white-space: pre-wrap; margin: 8px 0 0;
  font: 12px/1.4 ui-monospace, Consolas, monospace; }
#fast-paging-panel .pass { color: #0a7a2f; font-weight: bold; }
#fast-paging-panel .fail { color: #b00020; font-weight: bold; }`;
    document.head.appendChild(style);

    const panel = document.createElement("div");
    panel.id = "fast-paging-panel";
    panel.innerHTML = `
<div><strong>Fast paging check (issue #6)</strong></div>
<button data-run="full">Full check</button>
<button data-run="pgdn">PgDn ×40</button>
<button data-run="box">Number box ×30</button>
<pre data-out>Keep the Segmentation panel open and wait for the page image to show,
then click "Full check". The editor flips through about 25 pages in
30 seconds; leave the keyboard alone meanwhile.</pre>`;
    document.body.appendChild(panel);
    const out = panel.querySelector("[data-out]");
    const buttons = Array.from(panel.querySelectorAll("button"));

    const settledOk = (r) => r.settled.loaded && r.settled.imgMatchesPart && r.settled.scaleOk
        && (r.settled.expectedLines === null || r.settled.overlayLines === r.settled.expectedLines);
    const line = (r) => `${r.run}: ${r.pageChanges} page changes, ${r.errors} console errors`
        + ` (${r.segPanelThrows} thrown in SegPanel), ${r.staleSrc} stale image sources,`
        + ` settled ${settledOk(r) ? "OK" : "WRONG"}`;
    const sum = (runs, key) => runs.reduce((a, r) => a + r[key], 0);
    const verdict = (runs) => {
        const errors = sum(runs, "errors");
        const stale = sum(runs, "staleSrc");
        const wrong = runs.filter((r) => !settledOk(r)).length;
        if (!errors && !stale && !wrong) {
            return ["pass",
                "PASS: no console errors, no stale images, the panel matched the page shown."];
        }
        const why = [];
        if (errors) why.push(`${errors} console errors`);
        if (stale) why.push(`${stale} stale image sources`);
        if (wrong) why.push(`${wrong} run(s) settled on the wrong image, scale or overlay`);
        return ["fail", `FAIL: ${why.join(", ")}.`];
    };

    panel.addEventListener("click", async (e) => {
        const button = e.target.closest("button[data-run]");
        if (!button) return;
        let S;
        try {
            S = window.__issue6Install();
        } catch (err) {
            out.textContent = err.message;
            return;
        }
        if (!S.hasSeg) {
            out.textContent = "Segmentation panel not found. Open it from the Layout menu, "
                + "wait for the page image to show, then try again.";
            return;
        }
        buttons.forEach((b) => { b.disabled = true; });
        button.blur();
        out.textContent = "Running... the editor flips through pages; leave the keyboard alone.";
        const runs = [];
        try {
            if (button.dataset.run === "pgdn") {
                runs.push(await S.runPgDn(40, 50));
            } else if (button.dataset.run === "box") {
                runs.push(await S.runNumberBox(30, 50));
            } else {
                await S.goToOrder(0);
                runs.push(await S.runPgDn(40, 50));
                runs.push(await S.runPgDn(40, 50));
                runs.push(await S.runPgDn(40, 50));
                runs.push(await S.runNumberBox(30, 50));
            }
        } catch (err) {
            out.textContent = "The check itself failed: " + err.message;
            buttons.forEach((b) => { b.disabled = false; });
            return;
        }
        const [cls, text] = verdict(runs);
        const firstError = runs.map((r) => r.sampleStack).find(Boolean);
        out.textContent = "";
        const v = document.createElement("div");
        v.className = cls;
        v.textContent = text;
        out.appendChild(v);
        out.appendChild(document.createTextNode(
            "\n" + runs.map(line).join("\n")
            + (firstError ? "\n\nFirst error:\n    " + firstError.join("\n    ") : ""),
        ));
        buttons.forEach((b) => { b.disabled = false; });
    });
})();
