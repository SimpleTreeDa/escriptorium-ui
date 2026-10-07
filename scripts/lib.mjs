// Shared helpers for the dev scripts in this directory.
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
export const FRONT = path.join(ROOT, "front");
export const DIST = path.join(FRONT, "dist");

// Where collectstatic puts the frontend bundles inside the containers.
// This directory is the shared `static` volume that nginx serves at /static/.
export const CONTAINER_STATIC = "/usr/src/app/static/";

export function parseArgs(argv, spec) {
    const opts = { ...spec.defaults };
    for (const arg of argv) {
        if (arg === "-h" || arg === "--help") {
            console.log(spec.help);
            process.exit(0);
        }
        const flag = spec.flags[arg];
        if (!flag) {
            console.error(`Unknown option: ${arg}\n`);
            console.error(spec.help);
            process.exit(2);
        }
        Object.assign(opts, flag);
    }
    return opts;
}

export function log(msg) {
    console.log(`\x1b[36m> ${msg}\x1b[0m`);
}

export function fail(msg) {
    console.error(`\x1b[31mERROR: ${msg}\x1b[0m`);
    process.exit(1);
}

// Run a command, streaming its output. Exits the process on failure unless
// `allowFailure` is set, in which case the result is returned for inspection.
export function run(cmd, args, { cwd = ROOT, allowFailure = false, quiet = false } = {}) {
    if (!quiet) console.log(`\x1b[2m$ ${[cmd, ...args].join(" ")}\x1b[0m`);
    const res = spawnSync(cmd, args, {
        cwd,
        stdio: quiet ? "pipe" : "inherit",
        shell: process.platform === "win32",
    });
    if (res.error) fail(`Could not run ${cmd}: ${res.error.message}`);
    if (res.status !== 0 && !allowFailure) {
        fail(`${cmd} ${args[0] ?? ""} exited with code ${res.status}`);
    }
    return res;
}

// Work out how to invoke docker. On Linux the daemon socket is often only
// accessible to root, so fall back to `sudo docker` when plain `docker` cannot
// reach the daemon. Pass --sudo (or set DOCKER_SUDO=1) to force it.
export function resolveDocker({ sudo = false } = {}) {
    const forceSudo = sudo || process.env.DOCKER_SUDO === "1";
    const canSudo = process.platform !== "win32";

    if (forceSudo) {
        if (!canSudo) fail("--sudo is not supported on Windows");
        return ["sudo", "docker"];
    }
    const probe = spawnSync("docker", ["version", "--format", "{{.Server.Version}}"], {
        stdio: "pipe",
        shell: process.platform === "win32",
    });
    if (probe.status === 0) return ["docker"];
    if (probe.error?.code === "ENOENT") fail("docker was not found on PATH");

    const isRoot = typeof process.getuid === "function" && process.getuid() === 0;
    if (canSudo && !isRoot) {
        log("docker daemon not reachable as the current user, using sudo");
        return ["sudo", "docker"];
    }
    fail("docker daemon is not reachable. Is Docker running?");
}

// Returns a function that runs `docker compose <args>` with the resolved prefix.
export function composeRunner(docker) {
    return (args, opts) => run(docker[0], [...docker.slice(1), "compose", ...args], opts);
}
