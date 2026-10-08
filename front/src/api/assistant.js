import axios from "axios";

// Ask the AI Chat assistant. `messages` is the conversation so far, as
// [{ role: "user" | "assistant", content }], the last one the user's;
// `project` is the pk of a project to focus on, or null for all of them.
// The server gives up on the model after its own timeout (ASSISTANT["TIMEOUT"]
// in settings.py, 55 s), so this one only guards against a hung connection.
export const sendChat = async ({ messages, project }) =>
    await axios.post(
        "/assistant/chat/",
        project ? { messages, project } : { messages },
        { timeout: 90000 },
    );
