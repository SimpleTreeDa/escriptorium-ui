// Run with `npm test` (Node 22 or later, no other dependency).
import assert from "node:assert/strict";
import { beforeEach, describe, test } from "node:test";
import Vue from "vue";
import Vuex, { Store } from "vuex";
import saveStatus from "../src/editor/store/saveStatus.js";
import {
    describeFailure,
    dismissFailedSaves,
    isSaveRequest,
    retryFailedSaves,
    trackSaves,
} from "../src/editor/saveTracking.js";

Vue.use(Vuex);

const newStore = () => new Store({ modules: { saveStatus } });
const status = (store) => store.getters["saveStatus/status"];

/**
 * Enough of axios to run the interceptors: `respond(config)` plays the server,
 * resolving to the response data or throwing an error with `response.status`
 * (no `response` for a network error).
 */
function fakeAxios(respond) {
    const requestInterceptors = [];
    const responseInterceptors = [];
    const axios = {
        sent: [],
        interceptors: {
            request: { use: (fn) => requestInterceptors.push(fn) },
            response: { use: (ok, ko) => responseInterceptors.push([ok, ko]) },
        },
        request(config) {
            let cfg = { ...config };
            requestInterceptors.forEach((fn) => { cfg = fn(cfg); });
            axios.sent.push(cfg);
            let promise = new Promise((resolve) => setTimeout(resolve, 0))
                .then(() => respond(cfg))
                .then(
                    (data) => ({ config: cfg, data }),
                    (err) => Promise.reject(Object.assign(err, { config: cfg })),
                );
            responseInterceptors.forEach(([ok, ko]) => { promise = promise.then(ok, ko); });
            return promise;
        },
    };
    return axios;
}

const httpError = (status) => Object.assign(new Error("HTTP " + status), { response: { status } });

describe("saveStatus store", () => {
    let store;
    beforeEach(() => { store = newStore(); });

    test("starts saved", () => {
        assert.equal(status(store), "saved");
        assert.equal(store.getters["saveStatus/hasUnsavedWork"], false);
    });

    test("saving while requests are pending, then saved", () => {
        store.commit("saveStatus/requestStarted");
        store.commit("saveStatus/requestStarted");
        assert.equal(status(store), "saving");
        store.commit("saveStatus/requestSucceeded", 1000);
        assert.equal(status(store), "saving");
        store.commit("saveStatus/requestSucceeded", 2000);
        assert.equal(status(store), "saved");
        assert.equal(store.state.saveStatus.lastSavedAt, 2000);
    });

    test("unsaved edits are counted once per panel", () => {
        store.commit("saveStatus/setUnsaved", { key: "diplomatic", unsaved: true });
        store.commit("saveStatus/setUnsaved", { key: "diplomatic", unsaved: true });
        store.commit("saveStatus/setUnsaved", { key: "line", unsaved: true });
        assert.equal(status(store), "unsaved");
        assert.equal(store.getters["saveStatus/hasUnsavedWork"], true);
        store.commit("saveStatus/setUnsaved", { key: "diplomatic", unsaved: false });
        assert.equal(status(store), "unsaved");
        store.commit("saveStatus/setUnsaved", { key: "line", unsaved: false });
        assert.equal(status(store), "saved");
    });

    test("saving takes precedence over unsaved, a failure over both", () => {
        store.commit("saveStatus/setUnsaved", { key: "line", unsaved: true });
        store.commit("saveStatus/requestStarted");
        store.commit("saveStatus/requestStarted");
        assert.equal(status(store), "saving");
        store.commit("saveStatus/requestFailed", { id: 1, retryable: true });
        assert.equal(status(store), "failed");
        // later successful saves do not hide the failure
        store.commit("saveStatus/requestSucceeded", 1000);
        store.commit("saveStatus/setUnsaved", { key: "line", unsaved: false });
        assert.equal(status(store), "failed");
        assert.equal(store.getters["saveStatus/canRetry"], true);
        store.commit("saveStatus/removeFailures", [1]);
        assert.equal(status(store), "saved");
    });

    test("pending never goes negative", () => {
        store.commit("saveStatus/requestSucceeded", 1000);
        store.commit("saveStatus/requestStarted");
        assert.equal(status(store), "saving");
    });
});

