// Run with `npm test` (Node 22 or later, no other dependency).
import assert from "node:assert/strict";
import { describe, test } from "node:test";
import { cancelPayload, partWorkflowUpdates } from "../src/taskGroups.js";

describe("cancelPayload", () => {
    test("names the task group to cancel", () => {
        assert.deepEqual(cancelPayload(12), { task_group: 12 });
        assert.deepEqual(cancelPayload("12"), { task_group: 12 });
    });

    test("refuses to build a request without a task group", () => {
        // Without one, the endpoint cancels every task of the document
        for (const id of [undefined, null, "", NaN, 0, -1, 1.5, "abc", {}, [], true]) {
            assert.throws(() => cancelPayload(id), /no task was selected/, String(id));
        }
    });
});

describe("partWorkflowUpdates", () => {
    const event = (name, data) => ({ type: "event", name, data });

    test("one update for one page", () => {
        const data = { id: 3, process: "segment", status: "ongoing" };
        assert.deepEqual(partWorkflowUpdates(event("part:workflow", data)), [data]);
    });

    test("one update per page of a canceled task", () => {
        const parts = [
            { id: 3, process: "segment", status: "canceled", reason: "Canceled." },
            { id: 4, process: "segment", status: "canceled", reason: "Canceled." },
        ];
        assert.deepEqual(partWorkflowUpdates(event("parts:workflow", { parts })), parts);
    });

    test("no update without pages", () => {
        assert.deepEqual(partWorkflowUpdates(event("parts:workflow", {})), []);
        assert.deepEqual(partWorkflowUpdates(event("parts:workflow")), []);
        assert.deepEqual(partWorkflowUpdates(event("part:workflow")), []);
    });

    test("no update for other messages", () => {
        assert.deepEqual(partWorkflowUpdates(event("training:error", { id: 3 })), []);
        assert.deepEqual(partWorkflowUpdates(event("import:done", {})), []);
        assert.deepEqual(partWorkflowUpdates({ type: "message", name: "part:workflow" }), []);
        assert.deepEqual(partWorkflowUpdates(undefined), []);
    });
});
