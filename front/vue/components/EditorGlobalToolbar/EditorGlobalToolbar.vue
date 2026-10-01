<template>
    <div class="escr-toolbar escr-editor-global-toolbar">
        <!-- empty div for space -->
        <div class="escr-editortoolbar-section" />

        <!-- main toolbar items -->
        <div class="escr-editortoolbar-section">
            <VDropdown
                theme="escr-tooltip-small"
                placement="bottom"
                :disabled="disabled"
                :distance="8"
                :triggers="['hover']"
            >
                <ToggleButton
                    id="escr-toggle-select"
                    color="text"
                    :checked="tool === 'select'"
                    :disabled="disabled"
                    :on-change="() => toggleTool('select')"
                >
                    <template #button-icon>
                        <CursorSelectIcon />
                    </template>
                </ToggleButton>
                <template #popper>
                    Select (S)
                </template>
            </VDropdown>
            <VDropdown
                theme="escr-tooltip-small"
                placement="bottom"
                :disabled="disabled"
                :distance="8"
                :triggers="['hover']"
            >
                <ToggleButton
                    id="escr-toggle-pan"
                    color="text"
                    :checked="tool === 'pan'"
                    :disabled="disabled"
                    :on-change="() => toggleTool('pan')"
                >
                    <template #button-icon>
                        <CursorPanIcon />
                    </template>
                </ToggleButton>
                <template #popper>
                    Pan (P)
                </template>
            </VDropdown>
            <div class="new-section with-separator">
                <VDropdown
                    theme="escr-tooltip-small"
                    placement="bottom"
                    :distance="8"
                    :triggers="['hover']"
                >
                    <EscrButton
                        aria-label="Zoom in"
                        color="text"
                        :on-click="onZoomIn"
                        :disabled="disabled"
                    >
                        <template #button-icon>
                            <ZoomInIcon />
                        </template>
                    </EscrButton>
                    <template #popper>
                        Zoom in (Ctrl +)
                    </template>
                </VDropdown>
                <VDropdown
                    theme="escr-tooltip-small"
                    placement="bottom"
                    :distance="8"
                    :triggers="['hover']"
                >
                    <EscrButton
                        aria-label="Zoom out"
                        color="text"
                        :on-click="onZoomOut"
                        :disabled="disabled"
                    >
                        <template #button-icon>
                            <ZoomOutIcon />
                        </template>
                    </EscrButton>
                    <template #popper>
                        Zoom out (Ctrl -)
                    </template>
                </VDropdown>
                <VDropdown
                    theme="escr-tooltip-small"
                    placement="bottom"
                    :distance="8"
                    :triggers="['hover']"
                >
                    <EscrButton
                        aria-label="Reset zoom"
                        color="text"
                        :on-click="onZoomReset"
                        :disabled="disabled"
                    >
                        <template #button-icon>
                            <ZoomResetIcon />
                        </template>
                    </EscrButton>
                    <template #popper>
                        Reset zoom (Ctrl 0)
                    </template>
                </VDropdown>
            </div>
            <div class="new-section with-separator">
                <VDropdown
                    theme="escr-tooltip-small"
                    placement="bottom"
                    :distance="8"
                    :triggers="['hover']"
                >
                    <EscrButton
                        aria-label="Rotate Counterclockwise"
                        color="text"
                        :on-click="() => onRotate(270)"
                        :disabled="disabled"
                    >
                        <template #button-icon>
                            <RotateCCWIcon />
                        </template>
                    </EscrButton>
                    <template #popper>
                        Rotate Counterclockwise (Ctrl ,)
                    </template>
                </VDropdown>
                <VDropdown
                    theme="escr-tooltip-small"
                    placement="bottom"
                    :distance="8"
                    :triggers="['hover']"
                >
                    <EscrButton
                        aria-label="Rotate Clockwise"
                        color="text"
                        :on-click="() => onRotate(90)"
                        :disabled="disabled"
                    >
                        <template #button-icon>
                            <RotateCWIcon />
                        </template>
                    </EscrButton>
                    <template #popper>
                        Rotate Clockwise (Ctrl .)
                    </template>
                </VDropdown>
            </div>
        </div>

        <!-- quick actions, panel layout and add panel -->
        <div class="escr-editortoolbar-section">
            <VDropdown
                placement="bottom-end"
                theme="vertical-menu"
                :shown="layoutMenuOpen"
                :triggers="[]"
                :auto-hide="true"
                @apply-hide="closeLayoutMenu"
            >
                <EscrButton
                    class="escr-layout-menu-toggle"
                    :disabled="disabled"
                    :on-click="openLayoutMenu"
                    color="text-alt"
                    label="Layout"
                    aria-label="Panel layout"
                >
                    <template #button-icon>
                        <LayoutStackedIcon v-if="layoutOrientation === 'column'" />
                        <LayoutSideBySideIcon v-else />
                    </template>
                    <template #button-icon-right>
                        <ChevronDownIcon />
                    </template>
                </EscrButton>
                <template #popper>
                    <ul
                        class="escr-vertical-menu escr-layout-menu"
                        role="menu"
                        aria-label="Panel layout"
                    >
                        <li>
                            <button
                                type="button"
                                role="menuitemradio"
                                :aria-checked="layoutOrientation === 'row' ? 'true' : 'false'"
                                :class="{ preselected: layoutOrientation === 'row' }"
                                @mousedown="onSetLayout('row')"
                            >
                                <LayoutSideBySideIcon />
                                <span>Side by side</span>
                            </button>
                        </li>
                        <li>
                            <button
                                type="button"
                                role="menuitemradio"
                                :aria-checked="layoutOrientation === 'column' ? 'true' : 'false'"
                                :class="{ preselected: layoutOrientation === 'column' }"
                                @mousedown="onSetLayout('column')"
                            >
                                <LayoutStackedIcon />
                                <span>Stacked</span>
                            </button>
                        </li>
                        <li class="new-section">
                            <button
                                type="button"
                                role="menuitem"
                                :disabled="editorPanels.length < 2"
                                @mousedown="onResetPanelSizes"
                            >
                                <span class="escr-menuitem-noicon">Reset panel sizes</span>
                            </button>
                        </li>
                    </ul>
                </template>
            </VDropdown>
            <VDropdown
                v-if="editorPanels.length < 3"
                placement="bottom-end"
                theme="vertical-menu"
                :shown="addPanelMenuOpen"
                :triggers="[]"
                :auto-hide="true"
                @apply-hide="closeAddPanelMenu"
            >
                <EscrButton
                    :disabled="disabled"
                    :on-click="openAddPanelMenu"
                    color="text-alt"
                    label="Add Panel"
                >
                    <template #button-icon>
                        <AddPanelIcon />
                    </template>
                    <template #button-icon-right>
                        <ChevronDownIcon />
                    </template>
                </EscrButton>
                <template #popper>
                    <ul class="escr-vertical-menu">
                        <li v-if="!editorPanels.includes('segmentation')">
                            <button
                                type="button"
                                @mousedown="onAddEditorPanel('segmentation')"
                            >
                                <SegmentIcon />
                                <span>Segmentation</span>
                            </button>
                        </li>
                        <li v-if="!editorPanels.includes('visualisation')">
                            <button
                                type="button"
                                @mousedown="onAddEditorPanel('visualisation')"
                            >
                                <TranscribeIcon />
                                <span>Transcription</span>
                            </button>
                        </li>
                        <li v-if="!editorPanels.includes('diplomatic')">
                            <button
                                type="button"
                                @mousedown="onAddEditorPanel('diplomatic')"
                            >
                                <TextPanelIcon />
                                <span>Text / Line Ordering</span>
                            </button>
                        </li>
                        <li v-if="!editorPanels.includes('source')">
                            <button
                                type="button"
                                @mousedown="onAddEditorPanel('source')"
                            >
                                <ImageAnnotationIcon />
                                <span>Image Annotation</span>
                            </button>
                        </li>
                    </ul>
                </template>
            </VDropdown>
        </div>
    </div>
