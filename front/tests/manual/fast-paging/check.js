#!/usr/bin/env node
// One-command setup for the fast-paging check (issue #6). See README.md.
//
//   node front/tests/manual/fast-paging/check.js [--bundle main|control] [--build] [--down]
//        [--project issue6] [--port 8081] [--proxy-port 8082]
//        [--api-delay 120-300] [--media-delay 100-400]
//
// Starts a throwaway stack from this checkout (the pulled base image with app/ and
// front/dist mounted), seeds a 200-page document, and runs a latency proxy that adds a
// test panel to the editor page. Open the printed URL, sign in, click "Full check".
//
//   --bundle main     build the current code (default; rebuilds only when needed)
//   --bundle control  build the editor without PR #9, i.e. with the bug, to see the test fail
//   --build           force a rebuild
//   --down            remove the stack and its data
//
// Ctrl+C stops the proxy; the stack keeps running until --down.
"use strict";
const { spawnSync } = require("child_process");
const fs = require("fs");
const http = require("http");
const path = require("path");
const { startProxy } = require("./latency-proxy.js");

const HERE = __dirname;
const ROOT = path.resolve(HERE, "..", "..", "..", "..");
const FRONT = path.join(ROOT, "front");
const DIST_EDITOR = path.join(FRONT, "dist", "editor.js");
const SEGPANEL = "front/vue/components/SegPanel.vue";
const FIX_COMMIT = "4773072b"; // PR #9, "Ignore stale image loads in the segmentation panel"
const FIX_MARKER = "the user moved to another page"; // a comment only PR #9's code contains
const SERVICES = ["db", "redis", "web", "channelserver", "nginx"];
const USAGE = fs.readFileSync(__filename, "utf8").split("\n")
    .slice(1).filter((l) => l.startsWith("//")).map((l) => l.slice(3)).join("\n");

const log = (...a) => console.log("[check]", ...a);
const warn = (...a) => console.warn("[check] WARNING:", ...a);
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const describe = (hasFix) => (
    hasFix ? "main (with PR #9)" : "control (without PR #9: bug present)"
);

function parseArgs(argv) {
    const o = {
        bundle: "main", build: false, down: false, help: false, project: "issue6",
        port: 8081, proxyPort: 8082, apiDelay: "120-300", mediaDelay: "100-400",
    };
    for (let i = 0; i < argv.length; i++) {
        const a = argv[i];
        const next = () => argv[++i];
        if (a === "--help" || a === "-h") o.help = true;
        else if (a === "--build") o.build = true;
        else if (a === "--down") o.down = true;
        else if (a === "--bundle") o.bundle = next();
        else if (a === "--project") o.project = next();
        else if (a === "--port") o.port = Number(next());
        else if (a === "--proxy-port") o.proxyPort = Number(next());
        else if (a === "--api-delay") o.apiDelay = next();
        else if (a === "--media-delay") o.mediaDelay = next();
        else throw new Error(`unknown option ${a} (try --help)`);
    }
    if (!["main", "control"].includes(o.bundle)) {
        throw new Error("--bundle must be main or control");
    }
    return o;
}

// Run a command to completion. Throws (never exits) so cleanup in finally blocks runs.
function run(cmd, cmdArgs, opts = {}) {
    const res = spawnSync(cmd, cmdArgs, {
        cwd: opts.cwd || ROOT,
        encoding: "utf8",
        shell: !!opts.shell, // npm is npm.cmd on Windows and needs a shell
        input: opts.input,
        stdio: [
            opts.input === undefined ? "inherit" : "pipe",
            opts.capture ? "pipe" : "inherit",
            opts.capture ? "pipe" : "inherit",
        ],
    });
    if (res.error) throw new Error(`could not run ${cmd}: ${res.error.message}`);
    if (res.status !== 0) {
        if (opts.capture) process.stderr.write((res.stdout || "") + (res.stderr || ""));
        throw new Error(`"${cmd} ${cmdArgs.join(" ")}" exited with code ${res.status}`);
    }
    return res;
}

const composeArgs = (o) => [
    "compose", "-p", o.project,
    "-f", path.join(ROOT, "docker-compose.yml"),
    "-f", path.join(HERE, "compose.dev.yml"),
];
const compose = (o, rest, opts) => run("docker", [...composeArgs(o), ...rest], opts);

function ensureEnvFile(o) {
    const envPath = path.join(ROOT, "variables.env");
    const origins = `http://127.0.0.1:${o.port},http://127.0.0.1:${o.proxyPort}`;
    if (!fs.existsSync(envPath)) {
        const example = fs.readFileSync(path.join(ROOT, "variables.env_example"), "utf8");
        fs.writeFileSync(envPath, example.replace(/^CSRF_TRUSTED_ORIGINS=.*$/m,
            `CSRF_TRUSTED_ORIGINS=${origins}`));
        log(`created variables.env from variables.env_example (CSRF_TRUSTED_ORIGINS=${origins})`);
    } else if (!fs.readFileSync(envPath, "utf8").includes(`127.0.0.1:${o.proxyPort}`)) {
        warn(`variables.env: add http://127.0.0.1:${o.proxyPort} to CSRF_TRUSTED_ORIGINS, `
            + "or signing in through the proxy fails with a CSRF error");
    }
    return envPath;
}

