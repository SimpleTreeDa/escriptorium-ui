/**
 * Report every request writing to the server to the saveStatus store: when it
 * starts, and whether it succeeded or failed. Requests starting a background
 * task are not edits and are left out, their panels report their own errors.
 */
const WRITE_METHODS = ["post", "put", "patch", "delete"];
const TASK_ACTIONS =
    /\/(align|cancel_tasks|export|import|segment|segtrain|share|train|transcribe)\/?$/;

// configs of the failed requests by failure id, to send them again; kept out of
// the store so that Vue does not make them reactive
const failedRequests = new Map();
let nextId = 0;
let trackedAxios = null;

export function isSaveRequest(config) {
    const method = (config.method || "get").toLowerCase();
    return WRITE_METHODS.includes(method) && !TASK_ACTIONS.test((config.url || "").split("?")[0]);
}

/**
 * What to tell the user about a failed request, and whether sending it again
 * could work: yes when the server could not be reached, failed, or refused
 * the user (logged out in the meantime), not when it rejected the data.
 */
export function describeFailure(error) {
    const status = error.response && error.response.status;
    if (!status) {
        return { message: "The server could not be reached", retryable: true };
    }
    if (status === 401 || status === 403) {
        return {
            message: "Not allowed: you may have been logged out, log in again in another tab",
            retryable: true,
        };
    }
    if (status === 408 || status === 429 || status >= 500) {
        return { message: `The server failed to save (error ${status})`, retryable: true };
    }
    return { message: `The server rejected the change (error ${status})`, retryable: false };
}

export function trackSaves(axios, store) {
    trackedAxios = axios;
    axios.interceptors.request.use((config) => {
        if (isSaveRequest(config)) {
            nextId += 1;
            config.saveTrackingId = nextId;
            store.commit("saveStatus/requestStarted");
        }
        return config;
    });
    axios.interceptors.response.use(
        (response) => {
            if (response.config && response.config.saveTrackingId) {
                store.commit("saveStatus/requestSucceeded", Date.now());
            }
            return response;
        },
        (error) => {
            const config = error.config;
            if (config && config.saveTrackingId) {
                failedRequests.set(config.saveTrackingId, config);
                store.commit("saveStatus/requestFailed", {
                    id: config.saveTrackingId,
                    method: config.method.toUpperCase(),
                    url: config.url,
                    ...describeFailure(error),
                });
            }
            return Promise.reject(error);
        },
    );
}

/**
 * Send the failed requests that may work now again, in their original order.
 * Those failing again are reported again. Resolves to the number of requests
 * sent, and whether one of them created something: the store does not know
 * about what a request sent again created, the page has to be reloaded.
 */
export async function retryFailedSaves(store) {
    const failures = store.state.saveStatus.failures.filter((failure) => failure.retryable);
    store.commit("saveStatus/removeFailures", failures.map((failure) => failure.id));
    let created = false;
    for (const failure of failures) {
        const config = failedRequests.get(failure.id);
        failedRequests.delete(failure.id);
        if (!config) continue;
        try {
            await trackedAxios.request(config);
            created = created || failure.method === "POST";
        } catch (err) {
            // reported by the interceptor
        }
    }
    return { sent: failures.length, created };
}

/**
 * Forget the failed requests, e.g. once the user reloaded the page data.
 */
export function dismissFailedSaves(store) {
    const ids = store.state.saveStatus.failures.map((failure) => failure.id);
    ids.forEach((id) => failedRequests.delete(id));
    store.commit("saveStatus/removeFailures", ids);
}
