import Vue from "vue";
import store from "../store";
import AiChat from "../pages/AiChat/AiChat.vue";

export default new Vue({
    el: "#assistant-chat",
    store,
    components: {
        "ai-chat": AiChat,
    },
});
