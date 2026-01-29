<template>
  <div class="constitution_search_page">
    <!-- 헤더 -->
    <header class="search_header">
      <div class="inner">
        <div class="header_content">
          <div class="logo">
            <img src="/img/main/txt_search_main.svg" alt="헌법 비교 검색" />
          </div>
          <div class="header_actions">
            <button class="btn_lang" @click="toggleLanguage">
              <img src="/img/icon/ic_lang_b.svg" alt="" />
              {{ currentLanguage === "ko" ? "한국어" : "English" }}
            </button>
            <NuxtLink to="/" class="btn_home">
              <i class="fas fa-home"></i>
            </NuxtLink>
          </div>
        </div>
      </div>
    </header>

    <!-- 검색 영역 -->
    <section class="search_section">
      <div class="inner">
        <div class="search_main">
          <h1 class="search_title">AI 헌법 비교 검색 시스템</h1>
          <p class="search_description">
            사용자의 질문에 대한민국 헌법과 세계 각국 헌법을 비교하여
            분석합니다.
          </p>

          <!-- 검색 박스 -->
          <div class="search_box_wrap">
            <div class="search_condition_wrap" v-if="showFilters">
              <div class="select_box">
                <select v-model="searchFilters.top_k" title="검색 결과 수">
                  <option :value="5">상위 5개</option>
                  <option :value="10">상위 10개</option>
                  <option :value="20">상위 20개</option>
                </select>
              </div>
              <div class="form_check">
                <input
                  type="checkbox"
                  id="use_reranking"
                  v-model="searchFilters.use_reranking"
                />
                <label for="use_reranking">리랭킹 사용</label>
              </div>
            </div>

            <div class="search_box">
              <button
                class="btn_filter"
                @click="showFilters = !showFilters"
                :class="{ active: showFilters }"
                aria-label="검색 조건 설정"
              >
                <i class="fas fa-sliders-h"></i>
              </button>

              <input
                type="text"
                v-model="query"
                @keyup.enter="handleSearch"
                placeholder="연구 질문을 입력하세요. (예: 국민의 기본권은 어떻게 보장되나요?)"
                class="search_input"
                :disabled="isSearching"
              />

              <button
                class="btn_search"
                @click="handleSearch"
                :disabled="isSearching || !query.trim()"
              >
                <i v-if="!isSearching" class="fas fa-search"></i>
                <i v-else class="fas fa-spinner fa-spin"></i>
                {{ isSearching ? "검색 중..." : "검색" }}
              </button>
            </div>

            <!-- 에러 메시지 -->
            <div v-if="error" class="error_message">
              <i class="fas fa-exclamation-circle"></i>
              {{ error }}
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 검색 결과 영역 -->
    <section v-if="hasResults" class="results_section">
      <div class="inner_wide">
        <!-- 국가 선택 -->
        <div class="country_selector_wrap">
          <div class="country_selector_header">
            <h2>비교 국가 선택</h2>
            <p>
              좌측: {{ getReferenceCountryName() }} | 우측:
              {{ getComparisonCountryName() }}
            </p>
          </div>
          <CountrySelector
            v-model="comparisonCountry"
            :countries="formattedCountries"
            @update:modelValue="handleCountryChange"
          />
        </div>

        <!-- PDF 비교 뷰 -->
        <div class="pdf_comparison_wrap">
          <!-- 좌측: 대한민국 헌법 -->
          <div class="pdf_panel left">
            <PDFViewer
              :pdf-url="getReferencePDFUrl()"
              :title="`대한민국 헌법`"
              :country-code="referenceCountry"
              :search-results="referenceResults"
            />
          </div>

          <!-- 우측: 비교 국가 헌법 -->
          <div class="pdf_panel right">
            <PDFViewer
              :pdf-url="getComparisonPDFUrl()"
              :title="`${getComparisonCountryName()} 헌법`"
              :country-code="comparisonCountry"
              :search-results="comparisonResults"
            />
          </div>
        </div>

        <!-- 검색 통계 -->
        <div class="search_stats">
          <div class="stat_item">
            <i class="fas fa-clock"></i>
            <span
              >검색 시간: {{ searchResults?.search_time_ms.toFixed(0) }}ms</span
            >
          </div>
          <div class="stat_item">
            <i class="fas fa-file-alt"></i>
            <span>총 {{ searchResults?.total_found }}개 결과</span>
          </div>
          <div class="stat_item">
            <i class="fas fa-language"></i>
            <span
              >감지된 언어:
              {{ searchResults?.query_analysis.detected_language }}</span
            >
          </div>
        </div>
      </div>
    </section>

    <!-- 사용 가이드 (결과 없을 때) -->
    <section v-else class="guide_section">
      <div class="inner">
        <div class="guide_content">
          <div class="guide_item">
            <div class="guide_icon">
              <i class="fas fa-search"></i>
            </div>
            <h3>검색 방법</h3>
            <p>궁금한 헌법 내용을 자연어로 질문하세요</p>
          </div>
          <div class="guide_item">
            <div class="guide_icon">
              <i class="fas fa-balance-scale"></i>
            </div>
            <h3>비교 분석</h3>
            <p>대한민국과 다른 국가의 헌법을 동시에 비교합니다</p>
          </div>
          <div class="guide_item">
            <div class="guide_icon">
              <i class="fas fa-highlight"></i>
            </div>
            <h3>하이라이팅</h3>
            <p>관련도가 높은 조항을 자동으로 강조합니다</p>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useConstitutionSearch } from "~/composables/useConstitutionSearch";
