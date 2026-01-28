<!-- pages/about.vue -->
<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
    <h1 class="text-4xl font-bold text-gray-900 mb-8 text-center">
      About Library RAG System
    </h1>

    <!-- Hero Description -->
    <div class="bg-white rounded-lg shadow-md p-8 mb-12">
      <p class="text-lg text-gray-700 leading-relaxed mb-4">
        Library RAG is an AI-powered knowledge search system that goes beyond
        traditional keyword matching. Using advanced natural language processing
        and semantic understanding, it helps you find exactly what you're
        looking for across your entire book collection.
      </p>
      <p class="text-gray-600">
        Built with cutting-edge AI technology, optimized for NVIDIA A4000 GPU.
      </p>
    </div>

    <!-- How It Works -->
    <div class="mb-12">
      <h2 class="text-2xl font-bold text-gray-900 mb-6">How It Works</h2>
      <div class="grid md:grid-cols-3 gap-6">
        <div class="bg-white rounded-lg shadow-md p-6">
          <div
            class="w-12 h-12 bg-indigo-600 rounded-lg flex items-center justify-center mb-4"
          >
            <span class="text-white text-xl font-bold">1</span>
          </div>
          <h3 class="text-lg font-semibold text-gray-900 mb-2">
            Upload & Process
          </h3>
          <p class="text-gray-600 text-sm">
            Upload your PDF books. Our system extracts text, recognizes chapters
            and sections, and intelligently chunks the content while preserving
            structure.
          </p>
        </div>

        <div class="bg-white rounded-lg shadow-md p-6">
          <div
            class="w-12 h-12 bg-green-600 rounded-lg flex items-center justify-center mb-4"
          >
            <span class="text-white text-xl font-bold">2</span>
          </div>
          <h3 class="text-lg font-semibold text-gray-900 mb-2">AI Embedding</h3>
          <p class="text-gray-600 text-sm">
            Each text chunk is converted into a 1024-dimensional vector using
            BGE-M3, capturing semantic meaning beyond just keywords.
          </p>
        </div>

        <div class="bg-white rounded-lg shadow-md p-6">
          <div
            class="w-12 h-12 bg-purple-600 rounded-lg flex items-center justify-center mb-4"
          >
            <span class="text-white text-xl font-bold">3</span>
          </div>
          <h3 class="text-lg font-semibold text-gray-900 mb-2">
            Semantic Search
          </h3>
          <p class="text-gray-600 text-sm">
            Ask questions naturally. The AI understands your intent and finds
            relevant passages, even if they don't contain your exact words.
          </p>
        </div>
      </div>
    </div>

    <!-- Technology Stack -->
    <div class="mb-12">
      <h2 class="text-2xl font-bold text-gray-900 mb-6">Technology Stack</h2>
      <div class="bg-white rounded-lg shadow-md p-8">
        <div class="space-y-4">
          <div class="flex items-center space-x-4">
            <div class="w-32 font-semibold text-gray-700">Frontend</div>
            <div class="flex-1 text-gray-600">Nuxt.js, Vue 3, Tailwind CSS</div>
          </div>
          <div class="flex items-center space-x-4">
            <div class="w-32 font-semibold text-gray-700">Backend</div>
            <div class="flex-1 text-gray-600">FastAPI, Python 3.10</div>
          </div>
          <div class="flex items-center space-x-4">
            <div class="w-32 font-semibold text-gray-700">LLM</div>
            <div class="flex-1 text-gray-600">Llama-3.2-3B-Instruct (vLLM)</div>
          </div>
          <div class="flex items-center space-x-4">
            <div class="w-32 font-semibold text-gray-700">Embedding</div>
            <div class="flex-1 text-gray-600">BAAI/bge-m3 (1024 dim)</div>
          </div>
          <div class="flex items-center space-x-4">
            <div class="w-32 font-semibold text-gray-700">Reranker</div>
            <div class="flex-1 text-gray-600">BAAI/bge-reranker-v2-m3</div>
          </div>
          <div class="flex items-center space-x-4">
            <div class="w-32 font-semibold text-gray-700">Vector DB</div>
            <div class="flex-1 text-gray-600">Milvus 2.2.11 (HNSW index)</div>
          </div>
          <div class="flex items-center space-x-4">
            <div class="w-32 font-semibold text-gray-700">Storage</div>
            <div class="flex-1 text-gray-600">MinIO</div>
          </div>
          <div class="flex items-center space-x-4">
            <div class="w-32 font-semibold text-gray-700">GPU</div>
            <div class="flex-1 text-gray-600">
              NVIDIA A4000 16GB (optimized)
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Features -->
    <div class="mb-12">
      <h2 class="text-2xl font-bold text-gray-900 mb-6">Key Features</h2>
      <div class="grid md:grid-cols-2 gap-6">
        <div class="bg-white rounded-lg shadow-md p-6">
          <div class="flex items-start space-x-3">
            <svg
              class="w-6 h-6 text-green-600 mt-1"
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
            <div>
              <h3 class="font-semibold text-gray-900 mb-1">
                Semantic Understanding
              </h3>
              <p class="text-sm text-gray-600">
                Find answers based on meaning, not just keywords
              </p>
            </div>
          </div>
        </div>

        <div class="bg-white rounded-lg shadow-md p-6">
          <div class="flex items-start space-x-3">
            <svg
              class="w-6 h-6 text-green-600 mt-1"
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
            <div>
              <h3 class="font-semibold text-gray-900 mb-1">
                Chapter-Aware Chunking
              </h3>
              <p class="text-sm text-gray-600">
                Preserves book structure and context
              </p>
            </div>
          </div>
        </div>

        <div class="bg-white rounded-lg shadow-md p-6">
          <div class="flex items-start space-x-3">
            <svg
              class="w-6 h-6 text-green-600 mt-1"
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
            <div>
              <h3 class="font-semibold text-gray-900 mb-1">AI Reranking</h3>
              <p class="text-sm text-gray-600">
                Results ordered by relevance, not just similarity
              </p>
            </div>
          </div>
        </div>

        <div class="bg-white rounded-lg shadow-md p-6">
          <div class="flex items-start space-x-3">
            <svg
              class="w-6 h-6 text-green-600 mt-1"
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
            <div>
              <h3 class="font-semibold text-gray-900 mb-1">
                Multi-Language Support
              </h3>
              <p class="text-sm text-gray-600">
                Korean, English, Japanese, Chinese
              </p>
            </div>
          </div>
        </div>

        <div class="bg-white rounded-lg shadow-md p-6">
          <div class="flex items-start space-x-3">
            <svg
              class="w-6 h-6 text-green-600 mt-1"
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
            <div>
              <h3 class="font-semibold text-gray-900 mb-1">Fast Search</h3>
              <p class="text-sm text-gray-600">
                HNSW indexing for sub-second queries
              </p>
            </div>
          </div>
        </div>

        <div class="bg-white rounded-lg shadow-md p-6">
          <div class="flex items-start space-x-3">
            <svg
              class="w-6 h-6 text-green-600 mt-1"
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
            <div>
              <h3 class="font-semibold text-gray-900 mb-1">Genre Detection</h3>
              <p class="text-sm text-gray-600">
                Automatic categorization and optimization
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Performance Stats -->
    <div class="mb-12">
      <h2 class="text-2xl font-bold text-gray-900 mb-6">Performance</h2>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-6">
        <div class="bg-white rounded-lg shadow-md p-6 text-center">
          <div class="text-3xl font-bold text-indigo-600 mb-2">&lt;2s</div>
          <div class="text-sm text-gray-600">Search Time</div>
        </div>
        <div class="bg-white rounded-lg shadow-md p-6 text-center">
          <div class="text-3xl font-bold text-green-600 mb-2">85%+</div>
          <div class="text-sm text-gray-600">Accuracy</div>
        </div>
        <div class="bg-white rounded-lg shadow-md p-6 text-center">
          <div class="text-3xl font-bold text-purple-600 mb-2">10s</div>
          <div class="text-sm text-gray-600">100 Pages</div>
        </div>
        <div class="bg-white rounded-lg shadow-md p-6 text-center">
          <div class="text-3xl font-bold text-blue-600 mb-2">16GB</div>
          <div class="text-sm text-gray-600">GPU Memory</div>
        </div>
      </div>
    </div>

    <!-- Getting Started -->
    <div class="bg-indigo-50 rounded-lg p-8 text-center">
      <h2 class="text-2xl font-bold text-gray-900 mb-4">Ready to Start?</h2>
      <p class="text-gray-700 mb-6">
        Upload your first book and experience the power of AI-driven semantic
        search
      </p>
      <NuxtLink
        to="/upload"
        class="inline-block px-8 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition font-medium"
      >
        Upload Your First Book
      </NuxtLink>
    </div>
  </div>
</template>

<script setup lang="ts">
// No reactive data needed for static content
</script>
