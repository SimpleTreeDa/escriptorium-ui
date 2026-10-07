// Run with `npm test` (Node 22 or later, no other dependency).
import assert from "node:assert/strict";
import { describe, test } from "node:test";
import {
    MAX_PAGES,
    RECENT_MS,
    coalesce,
    countByState,
    crashReason,
    describeCounts,
    isListed,
    isTaskEvent,
    loadTasks,
    summarize,
    taskName,
    toTask,
} from "../src/editor/taskStatus.js";

const NOW = Date.parse("2026-10-07T12:00:00Z");
const HOUR = 60 * 60 * 1000;
const at = (hoursAgo) => new Date(NOW - hoursAgo * HOUR).toISOString();

const QUEUED = 0;
const RUNNING = 1;
const CRASHED = 2;
const FINISHED = 3;
const CANCELED = 4;

let nextPk = 1;
/** A report as /api/tasks/ returns it, ended `hoursAgo` if it ended */
function report(workflow_state, hoursAgo = 1, extra = {}) {
    const ended = workflow_state >= CRASHED;
    return {
        pk: nextPk++,
        document: 1,
        document_part: "Element 1",
        workflow_state,
        label: "Report for celery task 123 of type core.tasks.transcribe",
        messages: "",
        queued_at: at(hoursAgo + 1),
        started_at: workflow_state === QUEUED ? null : at(hoursAgo + 0.5),
        done_at: ended ? at(hoursAgo) : null,
        method: "core.tasks.transcribe",
        user: 1,
        ...extra,
    };
}

/** fetchPage for loadTasks, serving `reports` by pages of `size`, and recording the pages read */
function pages(reports, size = 50) {
    const fetchPage = async (page) => {
        fetchPage.read.push(page);
        const results = reports.slice((page - 1) * size, page * size);
        const next = page * size < reports.length ? `/api/tasks/?page=${page + 1}` : null;
        return { count: reports.length, next, previous: null, results };
    };
    fetchPage.read = [];
    return fetchPage;
}

const counts = (values) => ({
    failed: 0, running: 0, queued: 0, completed: 0, canceled: 0, ...values,
});

describe("taskName", () => {
    test("names the known tasks", () => {
        assert.equal(taskName("core.tasks.transcribe"), "Transcribe");
        assert.equal(taskName("core.tasks.segtrain"), "Train segmenter");
        assert.equal(taskName("core.tasks.train"), "Train recognizer");
        assert.equal(taskName("imports.tasks.document_export"), "Export");
    });

    test("makes a name of the others", () => {
        assert.equal(taskName("core.tasks.some_new_task"), "Some new task");
    });

    test("falls back to Task", () => {
        assert.equal(taskName(null), "Task");
        assert.equal(taskName(""), "Task");
    });
});

describe("crashReason", () => {
    test("is the last line written", () => {
        const messages = "Applying the replacement on line 1\nApplying the replacement on line 2\n"
            + "ValueError: no line to transcribe\n\n";
        assert.equal(crashReason(messages), "ValueError: no line to transcribe");
    });

    test("is empty when nothing was written", () => {
        assert.equal(crashReason(""), "");
        assert.equal(crashReason(null), "");
        assert.equal(crashReason(" \n "), "");
    });
});

describe("toTask", () => {
    test("maps the report", () => {
        const r = report(RUNNING, 0, {
            pk: 42, document_part: "Folio 3r", method: "core.tasks.segment",
        });
        assert.deepEqual(toTask(r), {
            pk: 42,
            state: "running",
            name: "Segment",
            page: "Folio 3r",
            queuedAt: r.queued_at,
            startedAt: r.started_at,
            doneAt: null,
            reason: "",
            href: "/quotas/42/",
        });
    });

    test("maps each state", () => {
        const states = [QUEUED, RUNNING, CRASHED, FINISHED, CANCELED]
            .map((s) => toTask(report(s)).state);
        assert.deepEqual(states, ["queued", "running", "failed", "completed", "canceled"]);
    });

    test("gives the reason of a crash only", () => {
        const crashed = report(CRASHED, 1, { messages: "Out of memory\n" });
        const canceled = report(CANCELED, 1, { messages: "Canceled by user alice\n" });
        assert.equal(toTask(crashed).reason, "Out of memory");
        assert.equal(toTask(canceled).reason, "");
    });

    test("has no page for a task of the whole document", () => {
        assert.equal(toTask(report(FINISHED, 1, { document_part: null })).page, null);
    });

    test("ignores an unknown state", () => {
        assert.equal(toTask(report(7)), null);
    });
});

