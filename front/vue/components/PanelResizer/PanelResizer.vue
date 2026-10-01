<template>
    <div
        :class="{
            'escr-panel-resizer': true,
            [`escr-panel-resizer-${orientation}`]: true,
            dragging,
        }"
        role="separator"
        tabindex="0"
        :aria-orientation="orientation === 'row' ? 'vertical' : 'horizontal'"
        :aria-label="label"
        aria-valuemin="0"
        aria-valuemax="100"
        :aria-valuenow="Math.round(sizes[index] * 100)"
        :title="`${label}. Double-click to make the panels the same size.`"
        @pointerdown="startDrag"
        @pointermove="drag"
        @pointerup="stopDrag"
        @pointercancel="stopDrag"
        @lostpointercapture="stopDrag"
        @dblclick="$emit('reset')"
        @keydown="onKeyDown"
    />
</template>
<script>
import { resizeAt } from "../../../src/editor/panelLayout";
import "./PanelResizer.css";

// keyboard steps, as fractions of the space
const STEP = 0.02;
const LARGE_STEP = 0.1;

/**
 * Handle between two editor panels: drag it (or use the arrow keys) to share
 * the space differently between the panel before it and the panel after it.
 */
export default {
    name: "EscrPanelResizer",
    props: {
        /**
         * Index of the panel before this handle
         */
        index: {
            type: Number,
            required: true,
        },
        /**
         * Accessible name, e.g. "Resize the Segmentation and Transcription panels"
         */
        label: {
            type: String,
            required: true,
        },
        /**
         * Smallest size of a panel, in pixels
         */
        minPanelSize: {
            type: Number,
            default: 0,
        },
        /**
         * "row" (panels side by side) or "column" (stacked)
         */
        orientation: {
            type: String,
            required: true,
        },
        /**
         * Sizes of all the panels, as fractions adding up to 1
         */
        sizes: {
            type: Array,
            required: true,
        },
    },
    data() {
        return {
            dragging: false,
        };
    },
    beforeDestroy() {
        if (this.dragging) {
            // drop the unsaved sizes
            this.setDraggingClass(false);
            this.$emit("resize-end", null);
        }
    },
    methods: {
        /**
         * While dragging, keep the resize cursor everywhere and don't select text
         */
        setDraggingClass(dragging) {
            const classes = ["escr-panel-resizing", `escr-panel-resizing-${this.orientation}`];
            if (dragging) document.body.classList.add(...classes);
            else document.body.classList.remove(...classes);
        },
        /**
         * Pixels per unit of size, the smallest size as a fraction, and the
         * direction (1 or -1) of the panel after this handle on screen.
         */
        measure() {
            const before = this.$el.previousElementSibling.getBoundingClientRect();
            const after = this.$el.nextElementSibling.getBoundingClientRect();
            const row = this.orientation === "row";
            const pixels = row ? before.width + after.width : before.height + after.height;
            const fraction = this.sizes[this.index] + this.sizes[this.index + 1];
            const pixelsPerUnit = pixels / fraction || 1;
            // with a right-to-left page, the panel after this handle is on the left
            const direction = (row ? after.left >= before.left : after.top >= before.top) ? 1 : -1;
            return {
                pixelsPerUnit,
                min: this.minPanelSize / pixelsPerUnit,
                direction,
            };
        },
        /**
         * The pointer position along the resize axis
         */
        position(event) {
            return this.orientation === "row" ? event.clientX : event.clientY;
        },
        startDrag(event) {
            if (event.button !== 0) return;
            event.preventDefault();
            // keep receiving the pointer events, even over the segmentation canvas
            this.$el.setPointerCapture(event.pointerId);
            this.start = {
                position: this.position(event),
                sizes: this.sizes.slice(),
                ...this.measure(),
            };
            this.lastSizes = null;
            this.dragging = true;
            this.setDraggingClass(true);
        },
        drag(event) {
            if (!this.dragging) return;
            const { position, sizes, pixelsPerUnit, min, direction } = this.start;
            const delta = ((this.position(event) - position) * direction) / pixelsPerUnit;
            this.lastSizes = resizeAt(sizes, this.index, delta, min);
            this.$emit("resize", this.lastSizes);
        },
        stopDrag() {
            if (!this.dragging) return;
            this.dragging = false;
            this.setDraggingClass(false);
            this.$emit("resize-end", this.lastSizes);
        },
        onKeyDown(event) {
            // the editor's keyboard shortcuts must not see the keys used here
            if (event.key === "Enter") {
                event.preventDefault();
                event.stopPropagation();
                this.$emit("reset");
                return;
            }
            const keys = this.orientation === "row"
                ? { ArrowLeft: -1, ArrowRight: 1 }
                : { ArrowUp: -1, ArrowDown: 1 };
            if (!(event.key in keys)) return;
            event.preventDefault();
            event.stopPropagation();
            const { min, direction } = this.measure();
            const step = (event.shiftKey ? LARGE_STEP : STEP) * keys[event.key] * direction;
            const sizes = resizeAt(this.sizes, this.index, step, min);
            this.$emit("resize-end", sizes);
        },
    },
};
</script>
