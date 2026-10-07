/*
 * Background tasks of the document open in the editor (new UI): the ones
 * queued or running, and the ones that ended in the last 24 hours, with the
 * reason of those that crashed.
 *
 * They come from the task reports of the API (/api/tasks/): one report per
 * task, or per page and task for the tasks run on pages. The API only returns
 * the reports of the current user.
 */

/** Task states, by TaskReport.workflow_state on the server */
const STATE_BY_CODE = ["queued", "running", "failed", "completed", "canceled"];

/** Task states, in the order they are counted and listed */
export const STATES = ["failed", "running", "queued", "completed", "canceled"];

/** How long a task that ended stays listed */
export const RECENT_MS = 24 * 60 * 60 * 1000;

/** Most report pages read at once; 50 reports per page */
export const MAX_PAGES = 10;

/**
 * Tasks run automatically, that the user did not ask for: not listed, like
 * on /quotas/. Mask recalculation runs after line edits in the editor itself.
 */
const HIDDEN_METHODS = [
    "core.tasks.convert",
    "core.tasks.generate_part_thumbnails",
    "core.tasks.lossless_compression",
    "core.tasks.recalculate_masks",
    "users.tasks.async_email",
];

const NAMES = {
    align: "Align",
    document_export: "Export",
    document_import: "Import",
    forced_align: "Forced alignment",
    replace_line_transcriptions_text: "Find and replace",
    segment: "Segment",
    segtrain: "Train segmenter",
    train: "Train recognizer",
    transcribe: "Transcribe",
};

/**
 * Name of a task for the user, from its method, e.g. "core.tasks.transcribe".
 */
export function taskName(method) {
    const short = (method || "").split(".").pop();
    if (NAMES[short]) return NAMES[short];
    const words = short.replace(/_/g, " ").trim();
    return words ? words.charAt(0).toUpperCase() + words.slice(1) : "Task";
}

/**
 * Why a task crashed, from the messages of its report: the error is the last
 * line written, after any progress lines.
 */
export function crashReason(messages) {
    const lines = (messages || "").split("\n").map((line) => line.trim()).filter(Boolean);
    return lines.length ? lines[lines.length - 1] : "";
}

/**
 * A task report of the API as the editor shows it, or null if its state is
 * unknown.
 */
export function toTask(report) {
    const state = STATE_BY_CODE[report.workflow_state];
    if (!state) return null;
    return {
        pk: report.pk,
        state,
        name: taskName(report.method),
        page: report.document_part || null,
        queuedAt: report.queued_at || null,
        startedAt: report.started_at || null,
        doneAt: report.done_at || null,
        reason: state === "failed" ? crashReason(report.messages) : "",
        href: `/quotas/${report.pk}/`,
    };
}

export function isActive(task) {
    return task.state === "queued" || task.state === "running";
}

/**
 * When the task last changed state, in ms since the epoch (0 if unknown).
 */
export function lastChange(task) {
    return Date.parse(task.doneAt || task.startedAt || task.queuedAt) || 0;
}

/**
 * Whether the task is listed `now` (ms): queued or running, or ended in the
 * last 24 hours.
 */
export function isListed(task, now) {
    return isActive(task) || now - lastChange(task) <= RECENT_MS;
}

export function sortTasks(tasks) {
    const rank = (task) => STATES.indexOf(task.state);
    return [...tasks].sort((a, b) => rank(a) - rank(b) || lastChange(b) - lastChange(a));
}

/**
 * Read the listed tasks, page after page of reports.
 *
 * `fetchPage(page)` resolves to a page of the API, { results, next }, with
 * the reports that did not end first, then the others by end time, newest
 * first. Reading stops at the first report that ended before the last 24
 * hours, or after `maxPages` pages; `complete` is false in that last case,
 * when some tasks may be missing.
 */
export async function loadTasks(fetchPage, now, maxPages = MAX_PAGES) {
    // pages can shift while they are read: count each report once
    const tasks = new Map();
    for (let page = 1; page <= maxPages; page++) {
        const { results = [], next = null } = await fetchPage(page);
        for (const report of results) {
            if (report.done_at && now - Date.parse(report.done_at) > RECENT_MS) {
                return { tasks: sortTasks(tasks.values()), complete: true };
            }
            const task = HIDDEN_METHODS.includes(report.method) ? null : toTask(report);
            if (task && isListed(task, now)) tasks.set(task.pk, task);
        }
        if (!next) return { tasks: sortTasks(tasks.values()), complete: true };
    }
    return { tasks: sortTasks(tasks.values()), complete: false };
}

/**
 * Number of tasks in each state.
 */
export function countByState(tasks) {
    const counts = Object.fromEntries(STATES.map((state) => [state, 0]));
    tasks.forEach((task) => {
        counts[task.state] += 1;
    });
    return counts;
}

/**
 * The counts as text, e.g. "2 running, 1 queued", leaving out the states
 * without tasks.
 */
export function describeCounts(counts) {
    return STATES
        .filter((state) => counts[state])
        .map((state) => `${counts[state]} ${state}`)
        .join(", ");
}

/**
 * What the indicator shows, or null when there is no task to show:
 * - `tone`: "active" while tasks are queued or running, else "failed" if a
 *   task crashed, else "done", or "canceled" if all were canceled
 * - `parts`: the two counts that matter most, e.g. 2 running and 1 failed, as
 *   { state, text }; the others are in the details
 */
export function summarize(counts) {
    if (!STATES.some((state) => counts[state])) return null;
    const firstTwo = (states) => states
        .filter((state) => counts[state])
        .slice(0, 2)
        .map((state) => ({ state, text: `${counts[state]} ${state}` }));
    let parts = firstTwo(["running", "failed", "queued"]);
    if (!parts.length) parts = firstTwo(["completed", "canceled"]);
    let tone = "done";
    if (counts.running || counts.queued) tone = "active";
    else if (counts.failed) tone = "failed";
    else if (!counts.completed) tone = "canceled";
    return { tone, parts };
}

/**
 * Wrap `run`, an async function, so that calls in a burst make it run once:
 * `wait` ms after the first call, then again after it ends if it was called
 * in the meantime. It runs at most once at a time, and at least every `wait`
 * ms while calls keep coming.
 */
export function coalesce(run, wait) {
    let timer = null;
    let running = false;
    let again = false;
    const start = async () => {
        timer = null;
        running = true;
        again = false;
        try {
            await run();
        } catch (err) {
            // the next call tries again
        } finally {
            running = false;
            if (again) schedule();
        }
    };
    const schedule = () => {
        if (running) {
            again = true;
        } else if (!timer) {
            timer = setTimeout(start, wait);
        }
    };
    schedule.cancel = () => {
        clearTimeout(timer);
        timer = null;
        again = false;
    };
    return schedule;
}

/**
 * Whether a websocket message of the document room can change the tasks:
 * events about tasks, except those of the tasks that are not listed.
 */
export function isTaskEvent(message) {
    if (!message || message.type !== "event" || typeof message.name !== "string") return false;
    const { name, data } = message;
    if (name === "part:workflow") {
        return !HIDDEN_METHODS.some((method) => method.endsWith(`.${data && data.process}`));
    }
    return (
        name === "parts:workflow" ||
        ["training:", "import:", "export:"].some((prefix) => name.startsWith(prefix)) ||
        // a task of the whole document canceled, e.g. "align: error"
        name.endsWith(": error")
    );
}
