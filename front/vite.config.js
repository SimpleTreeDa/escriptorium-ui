import { resolve } from "path";
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue2";
import viteCompression from "vite-plugin-compression";

const entries = {
    vendor: resolve(__dirname, "src/vendor.js"),
    main: resolve(__dirname, "src/main.js"),
    editor: resolve(__dirname, "src/editor/main.js"),
    doclist: resolve(__dirname, "src/documentlist/main.js"),
    docstasks: resolve(__dirname, "src/documentstasks/main.js"),
    documentDashboard: resolve(__dirname, "vue/exports/documentDashboard.js"),
    globalNavigation: resolve(__dirname, "vue/exports/globalNavigation.js"),
    projectDashboard: resolve(__dirname, "vue/exports/projectDashboard.js"),
    projectsList: resolve(__dirname, "vue/exports/projectsList.js"),
    imagesPage: resolve(__dirname, "vue/exports/imagesPage.js"),
};

export default defineConfig(({ mode }) => ({
    base: "",
    define: {
        "process.env.NODE_ENV": JSON.stringify(mode),
    },
    plugins: [
        vue(),
        viteCompression({
            algorithm: "gzip",
            ext: ".gz",
            filter: /\.(js|css)$/i,
            threshold: 0,
            deleteOriginFile: false,
        }),
    ],
    resolve: {
        alias: {
            vue: "vue/dist/vue.esm.js",
        },
    },
    build: {
        outDir: "dist",
        cssCodeSplit: true,
        rollupOptions: {
            input: entries,
            output: {
                entryFileNames: "[name].js",
                chunkFileNames: "[name].js",
                assetFileNames: "[name][extname]",
            },
        },
    },
}));
