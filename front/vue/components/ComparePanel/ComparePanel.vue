<template>
    <div
        id="compare-panel"
        class="col panel"
    >
        <EditorToolbar
            panel-type="comparison"
            :disabled="disabled"
            :panel-index="panelIndex"
        >
            <template #editor-tools-center>
                <div class="escr-editortools-paneltools">
                    <TranscriptionDropdown :disabled="disabled" />
                    <ToggleButton
                        class="compare-filter-toggle"
                        color="secondary"
                        label="Only lines that differ"
                        :checked="onlyChanged"
                        :disabled="disabled || !comparable"
                        :on-change="toggleOnlyChanged"
                    />
                </div>
            </template>
        </EditorToolbar>
        <div class="content-container escr-compare-content">
            <p
                v-if="!transcriptionsLoaded"
                class="compare-message"
            >
                Loading the text…
            </p>
            <p
                v-else-if="!rows.length"
                class="compare-message"
            >
                This page has no lines.
            </p>
            <p
                v-else-if="!comparable"
                class="compare-message"
            >
                No earlier version of the text of this page is kept in this transcription.
            </p>
            <template v-else>
                <div class="compare-bar">
                    <ul class="compare-summaries">
                        <li
                            v-for="summary in summaries"
                            :key="`${summary.left}-${summary.right}`"
                        >
                            <span class="compare-pair">
                                {{ shortLabel(columns[summary.left]) }}
                                →
                                {{ shortLabel(columns[summary.right]) }}:
                            </span>
                            {{ summary.changed }} of {{ summary.compared }}
                            {{ summary.compared === 1 ? "line differs" : "lines differ" }}
                            <span
                                v-if="summary.cer !== null"
                                class="compare-cer"
                                :title="cerExplanation(summary)"
                            >· CER {{ formatPercent(summary.cer) }}</span>
                            <span
                                v-if="summary.skipped"
                                class="compare-skipped"
                                :title="skippedExplanation"
                            >· {{ summary.skipped }} not compared</span>
                        </li>
                    </ul>
                    <EscrButton
                        v-if="columns.length < maxColumns"
                        color="text"
                        size="small"
                        label="Add a column"
                        :disabled="disabled"
                        :on-click="addColumn"
                    >
                        <template #button-icon>
                            <PlusIcon />
                        </template>
                    </EscrButton>
                </div>
                <table class="compare-table">
                    <thead>
                        <tr>
                            <th
                                scope="col"
                                class="compare-line-number"
                            >
                                <span class="sr-only">Line</span>
                            </th>
                            <th
                                v-for="(column, i) in columns"
                                :key="i"
                                scope="col"
                            >
                                <div class="compare-column-heading">
                                    <select
                                        :value="column.id"
                                        :aria-label="`Version shown in column ${i + 1}`"
                                        :disabled="disabled"
                                        @change="setColumn(i, $event.target.value)"
                                    >
                                        <option
                                            v-for="version in versions"
                                            :key="version.id"
                                            :value="version.id"
                                        >
                                            {{ versionLabel(version) }}
                                        </option>
                                    </select>
                                    <button
                                        v-if="columns.length > 2"
                                        type="button"
                                        class="compare-remove-column"
                                        :aria-label="`Remove column ${i + 1}`"
                                        :title="`Remove column ${i + 1}`"
                                        :disabled="disabled"
                                        @click="removeColumn(i)"
                                    >
                                        <XIcon />
                                    </button>
                                </div>
                            </th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr
                            v-for="row in shownRows"
                            :key="row.pk"
                            :data-line="row.pk"
                            :class="{ 'is-edited': row.pk === editedPk }"
                        >
                            <th
                                scope="row"
                                class="compare-line-number"
                            >
                                <button
                                    type="button"
                                    :aria-label="`Edit line ${row.number}`"
                                    :title="`Edit line ${row.number}`"
                                    @click="editLine(row.pk)"
                                >
                                    {{ row.number }}
                                </button>
                            </th>
                            <td
                                v-for="(cell, i) in row.cells"
                                :key="i"
                                :class="`is-${cell.status}`"
                                dir="auto"
                            >
                                <!-- text inline, no line breaks: the cells keep white space -->
                                <!-- eslint-disable vue/multiline-html-element-content-newline -->
                                <!-- eslint-disable vue/singleline-html-element-content-newline -->
                                <span
                                    v-if="cell.status === 'unknown'"
                                    class="compare-note"
                                >Not in the kept history</span>
                                <span
                                    v-else-if="cell.status === 'none'"
                                    class="compare-note"
                                >No text</span>
                                <template v-else-if="cell.parts && cell.parts.length">
                                    <component
                                        :is="partTags[part.type]"
                                        v-for="(part, j) in cell.parts"
                                        :key="j"
                                        :class="`compare-${part.type}`"
                                    >{{ part.text }}</component>
                                </template>
                                <span
                                    v-else-if="!cell.text"
                                    class="compare-note"
                                >Empty</span>
                                <template v-else>{{ cell.text }}</template>
                                <!-- eslint-enable vue/multiline-html-element-content-newline -->
                                <!-- eslint-enable vue/singleline-html-element-content-newline -->
                            </td>
                        </tr>
                    </tbody>
                </table>
                <p
                    v-if="onlyChanged && !shownRows.length"
                    class="compare-message"
                >
                    No line differs between these versions.
                </p>
            </template>
        </div>
    </div>
