<template>
    <!-- a selection box around whole shapes -->
    <svg
        width="16"
        height="16"
        viewBox="0 0 16 16"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
    >
        <rect
            x="1"
            y="1"
            width="14"
            height="14"
            rx="1"
            fill="none"
            stroke="currentColor"
            stroke-width="1.25"
            stroke-dasharray="2.2 1.8"
        />
        <rect
            x="3.75"
            y="4.25"
            width="8.5"
            height="2.75"
            rx="1.1"
            fill="currentColor"
        />
        <rect
            x="3.75"
            y="9"
            width="6"
            height="2.75"
            rx="1.1"
            fill="currentColor"
        />
    </svg>
</template>
<script>
export default {
    name: "EscrBoxSelectIcon",
}
</script>
