#!/usr/bin/env node
// Full rebuild: stop the stack, rebuild the images, start everything again.
//
//   node scripts/rebuild.mjs [--no-cache] [--no-wait] [--sudo]
//   npm run rebuild          (or: npm run rebuild:clean for --no-cache)
//
// Use this when backend code, templates, Dockerfiles or dependencies changed.
// For frontend-only changes, scripts/refresh-ui.mjs is much faster.
import { composeRunner, log, parseArgs, resolveDocker } from "./lib.mjs";

const help = `Usage: node scripts/rebuild.mjs [options]

Stops the docker compose stack, rebuilds the images and starts it again.

Options:
  --no-cache   Rebuild every image layer from scratch (slow). Only needed when
               the base image, apt packages or the npm registry changed; a
               normal cached build already picks up all code changes.
  --no-wait    Return as soon as containers are started instead of waiting for
               the web healthcheck to pass.
  --sudo       Run docker through sudo (auto-detected on Linux when needed).
  -h, --help   Show this help.`;

const opts = parseArgs(process.argv.slice(2), {
    defaults: { noCache: false, wait: true, sudo: false },
    flags: {
        "--no-cache": { noCache: true },
        "--no-wait": { wait: false },
        "--sudo": { sudo: true },
    },
    help,
});

const compose = composeRunner(resolveDocker({ sudo: opts.sudo }));
const started = Date.now();

log("Stopping containers");
compose(["down"]);

log(opts.noCache ? "Building images (no cache)" : "Building images");
compose(["build", ...(opts.noCache ? ["--no-cache"] : [])]);

log(opts.wait ? "Starting containers and waiting for them to be healthy" : "Starting containers");
compose(["up", "-d", ...(opts.wait ? ["--wait"] : [])]);

log("Container status");
compose(["ps"]);

const port = compose(["port", "nginx", "80"], { quiet: true, allowFailure: true });
const address = port.status === 0
    ? String(port.stdout).trim().replace(/^0\.0\.0\.0/, "localhost")
    : null;
const minutes = ((Date.now() - started) / 60000).toFixed(1);
log(`Done in ${minutes} min.${address ? ` App should be reachable at http://${address}/` : ""}`);
