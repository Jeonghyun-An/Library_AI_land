// https://nuxt.com/docs/api/configuration/nuxt-config
import { defineNuxtConfig } from "nuxt/config";
export default defineNuxtConfig({
  devtools: { enabled: true },

  modules: ["@nuxtjs/tailwindcss"],

  typescript: {
    strict: false,
    typeCheck: false,
    shim: false,
    tsConfig: {
      compilerOptions: {
        strict: false,
        skipLibCheck: true,
      },
    },
  },

  imports: {
    autoImport: true,
  },

  runtimeConfig: {
    public: {
      apiBase: process.env.NUXT_PUBLIC_API_BASE || "http://localhost:8000/api",
    },
  },

  app: {
    head: {
      title: "Library Knowledge Search",
      meta: [
        { charset: "utf-8" },
        { name: "viewport", content: "width=device-width, initial-scale=1" },
        {
          name: "description",
          content: "AI-powered library knowledge search system",
        },
      ],
      link: [
        { rel: "icon", type: "image/x-icon", href: "/favicon.ico" },

        {
          rel: "stylesheet",
          href: "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css",
        },
      ],
      script: [],
    },
  },

  css: [
    "~/assets/css/reset.css",
    "~/assets/css/common.css",
    "~/assets/css/layout.css",
    "~/assets/css/main.css",
  ],

  compatibilityDate: "2026-01-21",

  // Vite 설정
  vite: {
    server: {
      hmr: {
        clientPort: 3000,
      },
    },
  },
});
