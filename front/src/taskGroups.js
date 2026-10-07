/*
 * Task groups of a document (new UI): one group per task the user asked for,
 * e.g. one segmentation of several pages. The document's task dashboard
 * lists them, from /api/documents/<pk>/task_groups/.
 */

/**
 * The body of a request to cancel the tasks of one task group. Throws without
 * a valid task group pk: the endpoint cancels every task of the document,
 * including the ones of other users, when it gets no task group.
 */
export function cancelPayload(taskGroupId) {
    const pk = ["number", "string"].includes(typeof taskGroupId) ? Number(taskGroupId) : NaN;
    if (!Number.isInteger(pk) || pk <= 0) {
        throw new Error("Could not cancel: no task was selected.");
    }
    return { task_group: pk };
}

/**
 * The page task updates of a websocket message of the document room, as a
 * list of `{ id, process, status }`: one for "part:workflow", one per page
 * for "parts:workflow" (sent when tasks are canceled), none otherwise.
 */
export function partWorkflowUpdates(message) {
    if (!message || message.type !== "event") return [];
    if (message.name === "part:workflow") {
        return message.data ? [message.data] : [];
    }
    if (message.name === "parts:workflow") {
        return Array.isArray(message.data?.parts) ? message.data.parts : [];
    }
    return [];
}
