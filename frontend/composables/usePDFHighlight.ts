// frontend/composables/usePDFHighlight.ts
/**
 * PDF 하이라이트 Composable (bbox 기반)
 *
 * Milvus에 저장된 bbox_info를 사용하여 PDF 페이지 이미지 위에
 * 하이라이트 오버레이를 정확한 좌표로 표시합니다.
 *
 * bbox 좌표: PyMuPDF 기준 (72 DPI, 원점 = 좌상단)
 * 이미지 좌표: 렌더링 DPI 기준
 *
 * scale_x = container_display_width / page_width_pt
 * scale_y = container_display_height / page_height_pt
 */

import { ref, computed, type Ref } from "vue";

// ==================== 타입 정의 ====================

/** Milvus에 저장된 bbox 정보 (청킹 시 _pack_bbox_info에서 생성) */
export interface BboxInfo {
  page: number;
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  text: string;
}

/** 검색 결과 1개에 대한 하이라이트 정보 */
export interface HighlightData {
  /** 원본 bbox 목록 (PDF pt 좌표) */
  bboxList: BboxInfo[];
  /** 해당 검색 결과의 유사도 점수 */
  score: number;
  /** 검색 결과 텍스트 (tooltip 표시용) */
  displayText: string;
  /** 조항 번호 (표시용) */
  articleLabel: string;
  /** 검색 결과 인덱스 */
  resultIndex: number;
}

/** 화면에 표시될 개별 하이라이트 사각형 (이미지 좌표로 변환 완료) */
export interface HighlightRect {
  /** CSS left (px, 이미지 좌표) */
  left: number;
  /** CSS top (px, 이미지 좌표) */
  top: number;
  /** CSS width (px) */
  width: number;
  /** CSS height (px) */
  height: number;
  /** 원본 페이지 번호 */
  pageNumber: number;
  /** 유사도 점수 (0~1) */
  score: number;
  /** 텍스트 미리보기 */
  text: string;
  /** 조항 레이블 */
  articleLabel: string;
  /** 부모 HighlightData의 인덱스 */
  resultIndex: number;
  /** 하이라이트 등급 */
  level: "high" | "medium" | "low";
}

/** 페이지 치수 정보 (백엔드 PageDimensionsResponse 대응) */
export interface PageDimensions {
  pageNo: number;
  widthPt: number; // PDF 원본 (72 DPI)
  heightPt: number; // PDF 원본 (72 DPI)
  imageWidthPx: number; // 렌더링 이미지
  imageHeightPx: number; // 렌더링 이미지
}

// ==================== 유틸리티 함수 ====================

/**
 * 점수를 기반으로 하이라이트 등급 결정
 */
function getHighlightLevel(score: number): "high" | "medium" | "low" {
  if (score >= 0.8) return "high";
  if (score >= 0.6) return "medium";
  return "low";
}

/**
 * bbox의 머지 (같은 결과의 여러 bbox를 하나의 큰 사각형으로)
 * - 같은 페이지의 bbox들만 머지
 */
function mergeBboxesByPage(
  bboxList: BboxInfo[],
): Map<
  number,
  { x0: number; y0: number; x1: number; y1: number; texts: string[] }
> {
  const pageMap = new Map<
    number,
    { x0: number; y0: number; x1: number; y1: number; texts: string[] }
  >();

  for (const bbox of bboxList) {
    const existing = pageMap.get(bbox.page);
    if (existing) {
      existing.x0 = Math.min(existing.x0, bbox.x0);
      existing.y0 = Math.min(existing.y0, bbox.y0);
      existing.x1 = Math.max(existing.x1, bbox.x1);
      existing.y1 = Math.max(existing.y1, bbox.y1);
      existing.texts.push(bbox.text);
    } else {
      pageMap.set(bbox.page, {
        x0: bbox.x0,
        y0: bbox.y0,
        x1: bbox.x1,
        y1: bbox.y1,
        texts: [bbox.text],
      });
    }
  }

  return pageMap;
}

// ==================== 메인 Composable ====================

