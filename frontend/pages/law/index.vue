<template>
  <div class="flex min-h-screen bg-gray-50">
    <!-- 헤더 -->
    <header
      class="fixed top-0 left-0 right-0 h-16 bg-white border-b border-gray-200 z-50"
    >
      <div class="flex items-center justify-between h-full px-5">
        <!-- 햄버거 메뉴 -->
        <button
          @click="toggleSidebar"
          class="w-10 h-10 flex items-center justify-center rounded hover:bg-gray-100 transition"
          aria-label="메뉴"
        >
          <i class="fas fa-bars text-xl text-gray-700"></i>
        </button>

        <!-- 로고 -->
        <div class="logo">
          <img
            src="/img/layout/hd_logo.svg"
            alt="LANDSOFT AI 헌법 특화 에이전트"
            class="hd_logo view_ctr"
          />
        </div>

        <!-- 사용자 메뉴 -->
        <button
          @click="toggleUserMenu"
          class="flex items-center gap-2 px-3 py-2 border border-gray-300 rounded-md hover:bg-gray-50 transition"
        >
          <i class="fas fa-user text-sm"></i>
          <span class="text-sm">최승환 님</span>
          <i class="fas fa-chevron-down text-xs"></i>
        </button>
      </div>
    </header>

    <!-- 사이드바 -->
    <aside
      :class="[
        'fixed top-16 left-0 w-80 h-[calc(100vh-4rem)] bg-white border-r border-gray-200 z-40 overflow-y-auto transition-transform duration-300',
        isSidebarOpen ? 'translate-x-0' : '-translate-x-full',
      ]"
    >
      <div
        class="flex items-center justify-between p-5 border-b border-gray-200"
      >
        <h2 class="text-lg font-semibold">질의 히스토리</h2>
        <button
          @click="toggleSidebar"
          class="w-8 h-8 flex items-center justify-center rounded hover:bg-gray-100"
        >
          <i class="fas fa-times"></i>
        </button>
      </div>

      <div class="p-5">
        <!-- 오늘 히스토리 -->
        <div class="mb-6">
          <h3 class="text-sm font-semibold text-gray-600 mb-3">오늘</h3>
          <div
            v-for="(item, idx) in todayHistory"
            :key="`today-${idx}`"
            @click="loadHistory(item, idx)"
            :class="[
              'flex items-center gap-3 p-3 rounded-md cursor-pointer transition mb-1',
              selectedHistory === idx
                ? 'bg-blue-50 text-blue-600'
                : 'hover:bg-gray-100',
            ]"
          >
            <i class="fas fa-clock text-sm text-gray-400"></i>
            <span class="text-sm flex-1 truncate">{{ item.query }}</span>
          </div>
        </div>

        <!-- 최근 히스토리 -->
        <div class="mb-6">
          <h3 class="text-sm font-semibold text-gray-600 mb-3">
            주요 국가 법령 비교/시사 오늘 비교 해석
          </h3>
          <div
            v-for="(item, idx) in recentHistory"
            :key="`recent-${idx}`"
            @click="loadHistory(item, idx + 100)"
            class="flex items-center gap-3 p-3 rounded-md cursor-pointer hover:bg-gray-100 transition mb-1"
          >
            <i class="fas fa-history text-sm text-gray-400"></i>
            <span class="text-sm flex-1 truncate">{{ item.query }}</span>
          </div>
        </div>

        <!-- 하단 안내 -->
        <div class="mt-8 pt-5 border-t border-gray-200">
          <p class="text-xs text-gray-600 mb-3">
            AI가 생성한 콘텐츠입니다. 콘텐츠의 정확성은 보장되지 않을 수
            있습니다.
          </p>
          <div class="space-y-2">
            <a
              href="#"
              class="flex items-center gap-2 text-xs text-gray-700 hover:text-blue-600 py-1"
            >
              <i class="fas fa-info-circle"></i>
              AI 언어모델 이용지침 소개
            </a>
            <a
              href="#"
              class="flex items-center gap-2 text-xs text-gray-700 hover:text-blue-600 py-1"
            >
              <i class="fas fa-exclamation-triangle"></i>
              개인정보 보호 및 면책 고지
            </a>
          </div>
        </div>
      </div>
    </aside>

    <!-- 메인 컨텐츠 -->
    <main
      :class="[
        'flex-1 mt-16 transition-all duration-300',
        isSidebarOpen ? 'ml-80' : 'ml-0',
      ]"
    >
      <!-- 검색 전 초기 화면 -->
      <div v-if="!hasSearched" class="max-w-3xl mx-auto px-5 py-20">
        <!-- 히어로 섹션 -->
        <div class="text-center mb-12">
          <div
            class="w-20 h-20 mx-auto mb-6 flex items-center justify-center bg-gradient-to-br from-cyan-400 to-blue-500 rounded-full"
          >
            <i class="fas fa-gavel text-4xl text-white"></i>
          </div>
          <h1 class="text-4xl font-bold text-gray-900 mb-4">
            AI 헌법 특화 에이전트
          </h1>
          <p class="text-base text-gray-600 leading-relaxed">
            우리나라 헌법과 국군의 헌법과 비교 분석해주는 법령도서관의 생성형
            인공지능 서비스입니다.
          </p>
        </div>

        <!-- 검색 박스 -->
        <div class="mb-12">
          <div
            class="flex items-center bg-white border-2 border-gray-200 rounded-xl p-1 focus-within:border-blue-500 transition"
          >
            <button
              @click="toggleSearchFilter"
              class="w-10 h-10 flex items-center justify-center rounded-lg hover:bg-gray-100 transition"
            >
              <i class="fas fa-sliders-h text-gray-600"></i>
            </button>

            <input
              type="text"
              v-model="query"
              @keyup.enter="handleSearch"
              placeholder="질문을 입력해주세요."
              class="flex-1 px-4 py-3 text-base outline-none"
              :disabled="isSearching"
            />

            <button
              @click="handleSearch"
              :disabled="isSearching || !query.trim()"
              class="w-12 h-12 flex items-center justify-center bg-gradient-to-br from-cyan-400 to-blue-500 text-white rounded-lg hover:shadow-lg hover:-translate-y-0.5 disabled:opacity-50 disabled:cursor-not-allowed transition"
            >
              <i v-if="!isSearching" class="fas fa-search"></i>
              <i v-else class="fas fa-spinner fa-spin"></i>
            </button>
          </div>
        </div>

        <!-- 질문 예시 -->
        <div class="mb-8">
          <div class="flex items-center justify-between mb-5">
            <h3 class="text-lg font-semibold">질문 예시</h3>
            <a
              href="#"
              class="flex items-center gap-1.5 text-sm text-blue-600 hover:underline"
            >
              <i class="fas fa-lightbulb"></i>
              AI 언어모델 이용지침 소개
            </a>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
            <button
              v-for="(example, idx) in exampleQuestions"
              :key="idx"
              @click="selectExample(example)"
              class="flex items-start justify-between p-4 bg-white border border-gray-200 rounded-lg text-left hover:border-blue-500 hover:bg-blue-50 hover:-translate-y-0.5 transition"
            >
              <span class="text-sm text-gray-700 leading-relaxed flex-1">
                {{ example }}
              </span>
              <i class="fas fa-arrow-right text-gray-400 ml-3 mt-1"></i>
            </button>
          </div>
        </div>

        <!-- 에러 메시지 -->
        <div
          v-if="error"
          class="flex items-center gap-3 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700"
        >
          <i class="fas fa-exclamation-circle"></i>
          <span class="text-sm">{{ error }}</span>
        </div>
      </div>

      <!-- 검색 결과 화면 -->
      <div v-else class="p-5">
        <!-- 검색 박스 (상단 고정) -->
        <div class="max-w-3xl mx-auto mb-8">
          <div
            class="flex items-center bg-white border-2 border-gray-200 rounded-xl p-1 focus-within:border-blue-500 transition"
          >
            <button
              @click="toggleSearchFilter"
              class="w-10 h-10 flex items-center justify-center rounded-lg hover:bg-gray-100 transition"
            >
              <i class="fas fa-sliders-h text-gray-600"></i>
            </button>

            <input
              type="text"
              v-model="query"
              @keyup.enter="handleSearch"
              placeholder="질문을 입력해주세요."
              class="flex-1 px-4 py-3 text-base outline-none"
              :disabled="isSearching"
            />

            <button
              @click="handleSearch"
              :disabled="isSearching || !query.trim()"
              class="w-12 h-12 flex items-center justify-center bg-gradient-to-br from-cyan-400 to-blue-500 text-white rounded-lg hover:shadow-lg hover:-translate-y-0.5 disabled:opacity-50 disabled:cursor-not-allowed transition"
            >
              <i v-if="!isSearching" class="fas fa-search"></i>
              <i v-else class="fas fa-spinner fa-spin"></i>
            </button>
          </div>
        </div>

        <!-- AI 요약 -->
        <div
          v-if="searchResults?.summary"
          class="max-w-5xl mx-auto mb-8 p-6 bg-white rounded-xl shadow-sm"
        >
          <div class="flex items-center gap-3 mb-4">
            <i class="fas fa-robot text-2xl text-blue-600"></i>
            <h3 class="text-lg font-semibold">AI 비교 요약</h3>
          </div>
          <p class="text-sm text-gray-700 leading-relaxed">
            {{ searchResults.summary }}
          </p>
        </div>

        <!-- 검색 메타 정보 -->
        <div
          class="max-w-5xl mx-auto mb-8 flex gap-6 px-6 py-4 bg-white rounded-lg"
        >
          <div class="flex gap-2">
            <span class="text-sm text-gray-600">검색 시간:</span>
            <span class="text-sm font-semibold text-gray-900">
              {{ searchResults?.search_time_ms?.toFixed(0) }}ms
            </span>
          </div>
          <div class="flex gap-2">
            <span class="text-sm text-gray-600">한국 헌법:</span>
            <span class="text-sm font-semibold text-gray-900">
              {{ searchResults?.total_korean_found }}건
            </span>
          </div>
          <div class="flex gap-2">
            <span class="text-sm text-gray-600">외국 헌법:</span>
            <span class="text-sm font-semibold text-gray-900">
              {{ searchResults?.total_foreign_found }}건
            </span>
          </div>
        </div>

        <!-- 국가 선택 -->
        <div class="max-w-5xl mx-auto mb-8 p-6 bg-white rounded-xl">
          <h3 class="text-lg font-semibold mb-5">국가선택</h3>

          <!-- 대륙 탭 -->
          <div class="flex gap-2 mb-5">
            <button
              v-for="continent in continents"
              :key="continent.id"
              @click="selectContinent(continent.id)"
              :class="[
                'px-4 py-2 border rounded-md text-sm font-medium transition',
                selectedContinent === continent.id
                  ? 'bg-blue-500 text-white border-blue-500'
                  : 'bg-white text-gray-700 border-gray-300 hover:border-blue-500 hover:bg-blue-50',
              ]"
            >
              {{ continent.name }}
            </button>
          </div>

          <!-- 국가 그리드 -->
          <div class="grid grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-3">
            <button
              v-for="country in filteredCountries"
              :key="country.code"
              @click="selectCountry(country.code)"
              :class="[
                'flex flex-col items-center gap-2 p-3 border rounded-lg transition',
                selectedCountry === country.code
                  ? 'border-blue-500 bg-blue-50 ring-2 ring-blue-200'
                  : 'border-gray-200 hover:border-blue-500 hover:bg-blue-50',
              ]"
            >
              <img
                :src="`/img/flags/${country.code.toLowerCase()}.png`"
                :alt="country.name"
                @error="handleFlagError"
                class="w-12 h-9 object-cover rounded border border-gray-200"
              />
              <span class="text-xs text-gray-700 text-center">
                {{ country.name }}
              </span>
            </button>
          </div>
        </div>

        <!-- PDF 비교 뷰 -->
        <div class="max-w-5xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-6">
          <!-- 좌측: 대한민국 헌법 -->
          <div class="bg-white rounded-xl shadow-sm overflow-hidden">
            <div class="px-5 py-4 bg-gray-50 border-b border-gray-200">
              <h3 class="flex items-center gap-2 font-semibold">
                <i class="fas fa-file-pdf text-blue-600"></i>
                대한민국 헌법
              </h3>
            </div>
            <div class="p-5 max-h-[600px] overflow-y-auto">
              <div v-if="koreanResults.length > 0" class="space-y-4">
                <div
                  v-for="(result, idx) in koreanResults"
                  :key="idx"
                  @click="scrollToResult('korean', Number(idx))"
                  class="flex gap-4 p-4 border border-gray-200 rounded-lg cursor-pointer hover:border-blue-500 hover:bg-blue-50 transition"
                >
                  <div class="flex-shrink-0">
                    <div
                      class="w-14 h-14 flex items-center justify-center bg-gradient-to-br from-cyan-400 to-blue-500 text-white rounded-full font-bold text-base"
                    >
                      {{ Math.round(result.score * 100) }}
                    </div>
                  </div>
                  <div class="flex-1 min-w-0">
                    <div class="text-sm font-semibold text-gray-900 mb-2">
                      {{ result.display_path }}
                    </div>
                    <div
                      class="text-xs text-gray-600 leading-relaxed mb-2 line-clamp-3"
                    >
                      {{ result.korean_text?.substring(0, 150) }}...
                    </div>
                    <div class="text-xs text-gray-400">
                      페이지 {{ result.page_korean || result.page }}
                    </div>
                  </div>
                </div>
              </div>
              <div
                v-else
                class="flex flex-col items-center justify-center py-20 text-gray-400"
              >
                <i class="fas fa-inbox text-5xl mb-4"></i>
                <p class="text-sm">검색 결과가 없습니다</p>
              </div>
            </div>
          </div>

          <!-- 우측: 비교 국가 헌법 -->
          <div class="bg-white rounded-xl shadow-sm overflow-hidden">
            <div class="px-5 py-4 bg-gray-50 border-b border-gray-200">
              <h3 class="flex items-center gap-2 font-semibold">
                <i class="fas fa-file-pdf text-blue-600"></i>
                {{ getSelectedCountryName() }} 헌법
              </h3>
            </div>
            <div class="p-5 max-h-[600px] overflow-y-auto">
              <div v-if="foreignResults.length > 0" class="space-y-4">
                <div
                  v-for="(result, idx) in foreignResults"
                  :key="idx"
                  @click="scrollToResult('foreign', Number(idx))"
                  class="flex gap-4 p-4 border border-gray-200 rounded-lg cursor-pointer hover:border-blue-500 hover:bg-blue-50 transition"
                >
                  <div class="flex-shrink-0">
                    <div
                      class="w-14 h-14 flex items-center justify-center bg-gradient-to-br from-cyan-400 to-blue-500 text-white rounded-full font-bold text-base"
                    >
                      {{ Math.round(result.score * 100) }}
                    </div>
                  </div>
                  <div class="flex-1 min-w-0">
                    <div class="text-xs text-gray-500 mb-1">
                      {{ result.country_name }}
                    </div>
                    <div class="text-sm font-semibold text-gray-900 mb-2">
                      {{ result.display_path }}
                    </div>
                    <div
                      v-if="result.has_korean"
                      class="text-xs text-gray-600 leading-relaxed mb-1 line-clamp-2"
                    >
                      [한글] {{ result.korean_text?.substring(0, 100) }}...
                    </div>
                    <div
                      v-if="result.has_english"
                      class="text-xs text-gray-600 leading-relaxed mb-2 line-clamp-2"
                    >
                      [영어] {{ result.english_text?.substring(0, 100) }}...
                    </div>
                    <div class="text-xs text-gray-400">
                      페이지
                      {{
                        result.page_english || result.page_korean || result.page
                      }}
                    </div>
                  </div>
                </div>
              </div>
              <div
                v-else
                class="flex flex-col items-center justify-center py-20 text-gray-400"
              >
                <i class="fas fa-inbox text-5xl mb-4"></i>
                <p class="text-sm">검색 결과가 없습니다</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from "vue";

