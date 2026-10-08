<template>
    <div :class="classes">
        <div class="escr-chat-message-meta">
            <span class="escr-chat-message-author">{{ author }}</span>
            <time
                v-if="time"
                class="escr-chat-message-time"
                :datetime="at"
            >{{ time }}</time>
        </div>
        <div
            v-if="pending"
            class="escr-chat-message-body escr-chat-message-pending"
            role="status"
        >
            <span class="escr-spinner escr-spinner--secondary" />
            <span>{{ author }} is thinking…</span>
        </div>
        <div
            v-else
            class="escr-chat-message-body"
            v-text="content"
        />
    </div>
</template>
<script>
import "./ChatMessage.css";

export default {
    name: "EscrChatMessage",
    props: {
        /**
         * Who wrote the message: "user" or "assistant".
         */
        role: {
            type: String,
            required: true,
            validator(value) {
                return ["user", "assistant"].includes(value);
            },
        },
        /**
         * The name shown above the message.
         */
        author: {
            type: String,
            required: true,
        },
        /**
         * The text, shown as written: line breaks kept, never rendered as HTML.
         */
        content: {
            type: String,
            default: "",
        },
        /**
         * When it was written, as an ISO date (optional).
         */
        at: {
            type: String,
            default: "",
        },
        /**
         * Whether this is the placeholder for an answer still being written.
         */
        pending: {
            type: Boolean,
            default: false,
        },
    },
    computed: {
        classes() {
            return {
                "escr-chat-message": true,
                [`escr-chat-message--${this.role}`]: true,
            };
        },
        time() {
            if (!this.at) return "";
            const date = new Date(this.at);
            if (Number.isNaN(date.getTime())) return "";
            return date.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
        },
    },
}
</script>
