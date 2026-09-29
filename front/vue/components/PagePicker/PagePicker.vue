<template>
    <VMenu
        placement="bottom-end"
        theme="modal-menu"
        :distance="8"
        :shown="isOpen"
        :triggers="[]"
        :auto-hide="true"
        :no-auto-focus="true"
        @apply-show="onShown"
        @apply-hide="close"
    >
        <VDropdown
            theme="escr-tooltip-small"
            placement="bottom"
            :distance="8"
            :triggers="['hover']"
            :disabled="isOpen"
        >
            <EscrButton
                color="text"
                aria-label="Go to page"
                :disabled="disabled"
                :on-click="toggle"
            >
                <template #button-icon>
                    <ImagesIcon />
                </template>
            </EscrButton>
            <template #popper>
                Go to page (Ctrl+G)
            </template>
        </VDropdown>
        <template #popper>
            <div class="escr-page-picker">
                <input
                    ref="search"
                    v-model="query"
                    type="search"
                    placeholder="Page number, label or filename"
                    aria-label="Search pages by number, label or filename"
                    @keydown="onKeydown"
                >
                <p
                    v-if="loading && !pages.length"
                    class="picker-message"
                >
                    Loading pages…
                </p>
                <p
                    v-else-if="error"
                    class="picker-message"
                >
                    {{ error }}
                </p>
                <p
                    v-else-if="!results.length"
                    class="picker-message"
                >
                    No page matches “{{ query }}”
                </p>
                <ul
                    ref="list"
                    role="listbox"
                    aria-label="Pages"
                >
                    <li
                        v-for="(page, index) in results"
                        :key="page.pk"
                        role="option"
                        :aria-selected="index === activeIndex"
                        :aria-current="page.pk === currentPk ? 'page' : null"
                        :class="{ active: index === activeIndex, current: page.pk === currentPk }"
                        @click="go(page)"
                        @mousemove="activeIndex = index"
                    >
                        <img
                            v-if="page.thumbnail"
                            :src="page.thumbnail"
                            loading="lazy"
                            alt=""
                        >
                        <span
                            v-else
                            class="no-thumbnail"
                        />
                        <span class="page-number">{{ page.order + 1 }}</span>
                        <span class="page-names">
                            <span
                                v-if="page.name"
                                class="page-label"
                                dir="auto"
                            >{{ page.name }}</span>
                            <span
                                class="page-filename"
                                :title="page.filename"
                            >{{ shorten(page.filename) }}</span>
                            <span
                                v-if="page.editorial_status"
                                :class="['escr-editorial-status', 'page-status',
                                         `status-${page.editorial_status}`]"
                            >{{ statusLabel(page.editorial_status) }}</span>
                        </span>
                    </li>
                </ul>
            </div>
        </template>
    </VMenu>
</template>
<script>
import { Dropdown as VDropdown, Menu as VMenu } from "floating-vue";
import { mapActions, mapMutations, mapState } from "vuex";
import { retrieveDocumentPartsNavigation } from "../../../src/api";
import EscrButton from "../Button/Button.vue";
import ImagesIcon from "../Icons/ImagesIcon/ImagesIcon.vue";
import { editorialStatusLabel } from "../../store/util/editorialStatus";
import { middleTruncate } from "../../store/util/filename";
import { searchPages } from "../../store/util/pageSearch";
import "../EditorialStatus/EditorialStatus.css";
import "./PagePicker.css";

/**
 * Find a page of the document by position, label or filename and go to it.
 */
export default {
    name: "EscrPagePicker",
    components: { EscrButton, ImagesIcon, VDropdown, VMenu },
    props: {
        /**
         * True if the picker cannot be opened
         */
        disabled: {
            type: Boolean,
            default: false,
        },
    },
    data() {
        return {
            isOpen: false,
            loading: false,
            error: "",
            pages: [],
            query: "",
            activeIndex: 0,
        };
    },
    computed: {
        ...mapState({
            blockShortcuts: (state) => state.document.blockShortcuts,
            currentPk: (state) => state.parts.pk,
            documentId: (state) => state.document.id,
        }),
        results() {
            return searchPages(this.pages, this.query);
        },
    },
    watch: {
        query() {
            this.activeIndex = 0;
            this.scrollToActive();
        },
    },
    mounted() {
        document.addEventListener("keydown", this.onGlobalKeydown);
    },
    beforeDestroy() {
        document.removeEventListener("keydown", this.onGlobalKeydown);
    },
    methods: {
        ...mapActions("parts", ["loadPartByOrder"]),
        ...mapMutations("document", ["setBlockShortcuts"]),
        toggle() {
            if (this.isOpen) this.close();
            else this.open();
        },
        async open() {
            if (this.disabled || this.isOpen) return;
            this.query = "";
            this.isOpen = true;
            // typing in the picker must not trigger the editor's shortcuts
            this.setBlockShortcuts(true);
            await this.fetchPages();
        },
        close() {
            if (!this.isOpen) return;
            this.isOpen = false;
            this.setBlockShortcuts(false);
        },
        async fetchPages() {
            // fetched on every opening so pages added or renamed meanwhile show up
            this.loading = true;
            this.error = "";
            try {
                const { data } = await retrieveDocumentPartsNavigation(this.documentId);
                this.pages = data;
                this.activeIndex = Math.max(
                    this.results.findIndex((page) => page.pk === this.currentPk), 0,
                );
                this.scrollToActive();
            } catch (err) {
                this.error = "The pages could not be loaded.";
            } finally {
                this.loading = false;
            }
        },
        onShown() {
            this.$nextTick(() => {
                if (this.$refs.search) this.$refs.search.focus();
                this.scrollToActive();
            });
        },
        scrollToActive() {
            this.$nextTick(() => {
                const item = this.$refs.list && this.$refs.list.children[this.activeIndex];
                if (item) item.scrollIntoView({ block: "nearest" });
            });
        },
        onKeydown(e) {
            switch (e.key) {
                case "ArrowDown":
                    e.preventDefault();
                    this.activeIndex = Math.min(this.activeIndex + 1, this.results.length - 1);
                    this.scrollToActive();
                    break;
                case "ArrowUp":
                    e.preventDefault();
                    this.activeIndex = Math.max(this.activeIndex - 1, 0);
                    this.scrollToActive();
                    break;
                case "Enter":
                    e.preventDefault();
                    if (this.results[this.activeIndex]) this.go(this.results[this.activeIndex]);
                    break;
                case "Escape":
                    e.preventDefault();
                    this.close();
                    break;
                default:
                    break;
            }
        },
        onGlobalKeydown(e) {
            // Ctrl+G, or Alt+G like the legacy editor's "go to" dialog
            if (
                !this.isOpen && !this.blockShortcuts &&
                (e.ctrlKey || e.altKey) && e.key.toLowerCase() === "g"
            ) {
                e.preventDefault();
                this.open();
            }
        },
        go(page) {
            this.close();
            if (page.pk !== this.currentPk) this.loadPartByOrder(page.order);
        },
        shorten(filename) {
            return middleTruncate(filename, 44);
        },
        statusLabel(status) {
            return editorialStatusLabel(status);
        },
    },
};
</script>
