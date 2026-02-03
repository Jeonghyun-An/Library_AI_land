<!-- pages/index.vue -->
<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
    <!-- Hero Section -->
    <div class="text-center mb-12">
      <h1 class="text-4xl md:text-5xl font-bold text-gray-900 mb-4">
        Search Your Library
      </h1>
      <p class="text-xl text-gray-600 max-w-3xl mx-auto">
        AI-powered semantic search across your entire book collection. Find
        answers, not just keywords.
      </p>
    </div>

    <!-- Search Box -->
    <div class="max-w-4xl mx-auto mb-12">
      <div class="relative">
        <input
          v-model="searchQuery"
          @keyup.enter="performSearch"
          type="text"
          placeholder="Ask anything... (e.g., 'What are the principles of quantum mechanics?')"
          class="w-full px-6 py-4 text-lg border-2 border-gray-300 rounded-xl focus:border-indigo-500 focus:outline-none shadow-sm"
        />
        <button
          @click="performSearch"
          :disabled="loading || !searchQuery.trim()"
          class="absolute right-2 top-2 px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition"
        >
          <span v-if="!loading">Search</span>
          <span v-else class="flex items-center">
            <svg
              class="animate-spin h-5 w-5 mr-2"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                class="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                stroke-width="4"
              ></circle>
              <path
                class="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              ></path>
            </svg>
            Searching...
          </span>
        </button>
      </div>

      <!-- Search Options -->
      <div class="mt-4 flex items-center space-x-6 text-sm">
        <label class="flex items-center space-x-2 cursor-pointer">
          <input
            v-model="useReranking"
            type="checkbox"
            class="rounded text-indigo-600"
          />
          <span class="text-gray-700">Use AI reranking</span>
        </label>
        <label class="flex items-center space-x-2">
          <span class="text-gray-700">Results:</span>
          <select
            v-model.number="topK"
            class="border border-gray-300 rounded px-2 py-1"
          >
            <option :value="3">3</option>
            <option :value="5">5</option>
            <option :value="10">10</option>
            <option :value="20">20</option>
          </select>
        </label>
      </div>
    </div>

    <!-- Search Results -->
    <div v-if="searchResults.length > 0" class="max-w-5xl mx-auto">
      <div class="mb-6 flex items-center justify-between">
        <h2 class="text-2xl font-semibold text-gray-900">
          Results ({{ totalFound }})
        </h2>
        <span class="text-sm text-gray-600">
          Found in {{ searchTimeMs }}ms
        </span>
      </div>

      <div class="space-y-6">
        <div
          v-for="(result, index) in searchResults"
          :key="index"
          class="bg-white rounded-lg shadow-md p-6 hover:shadow-lg transition fade-in"
        >
          <!-- Result Header -->
          <div class="flex items-start justify-between mb-3">
            <div class="flex-1">
              <h3 class="text-lg font-semibold text-gray-900 mb-1">
                {{ result.book_title || "Untitled" }}
              </h3>
              <div class="flex items-center space-x-3 text-sm text-gray-600">
                <span v-if="result.author" class="flex items-center">
                  <svg
                    class="w-4 h-4 mr-1"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                    />
                  </svg>
                  {{ result.author }}
                </span>
                <span v-if="result.chapter" class="flex items-center">
                  <svg
                    class="w-4 h-4 mr-1"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"
                    />
                  </svg>
                  {{ result.chapter }}
                </span>
                <span v-if="result.page" class="flex items-center">
                  <svg
                    class="w-4 h-4 mr-1"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"
                    />
                  </svg>
                  Page {{ result.page }}
                </span>
              </div>
            </div>
            <div class="ml-4 flex-shrink-0">
              <div
                class="px-3 py-1 bg-indigo-100 text-indigo-800 rounded-full text-sm font-medium"
              >
                {{ (result.score * 100).toFixed(1) }}% match
              </div>
            </div>
          </div>

          <!-- Section -->
          <div
            v-if="result.section"
            class="text-sm text-gray-700 mb-2 font-medium"
          >
            {{ result.section }}
          </div>

          <!-- Result Text -->
          <p class="text-gray-700 leading-relaxed">
            {{ truncateText(result.chunk_text, 300) }}
          </p>

          <!-- Metadata -->
          <div
            v-if="result.metadata"
            class="mt-4 pt-4 border-t border-gray-200"
          >
            <details class="text-sm text-gray-600">
              <summary class="cursor-pointer hover:text-indigo-600">
                View metadata
              </summary>
              <pre
                class="mt-2 p-3 bg-gray-50 rounded text-xs overflow-x-auto"
                >{{ JSON.stringify(result.metadata, null, 2) }}</pre
              >
            </details>
          </div>
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div
      v-else-if="!loading && hasSearched"
      class="max-w-2xl mx-auto text-center py-12"
    >
      <svg
        class="w-24 h-24 mx-auto text-gray-400 mb-4"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
        />
      </svg>
      <h3 class="text-xl font-semibold text-gray-900 mb-2">No results found</h3>
      <p class="text-gray-600">
        Try different keywords or upload more books to search
      </p>
    </div>

    <!-- Quick Links -->
    <div v-if="!hasSearched" class="max-w-4xl mx-auto mt-16">
      <h3 class="text-lg font-semibold text-gray-900 mb-4 text-center">
        Quick Actions
      </h3>
      <div class="grid md:grid-cols-3 gap-6">
        <NuxtLink
          to="/upload"
          class="p-6 bg-white rounded-lg shadow hover:shadow-md transition text-center"
        >
          <svg
            class="w-12 h-12 mx-auto text-indigo-600 mb-3"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
            />
          </svg>
          <h4 class="font-semibold text-gray-900 mb-2">Upload Book</h4>
          <p class="text-sm text-gray-600">Add new books to your library</p>
        </NuxtLink>

        <NuxtLink
          to="/books"
          class="p-6 bg-white rounded-lg shadow hover:shadow-md transition text-center"
        >
          <svg
            class="w-12 h-12 mx-auto text-green-600 mb-3"
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
          <h4 class="font-semibold text-gray-900 mb-2">Browse Library</h4>
          <p class="text-sm text-gray-600">View all your books</p>
        </NuxtLink>

        <NuxtLink
          to="/about"
          class="p-6 bg-white rounded-lg shadow hover:shadow-md transition text-center"
        >
          <svg
            class="w-12 h-12 mx-auto text-blue-600 mb-3"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <h4 class="font-semibold text-gray-900 mb-2">How it Works</h4>
          <p class="text-sm text-gray-600">Learn about the technology</p>
        </NuxtLink>
      </div>
    </div>

    <!-- Error Message -->
    <div v-if="errorMessage" class="max-w-4xl mx-auto mt-6">
      <div class="bg-red-50 border border-red-200 rounded-lg p-4">
        <div class="flex items-start">
          <svg
            class="w-5 h-5 text-red-600 mt-0.5 mr-3"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <div class="flex-1">
            <h4 class="font-semibold text-red-900 mb-1">Search Error</h4>
            <p class="text-sm text-red-700">{{ errorMessage }}</p>
          </div>
          <button
            @click="errorMessage = ''"
            class="text-red-600 hover:text-red-800"
          >
            <svg
              class="w-5 h-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
