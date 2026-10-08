<template>
    <div class="escr-chat-composer">
        <TextField
            class="escr-chat-composer-field"
            label="Your question"
            :label-visible="false"
            :textarea="true"
            :placeholder="placeholder"
            :value="value"
            :disabled="disabled"
            :max-length="maxLength"
            :on-input="onInput"
            :on-keydown="handleKeydown"
        />
        <EscrButton
            label="Send"
            :disabled="disabled || !sendable"
            :on-click="submit"
        />
    </div>
</template>
<script>
import EscrButton from "../Button/Button.vue";
import TextField from "../TextField/TextField.vue";
import { MAX_CONTENT_LENGTH, canSend, shouldSend } from "../../../src/assistant/chat";
import "./ChatComposer.css";

export default {
    name: "EscrChatComposer",
    components: { EscrButton, TextField },
    props: {
        /**
         * The text of the question being written.
         */
        value: {
            type: String,
            default: "",
        },
        /**
         * Whether the box is disabled, e.g. while an answer is awaited.
         */
        disabled: {
            type: Boolean,
            default: false,
        },
        /**
         * Placeholder text.
         */
        placeholder: {
            type: String,
            default: "Ask a question…",
        },
        /**
         * Called with the input event when the text changes.
         */
        onInput: {
            type: Function,
            required: true,
        },
        /**
         * Called with the text when the user sends it.
         */
        onSend: {
            type: Function,
            required: true,
        },
    },
    computed: {
        maxLength() {
            return MAX_CONTENT_LENGTH;
        },
        sendable() {
            return canSend(this.value, this.disabled);
        },
    },
    methods: {
        /**
         * Enter sends; Shift+Enter (and other modifiers) add a line.
         */
        handleKeydown(event) {
            if (shouldSend(event)) {
                event.preventDefault();
                this.submit();
            }
        },
        submit() {
            if (this.sendable) {
                this.onSend(this.value);
            }
        },
    },
}
</script>
