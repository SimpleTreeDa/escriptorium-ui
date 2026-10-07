<template>
    <div
        :class="{
            ['d-table-row']: true,
            ['pt-1']: legacyModeEnabled,
            ['escr-line-version']: !legacyModeEnabled,
        }"
    >
        <div
            class="d-table-cell w-100 escr-line-content"
            :title="version.data.content"
        >
            <TextDiff
                :before="previous ? previous.data.content : null"
                :after="versionContent"
            />
        </div>
        <div
            class="d-table-cell"
            title="Edited by author (source)"
        >
            {{ version.author }} ( {{ version.source }} )
        </div>
        <div
            class="d-table-cell"
            title="Edited on"
        >
            {{ momentDate }}
        </div>
        <div class="d-table-cell">
            <button
                v-if="legacyModeEnabled"
                class="btn btn-sm btn-info js-pull-state"
                title="Load this state"
                @click="loadState"
            >
                <i class="fas fa-file-upload" />
            </button>
            <EscrButton
                v-else
                size="small"
                color="text-alt"
                :on-click="loadState"
            >
                <template #button-icon>
                    <HistoryIcon />
                </template>
            </EscrButton>
        </div>
    </div>
</template>

<script>
import EscrButton from "./Button/Button.vue";
import HistoryIcon from "./Icons/HistoryIcon/HistoryIcon.vue";
import TextDiff from "./TextDiff.vue";

export default Vue.extend({
    components: {
        EscrButton,
        HistoryIcon,
        TextDiff,
    },
    props: {
        version: {
            type: Object,
            required: true,
        },
        previous: {
            type: Object,
            default: null,
        },
        /**
         * Whether or not legacy mode is enabled by the user.
         */
        legacyModeEnabled: {
            type: Boolean,
            default: true,
        },
    },
    computed: {
        momentDate() {
            return moment.tz(this.version.created_at, this.timeZone).calendar();
        },
        versionContent() {
            if (this.version.data) {
                return this.version.data.content;
            }
            return "";
        },
    },
    created() {
        this.timeZone = this.$parent.timeZone;
    },
    beoforeDestroy() {
        this.timeZone = null;  // make sure it's garbage collected
    },
    methods: {
        async loadState() {
            this.$parent.localTranscription = this.version.data.content;
        },
    }
});
</script>
