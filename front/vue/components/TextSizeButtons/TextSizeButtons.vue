<template>
    <div
        class="escr-text-size"
        role="group"
        aria-label="Text size"
    >
        <VDropdown
            theme="escr-tooltip-small"
            placement="bottom"
            :distance="8"
            :triggers="['hover']"
        >
            <EscrButton
                class="escr-text-size-smaller"
                color="text"
                size="small"
                label="A−"
                aria-label="Smaller text"
                :disabled="disabled || !canBeSmaller"
                :on-click="onSmaller"
            />
            <template #popper>
                Smaller text
            </template>
        </VDropdown>
        <VDropdown
            theme="escr-tooltip-small"
            placement="bottom"
            :distance="8"
            :triggers="['hover']"
        >
            <EscrButton
                class="escr-text-size-larger"
                color="text"
                size="small"
                label="A+"
                aria-label="Larger text"
                :disabled="disabled || !canBeLarger"
                :on-click="onLarger"
            />
            <template #popper>
                Larger text
            </template>
        </VDropdown>
    </div>
</template>
<script>
import { Dropdown as VDropdown } from "floating-vue";
import EscrButton from "../Button/Button.vue";
import "./TextSizeButtons.css";

/**
 * A− and A+ buttons of the panel toolbars, to change the size of the text.
 */
export default {
    name: "EscrTextSizeButtons",
    components: { EscrButton, VDropdown },
    props: {
        disabled: {
            type: Boolean,
            default: false,
        },
        /**
         * False at the smallest size
         */
        canBeSmaller: {
            type: Boolean,
            required: true,
        },
        /**
         * False at the largest size
         */
        canBeLarger: {
            type: Boolean,
            required: true,
        },
        onSmaller: {
            type: Function,
            required: true,
        },
        onLarger: {
            type: Function,
            required: true,
        },
    },
};
</script>