</template>
<script>
import { mapActions, mapMutations, mapState } from "vuex";
import AddPanelIcon from "../Icons/AddPanelIcon/AddPanelIcon.vue";
import ChevronDownIcon from "../Icons/ChevronDownIcon/ChevronDownIcon.vue";
import CursorPanIcon from "../Icons/CursorPanIcon/CursorPanIcon.vue";
import CursorSelectIcon from "../Icons/CursorSelectIcon/CursorSelectIcon.vue";
import EscrButton from "../Button/Button.vue";
import ImageAnnotationIcon from "../Icons/ImageAnnotationIcon/ImageAnnotationIcon.vue";
import LayoutSideBySideIcon from "../Icons/LayoutSideBySideIcon/LayoutSideBySideIcon.vue";
import LayoutStackedIcon from "../Icons/LayoutStackedIcon/LayoutStackedIcon.vue";
import RotateCCWIcon from "../Icons/RotateCCWIcon/RotateCCWIcon.vue";
import RotateCWIcon from "../Icons/RotateCWIcon/RotateCWIcon.vue";
import SegmentIcon from "../Icons/SegmentIcon/SegmentIcon.vue";
import TextPanelIcon from "../Icons/TextPanelIcon/TextPanelIcon.vue";
import ToggleButton from "../ToggleButton/ToggleButton.vue";
import TranscribeIcon from "../Icons/TranscribeIcon/TranscribeIcon.vue";
import ZoomInIcon from "../Icons/ZoomInIcon/ZoomInIcon.vue";
import ZoomOutIcon from "../Icons/ZoomOutIcon/ZoomOutIcon.vue";
import ZoomResetIcon from "../Icons/ZoomResetIcon/ZoomResetIcon.vue";
import { Dropdown as VDropdown } from "floating-vue";
import "./EditorGlobalToolbar.css";

