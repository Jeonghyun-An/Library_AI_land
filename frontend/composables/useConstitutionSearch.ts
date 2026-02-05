// frontend/composables/useConstitutionSearch.ts
import { ref, computed, type Ref } from "vue";

export interface SearchResult {
  chunk_id: string;
  text: string;
  score: number;
  metadata: {
    country_code: string;
    country_name: string;
    article_number?: string;
    article_title?: string;
    chapter?: string;
    page_number?: number;
  };
  highlights?: Array<{ start: number; end: number }>;
}

export interface SearchResponse {
  query: string;
  query_analysis: {
    detected_language: string;
    keywords: string[];
    article_references: string[];
  };
  results: SearchResult[];
  total_found: number;
  search_time_ms: number;
}

export interface ConstitutionMetadata {
  country_code: string;
  country_name: string;
  language: string;
  version?: string;
  total_chunks: number;
}

export const useConstitutionSearch = () => {
  const config = useRuntimeConfig();
  const apiBase = config.public.apiBase;

  // 상태 관리
  const query = ref("");
  const isSearching = ref(false);
  const searchResults = ref<SearchResponse | null>(null);
  const error = ref<string | null>(null);

  // 국가 선택
  const referenceCountry = ref("KR"); // 기준 국가 (좌측 PDF)
  const comparisonCountry = ref("US"); // 비교 국가 (우측 PDF)
  const availableCountries = ref<ConstitutionMetadata[]>([]);

  // 필터 옵션
  const searchFilters = ref({
    top_k: 5,
    use_reranking: true,
    article_filter: [] as string[],
    chapter_filter: [] as string[],
  });

  // 계산된 속성
  const hasResults = computed(() => {
    return searchResults.value && searchResults.value.results.length > 0;
  });

  const referenceResults = computed(() => {
    if (!searchResults.value) return [];
    return searchResults.value.results.filter(
      (r) => r.metadata.country_code === referenceCountry.value,
    );
  });

  const comparisonResults = computed(() => {
    if (!searchResults.value) return [];
    return searchResults.value.results.filter(
      (r) => r.metadata.country_code === comparisonCountry.value,
    );
  });

  /**
   * 헌법 검색 실행
   */
  const executeSearch = async () => {
    if (!query.value.trim()) {
      error.value = "검색어를 입력해주세요";
      return;
    }

    isSearching.value = true;
    error.value = null;

    try {
      const response = await $fetch<SearchResponse>(
        `${apiBase}/constitution/search`,
        {
          method: "POST",
          body: {
            query: query.value,
            ...searchFilters.value,
          },
        },
      );

      searchResults.value = response;
    } catch (err: any) {
      error.value = err.message || "검색 중 오류가 발생했습니다";
      console.error("Search error:", err);
    } finally {
      isSearching.value = false;
    }
  };

  /**
   * 사용 가능한 국가 목록 로드
   */
  const loadAvailableCountries = async () => {
    try {
      const response = await $fetch<{ countries: ConstitutionMetadata[] }>(
        `${apiBase}/constitution/countries`,
      );
      availableCountries.value = response.countries;
    } catch (err) {
      console.error("Failed to load countries:", err);
    }
  };

  /**
   * 비교 국가 변경
   */
  const changeComparisonCountry = async (countryCode: string) => {
    comparisonCountry.value = countryCode;

    // 검색 결과가 있으면 재검색
    if (hasResults.value) {
      await executeSearch();
    }
  };

  /**
   * 검색 초기화
   */
  const resetSearch = () => {
    query.value = "";
    searchResults.value = null;
    error.value = null;
  };

  return {
    // 상태
    query,
    isSearching,
    searchResults,
    error,
    referenceCountry,
    comparisonCountry,
    availableCountries,
    searchFilters,

    // 계산된 속성
    hasResults,
    referenceResults,
    comparisonResults,

    // 메서드
    executeSearch,
    loadAvailableCountries,
    changeComparisonCountry,
    resetSearch,
  };
};
