import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;
          if (id.includes("leaflet") || id.includes("@turf")) {
            return "vendor-map";
          }
          if (id.includes("i18next")) {
            return "vendor-i18n";
          }
          if (id.includes("lucide-react")) {
            return "vendor-icons";
          }
          if (id.includes("react-dom") || id.includes("react")) {
            return "vendor-react";
          }
          return undefined;
        },
      },
    },
  },
});