describe("which requests are saves", () => {
    test("writes are, reads are not", () => {
        const part = "/documents/1/parts/2";
        assert.equal(isSaveRequest({ method: "put", url: `${part}/lines/bulk_update/` }), true);
        assert.equal(isSaveRequest({ method: "POST", url: `${part}/transcriptions/` }), true);
        assert.equal(isSaveRequest({ method: "delete", url: `${part}/blocks/3/` }), true);
        assert.equal(isSaveRequest({ method: "get", url: "/documents/1/parts/2/" }), false);
        assert.equal(isSaveRequest({ url: "/documents/1/" }), false);
    });

    test("starting a background task is not a save", () => {
        for (const action of ["segment", "transcribe", "train", "segtrain", "align", "export",
            "import", "cancel_tasks", "share"]) {
            const url = `/documents/1/${action}/`;
            assert.equal(isSaveRequest({ method: "post", url }), false, action);
        }
        // creating a transcription layer is
        assert.equal(isSaveRequest({ method: "post", url: "/documents/1/transcriptions/" }), true);
    });

    test("only failures that may pass later are retryable", () => {
        assert.equal(describeFailure(new Error("Network Error")).retryable, true);
        for (const code of [401, 403, 408, 429, 500, 502, 503]) {
            assert.equal(describeFailure(httpError(code)).retryable, true, code);
        }
        for (const code of [400, 404, 409]) {
            assert.equal(describeFailure(httpError(code)).retryable, false, code);
        }
    });
});

describe("request tracking", () => {
    let store;
    let server;
    let axios;
    beforeEach(() => {
        store = newStore();
        server = { fail: null };
        axios = fakeAxios((config) => {
            if (server.fail) throw server.fail;
            return { ok: config.url };
        });
        trackSaves(axios, store);
    });

    test("a write is saving until the server answers", async () => {
        const url = "/documents/1/parts/2/transcriptions/3/";
        const request = axios.request({ method: "put", url });
        assert.equal(status(store), "saving");
        await request;
        assert.equal(status(store), "saved");
        assert.ok(store.state.saveStatus.lastSavedAt);
    });

    test("reads do not change the status", async () => {
        const request = axios.request({ method: "get", url: "/documents/1/" });
        assert.equal(status(store), "saved");
        await request;
        assert.equal(status(store), "saved");
    });

    test("a failed write is reported even when the caller swallows the error", async () => {
        server.fail = httpError(500);
        try {
            const url = "/documents/1/parts/2/transcriptions/bulk_create/";
            await axios.request({ method: "post", url });
        } catch (err) {
            // the editor's store actions only log the error
        }
        assert.equal(status(store), "failed");
        const [failure] = store.state.saveStatus.failures;
        assert.equal(failure.method, "POST");
        assert.equal(failure.url, "/documents/1/parts/2/transcriptions/bulk_create/");
        assert.equal(failure.retryable, true);
        assert.match(failure.message, /500/);
    });

    test("retrying sends the failed writes again, in order", async () => {
        server.fail = new Error("Network Error");
        const part = "/documents/1/parts/2";
        const first = { method: "put", url: `${part}/lines/bulk_update/`, data: "{\"a\":1}" };
        const second = { method: "post", url: `${part}/transcriptions/`, data: "{\"b\":2}" };
        await axios.request(first).catch(() => {});
        await axios.request(second).catch(() => {});
        assert.equal(store.state.saveStatus.failures.length, 2);

        server.fail = null;
        axios.sent = [];
        const result = await retryFailedSaves(store);
        assert.deepEqual(axios.sent.map((config) => [config.url, config.data]), [
            [first.url, first.data], [second.url, second.data],
        ]);
        assert.deepEqual(result, { sent: 2, created: true });
        assert.equal(status(store), "saved");
    });

    test("a write failing again on retry is reported again", async () => {
        server.fail = httpError(503);
        const request = axios.request({ method: "patch", url: "/documents/1/parts/2/" });
        await request.catch(() => {});
        await retryFailedSaves(store);
        assert.equal(status(store), "failed");
        assert.equal(store.state.saveStatus.failures.length, 1);
    });

    test("rejected changes are not retried but can be dismissed", async () => {
        server.fail = httpError(400);
        const url = "/documents/1/parts/2/lines/bulk_update/";
        await axios.request({ method: "put", url }).catch(() => {});
        assert.equal(store.getters["saveStatus/canRetry"], false);
        server.fail = null;
        axios.sent = [];
        const result = await retryFailedSaves(store);
        assert.equal(result.sent, 0);
        assert.equal(axios.sent.length, 0);
        assert.equal(status(store), "failed");
        dismissFailedSaves(store);
        assert.equal(status(store), "saved");
    });
});