</template>

<script>
import { mapState } from "vuex";
import EditorToolbar from "../EditorToolbar/EditorToolbar.vue";
import EscrButton from "../Button/Button.vue";
import PlusIcon from "../Icons/PlusIcon/PlusIcon.vue";
import ToggleButton from "../ToggleButton/ToggleButton.vue";
import TranscriptionDropdown from "../EditorTranscriptionDropdown/EditorTranscriptionDropdown.vue";
import XIcon from "../Icons/XIcon/XIcon.vue";
import {
    MAX_COLUMNS,
    chooseColumns,
    compareColumns,
    compareRows,
    lineHistory,
    pageVersions,
    versionToAdd,
} from "../../../src/editor/versionCompare";
import "./ComparePanel.css";

/**
 * Versions of the text of the page side by side, in the selected transcription:
 * the model output, the page as each person left it, the imported text and the
 * current text. Each column shows its differences with the column on its left.
 * Read only.
 */
export default {
    name: "EscrComparePanel",
    components: {
        EditorToolbar,
        EscrButton,
        PlusIcon,
        ToggleButton,
        TranscriptionDropdown,
        XIcon,
    },
    props: {
        /**
         * True if all buttons and tools should be disabled
         */
        disabled: {
            type: Boolean,
            required: true,
        },
        /**
         * The index of this panel, to allow swapping panels
         */
        panelIndex: {
            type: Number,
            required: true,
        },
    },
    data() {
        return {
            // ids of the versions chosen for the columns, kept from page to page
            columnIds: [],
            onlyChanged: false,
            maxColumns: MAX_COLUMNS,
            // the diff as text: <ins> and <del> also tell assistive technologies
            partTags: { same: "span", added: "ins", removed: "del" },
            skippedExplanation: "Lines without text in one of the two versions, "
                + "or older than the history kept",
        };
    },
    computed: {
        ...mapState({
            allLines: (state) => state.lines.all,
            editedLine: (state) => state.lines.editedLine,
            transcriptionsLoaded: (state) => state.transcriptions.transcriptionsLoaded,
        }),
        editedPk() {
            return this.editedLine ? this.editedLine.pk : null;
        },
        lines() {
            return this.allLines.map((line, index) => ({
                pk: line.pk,
                order: Number.isInteger(line.order) ? line.order : index,
                history: lineHistory(line.currentTrans),
            }));
        },
        versions() {
            return pageVersions(this.lines.map((line) => line.history));
        },
        comparable() {
            return this.versions.length > 1;
        },
        columns() {
            return chooseColumns(this.columnIds, this.versions);
        },
        rows() {
            return compareRows(this.lines, this.columns);
        },
        shownRows() {
            return this.onlyChanged ? this.rows.filter((row) => row.changed) : this.rows;
        },
        /**
         * Each column compared with the one on its left, and the first with the
         * last when there are three
         */
        summaries() {
            const pairs = this.columns.slice(1).map((_, i) => [i, i + 1]);
            if (this.columns.length > 2) pairs.push([0, this.columns.length - 1]);
            return pairs.map(([left, right]) => ({
                left,
                right,
                ...compareColumns(this.rows, left, right),
            }));
        },
    },
    watch: {
        editedPk(pk) {
            if (pk === null) return;
            // show the line edited in another panel
            this.$nextTick(() => {
                const row = this.$el.querySelector(`tr[data-line="${pk}"]`);
                if (row) row.scrollIntoView({ block: "nearest" });
            });
        },
    },
    methods: {
        toggleOnlyChanged() {
            this.onlyChanged = !this.onlyChanged;
        },
        setColumn(index, id) {
            const ids = this.columns.map((column) => column.id);
            ids[index] = id;
            this.columnIds = ids;
        },
        addColumn() {
            const ids = this.columns.map((column) => column.id);
            ids.splice(ids.length - 1, 0, versionToAdd(this.columns, this.versions).id);
            this.columnIds = ids;
        },
        removeColumn(index) {
            this.columnIds = this.columns
                .map((column) => column.id)
                .filter((_, i) => i !== index);
        },
        /**
         * Edit the line in the other panels: the transcription panel opens it
         */
        editLine(pk) {
            const line = this.allLines.find((l) => l.pk === pk);
            if (line) this.$store.commit("lines/setEditedLine", line);
        },
        formatTime(at) {
            if (!Number.isFinite(at)) return "";
            return new Date(at).toLocaleString(undefined, {
                month: "short",
                day: "numeric",
                hour: "numeric",
                minute: "2-digit",
            });
        },
        versionLabel(version) {
            return version.kind === "author"
                ? `${version.label}, ${this.formatTime(version.at)}`
                : version.label;
        },
        shortLabel(version) {
            if (version.kind === "model") return "Model output";
            if (version.kind === "author") return version.author;
            return version.label;
        },
        formatPercent(rate) {
            return rate.toLocaleString(undefined, {
                style: "percent",
                maximumFractionDigits: 1,
            });
        },
        cerExplanation(summary) {
            return `Character error rate of "${this.versionLabel(this.columns[summary.left])}" `
                + `against "${this.versionLabel(this.columns[summary.right])}": `
                + `${summary.edits} characters to change for ${summary.referenceLength}`;
        },
    },
};
</script>