describe("isListed", () => {
    test("lists queued and running tasks, however old", () => {
        assert.ok(isListed(toTask(report(QUEUED, 100)), NOW));
        assert.ok(isListed(toTask(report(RUNNING, 100)), NOW));
    });

    test("lists the tasks that ended in the last 24 hours only", () => {
        assert.ok(isListed(toTask(report(FINISHED, 23)), NOW));
        assert.ok(isListed(toTask(report(CRASHED, 24)), NOW));
        assert.ok(!isListed(toTask(report(FINISHED, 25)), NOW));
        assert.ok(!isListed(toTask(report(CANCELED, 25)), NOW));
    });

    test("uses the last known time of a task that ended without an end time", () => {
        assert.ok(isListed(toTask(report(FINISHED, 1, { done_at: null })), NOW));
        assert.ok(!isListed(toTask(report(FINISHED, 30, { done_at: null })), NOW));
    });
});

describe("loadTasks", () => {
    test("lists failed, running, queued, then the others, newest first", async () => {
        const reports = [
            report(QUEUED, 5, { pk: 1 }),
            report(RUNNING, 0, { pk: 2 }),
            report(QUEUED, 0, { pk: 3 }),
            report(FINISHED, 1, { pk: 4 }),
            report(CRASHED, 2, { pk: 5 }),
            report(CANCELED, 3, { pk: 6 }),
            report(FINISHED, 4, { pk: 7 }),
            report(CRASHED, 6, { pk: 8 }),
        ];
        const { tasks, complete } = await loadTasks(pages(reports), NOW);
        assert.deepEqual(tasks.map((t) => t.pk), [5, 8, 2, 3, 1, 4, 7, 6]);
        assert.equal(complete, true);
    });

    test("stops at the first report that ended before the last 24 hours", async () => {
        const reports = [
            report(RUNNING, 0, { pk: 1 }),
            report(FINISHED, 2, { pk: 2 }),
            report(FINISHED, 25, { pk: 3 }),
            // older reports are not read
            report(CRASHED, 30, { pk: 4 }),
            ...Array.from({ length: 60 }, () => report(FINISHED, 40)),
        ];
        const fetchPage = pages(reports);
        const { tasks, complete } = await loadTasks(fetchPage, NOW);
        assert.deepEqual(tasks.map((t) => t.pk), [1, 2]);
        assert.equal(complete, true);
        assert.deepEqual(fetchPage.read, [1]);
    });

    test("reads the next pages while the reports are recent", async () => {
        const reports = [
            ...Array.from({ length: 120 }, () => report(QUEUED, 0)),
            report(FINISHED, 1),
        ];
        const fetchPage = pages(reports);
        const { tasks, complete } = await loadTasks(fetchPage, NOW);
        assert.equal(tasks.length, 121);
        assert.equal(complete, true);
        assert.deepEqual(fetchPage.read, [1, 2, 3]);
    });

    test("is not complete when there are more pages than it reads", async () => {
        const reports = Array.from({ length: 50 * MAX_PAGES + 1 }, () => report(QUEUED, 0));
        const fetchPage = pages(reports);
        const { tasks, complete } = await loadTasks(fetchPage, NOW);
        assert.equal(tasks.length, 50 * MAX_PAGES);
        assert.equal(complete, false);
        assert.equal(fetchPage.read.length, MAX_PAGES);
    });

    test("counts a report once when pages shift while they are read", async () => {
        const shifted = report(QUEUED, 0, { pk: 1 });
        const fetchPage = async (page) => (page === 1
            ? { next: "/api/tasks/?page=2", results: [report(QUEUED, 0, { pk: 2 }), shifted] }
            : { next: null, results: [shifted, report(FINISHED, 1, { pk: 3 })] });
        const { tasks } = await loadTasks(fetchPage, NOW);
        assert.deepEqual(tasks.map((t) => t.pk).sort(), [1, 2, 3]);
    });

    test("leaves out the tasks run automatically", async () => {
        const reports = [
            report(RUNNING, 0, { pk: 1, method: "core.tasks.recalculate_masks" }),
            report(FINISHED, 1, { pk: 2, method: "core.tasks.convert" }),
            report(FINISHED, 1, { pk: 3, method: "core.tasks.segment" }),
        ];
        const { tasks } = await loadTasks(pages(reports), NOW);
        assert.deepEqual(tasks.map((t) => t.pk), [3]);
    });

    test("stops at an old report even if it is not listed", async () => {
        const reports = [
            report(FINISHED, 30, { method: "core.tasks.recalculate_masks" }),
            report(FINISHED, 1),
        ];
        const { tasks } = await loadTasks(pages(reports), NOW);
        assert.deepEqual(tasks, []);
    });

    test("fails when a page cannot be read", async () => {
        const fetchPage = async () => { throw new Error("Network Error"); };
        await assert.rejects(loadTasks(fetchPage, NOW), /Network Error/);
    });

    test("finds nothing in an empty page", async () => {
        assert.deepEqual(await loadTasks(pages([]), NOW), { tasks: [], complete: true });
    });
});

