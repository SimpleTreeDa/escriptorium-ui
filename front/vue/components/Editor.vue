<template>
    <div id="escr-editor">
        <nav v-if="legacyModeEnabled">
            <div
                id="nav-tab"
                class="nav nav-tabs mb-3"
                role="tablist"
            >
                <slot />
                <ExtraInfo />
                <TranscriptionManagement />
                <ExtraNav />
            </div>
        </nav>
        <EditorNavigation
            v-else
            :disabled="!partsLoaded"
        />

        <TabContent :legacy-mode-enabled="legacyModeEnabled" />

        <!-- modals -->
        <ElementDetailsModal
            v-if="!legacyModeEnabled && modalOpen && modalOpen.elementDetails"
            :disabled="!partsLoaded"
            :on-cancel="closeElementDetailsModal"
            :on-save="onSavePart"
        />
        <TranscriptionsModal
            v-if="!legacyModeEnabled && modalOpen && modalOpen.transcriptions"
            :disabled="!partsLoaded || saveTranscriptionsLoading"
            :on-cancel="closeTranscriptionsModal"
            :on-save="onSaveTranscriptions"
        />
        <OntologyModal
            v-if="!legacyModeEnabled && modalOpen && modalOpen.ontology"
            :disabled="!partsLoaded || saveOntologyLoading"
            :on-cancel="closeOntologyModal"
            :on-save="onSaveOntology"
        />
        <ConfirmModal
            v-if="!legacyModeEnabled && modalOpen && modalOpen.deleteTranscription"
            :body-text="`Are you sure you want to delete ${transcriptionToDelete.name}?`"
            confirm-verb="Delete"
            title="Delete Transcription"
            :cannot-undo="true"
            :disabled="!partsLoaded"
            :on-cancel="closeDeleteTranscriptionModal"
            :on-confirm="deleteTranscription"
        />
        <Alerts
            v-if="!legacyModeEnabled"
        />
    </div>
</template>

<script>
import axios from "axios";
import ReconnectingWebSocket from "reconnectingwebsocket";
import { mapActions, mapState } from "vuex";
import Alerts from "./Toast/ToastGroup.vue";
import ConfirmModal from "./ConfirmModal/ConfirmModal.vue";
import EditorNavigation from "./EditorNavigation/EditorNavigation.vue";
import ElementDetailsModal from "./ElementDetailsModal/ElementDetailsModal.vue";
import ExtraInfo from "./ExtraInfo.vue";
import ExtraNav from "./ExtraNav.vue";
import OntologyModal from "./OntologyModal/OntologyModal.vue";
import TabContent from "./TabContent.vue";
import TranscriptionManagement from "./TranscriptionManagement.vue";
import TranscriptionsModal from "./TranscriptionsModal/TranscriptionsModal.vue";
import { trackSaves } from "../../src/editor/saveTracking";
import { isTaskEvent } from "../../src/editor/taskStatus";
import "./Editor.css";