import CountrySelector from "~/components/CountrySelector.vue";
import PDFViewer from "~/components/PDFViewer.vue";

const {
  query,
  isSearching,
  searchResults,
  error,
  referenceCountry,
  comparisonCountry,
  availableCountries,
  searchFilters,
  hasResults,
  referenceResults,
  comparisonResults,
  executeSearch,
  loadAvailableCountries,
  changeComparisonCountry,
} = useConstitutionSearch();

const currentLanguage = ref("ko");
const showFilters = ref(false);

// 국가 정보 포매팅 (CountrySelector용)
const formattedCountries = computed(() => {
  return availableCountries.value.map((country) => ({
    code: country.country_code,
    name: country.country_name,
    region: inferRegion(country.country_code),
    version: country.version,
  }));
});

/**
 * 검색 실행
 */
const handleSearch = async () => {
  await executeSearch();
};

/**
 * 비교 국가 변경
 */
const handleCountryChange = async (countryCode: string) => {
  await changeComparisonCountry(countryCode);
};

/**
 * 언어 토글
 */
const toggleLanguage = () => {
  currentLanguage.value = currentLanguage.value === "ko" ? "en" : "ko";
};

/**
 * PDF URL 생성
 */
const getReferencePDFUrl = () => {
  return `/pdfs/constitutions/${referenceCountry.value}.pdf`;
};

const getComparisonPDFUrl = () => {
  return `/pdfs/constitutions/${comparisonCountry.value}.pdf`;
};

/**
 * 국가명 조회
 */
const getReferenceCountryName = () => {
  const country = availableCountries.value.find(
    (c) => c.country_code === referenceCountry.value,
  );
  return country?.country_name || "대한민국";
};

const getComparisonCountryName = () => {
  const country = availableCountries.value.find(
    (c) => c.country_code === comparisonCountry.value,
  );
  return country?.country_name || "미국";
};

/**
 * 지역 추론 (국가 코드 기반)
 */
const inferRegion = (code: string): string => {
  const asiaCountries = ["KR", "JP", "CN", "IN", "TH", "VN", "PH"];
  const europeCountries = ["UK", "FR", "DE", "IT", "ES", "NL", "SE"];
  const americasCountries = ["US", "CA", "MX", "BR", "AR", "CL"];
  const africaCountries = ["ZA", "NG", "EG", "KE", "GH"];
  const oceaniaCountries = ["AU", "NZ"];

  if (asiaCountries.includes(code)) return "asia";
  if (europeCountries.includes(code)) return "europe";
  if (americasCountries.includes(code)) return "americas";
  if (africaCountries.includes(code)) return "africa";
  if (oceaniaCountries.includes(code)) return "oceania";

  return "all";
};

onMounted(async () => {
  await loadAvailableCountries();
});
</script>