const distHasFix = () => fs.existsSync(DIST_EDITOR)
    && fs.readFileSync(DIST_EDITOR, "utf8").includes(FIX_MARKER);

function build() {
    if (!fs.existsSync(path.join(FRONT, "node_modules"))) {
        log("installing front-end dependencies (npm ci)...");
        run("npm", ["ci", "--no-audit", "--no-fund"], { cwd: FRONT, shell: true });
    }
    log("building the editor bundle (npm run build: development mode, readable stack traces)...");
    run("npm", ["run", "build"], { cwd: FRONT, shell: true });
}

function ensureBundle(o) {
    const exists = fs.existsSync(DIST_EDITOR);
    const hasFix = exists && distHasFix();
    const wantFix = o.bundle === "main";
    if (!o.build && exists && hasFix === wantFix) {
        log(`bundle: ${describe(hasFix)} (already built)`);
        return;
    }
    if (o.bundle === "control") {
        const status = run("git", ["status", "--porcelain", "--", SEGPANEL], { capture: true });
        const dirty = status.stdout.trim();
        if (dirty) throw new Error(`${SEGPANEL} has local changes; commit or stash them first`);
        const patch = run("git", ["show", FIX_COMMIT, "--", SEGPANEL], { capture: true }).stdout;
        run("git", ["apply", "-R", "--check"], { input: patch, capture: true });
        run("git", ["apply", "-R"], { input: patch, capture: true });
        log(`reverse-applied PR #9 (${FIX_COMMIT}) to ${SEGPANEL} for the control build`);
        try {
            build();
        } finally {
            run("git", ["checkout", "--", SEGPANEL]);
            log(`restored ${SEGPANEL}`);
        }
    } else {
        build();
    }
    if (distHasFix() !== wantFix) throw new Error("the built bundle is not the one requested");
    log(`bundle: ${describe(distHasFix())}`);
}

const httpStatus = (url) => new Promise((resolve) => {
    const req = http.get(url, (res) => {
        res.resume();
        resolve(res.statusCode);
    });
    req.on("error", () => resolve(0));
    req.setTimeout(5000, () => {
        req.destroy();
        resolve(0);
    });
});

async function waitForStack(o) {
    const url = `http://127.0.0.1:${o.port}/login/`;
    const deadline = Date.now() + 10 * 60 * 1000;
    log("waiting for the stack (the first start runs migrations; this can take a few minutes)...");
    while (Date.now() < deadline) {
        if (await httpStatus(url) === 200) {
            log(`stack is up at http://127.0.0.1:${o.port}`);
            return;
        }
        await sleep(3000);
    }
    throw new Error(`the stack did not answer at ${url} within 10 minutes; `
        + `see "docker compose -p ${o.project} logs web nginx"`);
}

function seed(o) {
    log("seeding the 200-page test document (kept if it already exists)...");
    const res = compose(o, ["exec", "-T", "web", "python", "manage.py", "shell"], {
        input: fs.readFileSync(path.join(HERE, "seed.py"), "utf8"), capture: true,
    });
    const m = /EDITOR_URL (\S+)/.exec(res.stdout);
    if (!m) throw new Error("seed.py did not print the editor URL:\n" + res.stdout + res.stderr);
    return m[1];
}

async function main() {
    const o = parseArgs(process.argv.slice(2));
    if (o.help) {
        console.log(USAGE);
        return;
    }
    run("docker", ["compose", "version"], { capture: true });
    if (o.down) {
        compose(o, ["down", "-v"]);
        log(`stack "${o.project}" and its data removed`);
        return;
    }
    const envPath = ensureEnvFile(o);
    ensureBundle(o);
    log(`starting the stack "${o.project}"...`);
    compose(o, ["up", "-d", "--no-build", ...SERVICES]);
    await waitForStack(o);
    log("publishing the bundle (collectstatic)...");
    compose(o, ["exec", "-T", "web", "python", "manage.py", "collectstatic", "--no-input"],
        { capture: true });
    const editorUrl = seed(o);
    const envText = fs.readFileSync(envPath, "utf8");
    const user = (/^DJANGO_SU_NAME=(.*)$/m.exec(envText) || [null, "admin"])[1].trim();

    startProxy({
        port: o.proxyPort, upstreamPort: o.port, apiDelay: o.apiDelay, mediaDelay: o.mediaDelay,
        injectDir: HERE, log,
    });
    const self = path.relative(process.cwd(), __filename) || __filename;
    console.log(`
Ready. Bundle under test: ${describe(distHasFix())}

  1. Open      http://127.0.0.1:${o.proxyPort}${editorUrl}
  2. Sign in as "${user}" (DJANGO_SU_PASSWORD in variables.env).
  3. Keep the Segmentation panel open and wait for the page image to show.
  4. In the "Fast paging check" box at the bottom right, click "Full check"
     and wait about 30 seconds.

  Expected: PASS with --bundle main, FAIL with --bundle control.
  Same page without added latency: http://127.0.0.1:${o.port}${editorUrl}

Ctrl+C stops the proxy (the stack keeps running).
Remove the stack and its data:  node ${self} --down
`);
    process.on("SIGINT", () => {
        console.log("\nproxy stopped; the stack is still running (remove it with --down)");
        process.exit(0);
    });
}

main().catch((err) => {
    console.error("\n[check] error:", err.message);
    process.exit(1);
});
