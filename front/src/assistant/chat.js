/*
 * AI Chat (new UI): the conversation with the assistant, kept in the browser
 * for the life of the page and sent in full with every question to
 * /api/assistant/chat/. The server adds its own system prompt and the
 * snapshot of the user's projects and tasks, and talks to the model.
 *
 * No DOM and no network here, so `npm test` covers these helpers; the store
 * module (vue/store/modules/assistant.js) and the page do the rest.
 */

/** Most messages of the history sent with a question (the server keeps as many) */
export const MAX_HISTORY = 20;

/** Longest question the server accepts, in characters */
export const MAX_CONTENT_LENGTH = 8000;

/** Questions offered on an empty conversation */
export const SUGGESTED_QUESTIONS = [
    "What's currently happening with my projects?",
    "What tasks are still open?",
    "What should I work on next?",
    "What has changed recently?",
];

/** Shown when a reply of the server carries no answer */
export const EMPTY_RESPONSE =
    "The assistant returned no answer. Try again, or rephrase the question.";

const ROLES = ["user", "assistant"];
let nextId = 1;

/** A message of the conversation, with a key for rendering and its time */
export function makeMessage(role, content, extra = {}) {
    return { id: nextId++, role, content, at: new Date().toISOString(), ...extra };
}

/**
 * The history as the API takes it: user and assistant messages only, with
 * their role and content only, the last `limit` of them.
 */
export function toApiMessages(history, limit = MAX_HISTORY) {
    return (Array.isArray(history) ? history : [])
        .filter((m) => (
            m && ROLES.includes(m.role) && typeof m.content === "string" && m.content.trim()
        ))
        .slice(-limit)
        .map(({ role, content }) => ({ role, content }));
}

/**
 * The answer in a reply of /api/assistant/chat/; throws when there is none.
 */
export function parseChatResponse(data) {
    const content = data?.message?.content;
    if (typeof content !== "string" || !content.trim()) {
        throw new Error(EMPTY_RESPONSE);
    }
    return {
        content: content.trim(),
        model: typeof data.model === "string" ? data.model : "",
        usage: data.usage && typeof data.usage === "object" ? data.usage : {},
        context: data.context && typeof data.context === "object" ? data.context : {},
    };
}

/**
 * What to tell the user when a question failed: the server's own message
 * when it sent one, otherwise one for the kind of failure.
 */
export function errorMessage(error) {
    const status = error?.response?.status;
    const serverError = error?.response?.data?.error;
    if (typeof serverError === "string" && serverError.trim()) return serverError;
    if (status === 401 || status === 403) return "Sign in again to use the assistant.";
    if (status === 404) return "That project is no longer available.";
    if (status === 429) {
        return "Too many questions in a short time. Wait a moment, then try again.";
    }
    if (status === 400) return "The question could not be sent. Try rephrasing it.";
    if (status >= 500) return "The assistant is not reachable right now.";
    if (error?.code === "ECONNABORTED" || /timeout/i.test(error?.message || "")) {
        return "The assistant took too long to answer.";
    }
    if (error?.message === EMPTY_RESPONSE) return EMPTY_RESPONSE;
    if (error?.request || error?.message === "Network Error") {
        return "The assistant is not reachable right now.";
    }
    return "Something went wrong. Try again.";
}

/**
 * Whether a key press in the question box sends the question: Enter alone.
 * Shift+Enter (and the other modifiers) add a line instead.
 */
export function shouldSend(event) {
    return Boolean(event)
        && event.key === "Enter"
        && !event.shiftKey && !event.ctrlKey && !event.altKey && !event.metaKey
        && !event.isComposing;
}

/**
 * The projects of the focus menu, from the results of /api/projects/ (which
 * names the key `id`, like the project dashboard's prop, not `pk`).
 */
export function projectChoices(results) {
    return (Array.isArray(results) ? results : [])
        .filter((p) => p && Number.isInteger(p.id) && typeof p.name === "string")
        .map(({ id, name }) => ({ pk: id, name }));
}

/** Whether a draft can be sent now */
export function canSend(draft, loading) {
    if (loading || typeof draft !== "string") return false;
    const length = draft.trim().length;
    return length > 0 && length <= MAX_CONTENT_LENGTH;
}