describe("countByState", () => {
    test("counts the tasks of each state", () => {
        const tasks = [QUEUED, QUEUED, RUNNING, CRASHED, FINISHED, FINISHED, FINISHED, CANCELED]
            .map((s) => toTask(report(s)));
        assert.deepEqual(countByState(tasks), counts({
            failed: 1, running: 1, queued: 2, completed: 3, canceled: 1,
        }));
    });

    test("counts zero of each state without tasks", () => {
        assert.deepEqual(countByState([]), counts({}));
    });
});

describe("describeCounts", () => {
    test("lists the states with tasks", () => {
        assert.equal(
            describeCounts(counts({ running: 2, queued: 1, completed: 3 })),
            "2 running, 1 queued, 3 completed",
        );
        assert.equal(
            describeCounts(counts({ failed: 1, canceled: 4 })),
            "1 failed, 4 canceled",
        );
    });
});

describe("summarize", () => {
    const texts = (summary) => summary.parts.map((part) => part.text);

    test("shows nothing without tasks", () => {
        assert.equal(summarize(counts({})), null);
    });

    test("shows the tasks running and queued", () => {
        const summary = summarize(counts({ running: 2, queued: 5, completed: 3 }));
        assert.equal(summary.tone, "active");
        assert.deepEqual(texts(summary), ["2 running", "5 queued"]);
    });

    test("shows failures before queued tasks while tasks run", () => {
        const summary = summarize(counts({ running: 2, queued: 5, failed: 1 }));
        assert.equal(summary.tone, "active");
        assert.deepEqual(summary.parts, [
            { state: "running", text: "2 running" },
            { state: "failed", text: "1 failed" },
        ]);
    });

    test("is active with queued tasks only", () => {
        const summary = summarize(counts({ queued: 1 }));
        assert.equal(summary.tone, "active");
        assert.deepEqual(texts(summary), ["1 queued"]);
    });

    test("shows failures once nothing runs", () => {
        const summary = summarize(counts({ failed: 2, completed: 8 }));
        assert.equal(summary.tone, "failed");
        assert.deepEqual(texts(summary), ["2 failed"]);
    });

    test("shows the tasks that ended when all went well", () => {
        const summary = summarize(counts({ completed: 3, canceled: 1 }));
        assert.equal(summary.tone, "done");
        assert.deepEqual(texts(summary), ["3 completed", "1 canceled"]);
    });

    test("is canceled when all tasks were canceled", () => {
        const summary = summarize(counts({ canceled: 2 }));
        assert.equal(summary.tone, "canceled");
        assert.deepEqual(texts(summary), ["2 canceled"]);
    });
});