const config = useRuntimeConfig();
const apiBase = config.public.apiBase;

// UI 상태
const isSidebarOpen = ref(false);
const hasSearched = ref(false);
const isSearching = ref(false);
const selectedHistory = ref<number | null>(null);
const selectedContinent = ref("all");
const selectedCountry = ref("GH");

// 검색 상태
const query = ref("");
const searchResults = ref<any>(null);
const error = ref<string | null>(null);

// 히스토리 데이터
const todayHistory = ref([
  { query: "인간의 존엄성과 권리의 자국의 헌법 조항 알려줘." },
]);

const recentHistory = ref([
  { query: "주요 국가 법령 분석에 자유 오늘 비교 해석" },
  { query: "주요 국가 법령 비교/시사 오늘 비교 해석" },
]);

// 예시 질문
const exampleQuestions = ref([
  "인간의 존엄성과 권리의 각 국의 헌법 조항 알려줘.",
  "주요 국가 법령 분석에 자유 오늘 비교 해석. (권리 국가 독립 보장 등등)",
  "인간의 존엄성과 권리의 각 국의 헌법 조항 알려줘. 인간의 존엄성과 권리의 각 국의 헌법 조항 알려줘.",
  "인간의 존엄성과 권리의 각 국의 헌법 조항 알려줘.",
]);