<style scoped>
.constitution_search_page {
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

/* 헤더 */
.search_header {
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  position: sticky;
  top: 0;
  z-index: 100;
}

.header_content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 0;
}

.logo img {
  height: 40px;
}

.header_actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

.btn_lang,
.btn_home {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: white;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 14px;
  color: #374151;
  text-decoration: none;
}

.btn_lang:hover,
.btn_home:hover {
  background: #f3f4f6;
  border-color: #2563eb;
}

/* 검색 영역 */
.search_section {
  padding: 80px 0;
}

.search_main {
  text-align: center;
  max-width: 800px;
  margin: 0 auto;
}

.search_title {
  font-size: 48px;
  font-weight: 700;
  color: white;
  margin: 0 0 16px 0;
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.search_description {
  font-size: 18px;
  color: rgba(255, 255, 255, 0.9);
  margin: 0 0 40px 0;
}

.search_box_wrap {
  background: white;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
}

.search_condition_wrap {
  display: flex;
  gap: 16px;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid #e5e7eb;
}

.select_box select {
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
}

.form_check {
  display: flex;
  align-items: center;
  gap: 8px;
}

.search_box {
  display: flex;
  gap: 12px;
  align-items: center;
}

.btn_filter {
  padding: 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: white;
  cursor: pointer;
  transition: all 0.2s;
  flex-shrink: 0;
}

.btn_filter:hover,
.btn_filter.active {
  background: #f3f4f6;
  border-color: #2563eb;
  color: #2563eb;
}

.search_input {
  flex: 1;
  padding: 14px 20px;
  border: 2px solid #e5e7eb;
  border-radius: 8px;
  font-size: 16px;
  transition: all 0.2s;
}

.search_input:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.search_input:disabled {
  background: #f9fafb;
  cursor: not-allowed;
}

.btn_search {
  padding: 14px 32px;
  border: none;
  border-radius: 8px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
  display: flex;
  align-items: center;
  gap: 8px;
}

.btn_search:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.btn_search:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.error_message {
  margin-top: 16px;
  padding: 12px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 6px;
  color: #dc2626;
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 결과 영역 */
.results_section {
  padding: 40px 0;
  background: white;
}

.inner_wide {
  max-width: 1600px;
  margin: 0 auto;
  padding: 0 20px;
}

.country_selector_wrap {
  margin-bottom: 32px;
  background: white;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.country_selector_header {
  margin-bottom: 20px;
}

.country_selector_header h2 {
  font-size: 24px;
  font-weight: 700;
  color: #1f2937;
  margin: 0 0 8px 0;
}

.country_selector_header p {
  font-size: 14px;
  color: #6b7280;
  margin: 0;
}

.pdf_comparison_wrap {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
  margin-bottom: 32px;
}

.pdf_panel {
  height: 800px;
}

.search_stats {
  display: flex;
  justify-content: center;
  gap: 32px;
  padding: 20px;
  background: #f9fafb;
  border-radius: 8px;
}

.stat_item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #6b7280;
}

.stat_item i {
  color: #2563eb;
}

/* 가이드 영역 */
.guide_section {
  padding: 80px 0;
}

.guide_content {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 32px;
  max-width: 1200px;
  margin: 0 auto;
}

.guide_item {
  text-align: center;
  padding: 32px;
  background: rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(10px);
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  transition: all 0.3s;
}

.guide_item:hover {
  transform: translateY(-8px);
  background: rgba(255, 255, 255, 0.15);
}

.guide_icon {
  width: 80px;
  height: 80px;
  margin: 0 auto 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 50%;
  font-size: 32px;
  color: white;
}

.guide_item h3 {
  font-size: 24px;
  font-weight: 600;
  color: white;
  margin: 0 0 12px 0;
}

.guide_item p {
  font-size: 16px;
  color: rgba(255, 255, 255, 0.9);
  margin: 0;
}

/* 반응형 */
@media (max-width: 1200px) {
  .pdf_comparison_wrap {
    grid-template-columns: 1fr;
  }

  .guide_content {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .search_title {
    font-size: 32px;
  }

  .search_box {
    flex-direction: column;
  }

  .btn_search {
    width: 100%;
  }

  .search_stats {
    flex-direction: column;
    gap: 12px;
  }
}
</style>
