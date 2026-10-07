// Local reverse proxy for the fast-paging check (see README.md): forwards :8082 -> :8081
// (nginx) and delays /api/ and /media/ responses so page loads overlap with fast paging,
// as they do against a real server. Without it the local API answers in under 50 ms.
//   node front/tests/manual/fast-paging/latency-proxy.js
//   PROXY_PORT, UPSTREAM_PORT, API_DELAY=120-300, MEDIA_DELAY=100-400 (ms) are optional.
const http = require("http");
const net = require("net");

const PORT = Number(process.env.PROXY_PORT || 8082);
const UP = { host: "127.0.0.1", port: Number(process.env.UPSTREAM_PORT || 8081) };
const range = (value, fallback) => (value || fallback).split("-").map(Number);
const API = range(process.env.API_DELAY, "120-300");
const MEDIA = range(process.env.MEDIA_DELAY, "100-400");
const pick = ([min, max]) => min + Math.random() * (max - min);
const kind = (url) => {
    if (url.startsWith("/api/")) return "api";
    if (url.startsWith("/media/")) return "media";
    return "other";
};
const delayFor = (url) => ({ api: pick(API), media: pick(MEDIA), other: 0 })[kind(url)];
const stats = { api: 0, media: 0, other: 0 };

const server = http.createServer((req, res) => {
    const delay = delayFor(req.url);
    stats[kind(req.url)]++;
    const upstream = http.request(
        { ...UP, method: req.method, path: req.url, headers: req.headers },
        (upRes) => {
            const send = () => {
                res.writeHead(upRes.statusCode, upRes.headers);
                upRes.pipe(res);
            };
            if (delay) setTimeout(send, delay);
            else send();
        },
    );
    upstream.on("error", (err) => {
        res.writeHead(502);
        res.end("proxy error: " + err.message);
    });
    req.pipe(upstream);
});

// websockets (/ws/): raw tunnel, no delay
server.on("upgrade", (req, socket, head) => {
    const up = net.connect(UP.port, UP.host, () => {
        const headers = Object.entries(req.headers).map(([k, v]) => `${k}: ${v}`).join("\r\n");
        up.write(`${req.method} ${req.url} HTTP/1.1\r\n${headers}\r\n\r\n`);
        if (head.length) up.write(head);
        socket.pipe(up).pipe(socket);
    });
    up.on("error", () => socket.destroy());
    socket.on("error", () => up.destroy());
});

server.listen(PORT, "127.0.0.1", () => {
    console.log(`proxy http://127.0.0.1:${PORT} -> :${UP.port}; ` +
        `/api/ ${API.join("-")}ms, /media/ ${MEDIA.join("-")}ms`);
});
setInterval(() => console.log("requests", JSON.stringify(stats)), 30000).unref();
