<template>
    <!-- a selection box over a line: its points inside are selected (filled),
         the one outside is not (hollow) -->
    <svg
        width="16"
        height="16"
        viewBox="0 0 16 16"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
    >
        <rect
            x="0.75"
            y="1.75"
            width="10"
            height="12.5"
            rx="1"
            fill="none"
            stroke="currentColor"
            stroke-width="1.25"
            stroke-dasharray="2.2 1.8"
        />
        <path
            d="M4 10.5L7.5 5.5L12.35 9.38"
            fill="none"
            stroke="currentColor"
            stroke-width="1"
        />
        <rect
            x="2.6"
            y="9.1"
            width="2.8"
            height="2.8"
            fill="currentColor"
        />
        <rect
            x="6.1"
            y="4.1"
            width="2.8"
            height="2.8"
            fill="currentColor"
        />
        <rect
            x="12.35"
            y="9.1"
            width="2.8"
            height="2.8"
            fill="none"
            stroke="currentColor"
            stroke-width="1"
        />
    </svg>
</template>
<script>
export default {
    name: "EscrBoxSelectPointsIcon",
}
</script>