// 대륙 목록
const continents = ref([
  { id: "all", name: "전체" },
  { id: "africa", name: "아프리카" },
  { id: "asia", name: "아시아" },
  { id: "europe", name: "유럽" },
  { id: "americas", name: "아메리카" },
]);

// 국가 목록
const allCountries = ref([
  { code: "GH", name: "가나", continent: "africa" },
  { code: "NG", name: "나이지리아", continent: "africa" },
  { code: "ZA", name: "남아공", continent: "africa" },
  { code: "RW", name: "르완다", continent: "africa" },
  { code: "US", name: "미국", continent: "americas" },
  { code: "JP", name: "일본", continent: "asia" },
  { code: "DE", name: "독일", continent: "europe" },
  { code: "FR", name: "프랑스", continent: "europe" },
]);

// 계산된 속성
const koreanResults = computed(() => {
  return searchResults.value?.korean_results || [];
});

const foreignResults = computed(() => {
  if (!searchResults.value) return [];
  return (
    searchResults.value.foreign_results?.filter(
      (r: any) => r.country === selectedCountry.value,
    ) || []
  );
});

const filteredCountries = computed(() => {
  if (selectedContinent.value === "all") {
    return allCountries.value;
  }
  return allCountries.value.filter(
    (c) => c.continent === selectedContinent.value,
  );
});

