<template>
    <div
        :class="['escr-save-status', `is-${status}`]"
        role="status"
        aria-live="polite"
    >
        <VDropdown
            theme="escr-tooltip-small"
            placement="bottom"
            :distance="8"
            :triggers="['hover']"
        >
            <span class="save-status-label">
                <ErrorIcon v-if="status === 'failed'" />
                <WarningIcon v-else-if="status === 'unsaved'" />
                <CheckCircleIcon v-else-if="status === 'saved'" />
                <span
                    v-else
                    class="save-status-spinner"
                    aria-hidden="true"
                />
                {{ label }}
            </span>
            <template #popper>
                {{ explanation }}
            </template>
        </VDropdown>
        <template v-if="status === 'failed'">
            <EscrButton
                v-if="canRetry"
                color="danger"
                size="small"
                label="Retry"
                :disabled="busy"
                :on-click="retry"
            />
            <VMenu
                placement="bottom-end"
                theme="modal-menu"
                :distance="8"
                :triggers="['click']"
                :auto-hide="true"
            >
                <EscrButton
                    color="text"
                    size="small"
                    label="Details"
                    :disabled="busy"
                    :on-click="() => {}"
                />
                <template #popper="{ hide }">
                    <div class="escr-save-failures">
                        <p>
                            These changes did not reach the server. They are still shown
                            in the editor, but are not saved.
                        </p>
                        <ul>
                            <li
                                v-for="failure in failures"
                                :key="failure.id"
                            >
                                <strong>{{ failure.message }}</strong>
                                <span class="failure-request">
                                    {{ failure.method }} {{ failure.url }}
                                </span>
                            </li>
                        </ul>
                        <div class="failure-actions">
                            <EscrButton
                                v-if="canRetry"
                                color="danger"
                                size="small"
                                label="Retry"
                                :on-click="() => { hide(); retry(); }"
                            />
                            <EscrButton
                                color="outline-text"
                                size="small"
                                label="Discard and reload the page"
                                :on-click="() => { hide(); discard(); }"
                            />
                        </div>
                    </div>
                </template>
            </VMenu>
        </template>
    </div>
</template>
<script>
import { Dropdown as VDropdown, Menu as VMenu } from "floating-vue";
import { mapActions, mapGetters, mapState } from "vuex";
import CheckCircleIcon from "../Icons/CheckCircleIcon/CheckCircleIcon.vue";
import ErrorIcon from "../Icons/ErrorIcon/ErrorIcon.vue";
import EscrButton from "../Button/Button.vue";
import WarningIcon from "../Icons/WarningIcon/WarningIcon.vue";
import { dismissFailedSaves, retryFailedSaves } from "../../../src/editor/saveTracking";
import "./SaveStatus.css";

const LABELS = {
    saved: "Saved",
    saving: "Saving…",
    unsaved: "Unsaved changes",
    failed: "Save failed",
};

/**
 * Whether the user's edits have reached the server, with a way to send failed
 * ones again.
 */
export default {
    name: "EscrSaveStatus",
    components: { CheckCircleIcon, ErrorIcon, EscrButton, VDropdown, VMenu, WarningIcon },
    data() {
        return { busy: false };
    },
    computed: {
        ...mapGetters("saveStatus", ["status", "canRetry"]),
        ...mapState({
            failures: (state) => state.saveStatus.failures,
            lastSavedAt: (state) => state.saveStatus.lastSavedAt,
        }),
        label() {
            return LABELS[this.status];
        },
        explanation() {
            switch (this.status) {
                case "saving":
                    return "Sending your changes to the server";
                case "unsaved":
                    return "Some edits are not sent yet. They are saved when you press Enter "
                        + "or click outside the text, or a few seconds after you stop typing.";
                case "failed":
                    return this.failures[0].message;
                default:
                    if (!this.lastSavedAt) return "No changes to save";
                    return "All changes saved, last at "
                        + new Date(this.lastSavedAt).toLocaleTimeString();
            }
        },
    },
    watch: {
        failures(failures, previous) {
            // an alert for each new failure, so that it cannot go unnoticed
            failures.filter((failure) => !previous.includes(failure)).forEach((failure) => {
                this.addAlert({ color: "alert", message: `Save failed: ${failure.message}` });
            });
        },
    },
    methods: {
        ...mapActions("alerts", { addAlert: "add" }),
        ...mapActions("parts", ["loadPartByOrder"]),
        async retry() {
            this.busy = true;
            try {
                const { created } = await retryFailedSaves(this.$store);
                if (created && this.status !== "failed") {
                    // what was created is saved, but the editor does not know it yet
                    await this.reloadPage();
                }
            } finally {
                this.busy = false;
            }
        },
        async discard() {
            this.busy = true;
            try {
                dismissFailedSaves(this.$store);
                await this.reloadPage();
            } finally {
                this.busy = false;
            }
        },
        async reloadPage() {
            // show the page as it is saved on the server
            await this.loadPartByOrder(this.$store.state.parts.order);
        },
    },
};
</script>
