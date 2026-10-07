<template>
    <!--
        auto-hide closes the menu on a click outside it and on Escape. It is set here
        because on the editor page floating-vue installs itself on the global Vue that the
        legacy editor creates, before store/index.js can register the project's themes, so
        "vertical-menu" inherits nothing from the built-in "menu" and "dropdown" themes there.
    -->
    <VMenu
        placement="bottom-start"
        theme="vertical-menu"
        :triggers="['click']"
        :auto-hide="true"
        :disabled="disabled"
    >
        <!--
            The tooltip is a child popper of the menu, and floating-vue never hides a popper
            while one of its children is shown. Hiding the tooltip on click lets a second
            click on the button close the menu.
        -->
        <VDropdown
            theme="escr-tooltip-small"
            placement="bottom"
            :distance="8"
            :triggers="['hover']"
            :hide-triggers="['hover', 'click']"
        >
            <button
                type="button"
                class="escr-editorial-status-button"
                :disabled="disabled"
                :aria-label="`Editorial status: ${label}. Change it`"
            >
                <span :class="['escr-editorial-status', `status-${status}`]">{{ label }}</span>
                <ChevronDownIcon />
            </button>
            <template #popper>
                {{ change || "Editorial status of this page" }}
            </template>
        </VDropdown>
        <template #popper="{ hide }">
            <ul class="escr-vertical-menu escr-editorial-status-menu">
                <li
                    v-for="option in statuses"
                    :key="option.value"
                >
                    <button
                        type="button"
                        :class="{ selected: option.value === status }"
                        @click="() => { hide(); onSelect(option.value); }"
                    >
                        <span :class="['escr-editorial-status', `status-${option.value}`]">
                            {{ option.label }}
                        </span>
                    </button>
                </li>
            </ul>
        </template>
    </VMenu>
</template>
<script>
import { Dropdown as VDropdown, Menu as VMenu } from "floating-vue";
import ChevronDownIcon from "../Icons/ChevronDownIcon/ChevronDownIcon.vue";
import { EDITORIAL_STATUSES, editorialStatusLabel } from "../../store/util/editorialStatus";
import "../VerticalMenu/VerticalMenu.css";
import "./EditorialStatus.css";

/**
 * The editorial status of a page, as a button opening the list of statuses.
 */
export default {
    name: "EscrEditorialStatusMenu",
    components: { ChevronDownIcon, VDropdown, VMenu },
    props: {
        /**
         * Current status, e.g. "reviewed_1"
         */
        status: {
            type: String,
            default: "not_started",
        },
        /**
         * Who set it and when, shown in the tooltip
         */
        change: {
            type: String,
            default: "",
        },
        disabled: {
            type: Boolean,
            default: false,
        },
        /**
         * Called with the status chosen
         */
        onSelect: {
            type: Function,
            required: true,
        },
    },
    data() {
        return { statuses: EDITORIAL_STATUSES };
    },
    computed: {
        label() {
            return editorialStatusLabel(this.status) || "Not started";
        },
    },
};
</script>
