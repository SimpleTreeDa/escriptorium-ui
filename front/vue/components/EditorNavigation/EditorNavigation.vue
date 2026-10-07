<template>
    <nav class="escr-editor-nav">
        <div class="escr-editor-nav-meta">
            <EscrBreadcrumbs
                :items="breadcrumbs"
            />
            <div class="escr-element-title-row">
                <h1
                    class="escr-element-title"
                    :title="elementHeadingFull"
                >
                    {{ elementHeading }}
                </h1>
                <EditorialStatusMenu
                    v-if="elementPk"
                    :status="editorialStatus || 'not_started'"
                    :change="statusChangeText"
                    :disabled="disabled"
                    :on-select="setStatus"
                />
            </div>
        </div>
        <div class="escr-editor-nav-actions">
            <SaveStatus />
            <TaskStatus />
            <VDropdown
                theme="escr-tooltip-small"
                placement="bottom"
                :distance="8"
                :triggers="['hover']"
            >
                <EscrButton
                    color="text"
                    :aria-label="`${getPrevOrNextString('left')} page`"
                    :on-click="() => loadPart(getPrevOrNextString('left'))"
                    :disabled="disabled || !hasPrevOrNextElement('left')"
                >
                    <template #button-icon>
                        <ArrowCircleLeftIcon />
                    </template>
                </EscrButton>
                <template #popper>
                    {{ getPrevOrNextTooltip('left') }}
                </template>
            </VDropdown>
            <VDropdown
                theme="escr-tooltip-small"
                placement="bottom"
                :distance="8"
                :triggers="['hover']"
            >
                <EscrButton
                    color="text"
                    :aria-label="`${getPrevOrNextString('right')} page`"
                    :on-click="() => loadPart(getPrevOrNextString('right'))"
                    :disabled="disabled || !hasPrevOrNextElement('right')"
                >
                    <template #button-icon>
                        <ArrowCircleRightIcon />
                    </template>
                </EscrButton>
                <template #popper>
                    {{ getPrevOrNextTooltip('right') }}
                </template>
            </VDropdown>
            <div
                v-if="partsCount"
                class="element-switcher"
            >
                <input
                    v-if="(elementNumber || elementNumber === 0) && elementNumber !== -1"
                    type="number"
                    :min="1"
                    :max="partsCount"
                    :value="elementNumber + 1"
                    @focus="() => setBlockShortcuts(true)"
                    @blur="() => setBlockShortcuts(false)"
                    @keydown="submitNavigation"
                >
                <span v-else>-</span> / {{ partsCount }}
            </div>
            <PagePicker :disabled="disabled" />
            <VDropdown
                class="new-section with-separator"
                theme="escr-tooltip-small"
                placement="bottom"
                :distance="8"
                :triggers="['hover']"
            >
                <EscrButton
                    color="text"
                    aria-label="View Element Details"
                    :disabled="disabled"
                    :on-click="() => openModal('elementDetails')"
                >
                    <template #button-icon>
                        <InfoOutlineIcon />
                    </template>
                </EscrButton>
                <template #popper>
                    View Element Details
                </template>
            </VDropdown>
            <VDropdown
                theme="escr-tooltip-small"
                placement="bottom"
                :distance="8"
                :triggers="['hover']"
            >
                <EscrButton
                    color="text"
                    aria-label="Manage Ontology"
                    :disabled="disabled"
                    :on-click="() => openModal('ontology')"
                >
                    <template #button-icon>
                        <OntologyIcon />
                    </template>
                </EscrButton>
                <template #popper>
                    Ontology
                </template>
            </VDropdown>
            <VDropdown
                theme="escr-tooltip-small"
                placement="bottom"
                :distance="8"
                :triggers="['hover']"
            >
                <EscrButton
                    color="text"
                    aria-label="Manage Transcriptions"
                    :disabled="disabled"
                    :on-click="() => openModal('transcriptions')"
                >
                    <template #button-icon>
                        <TranscribeIcon />
                    </template>
                </EscrButton>
                <template #popper>
                    Transcriptions
                </template>
            </VDropdown>
        </div>
    </nav>
</template>
<script>
import { Dropdown as VDropdown } from "floating-vue";
import { mapActions, mapMutations, mapState } from "vuex";
import ArrowCircleLeftIcon from "../Icons/ArrowCircleLeftIcon/ArrowCircleLeftIcon.vue";
import ArrowCircleRightIcon from "../Icons/ArrowCircleRightIcon/ArrowCircleRightIcon.vue";
import EscrBreadcrumbs from "../Breadcrumbs/Breadcrumbs.vue";
import EscrButton from "../Button/Button.vue";
import EditorialStatusMenu from "../EditorialStatus/EditorialStatusMenu.vue";
import InfoOutlineIcon from "../Icons/InfoOutlineIcon/InfoOutlineIcon.vue";
import OntologyIcon from "../Icons/OntologyIcon/OntologyIcon.vue";
import PagePicker from "../PagePicker/PagePicker.vue";
import SaveStatus from "../SaveStatus/SaveStatus.vue";
import TaskStatus from "../TaskStatus/TaskStatus.vue";
import TranscribeIcon from "../Icons/TranscribeIcon/TranscribeIcon.vue";
import { editorialStatusChange } from "../../store/util/editorialStatus";
import { middleTruncate } from "../../store/util/filename";
import "./EditorNavigation.css";