export default {
    name: "EscrEditor",
    components: {
        Alerts,
        ConfirmModal,
        ElementDetailsModal,
        EditorNavigation,
        ExtraInfo,
        ExtraNav,
        OntologyModal,
        TabContent,
        TranscriptionManagement,
        TranscriptionsModal,
    },
    props: {
        documentId: {
            type: String,
            required: true,
        },
        documentName: {
            type: String,
            required: true,
        },
        partId: {
            type: String,
            required: true,
        },
        defaultTextDirection: {
            type: String,
            required: true,
        },
        mainTextDirection: {
            type: String,
            required: true,
        },
        readDirection: {
            type: String,
            required: true,
        },
        /**
         * Whether or not legacy mode is enabled by the user.
         */
        legacyModeEnabled: {
            type: Boolean,
            required: true,
        },
    },
    computed: {
        lastViewedKey() {
            // a browser can be shared by several users
            return `${userProfile.userId}:${this.documentId}`;
        },
        ...mapState({
            modalOpen: (state) => state.globalTools.modalOpen,
            partsLoaded: (state) => state.parts.loaded,
            transcriptionToDelete: (state) => state.transcriptions.transcriptionToDelete,
            saveOntologyLoading: (state) => state.document.loading,
            saveTranscriptionsLoading: (state) => state.transcriptions.saveLoading,
        }),
    },
    watch: {
        "$store.state.parts.pk": function(n, o) {
            if (n) {
                // set the new url
                window.history.pushState(
                    {}, "",
                    document.location.href.replace(/(part\/)\d+(\/edit)/,
                        "$1"+this.$store.state.parts.pk+"$2"));

                // set the 'image' tab btn to select the corresponding image
                var tabUrl = new URL($("#nav-img-tab").attr("href"),
                    window.location.origin);
                tabUrl.searchParams.set("select", this.$store.state.parts.pk);
                $("#nav-img-tab").attr("href", tabUrl);

                // where to resume when the user has not transcribed anything in this document
                const lastViewed = userProfile.get("lastViewedParts") || {};
                lastViewed[this.lastViewedKey] = n;
                userProfile.set("lastViewedParts", lastViewed);
            }
        },
        "$store.state.transcriptions.selectedTranscription": function(n, o) {
            let itrans = userProfile.get("initialTranscriptions") || {};
            itrans[this.documentId] = n;
            userProfile.set("initialTranscriptions", itrans);
            this.$store.dispatch("transcriptions/getCurrentContent", n);
        },
        "$store.state.transcriptions.comparedTranscriptions": function(n, o) {
            n.forEach(async function(tr, i) {
                if (!o.find((e)=>e==tr)) {
                    await this.$store.dispatch("transcriptions/fetchContent", tr);
                }
            }.bind(this));
        },
    },

    async created() {
        if (!this.legacyModeEnabled) {
            // report whether edits reached the server, and warn before leaving if not
            trackSaves(axios, this.$store);
            window.addEventListener("beforeunload", this.warnBeforeLeaving);
        }
        this.$store.commit("document/setId", this.documentId);
        this.$store.commit("document/setName", this.documentName);
        this.$store.commit("document/setDefaultTextDirection", this.defaultTextDirection);
        this.$store.commit("document/setMainTextDirection", this.mainTextDirection);
        this.$store.commit("document/setReadDirection", this.readDirection);
        // "Continue where you left off" redirects here with ?line=<the line this user last
        // transcribed>, or ?resume=1 when there is none, to reopen the last page viewed.
        // Read it before loading a page, which records the new last viewed page.
        const params = new URLSearchParams(window.location.search);
        const resumeLine = !this.legacyModeEnabled && params.get("line");
        const resumePage = !this.legacyModeEnabled && params.has("resume")
            && (userProfile.get("lastViewedParts") || {})[this.lastViewedKey];
        if (params.has("line") || params.has("resume")) {
            params.delete("line");
            params.delete("resume");
            const query = params.toString();
            const url = window.location.pathname + (query ? `?${query}` : "");
            window.history.replaceState({}, "", url + window.location.hash);
        }
        try {
            let resumed = false;
            if (resumePage && resumePage != this.partId) {
                try {
                    await this.$store.dispatch("parts/fetchPart", {pk: resumePage});
                    resumed = true;
                } catch (err) {
                    // deleted since, open the first page instead
                }
            }
            if (!resumed) {
                await this.$store.dispatch("parts/fetchPart", {pk: this.partId});
            }
            const transcriptions = this.$store.state.transcriptions.all;
            const remembered = (userProfile.get("initialTranscriptions") || {})[this.documentId];
            let tr = transcriptions.find((e) => e.pk == remembered)
                ? remembered
                : transcriptions[0].pk;

            this.$store.commit("transcriptions/setSelectedTranscription", tr);

            if (resumeLine) {
                this.resumeOnLine(resumeLine);
            } else if (resumed) {
                this.add({ color: "text", message: `Resumed at ${this.$store.state.parts.title}` });
            }
        } catch (err) {
            console.log("couldn't fetch part data!", err);
        }

        document.addEventListener("keydown", async function(event) {
            if (this.$store.state.document.blockShortcuts) return;
            if (event.keyCode == 33 ||  // page up
                (event.keyCode == (this.readDirection == "rtl"?39:37) && event.ctrlKey)) {  // arrow left

                await this.$store.dispatch("parts/loadPart", "previous");
                event.preventDefault();
            } else if (event.keyCode == 34 ||   // page down
                       (event.keyCode == (this.readDirection == "rtl"?37:39) &&
                       event.ctrlKey)) {  // arrow right
                await this.$store.dispatch("parts/loadPart", "next");
                event.preventDefault();
            }
        }.bind(this));

        // catch background emitted events when masks are recalculated
        let $alertsContainer = $("#alerts-container");
        $alertsContainer.on("part:mask", function(ev, data) {
            data.lines.forEach(function(lineData) {
                let line = this.$store.state.lines.all.find((l)=>l.pk == lineData.pk);
                if (line) {  // might have been deleted in the meantime
                    this.$store.commit("lines/update", lineData)
                }
            }.bind(this));
        }.bind(this));

        if (!this.legacyModeEnabled) {
            // background tasks of the document, kept up to date by the websocket
            this.$store.dispatch("taskStatus/load").catch((err) => {
                console.log("couldn't fetch the tasks!", err);
            });
            // join document websocket room
            const msg = `{"type": "join-room", "object_cls": "document", "object_pk": ${
                this.documentId
            }}`;
            const scheme = location.protocol === "https:" ? "wss:" : "ws:";
            const msgSocket = new ReconnectingWebSocket(`${scheme}//${
                window.location.host
            }/ws/notif/`);
            msgSocket.maxReconnectAttempts = 3;
            // intercept all websocket messages
            msgSocket.addEventListener("message", this.websocketListener);
            let connected = false;
            msgSocket.addEventListener("open", function() {
                msgSocket.send(msg);
                if (connected) {
                    // reconnected: task events may have been missed
                    this.$store.dispatch("taskStatus/refresh");
                }
                connected = true;
            }.bind(this));
        }
    },
    beforeDestroy() {
        window.removeEventListener("beforeunload", this.warnBeforeLeaving);
    },
    methods: {
        /**
         * Make the browser ask for confirmation before leaving the page while edits are
         * not saved yet, still being saved, or failed to save.
         */
        warnBeforeLeaving(event) {
            if (this.$store.getters["saveStatus/hasUnsavedWork"]) {
                event.preventDefault();
                // still required by some browsers to show the dialog
                event.returnValue = "";
            }
        },
        ...mapActions("globalTools", [
            "closeElementDetailsModal",
            "closeOntologyModal",
            "closeTranscriptionsModal",
        ]),
        ...mapActions("transcriptions", {
            closeDeleteTranscriptionModal: "closeDeleteModal",
            deleteTranscription: "deleteTranscription",
            saveTranscriptionsChanges: "saveTranscriptionsChanges",
        }),
        ...mapActions("document", ["saveOntologyChanges"]),
        ...mapActions("parts", ["savePartChanges"]),
        ...mapActions("alerts", ["add"]),
        /**
         * Open the transcription of the line the user last edited, if it still exists.
         */
        resumeOnLine(linePk) {
            const findLine = () => this.$store.state.lines.all.find((l) => l.pk == linePk);
            const line = findLine();
            if (!line) return;
            this.add({
                color: "text",
                message: `Resumed at ${this.$store.state.parts.title}, line ${line.order + 1}`,
            });
            // the transcription modal lives in the visualisation panel
            if (!this.$store.state.document.editorPanels.includes("visualisation")) return;
            // wait for the line's text: loading it replaces the line objects
            const partPk = this.$store.state.parts.pk;
            const unwatch = this.$watch(
                () => this.$store.state.parts.pk !== partPk || (findLine() || {}).currentTrans,
                (loaded) => {
                    if (!loaded) return;
                    unwatch();
                    if (this.$store.state.parts.pk === partPk) {
                        this.$store.commit("lines/setEditedLine", findLine());
                    }
                },
            );
        },
        async onSavePart() {
            await this.savePartChanges();
            this.closeElementDetailsModal();
        },
        async onSaveOntology() {
            await this.saveOntologyChanges();
            this.closeOntologyModal();
        },
        async onSaveTranscriptions() {
            await this.saveTranscriptionsChanges();
            this.closeTranscriptionsModal();
        },
        websocketListener(e) {
            const data = JSON.parse(e.data);
            if (isTaskEvent(data)) {
                this.$store.dispatch("taskStatus/refresh");
            }
            if (data.type == "message") {
                // handle "message" type here, for display purposes
                const message = data.text;
                // map color to our color scheme
                let color = "text";
                const colorMap = {
                    danger: "alert",
                    success: "success",
                };
                if (Object.keys(colorMap).includes(data.level)) {
                    color = colorMap[data.level];
                }
                // add links if necessary
                if (data.links && data.links.length) {
                    const actionLink = data.links[0].src;
                    const actionLabel = data.links[0].text;
                    this.add({ color, message, actionLink, actionLabel, delay: 60000 });
                } else {
                    this.add({ color, message });
                }
            } else if (data.type === "event" && data.name === "part:mask") {
                // handle "event" type just for part:mask for mask recalculation
                data.data.lines.forEach((lineData) => {
                    let line = this.$store.state.lines.all.find((l) => l.pk == lineData.pk);
                    if (line) {  // might have been deleted in the meantime
                        this.$store.commit("lines/update", lineData)
                    }
                });
                this.add({ color: "success", message: "Successfully calculated masks" });
            }
        },
    }
}
</script>

<style scoped>
</style>
