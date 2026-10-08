<template>
    <div class="escr-filter-set">
        <span>Filter by:</span>
        <SearchInput
            :value="nameFilter"
            :placeholder="searchPlaceholder"
            :disabled="disabled"
            :on-input="handleNameInput"
            :on-clear="clearNameFilter"
            :on-enter="onFilter"
        />
        <!--
            auto-hide lets floating-vue close the dropdown on a click outside it; apply-hide
            then resets openFilter so the shown prop stays in sync. Escape is handled by the
            document keydown listener below, because focus stays on the Tags button while the
            dropdown is open and floating-vue only reacts to Escape from inside the popper.
        -->
        <VMenu
            :delay="{ show: 0, hide: 100 }"
            :triggers="[]"
            :shown="openFilter === 'tags'"
            :auto-hide="true"
            @apply-hide="() => toggleOpen(undefined)"
        >
            <FilterButton
                :active="tagFilterActive"
                :count="tagCount"
                label="Tags"
                :on-click="() => toggleOpen('tags')"
                :on-clear="() => clearFilter('tags')"
                :disabled="disabled"
            >
                <template #filter-icon="{active}">
                    <TagIcon :active="active" />
                </template>
            </FilterButton>
            <template #popper>
                <TagFilter
                    v-if="openFilter === 'tags'"
                    :tags="tags"
                    :selected="tagFilterSelectedTags"
                    :operator="tagFilterOperator"
                    :untagged-selected="untaggedSelected"
                    :on-apply="toggleClosedAndFilter"
                    :on-cancel="() => toggleOpen(undefined)"
                />
            </template>
        </VMenu>
    </div>
</template>
<script>
import { Menu as VMenu } from "floating-vue";
import { mapActions, mapGetters, mapState } from "vuex";
import FilterButton from "../FilterButton/FilterButton.vue";
import SearchInput from "../SearchInput/SearchInput.vue";
import TagFilter from "../TagFilter/TagFilter.vue";
import TagIcon from "../Icons/TagIcon/TagIcon.vue";
import "./FilterSet.css";

export default {
    name: "EscrFilterSet",
    components: { SearchInput, TagFilter, TagIcon, FilterButton, VMenu },
    props: {
        /**
         * Boolean indicating if the filter buttons should be disabled, e.g. during loading.
         */
        disabled: {
            type: Boolean,
            default: false,
        },
        /**
         * List of all tags on all [documents/projects/images] in view.
         */
        tags: {
            type: Array,
            default: () => [],
        },
        /**
         * Optional callback function to be performed after filter state changes.
         */
        onFilter: {
            type: Function,
            default: () => {},
        },
        /**
         * Placeholder text for the search input.
         */
        searchPlaceholder: {
            type: String,
            default: "Search by name...",
        },
    },
    data() {
        return {
            openFilter: undefined,
            debounceTimer: null,
        };
    },
    computed: {
        ...mapState({
            filters: (state) => state.filter.filters,
        }),
        ...mapGetters("filter", [
            "nameFilter",
            "tagFilterActive",
            "tagCount",
            "tagFilter",
            "tagFilterOperator",
            "tagFilterSelectedTags",
            "untaggedSelected",
        ]),
    },
    mounted() {
        document.addEventListener("keydown", this.onKeydown);
    },
    beforeDestroy() {
        document.removeEventListener("keydown", this.onKeydown);
        if (this.debounceTimer) {
            clearTimeout(this.debounceTimer);
        }
    },
    methods: {
        /**
         * Result of clicking the "clear" button by a filter
         */
        clearFilter(type) {
            this.openFilter = undefined;
            this.removeFilter(type);
            this.onFilter();
        },
        /**
         * Handle name input changes with debouncing
         */
        handleNameInput(value) {
            this.addFilter({
                type: "name",
                value: value || "",
            });

            // Debounce the filter callback
            if (this.debounceTimer) {
                clearTimeout(this.debounceTimer);
            }
            this.debounceTimer = setTimeout(() => {
                this.onFilter();
            }, 500);
        },
        /**
         * Clear the name filter
         */
        clearNameFilter() {
            if (this.debounceTimer) {
                clearTimeout(this.debounceTimer);
            }
            this.removeFilter("name");
            this.onFilter();
        },
        /**
         * Result of clicking on a filter button (open/close filter dialog)
         */
        toggleOpen(type) {
            if (this.openFilter === type) {
                this.openFilter = undefined;
            } else {
                this.openFilter = type;
            }
        },
        /**
         * Close the open filter dialog on Escape.
         */
        onKeydown(e) {
            if (e.key !== "Escape" || !this.openFilter) return;
            e.preventDefault();
            this.openFilter = undefined;
        },
        /**
         * Result of clicking "Submit" on a filter dialog: close the dialog
         * and apply the filter
         */
        toggleClosedAndFilter({ operator, tags, untagged }) {
            this.openFilter = undefined;
            this.addFilter({
                type: "tags",
                value: untagged
                    ? Array.from(new Set([...tags, "none"]))
                    : tags.filter((t) => t !== "none"),
                operator,
            });
            this.onFilter();
        },
        ...mapActions("filter", [
            "addFilter",
            "removeFilter",
        ]),
    },
};
</script>
