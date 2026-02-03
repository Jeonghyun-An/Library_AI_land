<!-- pages/upload.vue -->
<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
    <h1 class="text-3xl font-bold text-gray-900 mb-8">Upload New Book</h1>

    <!-- Upload Form -->
    <div class="bg-white rounded-lg shadow-md p-8">
      <!-- File Upload Area -->
      <div
        @drop.prevent="handleDrop"
        @dragover.prevent="dragover = true"
        @dragleave.prevent="dragover = false"
        :class="[
          'border-2 border-dashed rounded-lg p-12 text-center transition',
          dragover
            ? 'border-indigo-500 bg-indigo-50'
            : 'border-gray-300 hover:border-gray-400',
        ]"
      >
        <input
          ref="fileInput"
          type="file"
          accept=".pdf"
          @change="handleFileSelect"
          class="hidden"
        />

        <div v-if="!selectedFile">
          <svg
            class="w-16 h-16 mx-auto text-gray-400 mb-4"
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
          <p class="text-lg font-medium text-gray-900 mb-2">
            Drop your PDF file here, or
            <button
              @click="fileInput?.click()"
              class="text-indigo-600 hover:text-indigo-700"
            >
              browse
            </button>
          </p>
          <p class="text-sm text-gray-600">Supports: PDF (max 100MB)</p>
        </div>

        <div v-else class="flex items-center justify-center space-x-4">
          <svg
            class="w-12 h-12 text-indigo-600"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
            />
          </svg>
          <div class="text-left">
            <p class="font-medium text-gray-900">{{ selectedFile.name }}</p>
            <p class="text-sm text-gray-600">
              {{ formatFileSize(selectedFile.size) }}
            </p>
          </div>
          <button
            @click="selectedFile = null"
            class="text-red-600 hover:text-red-700"
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
      </div>

      <!-- Metadata Form -->
      <div v-if="selectedFile" class="mt-8 space-y-6">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">
            Title <span class="text-red-500">*</span>
          </label>
          <input
            v-model="bookData.title"
            type="text"
            required
            class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            placeholder="Enter book title"
          />
        </div>

        <div class="grid md:grid-cols-2 gap-6">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2"
              >Author</label
            >
            <input
              v-model="bookData.author"
              type="text"
              class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              placeholder="Author name"
            />
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2"
              >ISBN</label
            >
            <input
              v-model="bookData.isbn"
              type="text"
              class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              placeholder="ISBN (optional)"
            />
          </div>
        </div>

        <div class="grid md:grid-cols-2 gap-6">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2"
              >Publisher</label
            >
            <input
              v-model="bookData.publisher"
              type="text"
              class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              placeholder="Publisher name"
            />
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2"
              >Publication Year</label
            >
            <input
              v-model.number="bookData.publication_year"
              type="number"
              min="1800"
              :max="new Date().getFullYear()"
              class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              placeholder="YYYY"
            />
          </div>
        </div>

        <div class="grid md:grid-cols-2 gap-6">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2"
              >Category</label
            >
            <select
              v-model="bookData.category"
              class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            >
              <option value="general">General</option>
              <option value="technical">Technical</option>
              <option value="academic">Academic</option>
              <option value="fiction">Fiction</option>
              <option value="textbook">Textbook</option>
            </select>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2"
              >Language</label
            >
            <select
              v-model="bookData.language"
              class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            >
              <option value="ko">Korean</option>
              <option value="en">English</option>
              <option value="ja">Japanese</option>
              <option value="zh">Chinese</option>
            </select>
          </div>
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2"
            >Description</label
          >
          <textarea
            v-model="bookData.description"
            rows="4"
            class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            placeholder="Brief description of the book (optional)"
          ></textarea>
        </div>

        <!-- Upload Button -->
        <div class="flex items-center justify-between pt-6 border-t">
          <button
            @click="
              selectedFile = null;
              resetForm();
            "
            type="button"
            class="px-6 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition"
          >
            Cancel
          </button>
          <button
            @click="uploadBook"
            :disabled="uploading || !bookData.title"
            class="px-8 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition"
          >
            <span v-if="!uploading">Upload Book</span>
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
              Uploading...
            </span>
          </button>
        </div>
      </div>
    </div>

    <!-- Upload Progress -->
    <div v-if="uploadProgress" class="mt-8 bg-white rounded-lg shadow-md p-6">
      <h3 class="text-lg font-semibold text-gray-900 mb-4">Processing Book</h3>
      <div class="space-y-3">
        <div
          v-for="step in uploadProgress.steps"
          :key="step.name"
          class="flex items-center space-x-3"
        >
          <div
            v-if="step.status === 'completed'"
            class="w-6 h-6 bg-green-500 rounded-full flex items-center justify-center"
          >
            <svg
              class="w-4 h-4 text-white"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M5 13l4 4L19 7"
              />
            </svg>
          </div>
          <div v-else-if="step.status === 'processing'" class="w-6 h-6">
            <svg
              class="animate-spin text-indigo-600"
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
          </div>
          <div v-else class="w-6 h-6 bg-gray-300 rounded-full"></div>
          <span
            :class="
              step.status === 'completed' ? 'text-gray-900' : 'text-gray-500'
            "
          >
            {{ step.label }}
          </span>
        </div>
      </div>
    </div>

    <!-- Success Message -->
    <div
      v-if="uploadSuccess"
      class="mt-8 bg-green-50 border border-green-200 rounded-lg p-6"
    >
      <div class="flex items-start">
        <svg
          class="w-6 h-6 text-green-600 mt-0.5 mr-3"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
        <div class="flex-1">
          <h4 class="font-semibold text-green-900 mb-1">Upload Successful!</h4>
          <p class="text-sm text-green-700 mb-3">{{ uploadSuccess }}</p>
          <div class="flex space-x-4">
            <NuxtLink
              to="/"
              class="text-sm text-green-700 hover:text-green-800 underline"
            >
              Search your library
            </NuxtLink>
            <button
              @click="resetAll"
              class="text-sm text-green-700 hover:text-green-800 underline"
            >
              Upload another book
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Error Message -->
    <div
      v-if="uploadError"
      class="mt-8 bg-red-50 border border-red-200 rounded-lg p-6"
    >
      <div class="flex items-start">
        <svg
          class="w-6 h-6 text-red-600 mt-0.5 mr-3"
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
          <h4 class="font-semibold text-red-900 mb-1">Upload Failed</h4>
          <p class="text-sm text-red-700">{{ uploadError }}</p>
        </div>
        <button
          @click="uploadError = ''"
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
</template>

