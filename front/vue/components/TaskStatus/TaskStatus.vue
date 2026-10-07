<template>
    <div
        v-if="summary"
        :class="['escr-task-status', `is-${summary.tone}`]"
    >
        <VMenu
            placement="bottom-end"
            theme="modal-menu"
            :distance="8"
            :triggers="['click']"
            :auto-hide="true"
            @apply-show="refresh"
        >
            <button
                type="button"
                class="task-status-button"
                :aria-label="`Background tasks: ${description}`"
            >
                <span
                    v-if="summary.tone === 'active'"
                    class="task-status-spinner"
                    aria-hidden="true"
                />
                <ErrorIcon v-else-if="summary.tone === 'failed'" />
                <CanceledIcon v-else-if="summary.tone === 'canceled'" />
                <CheckCircleIcon v-else />
                <span
                    v-for="part in summary.parts"
                    :key="part.state"
                    :class="['task-count', `count-${part.state}`]"
                >{{ part.text }}</span>
            </button>
            <template #popper>
                <div class="escr-task-list">
                    <p>
                        Your tasks on this document, queued, running or ended in the
                        last 24 hours: {{ description }}.
                    </p>
                    <p
                        v-if="error"
                        class="task-list-error"
                    >
                        Could not update the tasks: {{ error }}
                    </p>
                    <ul>
                        <li
                            v-for="task in rows"
                            :key="task.pk"
                            :class="`is-${task.state}`"
                        >
                            <div class="task-heading">
                                <span class="task-name">{{ task.name }}</span>
                                <span class="task-state">{{ stateLabels[task.state] }}</span>
                            </div>
                            <div class="task-meta">
                                <span v-if="task.page">{{ task.page }}</span>
                                <time
                                    v-if="task.time"
                                    :datetime="task.time.at"
                                    :title="task.time.full"
                                >{{ task.time.verb }} {{ task.time.short }}</time>
                                <a :href="task.href">Report</a>
                            </div>
                            <p
                                v-if="task.state === 'failed'"
                                class="task-reason"
                            >
                                {{ task.reason || "No reason was recorded." }}
                            </p>
                        </li>
                    </ul>
                    <p
                        v-if="tasks.length > rows.length || !complete"
                        class="task-list-more"
                    >
                        <template v-if="!complete">
                            Too many tasks to count them all here.
                        </template>
                        <template v-else>
                            {{ tasks.length - rows.length }} more not shown.
                        </template>
                    </p>
                    <a
                        class="task-list-all"
                        href="/quotas/"
                    >All your tasks</a>
                </div>
            </template>
        </VMenu>
    </div>
</template>
<script>
import { Menu as VMenu } from "floating-vue";
import { mapActions, mapGetters, mapState } from "vuex";
import CanceledIcon from "../Icons/CanceledIcon/CanceledIcon.vue";
import CheckCircleIcon from "../Icons/CheckCircleIcon/CheckCircleIcon.vue";
import ErrorIcon from "../Icons/ErrorIcon/ErrorIcon.vue";
import { describeCounts } from "../../../src/editor/taskStatus";
import "./TaskStatus.css";

// most tasks listed in the details, failed first, see sortTasks
const MAX_SHOWN = 50;

/**
 * Background tasks of the document: queued, running, or ended in the last 24
 * hours, with the reason of the ones that crashed.
 */
export default {
    name: "EscrTaskStatus",
    components: { CanceledIcon, CheckCircleIcon, ErrorIcon, VMenu },
    data() {
        return {
            stateLabels: {
                queued: "Queued",
                running: "Running",
                failed: "Failed",
                completed: "Completed",
                canceled: "Canceled",
            },
        };
    },
    computed: {
        ...mapGetters("taskStatus", ["counts", "summary"]),
        ...mapState({
            tasks: (state) => state.taskStatus.tasks,
            complete: (state) => state.taskStatus.complete,
            error: (state) => state.taskStatus.error,
        }),
        description() {
            return describeCounts(this.counts);
        },
        rows() {
            return this.tasks.slice(0, MAX_SHOWN).map((task) => ({
                ...task,
                time: this.timeOf(task),
            }));
        },
    },
    methods: {
        ...mapActions("taskStatus", ["refresh"]),
        /**
         * When the task was queued, started or ended, as shown: the time only for
         * today, else the date too.
         */
        timeOf(task) {
            let verb = "Ended";
            let at = task.doneAt;
            if (task.state === "queued") {
                verb = "Queued";
                at = task.queuedAt;
            } else if (task.state === "running") {
                verb = "Started";
                at = task.startedAt;
            }
            if (!at) return null;
            const date = new Date(at);
            const today = date.toDateString() === new Date().toDateString();
            const short = date.toLocaleString(undefined, {
                ...(today ? {} : { month: "short", day: "numeric" }),
                hour: "numeric",
                minute: "2-digit",
            });
            return { verb, at, short, full: date.toLocaleString() };
        },
    },
};
</script>
