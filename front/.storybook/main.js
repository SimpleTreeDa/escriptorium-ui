const path = require("path");

module.exports = {
  "stories": [
    "../src/**/*.stories.mdx",
    "../src/**/*.stories.@(js|jsx|ts|tsx)"
  ],
  "addons": [
    "@storybook/addon-links",
    {
      name: '@storybook/addon-essentials',
      options: {
        backgrounds: false,
      }
    },
    "@storybook/addon-interactions",
    "storybook-addon-themes",
    "@storybook/addon-a11y",
    "storybook-addon-mock",
  ],
  "framework": "@storybook/vue",
  "core": {
    "builder": "@storybook/builder-vite"
  },
  async viteFinal(config, { configType }) {
    const { loadConfigFromFile, mergeConfig } = await import("vite");
    const viteConfig = await loadConfigFromFile(
      {
        command: "build",
        mode: configType === "PRODUCTION" ? "production" : "development",
      },
      path.resolve(__dirname, "../vite.config.js")
    );
    const appConfig = viteConfig?.config || {};
    const vue2Plugins = (appConfig.plugins || []).filter(
      (plugin) => plugin?.name === "vite:vue2"
    );

    return mergeConfig(config, {
      define: appConfig.define,
      plugins: vue2Plugins,
      resolve: {
        alias: appConfig.resolve?.alias || {},
      },
    });
  }
}
