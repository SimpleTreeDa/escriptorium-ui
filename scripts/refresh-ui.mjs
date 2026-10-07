#!/usr/bin/env node
// Fast UI refresh: build the frontend bundles on the host and copy them into
// the running containers. No image rebuild, no container restart.
//
//   node scripts/refresh-ui.mjs            build once, sync, exit
//   node scripts/refresh-ui.mjs --watch    rebuild + sync on every file save
//   npm run ui  /  npm run ui:watch
//
// How it works: at container start, Django's `collectstatic` copies front/dist
// into the shared `static` volume at /usr/src/app/static, which nginx serves
// directly at /static/. Bundle names are fixed (main.js, editor.js, ...), so
// replacing the files in that volume is enough. A browser refresh then shows
// the change.
//
// Note: restarting the `web` container re-runs collectstatic and restores the
// bundles baked into the image. Run this script again afterwards, or run
// scripts/rebuild.mjs to bake the new frontend into the image.
import fs from "node:fs";
import { createRequire } from "node:module";
import os from "node:os";
import path from "node:path";
import {
    CONTAINER_STATIC, DIST, FRONT, composeRunner, fail, log, parseArgs, resolveDocker, run,
} from "./lib.mjs";

const help = `Usage: node scripts/refresh-ui.mjs [options]

Builds the webpack bundles in front/ and copies them into the running
containers so the change is visible on the next browser refresh.

Options:
  --watch      Keep running; rebuild and sync whenever a source file changes.
  --prod       Use the production webpack config (same output as the docker
               image). Default is the development config, which builds faster.
  --no-sync    Only build; do not copy anything into the containers.
  --sudo       Run docker through sudo (auto-detected on Linux when needed).
  -h, --help   Show this help.`;

const opts = parseArgs(process.argv.slice(2), {
    defaults: { watch: false, prod: false, sync: true, sudo: false },
    flags: {
        "--watch": { watch: true },
        "--prod": { prod: true },
        "--no-sync": { sync: false },
        "--sudo": { sudo: true },
    },
    help,
});

// --- frontend toolchain -----------------------------------------------------

if (!fs.existsSync(path.join(FRONT, "node_modules"))) {
    log("front/node_modules is missing, running npm ci");
    run("npm", ["ci"], { cwd: FRONT });
}

// webpack (and vue-loader's compiler lookup) resolve relative paths from the
// current working directory, so behave exactly as if run from inside front/.
process.chdir(FRONT);
const requireFromFront = createRequire(path.join(FRONT, "package.json"));
const webpack = requireFromFront("webpack");
const config = requireFromFront(opts.prod ? "./webpack.prod.js" : "./webpack.dev.js");
config.context ??= FRONT;
const compiler = webpack(config);

// --- container sync ----------------------------------------------------------

let compose = null;
if (opts.sync) {
    compose = composeRunner(resolveDocker({ sudo: opts.sudo }));
    const running = compose(["ps", "-q", "--status", "running", "web"], { quiet: true, allowFailure: true });
    if (running.status !== 0 || !String(running.stdout).trim()) {
        fail("The web container is not running. Start the stack first (npm run rebuild, or docker compose up -d).");
    }
}

let firstSync = true;

// Copy either the whole dist directory (first time, so the container matches
// the local build exactly) or just the assets webpack emitted in this build.
function syncToContainer(emitted) {
    if (!compose) return;

    let source;
    let cleanup = () => {};
    if (firstSync) {
        source = DIST;
        log(`Copying all of front/dist into web:${CONTAINER_STATIC}`);
    } else {
        if (emitted.length === 0) {
            log("No assets changed, nothing to sync");
            return;
        }
        const staging = fs.mkdtempSync(path.join(os.tmpdir(), "escr-ui-"));
        for (const name of emitted) {
            const dest = path.join(staging, name);
            fs.mkdirSync(path.dirname(dest), { recursive: true });
            fs.copyFileSync(path.join(DIST, name), dest);
        }
        source = staging;
        cleanup = () => fs.rmSync(staging, { recursive: true, force: true });
        log(`Copying ${emitted.length} changed asset(s) into web:${CONTAINER_STATIC}`);
    }

    try {
        // A trailing "/." copies the directory contents rather than the directory itself.
        compose(["cp", `${source}${path.sep}.`, `web:${CONTAINER_STATIC}`], { quiet: true });
        firstSync = false;
        log("Synced. Refresh the browser to see the change.");
    } finally {
        cleanup();
    }
}

function report(err, stats) {
    if (err) {
        console.error(err.stack || err);
        return false;
    }
    const info = stats.toJson({ all: false, errors: true, warnings: true, timings: true });
    for (const w of info.warnings) console.warn(`\x1b[33m${w.message}\x1b[0m`);
    for (const e of info.errors) console.error(`\x1b[31m${e.message}\x1b[0m`);
    if (stats.hasErrors()) {
        log("Build failed, not syncing");
        return false;
    }
    log(`Built in ${(info.time / 1000).toFixed(1)}s`);
    return true;
}

function emittedAssets(stats) {
    return [...stats.compilation.emittedAssets];
}

// --- run ---------------------------------------------------------------------

const mode = opts.prod ? "production" : "development";

if (opts.watch) {
    log(`Watching front/ for changes (${mode} config). Ctrl+C to stop.`);
    const watching = compiler.watch({ aggregateTimeout: 200 }, (err, stats) => {
        if (report(err, stats)) syncToContainer(emittedAssets(stats));
    });
    const stop = () => watching.close(() => process.exit(0));
    process.on("SIGINT", stop);
    process.on("SIGTERM", stop);
} else {
    log(`Building frontend (${mode} config)`);
    compiler.run((err, stats) => {
        const ok = report(err, stats);
        if (ok) syncToContainer(emittedAssets(stats));
        compiler.close(() => process.exit(ok ? 0 : 1));
    });
}
