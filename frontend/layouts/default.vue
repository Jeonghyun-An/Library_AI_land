<!-- layouts/default.vue -->
<template>
  <div class="min-h-screen flex flex-col">
    <!-- Header -->
    <!--
    <header class="bg-white border-b border-gray-200 sticky top-0 z-50">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex justify-between items-center h-16">
          <NuxtLink to="/law" class="flex items-center space-x-3">
            <img
              src="/img/layout/hd_logo.svg"
              alt="LANDSOFT AI 도서정보 검색시스템"
              class="hd_logo view_ctr"
            />
          </NuxtLink>

          <nav class="hidden md:flex items-center space-x-6">
            <NuxtLink
              to="/"
              class="text-gray-700 hover:text-indigo-600 transition"
            >
              Search
            </NuxtLink>
            <NuxtLink
              to="/upload"
              class="text-gray-700 hover:text-indigo-600 transition"
            >
              Upload
            </NuxtLink>
            <NuxtLink
              to="/books"
              class="text-gray-700 hover:text-indigo-600 transition"
            >
              Library
            </NuxtLink>
            <NuxtLink
              to="/about"
              class="text-gray-700 hover:text-indigo-600 transition"
            >
              About
            </NuxtLink>
          </nav>

          <button
            @click="mobileMenuOpen = !mobileMenuOpen"
            class="md:hidden p-2"
          >
            <svg
              class="w-6 h-6"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M4 6h16M4 12h16M4 18h16"
              />
            </svg>
          </button>
        </div>

        <div v-if="mobileMenuOpen" class="md:hidden pb-4">
          <NuxtLink
            to="/"
            class="block py-2 text-gray-700 hover:text-indigo-600"
            >Search</NuxtLink
          >
          <NuxtLink
            to="/upload"
            class="block py-2 text-gray-700 hover:text-indigo-600"
            >Upload</NuxtLink
          >
          <NuxtLink
            to="/books"
            class="block py-2 text-gray-700 hover:text-indigo-600"
            >Library</NuxtLink
          >
          <NuxtLink
            to="/about"
            class="block py-2 text-gray-700 hover:text-indigo-600"
            >About</NuxtLink
          >
        </div>
      </div>
    </header>
    -->

    <!-- Main Content -->
    <main class="flex-1">
      <slot />
    </main>

    <!-- Footer -->
    <footer class="bg-white border-t border-gray-200 mt-auto">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div class="text-center text-gray-600 text-sm">
          <p>
            &copy; 2026 Constitution Knowledge RAG System. Powered by LANDSOFT
            AI.
          </p>
          <p class="mt-2">Built with Nuxt.js • FastAPI • Milvus • BGE-M3</p>
        </div>
      </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";

const mobileMenuOpen = ref<boolean>(false);
</script>
