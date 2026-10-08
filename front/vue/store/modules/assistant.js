import axios from "axios";
import { retrieveProjects, sendChat } from "../../../src/api";
import {
    canSend,
    errorMessage,
    makeMessage,
    parseChatResponse,
    projectChoices,
    toApiMessages,
} from "../../../src/assistant/chat";

// initial state
const state = () => ({
    /**
     * What went wrong with the last question, or "" when it was answered.
     */
    error: "",
    /**
     * Whether a question is waiting for its answer.
     */
    loading: false,
    /**
     * The conversation, kept for the life of the page and sent in full with
     * every question (the server is stateless):
     * messages: [{
     *     id: Number,
     *     role: "user" | "assistant",
     *     content: String,
     *     at: String (ISO date),
     *     model?: String,
     * }]
     */
    messages: [],
    /**
     * The pk of the project the questions are about, or null for all of them.
     */
    project: null,
    /**
     * projects: [{ pk: Number, name: String }], for the project focus menu
     */
    projects: [],
});

const getters = {};

const actions = {
    /**
     * Send the conversation so far and append the answer. On failure, keep the
     * question in place and set the error, so that the user can retry.
     */
    async ask({ commit, state }) {
        commit("setError", "");
        commit("setLoading", true);
        try {
            const { data } = await sendChat({
                messages: toApiMessages(state.messages),
                project: state.project,
            });
            const reply = parseChatResponse(data);
            commit("addMessage", makeMessage("assistant", reply.content, { model: reply.model }));
        } catch (error) {
            commit("setError", errorMessage(error));
        } finally {
            commit("setLoading", false);
        }
    },
    /**
     * Fetch the projects the user can see, every page of them, for the focus menu.
     */
    async fetchProjects({ commit, dispatch }) {
        try {
            const { data } = await retrieveProjects({});
            let projects = data?.results || [];
            let nextPage = data?.next;
            while (nextPage) {
                const res = await axios.get(nextPage);
                nextPage = res.data?.next;
                projects = [...projects, ...(res.data?.results || [])];
            }
            commit("setProjects", projectChoices(projects));
        } catch (error) {
            dispatch("alerts/addError", error, { root: true });
        }
    },
    /**
     * Start over: forget the conversation and any error.
     */
    reset({ commit }) {
        commit("setMessages", []);
        commit("setError", "");
    },
    /**
     * Ask again with the same conversation, after a failure.
     */
    async retry({ dispatch, state }) {
        if (state.loading || !state.messages.length) return;
        await dispatch("ask");
    },
    /**
     * Ask a new question: append it to the conversation and send everything.
     */
    async send({ commit, dispatch, state }, text) {
        if (!canSend(text, state.loading)) return;
        commit("addMessage", makeMessage("user", text.trim()));
        await dispatch("ask");
    },
    /**
     * Focus the next questions on one project (pk), or on all of them (null).
     */
    setProject({ commit }, project) {
        commit("setProject", project);
    },
};

const mutations = {
    addMessage(state, message) {
        state.messages.push(message);
    },
    setError(state, error) {
        state.error = error;
    },
    setLoading(state, loading) {
        state.loading = loading;
    },
    setMessages(state, messages) {
        state.messages = messages;
    },
    setProject(state, project) {
        state.project = project;
    },
    setProjects(state, projects) {
        state.projects = projects;
    },
};

export default {
    namespaced: true,
    state,
    getters,
    actions,
    mutations,
};