export default {
    name: "EscrEditorGlobalToolbar",
    components: {
        AddPanelIcon,
        CursorPanIcon,
        CursorSelectIcon,
        EscrButton,
        ImageAnnotationIcon,
        LayoutSideBySideIcon,
        LayoutStackedIcon,
        RotateCCWIcon,
        RotateCWIcon,
        SegmentIcon,
        TextPanelIcon,
        ToggleButton,
        TranscribeIcon,
        VDropdown,
        ZoomInIcon,
        ZoomOutIcon,
        ZoomResetIcon,
        ChevronDownIcon
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
         * Callback function to rotate
         */
        onRotate: {
            type: Function,
            required: true,
        },
        /**
         * Callback function to zoom in
         */
        onZoomIn: {
            type: Function,
            required: true,
        },
        /**
         * Callback function to zoom out
         */
        onZoomOut: {
            type: Function,
            required: true,
        },
        /**
         * Callback function to reset zoom
         */
        onZoomReset: {
            type: Function,
            required: true,
        },
        /**
         * Callback function to toggle one of the toggleable tools (pan, select)
         */
        toggleTool: {
            type: Function,
            required: true,
        },
        /**
         * Currently selected tool
         */
        tool: {
            type: String,
            required: true,
        },
    },
    data() {
        return {
            addPanelMenuOpen: false,
            layoutMenuOpen: false,
        }
    },
    computed: {
        ...mapState({
            editorPanels: (state) => state.document.editorPanels,
            layoutOrientation: (state) => state.document.editorLayout.orientation,
        }),
    },
    methods: {
        ...mapActions("document", ["addEditorPanel", "setEditorLayout"]),
        ...mapMutations("document", ["resetEditorPanelSizes"]),
        /**
         * Callback to close the panel layout menu
         */
        closeLayoutMenu() {
            this.layoutMenuOpen = false;
        },
        /**
         * Callback to open the panel layout menu
         */
        openLayoutMenu() {
            this.layoutMenuOpen = true;
        },
        /**
         * Callback to show the panels side by side ("row") or stacked ("column")
         */
        onSetLayout(orientation) {
            this.closeLayoutMenu();
            this.setEditorLayout(orientation);
        },
        /**
         * Callback to give all the panels the same size
         */
        onResetPanelSizes() {
            this.closeLayoutMenu();
            this.resetEditorPanelSizes();
        },
        /**
         * Callback to close the add panel menu
         */
        closeAddPanelMenu() {
            this.addPanelMenuOpen = false;
        },
        /**
         * Callback to open the add panel menu
         */
        openAddPanelMenu() {
            this.addPanelMenuOpen = true;
        },
        /**
         * Callback to add a panel and close the menu
         */
        onAddEditorPanel(panelType) {
            this.closeAddPanelMenu();
            this.addEditorPanel(panelType);
        }
    }
}
</script>
