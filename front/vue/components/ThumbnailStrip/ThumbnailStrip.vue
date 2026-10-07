<template>
    <div
        :class="['escr-thumbnail-strip', { collapsed }]"
        role="region"
        aria-label="Page thumbnails"
    >
        <VDropdown
            theme="escr-tooltip-small"
            placement="right"
            :distance="8"
            :triggers="['hover']"
        >
            <EscrButton
                class="strip-toggle"
                color="text"
                size="small"
                :aria-label="collapsed ? 'Show page thumbnails' : 'Hide page thumbnails'"
                :aria-expanded="collapsed ? 'false' : 'true'"
                :on-click="toggle"
            >
                <template #button-icon>
                    <ChevronDownIcon />
                </template>
            </EscrButton>
            <template #popper>
                {{ collapsed ? "Show page thumbnails" : "Hide page thumbnails" }}
            </template>
        </VDropdown>
        <template v-if="!collapsed">
            <p
                v-if="loading && !pages.length"
                class="strip-message"
            >
                Loading pages…
            </p>
            <p
                v-else-if="error"
                class="strip-message"
            >
                {{ error }}
            </p>
            <ul
                v-else
                ref="list"
                :dir="readDirection === 'rtl' ? 'rtl' : 'ltr'"
            >
                <li
                    v-for="page in pages"
                    :key="page.pk"
                    :class="{ current: page.pk === currentPk }"
                >
                    <button
                        type="button"
                        :title="tooltip(page)"
                        :aria-label="`Page ${page.order + 1}${page.name ? ', ' + page.name : ''}`"
                        :aria-current="page.pk === currentPk ? 'page' : null"
                        :disabled="disabled"
                        @click="go(page)"
                    >
                        <!-- lazy: only the thumbnails scrolled into view are fetched -->
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
                    </button>
                </li>
            </ul>
        </template>
    </div>
</template>
<script>
/* global userProfile */
import { Dropdown as VDropdown } from "floating-vue";
import { mapActions, mapState } from "vuex";
import { retrieveDocumentPartsNavigation } from "../../../src/api";
import {
    PROFILE_KEY,
    currentIndex,
    loadCollapsed,
    savedState,
    sortedPages,
    withPageName,
} from "../../../src/editor/thumbnailStrip";
import EscrButton from "../Button/Button.vue";
import ChevronDownIcon from "../Icons/ChevronDownIcon/ChevronDownIcon.vue";
import { middleTruncate } from "../../store/util/filename";
import "./ThumbnailStrip.css";

/**
 * Every page of the document as a thumbnail, under the editor's navigation
 * bar: the current page is highlighted, clicking one goes to it. Collapsible,
 * and whether it is collapsed is saved in the user profile.
 */
export default {
    name: "EscrThumbnailStrip",
    components: { ChevronDownIcon, EscrButton, VDropdown },
    props: {
        /**
         * True while pages cannot be changed (the editor is loading)
         */
        disabled: {
            type: Boolean,
            default: false,
        },
    },
    data() {
        return {
            collapsed: loadCollapsed(userProfile.get(PROFILE_KEY)),
            loading: false,
            error: "",
            pages: [],
        };
    },
    computed: {
        ...mapState({
            currentName: (state) => state.parts.name,
            currentPk: (state) => state.parts.pk,
            documentId: (state) => state.document.id,
            partsCount: (state) => state.document.partsCount,
            readDirection: (state) => state.document.readDirection,
        }),
    },
    watch: {
        currentPk(pk) {
            if (this.collapsed || !pk) return;
            if (this.pages.length && currentIndex(this.pages, pk) === -1) {
                // a page added since the list was fetched
                this.fetchPages();
            } else {
                this.scrollToCurrent();
            }
        },
        currentName(name) {
            // renamed in the editor: no need to fetch the list again
            this.pages = withPageName(this.pages, this.currentPk, name);
        },
        partsCount() {
            // pages were added or removed
            if (!this.collapsed) this.fetchPages();
        },
    },
    mounted() {
        if (!this.collapsed) this.fetchPages();
    },
    methods: {
        ...mapActions("parts", ["loadPartByOrder"]),
        toggle() {
            this.collapsed = !this.collapsed;
            userProfile.set(PROFILE_KEY, savedState(this.collapsed));
            if (!this.collapsed) {
                if (this.pages.length) this.scrollToCurrent();
                else this.fetchPages();
            }
        },
        async fetchPages() {
            if (!this.documentId) return;
            this.loading = true;
            this.error = "";
            try {
                const { data } = await retrieveDocumentPartsNavigation(this.documentId);
                this.pages = sortedPages(data);
                this.scrollToCurrent();
            } catch (err) {
                this.error = "The pages could not be loaded.";
            } finally {
                this.loading = false;
            }
        },
        scrollToCurrent() {
            this.$nextTick(() => {
                const list = this.$refs.list;
                const index = currentIndex(this.pages, this.currentPk);
                const item = list && index !== -1 && list.children[index];
                if (item && item.scrollIntoView) {
                    item.scrollIntoView({ block: "nearest", inline: "center" });
                }
            });
        },
        go(page) {
            if (this.disabled || page.pk === this.currentPk) return;
            this.loadPartByOrder(page.order);
        },
        tooltip(page) {
            const names = [page.name, middleTruncate(page.filename, 48)].filter(Boolean);
            return `${page.order + 1}: ${names.join(" – ")}`;
        },
    },
};
</script>
