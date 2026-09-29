<template>
    <VMenu
        placement="bottom-start"
        theme="vertical-menu"
        :triggers="['click']"
        :disabled="disabled"
    >
        <VDropdown
            theme="escr-tooltip-small"
            placement="bottom"
            :distance="8"
            :triggers="['hover']"
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
