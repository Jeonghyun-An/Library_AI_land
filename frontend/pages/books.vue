<!-- pages/books.vue -->
<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
    <div class="flex justify-between items-center mb-8">
      <h1 class="text-3xl font-bold text-gray-900">Library Collection</h1>
      <NuxtLink
        to="/upload"
        class="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition"
      >
        + Add Book
      </NuxtLink>
    </div>

    <!-- Filters -->
    <div class="bg-white rounded-lg shadow-sm p-6 mb-8">
      <div class="grid md:grid-cols-3 gap-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2"
            >Category</label
          >
          <select
            v-model="filters.category"
            @change="loadBooks()"
            class="w-full px-4 py-2 border border-gray-300 rounded-lg"
          >
            <option value="">All Categories</option>
            <option value="technical">Technical</option>
            <option value="academic">Academic</option>
            <option value="fiction">Fiction</option>
            <option value="textbook">Textbook</option>
            <option value="general">General</option>
          </select>
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2"
            >Author</label
          >
          <input
            v-model="filters.author"
            @input="debounceLoadBooks"
            type="text"
            placeholder="Filter by author"
            class="w-full px-4 py-2 border border-gray-300 rounded-lg"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2"
            >Sort By</label
          >
          <select
            v-model="sortBy"
            @change="loadBooks()"
            class="w-full px-4 py-2 border border-gray-300 rounded-lg"
          >
            <option value="recent">Most Recent</option>
            <option value="title">Title (A-Z)</option>
            <option value="author">Author (A-Z)</option>
          </select>
        </div>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="text-center py-12">
      <div class="spinner mx-auto mb-4"></div>
      <p class="text-gray-600">Loading books...</p>
    </div>

    <!-- Books Grid -->
    <div v-else-if="books.length > 0" class="space-y-6">
      <div class="text-sm text-gray-600 mb-4">
        Showing {{ books.length }} of {{ totalBooks }} books
      </div>

      <div class="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
        <div
          v-for="book in books"
          :key="book.doc_id"
          class="bg-white rounded-lg shadow-md hover:shadow-lg transition overflow-hidden"
        >
          <!-- Book Cover Placeholder -->
          <div
            class="h-48 bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center"
          >
            <svg
              class="w-24 h-24 text-white opacity-50"
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

          <!-- Book Info -->
          <div class="p-6">
            <h3 class="text-lg font-semibold text-gray-900 mb-2 line-clamp-2">
              {{ book.title }}
            </h3>

            <div class="space-y-2 mb-4">
              <p
                v-if="book.author"
                class="text-sm text-gray-600 flex items-center"
              >
                <svg
                  class="w-4 h-4 mr-2"
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
                {{ book.author }}
              </p>

              <p v-if="book.category" class="text-sm">
                <span
                  class="px-2 py-1 bg-indigo-100 text-indigo-800 rounded text-xs"
                >
                  {{ book.category }}
                </span>
              </p>

              <p v-if="book.chunk_count" class="text-xs text-gray-500">
                {{ book.chunk_count }} chunks indexed
              </p>
            </div>

            <div
              v-if="book.description"
              class="text-sm text-gray-600 mb-4 line-clamp-2"
            >
              {{ book.description }}
            </div>

            <div class="flex items-center justify-between pt-4 border-t">
              <button
                @click="viewBookDetails(book)"
                class="text-indigo-600 hover:text-indigo-700 text-sm font-medium"
              >
                View Details
              </button>
              <button
                @click="searchInBook(book)"
                class="text-gray-600 hover:text-gray-700"
                title="Search in this book"
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
                    d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                  />
                </svg>
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Load More -->
      <div v-if="books.length < totalBooks" class="text-center pt-8">
        <button
          @click="loadMore"
          :disabled="loadingMore"
          class="px-6 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition"
        >
          <span v-if="!loadingMore">Load More</span>
          <span v-else>Loading...</span>
        </button>
      </div>
    </div>

    <!-- Empty State -->
    <div v-else class="text-center py-12">
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
          d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
        />
      </svg>
      <h3 class="text-xl font-semibold text-gray-900 mb-2">No books found</h3>
      <p class="text-gray-600 mb-6">
        Start building your library by uploading books
      </p>
      <NuxtLink
        to="/upload"
        class="inline-block px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition"
      >
        Upload Your First Book
      </NuxtLink>
    </div>

    <!-- Book Details Modal -->
    <div
      v-if="selectedBook"
      @click="selectedBook = null"
      class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50"
    >
      <div
        @click.stop
        class="bg-white rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto"
      >
        <div class="p-6">
          <div class="flex justify-between items-start mb-6">
            <h2 class="text-2xl font-bold text-gray-900">
              {{ selectedBook.title }}
            </h2>
            <button
              @click="selectedBook = null"
              class="text-gray-500 hover:text-gray-700"
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
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          </div>

          <div class="space-y-4">
            <div v-if="selectedBook.author">
              <h3 class="text-sm font-medium text-gray-700">Author</h3>
              <p class="text-gray-900">{{ selectedBook.author }}</p>
            </div>

            <div v-if="selectedBook.isbn">
              <h3 class="text-sm font-medium text-gray-700">ISBN</h3>
              <p class="text-gray-900">{{ selectedBook.isbn }}</p>
            </div>

            <div v-if="selectedBook.publisher">
              <h3 class="text-sm font-medium text-gray-700">Publisher</h3>
              <p class="text-gray-900">{{ selectedBook.publisher }}</p>
            </div>

            <div v-if="selectedBook.publication_year">
              <h3 class="text-sm font-medium text-gray-700">
                Publication Year
              </h3>
              <p class="text-gray-900">{{ selectedBook.publication_year }}</p>
            </div>

            <div v-if="selectedBook.category">
              <h3 class="text-sm font-medium text-gray-700">Category</h3>
              <p class="text-gray-900 capitalize">
                {{ selectedBook.category }}
              </p>
            </div>

            <div v-if="selectedBook.language">
              <h3 class="text-sm font-medium text-gray-700">Language</h3>
              <p class="text-gray-900">
                {{ getLanguageName(selectedBook.language) }}
              </p>
            </div>

            <div v-if="selectedBook.description">
              <h3 class="text-sm font-medium text-gray-700">Description</h3>
              <p class="text-gray-900">{{ selectedBook.description }}</p>
            </div>

            <div v-if="selectedBook.chunk_count">
              <h3 class="text-sm font-medium text-gray-700">Indexed Chunks</h3>
              <p class="text-gray-900">
                {{ selectedBook.chunk_count }} text segments
              </p>
            </div>

            <div v-if="selectedBook.page_count">
              <h3 class="text-sm font-medium text-gray-700">Pages</h3>
              <p class="text-gray-900">{{ selectedBook.page_count }} pages</p>
            </div>
          </div>

          <div class="mt-8 pt-6 border-t flex space-x-4">
            <NuxtLink
              :to="`/?q=${encodeURIComponent(selectedBook.title)}`"
              class="flex-1 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 text-center transition"
            >
              Search in This Book
            </NuxtLink>
            <button
              @click="selectedBook = null"
              class="flex-1 px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { navigateTo } from "nuxt/app";