// 메서드
const toggleSidebar = () => {
  isSidebarOpen.value = !isSidebarOpen.value;
};

const toggleUserMenu = () => {
  console.log("User menu toggled");
};

const toggleSearchFilter = () => {
  console.log("Search filter toggled");
};

const handleSearch = async () => {
  if (!query.value.trim()) {
    error.value = "검색어를 입력해주세요";
    return;
  }

  isSearching.value = true;
  error.value = null;
  hasSearched.value = true;

  try {
    const response = await $fetch<any>(`${apiBase}/api/constitution/search`, {
      method: "POST",
      body: {
        query: query.value,
        korean_top_k: 3,
        foreign_top_k: 5,
        target_country: selectedCountry.value,
        generate_summary: true,
      },
    });

    searchResults.value = response;
    todayHistory.value.unshift({ query: query.value });
  } catch (err: any) {
    error.value = err.message || "검색 중 오류가 발생했습니다";
    console.error("Search error:", err);
  } finally {
    isSearching.value = false;
  }
};

const selectExample = (example: string) => {
  query.value = example;
  handleSearch();
};

const loadHistory = (item: any, idx: number) => {
  selectedHistory.value = idx;
  query.value = item.query;
  handleSearch();
};

const selectContinent = (continentId: string) => {
  selectedContinent.value = continentId;
};

const selectCountry = async (countryCode: string) => {
  selectedCountry.value = countryCode;
  if (hasSearched.value) {
    await handleSearch();
  }
};

const getSelectedCountryName = () => {
  const country = allCountries.value.find(
    (c) => c.code === selectedCountry.value,
  );
  return country?.name || "외국";
};

const handleFlagError = (event: Event) => {
  const target = event.target as HTMLImageElement;
  target.src = "/img/flags/default.png";
};

const scrollToResult = (type: "korean" | "foreign", index: number) => {
  console.log(`Scroll to ${type} result ${index}`);
};
</script>