export const usePDFHighlight = () => {
  // 상태
  const highlights = ref<HighlightData[]>([]);
  const currentPage = ref(1);
  const totalPages = ref(0);
  const pdfScale = ref(1.0); // 화면 표시 배율 (container 기준)
  const isLoading = ref(false);
  const activeHighlightIndex = ref<number | null>(null);

  // 페이지별 치수 캐시
  const pageDimensionsCache = ref<Map<number, PageDimensions>>(new Map());

  /**
   * 페이지 치수 설정 (백엔드에서 받아온 데이터)
   */
  const setPageDimensions = (pageNo: number, dims: PageDimensions) => {
    pageDimensionsCache.value.set(pageNo, dims);
  };

  /**
   * 전체 페이지 치수 일괄 설정
   */
  const setAllPageDimensions = (
    pages: Array<{
      page_no: number;
      width_pt: number;
      height_pt: number;
      image_width_px: number;
      image_height_px: number;
    }>,
  ) => {
    const newMap = new Map<number, PageDimensions>();
    for (const p of pages) {
      newMap.set(p.page_no, {
        pageNo: p.page_no,
        widthPt: p.width_pt,
        heightPt: p.height_pt,
        imageWidthPx: p.image_width_px,
        imageHeightPx: p.image_height_px,
      });
    }
    pageDimensionsCache.value = newMap;
  };

  /**
   * 검색 결과에서 하이라이트 데이터 생성
   *
   * @param searchResults - 검색 결과 배열 (ConstitutionArticleResult)
   *  각 결과는 bbox_info[], score, display_path, korean_text/english_text 를 포함
   */
  const applyHighlightsFromResults = (searchResults: any[]) => {
    const newHighlights: HighlightData[] = [];

    searchResults.forEach((result, index) => {
      const bboxInfoRaw: BboxInfo[] = result.bbox_info || [];
      if (bboxInfoRaw.length === 0) return;

      // bbox 유효성 검사
      const validBboxes = bboxInfoRaw.filter(
        (b) =>
          b &&
          typeof b.page === "number" &&
          typeof b.x0 === "number" &&
          typeof b.y0 === "number" &&
          typeof b.x1 === "number" &&
          typeof b.y1 === "number" &&
          b.x1 > b.x0 &&
          b.y1 > b.y0,
      );

      if (validBboxes.length === 0) return;

      const displayText =
        result.korean_text || result.english_text || result.search_text || "";
      const articleLabel =
        result.display_path || result.structure?.article_number || "";

      newHighlights.push({
        bboxList: validBboxes,
        score: result.score || result.display_score || 0,
        displayText: displayText.substring(0, 200),
        articleLabel,
        resultIndex: index,
      });
    });

    highlights.value = newHighlights;
  };

  /**
   * 특정 페이지의 하이라이트 사각형 목록 계산
   *
   * @param pageNo - 페이지 번호
   * @param displayWidth - 실제 화면에 표시되는 이미지 너비 (px)
   * @param displayHeight - 실제 화면에 표시되는 이미지 높이 (px)
   */
  const getHighlightRectsForPage = (
    pageNo: number,
    displayWidth: number,
    displayHeight: number,
  ): HighlightRect[] => {
    const dims = pageDimensionsCache.value.get(pageNo);
    if (!dims) return [];

    // 스케일 계산: PDF pt 좌표 → 화면 px 좌표
    const scaleX = displayWidth / dims.widthPt;
    const scaleY = displayHeight / dims.heightPt;

    const rects: HighlightRect[] = [];

    for (const hlData of highlights.value) {
      // 해당 페이지의 bbox만 필터링
      const pageBboxes = hlData.bboxList.filter((b) => b.page === pageNo);
      if (pageBboxes.length === 0) continue;

      // 같은 결과의 bbox를 페이지별로 머지
      const merged = mergeBboxesByPage(pageBboxes);
      const mergedBbox = merged.get(pageNo);
      if (!mergedBbox) continue;

      const left = mergedBbox.x0 * scaleX;
      const top = mergedBbox.y0 * scaleY;
      const width = (mergedBbox.x1 - mergedBbox.x0) * scaleX;
      const height = (mergedBbox.y1 - mergedBbox.y0) * scaleY;

      // 너무 작은 영역은 스킵
      if (width < 2 || height < 2) continue;

      rects.push({
        left,
        top,
        width,
        height,
        pageNumber: pageNo,
        score: hlData.score,
        text: hlData.displayText,
        articleLabel: hlData.articleLabel,
        resultIndex: hlData.resultIndex,
        level: getHighlightLevel(hlData.score),
      });
    }

    return rects;
  };

  /**
   * 하이라이트가 있는 페이지 목록
   */
  const highlightedPages = computed(() => {
    const pages = new Set<number>();
    for (const hl of highlights.value) {
      for (const bbox of hl.bboxList) {
        pages.add(bbox.page);
      }
    }
    return Array.from(pages).sort((a, b) => a - b);
  });

  /**
   * 첫 번째 하이라이트가 있는 페이지로 이동
   */
  const goToFirstHighlight = () => {
    const pages = highlightedPages.value;
    if (pages.length > 0) {
      currentPage.value = pages[0];
    }
  };

  /**
   * 특정 하이라이트 결과로 이동
   */
  const goToHighlight = (resultIndex: number) => {
    const hlData = highlights.value.find((h) => h.resultIndex === resultIndex);
    if (!hlData || hlData.bboxList.length === 0) return;

    activeHighlightIndex.value = resultIndex;
    currentPage.value = hlData.bboxList[0].page;
  };

  /**
   * 하이라이트 초기화
   */
  const clearHighlights = () => {
    highlights.value = [];
    activeHighlightIndex.value = null;
  };

  /**
   * 페이지 이동
   */
  const goToPage = (pageNumber: number) => {
    if (pageNumber < 1 || pageNumber > totalPages.value) return;
    currentPage.value = pageNumber;
  };

  /**
   * 확대/축소
   */
  const zoomIn = () => {
    pdfScale.value = Math.min(pdfScale.value + 0.25, 3.0);
  };

  const zoomOut = () => {
    pdfScale.value = Math.max(pdfScale.value - 0.25, 0.5);
  };

  const resetZoom = () => {
    pdfScale.value = 1.0;
  };

  /**
   * 특정 하이라이트로 스크롤
   */
  const scrollToHighlight = (highlightIndex: number) => {
    goToHighlight(highlightIndex);

    setTimeout(() => {
      const element = document.querySelector(
        `[data-highlight-result="${highlightIndex}"]`,
      );
      element?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 300);
  };

  return {
    // 상태
    highlights,
    currentPage,
    totalPages,
    pdfScale,
    isLoading,
    activeHighlightIndex,
    highlightedPages,

    // 페이지 치수
    pageDimensionsCache,
    setPageDimensions,
    setAllPageDimensions,

    // 하이라이트
    applyHighlightsFromResults,
    getHighlightRectsForPage,
    goToFirstHighlight,
    goToHighlight,
    clearHighlights,
    scrollToHighlight,

    // 네비게이션
    goToPage,
    zoomIn,
    zoomOut,
    resetZoom,
  };
};
