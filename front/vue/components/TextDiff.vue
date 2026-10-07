<template>
    <span>
        <!-- text inline, no line breaks: white space around the parts would show -->
        <!-- eslint-disable vue/multiline-html-element-content-newline -->
        <span
            v-for="(part, index) in parts"
            :key="index"
            :class="{ 'cmp-add': part.type === 'added', 'cmp-del': part.type === 'removed' }"
        >{{ part.text }}</span>
        <!-- eslint-enable vue/multiline-html-element-content-newline -->
    </span>
</template>

<script>
import { diffText } from "../../src/editor/versionCompare";

/**
 * The text of `after`, with its differences from `before` highlighted.
 * Line text is rendered as text, never as HTML: it is whatever people typed or imported.
 */
export default Vue.extend({
    props: {
        /**
         * The text to compare with (null: nothing to compare, `after` as it is).
         */
        before: {
            type: String,
            default: null,
        },
        after: {
            type: String,
            default: "",
        },
    },
    computed: {
        parts() {
            if (this.before === null) return [{ type: "same", text: this.after }];
            return diffText(this.before, this.after);
        },
    },
});
</script>