import { ref, onMounted } from "vue";
import type { BookInfo, BooksResponse } from "~/types";

const config = useRuntimeConfig();
const apiBase = config.public.apiBase as string;

const books = ref<BookInfo[]>([]);
const totalBooks = ref<number>(0);
const loading = ref<boolean>(true);
const loadingMore = ref<boolean>(false);
const selectedBook = ref<BookInfo | null>(null);
const limit = 12;
const offset = ref<number>(0);

const filters = ref({
  category: "",
  author: "",
});

const sortBy = ref<string>("recent");

let debounceTimer: ReturnType<typeof setTimeout> | null = null;

const loadBooks = async (loadMore = false) => {
  if (loadMore) {
    loadingMore.value = true;
  } else {
    loading.value = true;
    offset.value = 0;
  }

  try {
    const params = new URLSearchParams({
      limit: limit.toString(),
      offset: offset.value.toString(),
    });

    if (filters.value.category)
      params.append("category", filters.value.category);
    if (filters.value.author) params.append("author", filters.value.author);

    const response = await $fetch<BooksResponse>(
      `${apiBase}/library/books?${params}`,
    );

    if (response.success) {
      if (loadMore) {
        books.value = [...books.value, ...response.data];
      } else {
        books.value = response.data;
      }
      totalBooks.value = response.total;

      // Sort locally
      if (sortBy.value === "title") {
        books.value.sort((a, b) => a.title.localeCompare(b.title));
      } else if (sortBy.value === "author") {
        books.value.sort((a, b) =>
          (a.author || "").localeCompare(b.author || ""),
        );
      }
    }
  } catch (error) {
    console.error("Failed to load books:", error);
  } finally {
    loading.value = false;
    loadingMore.value = false;
  }
};

const debounceLoadBooks = () => {
  if (debounceTimer) clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    loadBooks();
  }, 500);
};

const loadMore = () => {
  offset.value += limit;
  loadBooks(true);
};

const viewBookDetails = (book: BookInfo) => {
  selectedBook.value = book;
};

const searchInBook = (book: BookInfo) => {
  navigateTo(`/?book=${encodeURIComponent(book.title)}`);
};

const getLanguageName = (code: string): string => {
  const languages: Record<string, string> = {
    ko: "Korean",
    en: "English",
    ja: "Japanese",
    zh: "Chinese",
  };
  return languages[code] || code;
};

onMounted(() => {
  loadBooks();
});
</script>
