// Local reverse proxy for the fast-paging check (see README.md): forwards :8082 -> :8081
// (nginx) and delays /api/ and /media/ responses so page loads overlap with fast paging,
// as they do against a real server. Without it the local API answers in under 50 ms.
//
// Standalone:
//   node front/tests/manual/fast-paging/latency-proxy.js
//   PROXY_PORT, UPSTREAM_PORT, API_DELAY=120-300, MEDIA_DELAY=100-400 (ms) are optional.
// From check.js: startProxy({ injectDir }) also adds the test panel (driver.js + panel.js)
// to editor pages and serves those two files under /__fast-paging/.
const fs = require("fs");
const http = require("http");
const net = require("net");
const path = require("path");

const EDITOR_PAGE = /^\/document\/\d+\/(part\/\d+\/)?edit\/?(\?.*)?$/;
const TEST_FILES = ["driver.js", "panel.js"];
const TEST_TAGS = TEST_FILES.map((f) => `<script src="/__fast-paging/${f}"></script>`).join("\n");

const parseRange = (value, fallback) => String(value || fallback).split("-").map(Number);
const pick = ([min, max]) => min + Math.random() * (max - min);
const kind = (url) => {
    if (url.startsWith("/api/")) return "api";
    if (url.startsWith("/media/")) return "media";
    return "other";
};

function serveTestFile(injectDir, req, res) {
    const name = path.basename(req.url.split("?")[0]);
    if (!TEST_FILES.includes(name)) {
        res.writeHead(404);
        res.end();
        return;
    }
    fs.readFile(path.join(injectDir, name), (err, data) => {
        if (err) {
            res.writeHead(500);
            res.end(err.message);
            return;
        }
        res.writeHead(200, {
            "content-type": "application/javascript; charset=utf-8",
            "cache-control": "no-store",
        });
        res.end(data);
    });
}

function startProxy(options = {}) {
    const port = Number(options.port || process.env.PROXY_PORT || 8082);
    const upstream = {
        host: "127.0.0.1",
        port: Number(options.upstreamPort || process.env.UPSTREAM_PORT || 8081),
    };
    const api = parseRange(options.apiDelay || process.env.API_DELAY, "120-300");
    const media = parseRange(options.mediaDelay || process.env.MEDIA_DELAY, "100-400");
    const injectDir = options.injectDir || null;
    const delays = { api, media };
    const stats = { api: 0, media: 0, other: 0 };
    const log = options.log || console.log;

    const server = http.createServer((req, res) => {
        if (injectDir && req.url.startsWith("/__fast-paging/")) {
            serveTestFile(injectDir, req, res);
            return;
        }
        const k = kind(req.url);
        stats[k]++;
        const delay = delays[k] ? pick(delays[k]) : 0;
        const inject = !!injectDir && EDITOR_PAGE.test(req.url);
        const headers = { ...req.headers };
        if (inject) headers["accept-encoding"] = "identity"; // plain text so we can edit it

        const upReq = http.request(
            { ...upstream, method: req.method, path: req.url, headers },
            (upRes) => {
                const isHtml = /text\/html/.test(upRes.headers["content-type"] || "");
                if (inject && isHtml) {
                    const chunks = [];
                    upRes.on("data", (c) => chunks.push(c));
                    upRes.on("end", () => {
                        const body = Buffer.concat(chunks).toString("utf8")
                            .replace(/<\/body>/i, `${TEST_TAGS}\n</body>`);
                        const h = { ...upRes.headers, "content-length": Buffer.byteLength(body) };
                        delete h["transfer-encoding"];
                        delete h["content-encoding"];
                        res.writeHead(upRes.statusCode, h);
                        res.end(body);
                    });
                    return;
                }
                const send = () => {
                    res.writeHead(upRes.statusCode, upRes.headers);
                    upRes.pipe(res);
                };
                if (delay) setTimeout(send, delay);
                else send();
            },
        );
        upReq.on("error", (err) => {
            res.writeHead(502);
            res.end("proxy error: " + err.message);
        });
        req.pipe(upReq);
    });

    // websockets (/ws/): raw tunnel, no delay
    server.on("upgrade", (req, socket, head) => {
        const up = net.connect(upstream.port, upstream.host, () => {
            const headers = Object.entries(req.headers).map(([k, v]) => `${k}: ${v}`).join("\r\n");
            up.write(`${req.method} ${req.url} HTTP/1.1\r\n${headers}\r\n\r\n`);
            if (head.length) up.write(head);
            socket.pipe(up).pipe(socket);
        });
        up.on("error", () => socket.destroy());
        socket.on("error", () => up.destroy());
    });

    server.on("error", (err) => {
        log(`proxy could not listen on 127.0.0.1:${port}: ${err.message} `
            + "(is another check.js or latency-proxy.js still running?)");
        process.exitCode = 1;
    });
    server.listen(port, "127.0.0.1", () => {
        log(`proxy http://127.0.0.1:${port} -> :${upstream.port}; ` +
            `/api/ ${api.join("-")}ms, /media/ ${media.join("-")}ms` +
            (injectDir ? "; test panel added to editor pages" : ""));
    });
    server.stats = stats;
    setInterval(() => log("requests", JSON.stringify(stats)), 60000).unref();
    return server;
}

module.exports = { startProxy };

if (require.main === module) startProxy();
