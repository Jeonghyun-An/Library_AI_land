// composables/useConstitutionAPI.ts
/**
 * 헌법 비교 검색 API Composable
 * 백엔드: app/api/comparative_constitution_router.py
 */

import { get } from "http";

export const useConstitutionAPI = () => {
  const config = useRuntimeConfig();
  const apiBase = config.public.apiBase || "http://localhost:8000";

  /**
   * 비교 검색
   *
   * @param params.query - 검색 쿼리
   * @param params.korean_top_k - 한국 헌법 상위 K개 (기본: 3)
   * @param params.foreign_per_country - 국가당 표시할 조항 수 (기본: 3)
   * @param params.foreign_pool_size - 국가별 후보 풀 크기 (기본: 50)
   * @param params.target_country - 특정 국가만 검색 (옵션)
   * @param params.cursor_map - 국가별 페이지 커서 (예: {"GH": 3, "NG": 6})
   * @param params.generate_summary - 요약 생성 여부 (기본: true)
   *
   * @returns ComparativeSearchResponse
   */
  // 여기서 환경변수 조절
  const comparativeSearch = async (params: {
    query: string;
    korean_top_k?: number;
    korean_score_threshold?: number;
    foreign_per_country?: number;
    foreign_pool_size?: number;
    target_country?: string;
    cursor_map?: Record<string, number>;
    generate_summary?: boolean;
  }) => {
    try {
      const response = await $fetch(
        `${apiBase}/constitution/comparative-search`,
        {
          method: "POST",
          body: {
            query: params.query,
            korean_top_k: params.korean_top_k ?? 5,
            korean_score_threshold: params.korean_score_threshold ?? 0.2,
            foreign_per_country: params.foreign_per_country ?? 8,
            foreign_pool_size: params.foreign_pool_size ?? 50,
            target_country: params.target_country,
            cursor_map: params.cursor_map,
            generate_summary: params.generate_summary ?? true,
          },
        },
      );
      return response;
    } catch (error: any) {
      console.error("[API] 비교 검색 실패:", error);
      throw error;
    }
  };

  /**
   * Pair 요약 생성 (현재 화면 상태 기반)
   *
   * @param params.query - 원본 검색 쿼리
   * @param params.korean_item - 한국 헌법 조항 1개
   * @param params.foreign_by_country - 국가별 현재 조항들
   * @param params.pair_id - 캐시 키 (옵션)
   * @param params.max_tokens - 최대 토큰 수 (기본: 320)
   * @param params.temperature - 온도 (기본: 0.3)
   *
   * @returns ComparativeSummaryResponse
   */
  const generatePairSummary = async (params: {
    query: string;
    korean_item: any;
    foreign_by_country: Record<string, any>;
    pair_id?: string;
    max_tokens?: number;
    temperature?: number;
  }) => {
    try {
      const response = await $fetch(
        `${apiBase}/constitution/comparative-summary`,
        {
          method: "POST",
          body: {
            query: params.query,
            korean_item: params.korean_item,
            foreign_by_country: params.foreign_by_country,
            pair_id: params.pair_id,
            max_tokens: params.max_tokens ?? 320,
            temperature: params.temperature ?? 0.3,
          },
        },
      );
      return response;
    } catch (error: any) {
      console.error("[API] Pair 요약 실패:", error);
      throw error;
    }
  };

  const generateCountrySummary = async (params: {
    query: string;
    korean_items: any[];
    foreign_country: string;
    foreign_items: any[];
    max_tokens?: number;
    temperature?: number;
  }) => {
    try {
      const response = await $fetch(`${apiBase}/constitution/country-summary`, {
        method: "POST",
        body: {
          query: params.query,
          korean_items: params.korean_items,
          foreign_country: params.foreign_country,
          foreign_items: params.foreign_items,
          max_tokens: params.max_tokens ?? 800,
          temperature: params.temperature ?? 0.3,
        },
      });
      return response;
    } catch (error: any) {
      console.error("[API] 국가 요약 실패:", error);
      throw error;
    }
  };

  /**
   * 헌법 문서 업로드
   *
   * @param file - PDF 파일
   * @param params.title - 헌법 제목 (옵션, 자동 생성)
   * @param params.version - 버전/개정일 (옵션, 파일명에서 추출)
   * @param params.is_bilingual - 이중언어 여부 (기본: false)
   * @param params.replace_existing - 기존 문서 자동 삭제 (기본: true)
   */
  const uploadConstitution = async (
    file: File,
    params?: {
      title?: string;
      version?: string;
      is_bilingual?: boolean;
      replace_existing?: boolean;
    },
  ) => {
    try {
      const formData = new FormData();
      formData.append("file", file);

      if (params?.title) formData.append("title", params.title);
      if (params?.version) formData.append("version", params.version);
      if (params?.is_bilingual !== undefined) {
        formData.append("is_bilingual", params.is_bilingual.toString());
      }
      if (params?.replace_existing !== undefined) {
        formData.append("replace_existing", params.replace_existing.toString());
      }

      const response = await $fetch(`${apiBase}/constitution/upload`, {
        method: "POST",
        body: formData,
      });
      return response;
    } catch (error: any) {
      console.error("[API] 업로드 실패:", error);
      throw error;
    }
  };

  /**
   * 헌법 일괄 업로드
   *
   * @param files - PDF 파일 배열
   */
  const batchUploadConstitutions = async (files: File[]) => {
    try {
      const formData = new FormData();

      files.forEach((file) => {
        formData.append("files", file);
      });

      const response = await $fetch(`${apiBase}/constitution/batch-upload`, {
        method: "POST",
        body: formData,
      });
      return response;
    } catch (error: any) {
      console.error("[API] 일괄 업로드 실패:", error);
      throw error;
    }
  };

  /**
   * 헌법 목록 조회
   *
   * @param params.country - 국가 코드 필터 (옵션)
   * @param params.limit - 최대 개수 (기본: 100)
   */
  const listConstitutions = async (params?: {
    country?: string;
    limit?: number;
  }) => {
    try {
      const query = new URLSearchParams();
      if (params?.country) query.append("country", params.country);
      if (params?.limit) query.append("limit", params.limit.toString());

      const url = `${apiBase}/constitution/list?${query.toString()}`;
      const response = await $fetch(url, {
        method: "GET",
      });
      return response;
    } catch (error: any) {
      console.error("[API] 목록 조회 실패:", error);
      throw error;
    }
  };

  /**
   * 특정 국가의 모든 헌법 문서 삭제
   *
   * @param countryCode - 국가 코드 (예: KR, GH, US)
   */
  const deleteCountryConstitutions = async (countryCode: string) => {
    try {
      const response = await $fetch(
        `${apiBase}/constitution/delete/country/${countryCode}`,
        {
          method: "DELETE",
        },
      );
      return response;
    } catch (error: any) {
      console.error("[API] 국가 삭제 실패:", error);
      throw error;
    }
  };

  /**
   * 특정 문서 삭제 (doc_id 지정)
   *
   * @param docId - 문서 ID (예: KR_1987_a1b2c3d4)
   */
  const deleteConstitution = async (docId: string) => {
    try {
      const response = await $fetch(`${apiBase}/constitution/delete/${docId}`, {
        method: "DELETE",
      });
      return response;
    } catch (error: any) {
      console.error("[API] 문서 삭제 실패:", error);
      throw error;
    }
  };

  /**
   * PDF 페이지 이미지 가져오기 (하이라이트용)
   *
   * @param docId - 문서 ID
   * @param pageNo - 페이지 번호 (1-based)
   * @param format - 이미지 포맷 (png | jpeg | base64)
   * @param dpi - 해상도 (기본: 150)
   */
  const getPdfPageImage = async (
    docId: string,
    pageNo: number,
    format: "png" | "jpeg" | "base64" = "png",
    dpi: number = 150,
  ) => {
    try {
      const url = `${apiBase}/constitution/pdf/${docId}/page/${pageNo}?format=${format}&dpi=${dpi}`;

      if (format === "base64") {
        // JSON 응답
        const response = await $fetch(url, { method: "GET" });
        return response;
      } else {
        // 이미지 Blob
        const response = await fetch(url);
        if (!response.ok) throw new Error("이미지 가져오기 실패");
        const blob = await response.blob();
        return URL.createObjectURL(blob);
      }
    } catch (error: any) {
      console.error("[API] PDF 페이지 이미지 실패:", error);
      throw error;
    }
  };

  /**
   * PDF 파일 다운로드 URL 생성
   *
   * @param docId - 문서 ID
   * @param inline - true=브라우저에서 보기, false=다운로드
   */
  const getPdfDownloadUrl = (docId: string, inline: boolean = true) => {
    return `${apiBase}/constitution/pdf/${docId}/download?inline=${inline}`;
  };

  /**
   * 국가 목록 조회
   *
   * @param continent - 대륙 필터 (옵션)
   */
  const getCountries = async (continent?: string) => {
    try {
      const url = continent
        ? `${apiBase}/constitution/countries?continent=${continent}`
        : `${apiBase}/constitution/countries`;

      const response = await $fetch(url, { method: "GET" });
      return response;
    } catch (error: any) {
      console.error("[API] 국가 목록 조회 실패:", error);
      throw error;
    }
  };

  /**
   * 대륙 목록 조회
   */
  const getContinents = async () => {
    try {
      const response = await $fetch(`${apiBase}/constitution/continents`, {
        method: "GET",
      });
      return response;
    } catch (error: any) {
      console.error("[API] 대륙 목록 조회 실패:", error);
      throw error;
    }
  };

  /**
   * 통계 조회
   */
  const getStats = async () => {
    try {
      const response = await $fetch(`${apiBase}/constitution/stats`, {
        method: "GET",
      });
      return response;
    } catch (error: any) {
      console.error("[API] 통계 조회 실패:", error);
      throw error;
    }
  };
  const matchForeign = async (params: {
    search_id: string;
    korean_text: string;
    target_country: string;
    top_k?: number;
  }) => {
    try {
      const response = await $fetch(
        `${apiBase}/constitution/comparative-match`,
        {
          method: "POST",
          body: params,
        },
      );

      return response;
    } catch (error) {
      console.error("Match foreign error:", error);
      throw error;
    }
  };

  /**
   * PDF 페이지 치수 + 이미지 URL 조회 (단일 페이지)
   *
   * @param docId - 문서 ID
   * @param pageNo - 페이지 번호 (1-based)
   * @param dpi - 해상도 (기본: 150)
   * @returns PageDimensionsResponse
   */
  const getPageDimensions = async (
    docId: string,
    pageNo: number,
    dpi: number = 150,
  ) => {
    try {
      const url = `${apiBase}/constitution/pdf/${docId}/page/${pageNo}/dimensions?dpi=${dpi}`;
      const response = await $fetch(url, { method: "GET" });
      return response;
    } catch (error: any) {
      console.error("[API] 페이지 치수 조회 실패:", error);
      throw error;
    }
  };

  /**
   * PDF 전체 페이지 치수 일괄 조회 (초기 로딩용)
   *
   * @param docId - 문서 ID
   * @param dpi - 해상도 (기본: 150)
   * @returns { doc_id, total_pages, dpi, pages: PageDimensions[] }
   */
  const getAllPageDimensions = async (docId: string, dpi: number = 150) => {
    try {
      const url = `${apiBase}/constitution/pdf/${docId}/all-page-dimensions?dpi=${dpi}`;
      const response = await $fetch(url, { method: "GET" });
      return response;
    } catch (error: any) {
      console.error("[API] 전체 페이지 치수 조회 실패:", error);
      throw error;
    }
  };

  return {
    // 검색
    comparativeSearch,
    generatePairSummary,
    generateCountrySummary,
    matchForeign,

    // 업로드/삭제
    uploadConstitution,
    batchUploadConstitutions,
    deleteConstitution,
    deleteCountryConstitutions,

    // 조회
    listConstitutions,
    getCountries,
    getContinents,
    getStats,

    // PDF
    getPdfPageImage,
    getPdfDownloadUrl,
    getPageDimensions,
    getAllPageDimensions,
  };
};
