// Run with `npm test` (Node 22 or later, no other dependency).
import assert from "node:assert/strict";
import { describe, test } from "node:test";
import {
    EMPTY_RESPONSE,
    MAX_CONTENT_LENGTH,
    MAX_HISTORY,
    SUGGESTED_QUESTIONS,
    canSend,
    errorMessage,
    makeMessage,
    parseChatResponse,
    projectChoices,
    shouldSend,
    toApiMessages,
} from "../src/assistant/chat.js";

const user = (content) => ({ role: "user", content });
const assistant = (content) => ({ role: "assistant", content });

/** An error as axios raises it for a response with a status */
const httpError = (status, data) => ({ response: { status, data } });

describe("makeMessage", () => {
    test("numbers messages, dates them, and keeps extras", () => {
        const a = makeMessage("user", "Hi");
        const b = makeMessage("assistant", "Hello", { model: "Qwen 3.6" });
        assert.equal(a.role, "user");
        assert.equal(a.content, "Hi");
        assert.ok(b.id > a.id);
        assert.ok(!Number.isNaN(Date.parse(a.at)));
        assert.equal(b.model, "Qwen 3.6");
    });
});

describe("toApiMessages", () => {
    test("keeps role and content only, in order", () => {
        const history = [makeMessage("user", "a"), makeMessage("assistant", "b", { model: "m" }),
            makeMessage("user", "c")];
        assert.deepEqual(toApiMessages(history), [user("a"), assistant("b"), user("c")]);
    });

    test("keeps the last MAX_HISTORY messages", () => {
        const history = [];
        for (let i = 0; i < 25; i++) {
            history.push(i % 2 ? assistant(`m${i}`) : user(`m${i}`));
        }
        const sent = toApiMessages(history);
        assert.equal(sent.length, MAX_HISTORY);
        assert.equal(sent[0].content, `m${25 - MAX_HISTORY}`);
        assert.equal(sent[sent.length - 1].content, "m24");
        assert.deepEqual(toApiMessages(history, 2), [assistant("m23"), user("m24")]);
    });

    test("drops what the API would refuse", () => {
        const history = [
            { role: "system", content: "not the client's to send" },
            user(""),
            user("   "),
            { role: "user", content: 42 },
            null,
            undefined,
            { role: "tool", content: "x" },
            user("kept"),
        ];
        assert.deepEqual(toApiMessages(history), [user("kept")]);
        assert.deepEqual(toApiMessages(undefined), []);
        assert.deepEqual(toApiMessages("nope"), []);
    });
});

describe("parseChatResponse", () => {
    test("the answer of a reply", () => {
        const reply = parseChatResponse({
            message: { role: "assistant", content: "  Two tasks are running.\n" },
            model: "Qwen 3.6",
            usage: { prompt_tokens: 2140, completion_tokens: 310 },
            context: { projects: 3, documents: 12, tasks: 7 },
        });
        assert.deepEqual(reply, {
            content: "Two tasks are running.",
            model: "Qwen 3.6",
            usage: { prompt_tokens: 2140, completion_tokens: 310 },
            context: { projects: 3, documents: 12, tasks: 7 },
        });
    });

    test("defaults for what the reply leaves out", () => {
        const reply = parseChatResponse({ message: { content: "Hi" }, model: 7, usage: null });
        assert.deepEqual(reply, { content: "Hi", model: "", usage: {}, context: {} });
    });

    test("an empty answer is an error", () => {
        const empty = (e) => e.message === EMPTY_RESPONSE;
        for (const data of [undefined, null, {}, { message: {} }, { message: { content: "" } },
            { message: { content: " \n " } }, { message: { content: 42 } }, { message: "Hi" }]) {
            assert.throws(() => parseChatResponse(data), empty, JSON.stringify(data));
        }
    });
});