export default {
    name: "EscrEditorNavigation",
    components: {
        ArrowCircleLeftIcon,
        ArrowCircleRightIcon,
        EscrBreadcrumbs,
        EditorialStatusMenu,
        EscrButton,
        InfoOutlineIcon,
        OntologyIcon,
        PagePicker,
        SaveStatus,
        TaskStatus,
        TranscribeIcon,
        VDropdown,
    },
    props: {
        /**
         * True if all buttons and tools should be disabled
         */
        disabled: {
            type: Boolean,
            required: true,
        },
    },
    computed: {
        ...mapState({
            documentId: (state) => state.document.id,
            documentName: (state) => state.document.name,
            elementFilename: (state) => state.parts.filename,
            elementNumber: (state) => state.parts.order,
            elementPk: (state) => state.parts.pk,
            elementTitle: (state) => state.parts.title,
            editorialStatus: (state) => state.parts.editorial_status,
            nextPart: (state) => state.parts.next,
            partsCount: (state) => state.document.partsCount,
            prevPart: (state) => state.parts.previous,
            projectName: (state) => state.document.projectName,
            projectSlug: (state) => state.document.projectSlug,
            readDirection: (state) => state.document.readDirection,
        }),
        statusChangeText() {
            return editorialStatusChange({
                editorial_status_by: this.$store.state.parts.editorial_status_by,
                editorial_status_at: this.$store.state.parts.editorial_status_at,
            });
        },
        breadcrumbs() {
            let breadcrumbs = [{ title: "Loading..." }];
            if (this.projectName && this.projectSlug && this.documentName && this.documentId) {
                breadcrumbs = [
                    { title: "My Projects", href: "/projects" },
                    {
                        title: this.projectName,
                        href: `/project/${this.projectSlug}`
                    },
                    {
                        title: this.documentName,
                        href: `/document/${this.documentId}`
                    },
                    {
                        title: "Processing",
                        // include select=pk to select the image being edited in the list
                        href: `/document/${this.documentId}/images${
                            this.elementPk ? "?select=" + this.elementPk : ""
                        }`,
                    },
                    {
                        title: this.elementTitle
                            ? (this.elementTitle.length > 60
                                ? this.elementTitle.slice(0, 60) + "…"
                                : this.elementTitle)
                            : "Loading...",
                    },
                ];
            }
            return breadcrumbs;
        },
        elementHeadingFull() {
            return (this.elementTitle && this.elementFilename)
                ? `${this.elementTitle} – ${this.elementFilename}`
                : "Loading...";
        },
        elementHeading() {
            if (!this.elementTitle || !this.elementFilename) return "Loading...";
            // shorten long filenames in the middle to keep their end (folio, extension) visible
            return `${this.elementTitle} – ${middleTruncate(this.elementFilename, 48)}`;
        },
    },
    methods: {
        ...mapActions("parts", ["loadPart", "loadPartByOrder", "setEditorialStatus"]),
        async setStatus(status) {
            try {
                await this.setEditorialStatus(status);
            } catch (err) {
                // reported by the save status
            }
        },
        ...mapActions("globalTools", ["openModal"]),
        ...mapMutations("document", ["setBlockShortcuts"]),
        hasPrevOrNextElement(direction) {
            if (direction === "left") {
                // left = next in RTL, previous in LTR
                return this.readDirection === "rtl" ? this.nextPart : this.prevPart;
            }else {
                // right = previous in RTL, next in LTR
                return this.readDirection === "rtl" ? this.prevPart : this.nextPart;
            }
        },
        getPrevOrNextString(direction) {
            if (direction === "left") {
                // left = next in RTL, previous in LTR
                return this.readDirection === "rtl" ? "next" : "previous";
            } else {
                // right = previous in RTL, next in LTR
                return this.readDirection === "rtl" ? "previous" : "next";
            }
        },
        getPrevOrNextTooltip(direction) {
            if (direction === "left") {
                // left = next in RTL, previous in LTR
                return this.readDirection === "rtl"
                    ? "Next Element (PgDn; End: last)"
                    : "Previous Element (PgUp; Home: first)";
            } else {
                // right = previous in RTL, next in LTR
                return this.readDirection === "rtl"
                    ? "Previous Element (PgUp; Home: first)"
                    : "Next Element (PgDn; End: last)";
            }
        },
        submitNavigation(e) {
            const num = parseInt(e.target.value);
            if (e.key === "Enter" && num && num > 0 && num <= this.partsCount) {
                this.loadPartByOrder(num - 1);
            }
        }
    }
}
</script>