const config = useRuntimeConfig();
const apiBase = config.public.apiBase;

const searchQuery = ref("");
const searchResults = ref<any[]>([]);
const loading = ref(false);
const hasSearched = ref(false);
const errorMessage = ref("");
const totalFound = ref(0);
const searchTimeMs = ref(0);

// Search options
const useReranking = ref(true);
const topK = ref(5);

const performSearch = async () => {
  if (!searchQuery.value.trim()) return;

  loading.value = true;
  errorMessage.value = "";
  hasSearched.value = true;

  try {
    const response = await $fetch<any>(`${apiBase}/library/search`, {
      method: "POST",
      body: {
        query: searchQuery.value,
        top_k: topK.value,
        use_reranking: useReranking.value,
        search_type: "hybrid",
      },
    });

    if (response.success) {
      searchResults.value = response.results;
      totalFound.value = response.total_found;
      searchTimeMs.value = response.search_time_ms;
    } else {
      errorMessage.value = "Search failed. Please try again.";
    }
  } catch (error: any) {
    console.error("Search error:", error);
    errorMessage.value = error.message || "Failed to connect to search service";
  } finally {
    loading.value = false;
  }
};

const truncateText = (text: string, maxLength: number) => {
  if (text.length <= maxLength) return text;
  return text.substring(0, maxLength) + "...";
};
</script>