describe("coalesce", () => {
    const flush = () => new Promise((resolve) => setImmediate(resolve));

    test("runs once for a burst of calls, after the wait", async (t) => {
        t.mock.timers.enable({ apis: ["setTimeout"] });
        let runs = 0;
        const refresh = coalesce(async () => { runs += 1; }, 2000);
        refresh();
        t.mock.timers.tick(500);
        refresh();
        refresh();
        assert.equal(runs, 0);
        t.mock.timers.tick(1500);
        await flush();
        assert.equal(runs, 1);
        t.mock.timers.tick(5000);
        await flush();
        assert.equal(runs, 1);
    });

    test("runs again after a run during which it was called, never two at once", async (t) => {
        t.mock.timers.enable({ apis: ["setTimeout"] });
        let runs = 0;
        let running = 0;
        let finish;
        const refresh = coalesce(async () => {
            runs += 1;
            running += 1;
            assert.equal(running, 1);
            await new Promise((resolve) => { finish = resolve; });
            running -= 1;
        }, 2000);
        refresh();
        t.mock.timers.tick(2000);
        await flush();
        assert.equal(runs, 1);
        // called while running: waits for the end of the run
        refresh();
        refresh();
        t.mock.timers.tick(5000);
        await flush();
        assert.equal(runs, 1);
        finish();
        await flush();
        t.mock.timers.tick(2000);
        await flush();
        assert.equal(runs, 2);
        finish();
        await flush();
        t.mock.timers.tick(5000);
        await flush();
        assert.equal(runs, 2);
    });

    test("keeps working after a failed run", async (t) => {
        t.mock.timers.enable({ apis: ["setTimeout"] });
        let runs = 0;
        const refresh = coalesce(async () => {
            runs += 1;
            throw new Error("Network Error");
        }, 2000);
        refresh();
        t.mock.timers.tick(2000);
        await flush();
        refresh();
        t.mock.timers.tick(2000);
        await flush();
        assert.equal(runs, 2);
    });

    test("can be canceled", async (t) => {
        t.mock.timers.enable({ apis: ["setTimeout"] });
        let runs = 0;
        const refresh = coalesce(async () => { runs += 1; }, 2000);
        refresh();
        refresh.cancel();
        t.mock.timers.tick(5000);
        await flush();
        assert.equal(runs, 0);
    });
});

describe("isTaskEvent", () => {
    const event = (name, data = {}) => ({ type: "event", name, data });

    test("is true for the changes of a task", () => {
        assert.ok(isTaskEvent(event("part:workflow", { id: 1, process: "transcribe" })));
        assert.ok(isTaskEvent(event("parts:workflow", { parts: [] })));
        assert.ok(isTaskEvent(event("training:done", { id: 3 })));
        assert.ok(isTaskEvent(event("import:progress", { progress: 2, total: 5 })));
        assert.ok(isTaskEvent(event("export:error", { reason: "Disk full" })));
        // a task of the whole document canceled
        assert.ok(isTaskEvent(event("align: error", { reason: "Canceled." })));
    });

    test("is false for the tasks that are not listed", () => {
        assert.ok(!isTaskEvent(event("part:workflow", { id: 1, process: "recalculate_masks" })));
        assert.ok(!isTaskEvent(event("part:workflow", { id: 1, process: "convert" })));
    });

    test("is false for other events and messages", () => {
        assert.ok(!isTaskEvent(event("part:mask", { lines: [] })));
        assert.ok(!isTaskEvent(event("part:new", { id: 1 })));
        assert.ok(!isTaskEvent(event("part:delete", { id: 1 })));
        assert.ok(!isTaskEvent({ type: "message", level: "danger", text: "Something went wrong" }));
        assert.ok(!isTaskEvent(null));
    });
});

test("RECENT_MS is 24 hours", () => {
    assert.equal(RECENT_MS, 24 * HOUR);
});
