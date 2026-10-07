/**
 * Background tasks of the document, for the indicator of the editor (new UI).
 *
 * Loaded from the API when the editor opens, then again when the websocket
 * reports a change of a task: see ../taskStatus.js.
 */
import { retrieveTaskReports } from "../api";
import { coalesce, countByState, loadTasks, summarize } from "../taskStatus";

// changes come in bursts, one event per page and task: load at most this often
const REFRESH_WAIT = 2000;

const state = () => ({
    // queued or running, or ended in the last 24 hours, see sortTasks
    tasks: [],
    // false when there were too many reports to read them all
    complete: true,
    loaded: false,
    // why the last load failed, if it did; the tasks are those of the previous load
    error: null,
});

const getters = {
    counts(state) {
        return countByState(state.tasks);
    },
    summary(state, getters) {
        return summarize(getters.counts);
    },
};

const mutations = {
    setTasks(state, { tasks, complete }) {
        state.tasks = tasks;
        state.complete = complete;
        state.loaded = true;
        state.error = null;
    },
    setError(state, error) {
        state.error = error;
    },
};

let refreshSoon = null;
// number of the last load started: an older one ending after it is ignored
let lastLoad = 0;

const actions = {
    async load({ commit, rootState }) {
        const documentId = rootState.document.id;
        const load = ++lastLoad;
        try {
            const result = await loadTasks(
                async (page) => (await retrieveTaskReports(documentId, page)).data,
                Date.now(),
            );
            if (load === lastLoad) commit("setTasks", result);
        } catch (err) {
            if (load === lastLoad) {
                commit("setError", err.message || "The server could not be reached");
            }
            throw err;
        }
    },
    /**
     * Load the tasks again soon, once for a burst of calls.
     */
    refresh({ dispatch }) {
        if (!refreshSoon) {
            refreshSoon = coalesce(() => dispatch("load"), REFRESH_WAIT);
        }
        refreshSoon();
    },
};

export default {
    namespaced: true,
    state,
    getters,
    mutations,
    actions,
};
