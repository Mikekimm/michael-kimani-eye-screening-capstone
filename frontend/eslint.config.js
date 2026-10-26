import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "dev-dist", "coverage"] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ["**/*.{ts,tsx}"],
    languageOptions: { ecmaVersion: 2022, globals: globals.browser },
    plugins: { "react-hooks": reactHooks },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "no-restricted-globals": ["error", { name: "fetch", message: "Use the typed API client in src/lib/api." }],
    },
  },
  {
    // The API client is the one place allowed to call fetch.
    files: ["src/lib/api/http.ts", "src/test/**"],
    rules: { "no-restricted-globals": "off" },
  },
);