describe("errorMessage", () => {
    test("the server's own message comes first", () => {
        const message = "The assistant took too long to answer.";
        assert.equal(errorMessage(httpError(502, { status: "error", error: message })), message);
        assert.equal(errorMessage(httpError(400, { error: "Send at least one message." })),
            "Send at least one message.");
        assert.equal(errorMessage(httpError(404, { error: "Project not found." })),
            "Project not found.");
    });

    test("one message per kind of failure", () => {
        assert.match(errorMessage(httpError(401)), /sign in/i);
        assert.match(errorMessage(httpError(403, { detail: "Forbidden" })), /sign in/i);
        assert.match(errorMessage(httpError(404)), /project/i);
        assert.match(errorMessage(httpError(429, { detail: "Request was throttled." })),
            /too many/i);
        assert.match(errorMessage(httpError(400, { error: { messages: ["bad"] } })), /rephras/i);
        assert.match(errorMessage(httpError(400, { error: "" })), /rephras/i);
        assert.match(errorMessage(httpError(500)), /not reachable/i);
        assert.match(errorMessage(httpError(503, "<html>")), /not reachable/i);
        assert.match(errorMessage(httpError(504)), /not reachable/i);
    });

    test("failures without a response", () => {
        assert.match(errorMessage({ code: "ECONNABORTED", message: "timeout of 90000ms exceeded" }),
            /too long/i);
        assert.match(errorMessage({ message: "Network Error", request: {} }), /not reachable/i);
        assert.equal(errorMessage(new Error(EMPTY_RESPONSE)), EMPTY_RESPONSE);
        assert.match(errorMessage(new Error("boom")), /went wrong/i);
        assert.match(errorMessage(undefined), /went wrong/i);
        assert.match(errorMessage({}), /went wrong/i);
    });
});

describe("shouldSend", () => {
    const key = (extra = {}) => ({ key: "Enter", shiftKey: false, ctrlKey: false, altKey: false,
        metaKey: false, isComposing: false, ...extra });

    test("Enter sends", () => {
        assert.equal(shouldSend(key()), true);
    });

    test("Shift+Enter and the other modifiers add a line instead", () => {
        assert.equal(shouldSend(key({ shiftKey: true })), false);
        assert.equal(shouldSend(key({ ctrlKey: true })), false);
        assert.equal(shouldSend(key({ altKey: true })), false);
        assert.equal(shouldSend(key({ metaKey: true })), false);
    });

    test("not while composing with an input method, and not for other keys", () => {
        assert.equal(shouldSend(key({ isComposing: true })), false);
        assert.equal(shouldSend(key({ key: "a" })), false);
        assert.equal(shouldSend(key({ key: "Escape" })), false);
        assert.equal(shouldSend(undefined), false);
        assert.equal(shouldSend(null), false);
    });
});

describe("canSend", () => {
    test("a question that is not blank, while nothing is loading", () => {
        assert.equal(canSend("What is running?", false), true);
        assert.equal(canSend("  padded  ", false), true);
    });

    test("not while loading, not blank, not too long, not a non-string", () => {
        assert.equal(canSend("What is running?", true), false);
        assert.equal(canSend("", false), false);
        assert.equal(canSend("   \n ", false), false);
        assert.equal(canSend("x".repeat(MAX_CONTENT_LENGTH), false), true);
        assert.equal(canSend("x".repeat(MAX_CONTENT_LENGTH + 1), false), false);
        assert.equal(canSend(undefined, false), false);
        assert.equal(canSend(42, false), false);
    });
});

describe("projectChoices", () => {
    test("reads the id and name of the projects the API lists", () => {
        const results = [
            { id: 3, name: "Ephrem Hymns", slug: "ephrem-hymns", owner: "logan" },
            { id: 7, name: "Syriac Printed Books", tags: [] },
        ];
        assert.deepEqual(projectChoices(results), [
            { pk: 3, name: "Ephrem Hymns" },
            { pk: 7, name: "Syriac Printed Books" },
        ]);
    });

    test("skips what is not a listed project", () => {
        assert.deepEqual(projectChoices([{ pk: 3, name: "no id" }, { id: "3", name: "x" },
            { id: 4 }, null, { id: 5, name: "kept" }]), [{ pk: 5, name: "kept" }]);
        assert.deepEqual(projectChoices(undefined), []);
        assert.deepEqual(projectChoices({ id: 1, name: "not a list" }), []);
    });
});

describe("SUGGESTED_QUESTIONS", () => {
    test("four distinct questions", () => {
        assert.equal(SUGGESTED_QUESTIONS.length, 4);
        assert.equal(new Set(SUGGESTED_QUESTIONS).size, 4);
        for (const question of SUGGESTED_QUESTIONS) {
            assert.ok(question.trim().length > 0 && question.endsWith("?"), question);
        }
    });
});
