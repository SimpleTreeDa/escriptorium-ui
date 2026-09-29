/**
 * Whether the user's edits in the editor have reached the server.
 *
 * Requests that write to the server are counted by the axios interceptors in
 * ../saveTracking.js; edits typed but not sent yet are reported by the panels
 * holding them with setUnsaved.
 */
const state = () => ({
    // write requests sent and not answered yet
    pending: 0,
    // keys of the panels holding edits not sent yet, e.g. "diplomatic", "line"
    unsaved: [],
    // write requests that failed: { id, method, url, message, retryable }
    failures: [],
    // time of the last successful write, in ms
    lastSavedAt: null,
});

const getters = {
    /**
     * One of "failed", "saving", "unsaved" or "saved", the first that applies:
     * a failed write stays reported until it is retried or dismissed.
     */
    status(state) {
        if (state.failures.length) return "failed";
        if (state.pending) return "saving";
        if (state.unsaved.length) return "unsaved";
        return "saved";
    },
    /**
     * True if leaving the page now could lose edits.
     */
    hasUnsavedWork(state, getters) {
        return getters.status !== "saved";
    },
    canRetry(state) {
        return state.failures.some((failure) => failure.retryable);
    },
};

const mutations = {
    requestStarted(state) {
        state.pending += 1;
    },
    requestSucceeded(state, savedAt) {
        state.pending = Math.max(state.pending - 1, 0);
        state.lastSavedAt = savedAt;
    },
    requestFailed(state, failure) {
        state.pending = Math.max(state.pending - 1, 0);
        state.failures = [...state.failures, failure];
    },
    setUnsaved(state, { key, unsaved }) {
        const others = state.unsaved.filter((k) => k !== key);
        state.unsaved = unsaved ? [...others, key] : others;
    },
    removeFailures(state, ids) {
        state.failures = state.failures.filter((failure) => !ids.includes(failure.id));
    },
};

export default {
    namespaced: true,
    state,
    getters,
    mutations,
};
