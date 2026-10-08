<template>
    <EscrPage class="escr-ai-chat">
        <template #page-content>
            <div class="escr-card escr-card-padding escr-ai-chat-card">
                <div class="escr-card-header">
                    <div class="escr-ai-chat-heading">
                        <h1>AI Chat</h1>
                        <span class="escr-ai-chat-model">{{ assistantName }}</span>
                    </div>
                    <div class="escr-card-actions">
                        <label class="escr-ai-chat-focus">
                            <span>Project</span>
                            <EscrDropdown
                                label="Project to ask about"
                                :disabled="loading"
                                :options="projectOptions"
                                :on-change="changeProject"
                            />
                        </label>
                        <EscrButton
                            label="New conversation"
                            color="outline-primary"
                            size="small"
                            :disabled="loading || !messages.length"
                            :on-click="startOver"
                        />
                    </div>
                </div>
                <div
                    ref="log"
                    class="escr-ai-chat-log"
                    aria-live="polite"
                >
                    <div
                        v-if="!messages.length"
                        class="escr-ai-chat-empty"
                    >
                        <p>
                            Ask {{ assistantName }} about your projects, documents and tasks.
                            Answers come from what you can see in the application right now,
                            not from the text of your transcriptions.
                        </p>
                        <div class="escr-ai-chat-suggestions">
                            <EscrButton
                                v-for="question in suggestions"
                                :key="question"
                                color="outline-secondary"
                                size="small"
                                :label="question"
                                :disabled="loading"
                                :on-click="() => submit(question)"
                            />
                        </div>
                    </div>
                    <ChatMessage
                        v-for="message in messages"
                        :key="message.id"
                        :role="message.role"
                        :author="message.role === 'user' ? 'You' : (message.model || assistantName)"
                        :content="message.content"
                        :at="message.at"
                    />
                    <ChatMessage
                        v-if="loading"
                        role="assistant"
                        :author="assistantName"
                        :pending="true"
                    />
                    <div
                        v-if="error"
                        class="escr-ai-chat-error"
                    >
                        <EscrAlert
                            color="danger"
                            :message="error"
                        />
                        <EscrButton
                            label="Retry"
                            color="outline-primary"
                            size="small"
                            :disabled="loading"
                            :on-click="retry"
                        />
                    </div>
                </div>
                <ChatComposer
                    :value="draft"
                    :disabled="loading"
                    :placeholder="placeholder"
                    :on-input="updateDraft"
                    :on-send="submit"
                />
            </div>
        </template>
    </EscrPage>
</template>
<script>
import { mapActions, mapState } from "vuex";
import ChatComposer from "../../components/ChatComposer/ChatComposer.vue";
import ChatMessage from "../../components/ChatMessage/ChatMessage.vue";
import EscrAlert from "../../components/Alert/Alert.vue";
import EscrButton from "../../components/Button/Button.vue";
import EscrDropdown from "../../components/Dropdown/Dropdown.vue";
import EscrPage from "../Page/Page.vue";
import { SUGGESTED_QUESTIONS } from "../../../src/assistant/chat";
import "../../components/Common/Card.css";
import "./AiChat.css";

// value of the focus menu's entry for every project
const ALL_PROJECTS = "all";

export default {
    name: "EscrAiChatPage",
    components: {
        ChatComposer,
        ChatMessage,
        EscrAlert,
        EscrButton,
        EscrDropdown,
        EscrPage,
    },
    props: {
        /**
         * The name of the model, as the server's settings call it.
         */
        assistantName: {
            type: String,
            default: "Assistant",
        },
    },
    data() {
        return {
            // the question being written
            draft: "",
        };
    },
    computed: {
        ...mapState({
            error: (state) => state.assistant.error,
            loading: (state) => state.assistant.loading,
            messages: (state) => state.assistant.messages,
            project: (state) => state.assistant.project,
            projects: (state) => state.assistant.projects,
        }),
        placeholder() {
            return `Ask ${this.assistantName} a question… `
                + "(Enter to send, Shift+Enter for a new line)";
        },
        projectOptions() {
            return [
                { value: ALL_PROJECTS, label: "All projects", selected: !this.project },
                ...this.projects.map(({ pk, name }) => ({
                    value: String(pk),
                    label: name,
                    selected: this.project === pk,
                })),
            ];
        },
        suggestions() {
            return SUGGESTED_QUESTIONS;
        },
    },
    watch: {
        messages() {
            this.scrollToEnd();
        },
        loading() {
            this.scrollToEnd();
        },
        error() {
            this.scrollToEnd();
        },
    },
    async created() {
        await this.fetchProjects();
    },
    methods: {
        ...mapActions("assistant", [
            "fetchProjects",
            "reset",
            "retry",
            "send",
            "setProject",
        ]),
        changeProject(event) {
            const { value } = event.target;
            this.setProject(value === ALL_PROJECTS ? null : Number(value));
        },
        /**
         * Keep the latest message in view.
         */
        scrollToEnd() {
            this.$nextTick(() => {
                const log = this.$refs.log;
                if (log) {
                    log.scrollTop = log.scrollHeight;
                }
            });
        },
        startOver() {
            this.reset();
            this.draft = "";
        },
        async submit(text) {
            this.draft = "";
            await this.send(text);
        },
        updateDraft(event) {
            this.draft = event.target.value;
        },
    },
}
</script>