<script setup lang="ts">
import type { UploadResponse } from "~/types";
import { ref } from "vue";

interface UploadStep {
  name: string;
  label: string;
  status: "pending" | "processing" | "completed";
}

interface UploadProgress {
  steps: UploadStep[];
}

const config = useRuntimeConfig();
const apiBase = config.public.apiBase as string;

const fileInput = ref<HTMLInputElement | null>(null);
const selectedFile = ref<File | null>(null);
const dragover = ref<boolean>(false);
const uploading = ref<boolean>(false);
const uploadSuccess = ref<string>("");
const uploadError = ref<string>("");
const uploadProgress = ref<UploadProgress | null>(null);

const bookData = ref({
  title: "",
  author: "",
  isbn: "",
  publisher: "",
  publication_year: null as number | null,
  category: "general",
  language: "ko",
  description: "",
});

const handleFileSelect = (event: Event) => {
  const target = event.target as HTMLInputElement;
  if (target.files && target.files[0]) {
    selectedFile.value = target.files[0];
    // Auto-fill title from filename
    if (!bookData.value.title) {
      bookData.value.title = target.files[0].name.replace(".pdf", "");
    }
  }
};

const handleDrop = (event: DragEvent) => {
  dragover.value = false;
  if (event.dataTransfer?.files && event.dataTransfer.files[0]) {
    selectedFile.value = event.dataTransfer.files[0];
    if (!bookData.value.title) {
      bookData.value.title = event.dataTransfer.files[0].name.replace(
        ".pdf",
        "",
      );
    }
  }
};

const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return "0 Bytes";
  const k = 1024;
  const sizes = ["Bytes", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + " " + sizes[i];
};

const uploadBook = async () => {
  if (!selectedFile.value || !bookData.value.title) return;

  uploading.value = true;
  uploadError.value = "";
  uploadSuccess.value = "";

  // Show progress
  uploadProgress.value = {
    steps: [
      { name: "upload", label: "Uploading file", status: "processing" },
      { name: "parse", label: "Parsing PDF", status: "pending" },
      { name: "chunk", label: "Chunking text", status: "pending" },
      { name: "embed", label: "Generating embeddings", status: "pending" },
      { name: "index", label: "Indexing to database", status: "pending" },
    ],
  };

  try {
    const formData = new FormData();
    formData.append("file", selectedFile.value);
    formData.append("title", bookData.value.title);
    if (bookData.value.author) formData.append("author", bookData.value.author);
    if (bookData.value.isbn) formData.append("isbn", bookData.value.isbn);
    if (bookData.value.publisher)
      formData.append("publisher", bookData.value.publisher);
    if (bookData.value.publication_year)
      formData.append(
        "publication_year",
        bookData.value.publication_year.toString(),
      );
    formData.append("category", bookData.value.category);
    formData.append("language", bookData.value.language);
    if (bookData.value.description)
      formData.append("description", bookData.value.description);

    const response = await $fetch<UploadResponse>(`${apiBase}/library/upload`, {
      method: "POST",
      body: formData,
    });

    if (response.success) {
      uploadProgress.value.steps[0].status = "completed";

      // Simulate progress (실제로는 WebSocket이나 polling으로 진행 상태 확인)
      setTimeout(() => {
        if (!uploadProgress.value) return;
        uploadProgress.value.steps[1].status = "processing";
        setTimeout(() => {
          if (!uploadProgress.value) return;
          uploadProgress.value.steps[1].status = "completed";
          uploadProgress.value.steps[2].status = "processing";
          setTimeout(() => {
            if (!uploadProgress.value) return;
            uploadProgress.value.steps[2].status = "completed";
            uploadProgress.value.steps[3].status = "processing";
            setTimeout(() => {
              if (!uploadProgress.value) return;
              uploadProgress.value.steps[3].status = "completed";
              uploadProgress.value.steps[4].status = "processing";
              setTimeout(() => {
                if (!uploadProgress.value) return;
                uploadProgress.value.steps[4].status = "completed";
                uploadSuccess.value = `Book "${bookData.value.title}" has been uploaded and indexed successfully!`;
              }, 2000);
            }, 3000);
          }, 2000);
        }, 2000);
      }, 1000);
    } else {
      uploadError.value = response.message || "Upload failed";
      uploadProgress.value = null;
    }
  } catch (error: any) {
    console.error("Upload error:", error);
    uploadError.value =
      error.data?.detail || error.message || "Failed to upload book";
    uploadProgress.value = null;
  } finally {
    uploading.value = false;
  }
};

const resetForm = () => {
  bookData.value = {
    title: "",
    author: "",
    isbn: "",
    publisher: "",
    publication_year: null,
    category: "general",
    language: "ko",
    description: "",
  };
};

const resetAll = () => {
  selectedFile.value = null;
  uploadSuccess.value = "";
  uploadError.value = "";
  uploadProgress.value = null;
  resetForm();
};
</script>
