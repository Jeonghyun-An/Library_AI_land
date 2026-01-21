<!-- layouts/default.vue -->
<template>
  <div class="min-h-screen flex flex-col">
    <!-- Header -->
    <header class="bg-white border-b border-gray-200 sticky top-0 z-50">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex justify-between items-center h-16">
          <!-- Logo -->
          <NuxtLink to="/" class="flex items-center space-x-3">
            <div
              class="w-10 h-10 bg-indigo-600 rounded-lg flex items-center justify-center"
            >
              <svg
                class="w-6 h-6 text-white"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
                />
              </svg>
            </div>
            <span class="text-xl font-bold text-gray-900">Library RAG</span>
          </NuxtLink>

          <!-- Navigation -->
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

          <!-- Mobile Menu Button -->
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

        <!-- Mobile Menu -->
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

    <!-- Main Content -->
    <main class="flex-1">
      <slot />
    </main>

    <!-- Footer -->
    <footer class="bg-white border-t border-gray-200 mt-auto">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div class="text-center text-gray-600 text-sm">
          <p>&copy; 2024 Library Knowledge RAG System. Powered by AI.</p>
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
