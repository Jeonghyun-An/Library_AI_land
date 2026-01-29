// frontend/composables/usePDFHighlight.ts
import { ref, type Ref } from "vue";
import type { SearchResult } from "./useConstitutionSearch";

export interface HighlightRegion {
  pageNumber: number;
  x: number;
  y: number;
  width: number;
  height: number;
  text: string;
  score: number;
}

export const usePDFHighlight = () => {
  const highlights = ref<HighlightRegion[]>([]);
  const currentPage = ref(1);
  const totalPages = ref(0);
  const pdfScale = ref(1.5);
  const isLoading = ref(false);

  /**
   * 검색 결과에서 하이라이트 영역 생성
   */
  const generateHighlights = (
    searchResults: SearchResult[],
    pdfTextContent: any[],
  ): HighlightRegion[] => {
    const newHighlights: HighlightRegion[] = [];

    searchResults.forEach((result) => {
      const pageNumber = result.metadata.page_number || 1;
      const textToFind = result.text.trim();

      // PDF 텍스트 컨텐츠에서 매칭되는 영역 찾기
      const pageContent = pdfTextContent[pageNumber - 1];
      if (!pageContent) return;

      const matchPositions = findTextPositions(pageContent, textToFind);

      matchPositions.forEach((pos) => {
        newHighlights.push({
          pageNumber,
          x: pos.x,
          y: pos.y,
          width: pos.width,
          height: pos.height,
          text: textToFind,
          score: result.score,
        });
      });
    });

    return newHighlights;
  };

  /**
   * PDF 텍스트 컨텐츠에서 특정 텍스트 위치 찾기
   */
  const findTextPositions = (
    pageContent: any,
    textToFind: string,
  ): Array<{ x: number; y: number; width: number; height: number }> => {
    const positions: Array<{
      x: number;
      y: number;
      width: number;
      height: number;
    }> = [];

    if (!pageContent.items) return positions;

    // 단순화된 텍스트 매칭 (실제로는 더 복잡한 로직 필요)
    let accumulatedText = "";
    let startIndex = -1;

    pageContent.items.forEach((item: any, index: number) => {
      accumulatedText += item.str;

      if (accumulatedText.includes(textToFind)) {
        if (startIndex === -1) startIndex = index;

        // 텍스트가 완전히 매칭되면 위치 계산
        if (accumulatedText.length >= textToFind.length) {
          const transform = item.transform;
          positions.push({
            x: transform[4],
            y: transform[5],
            width: item.width,
            height: item.height,
          });

          // 리셋
          accumulatedText = "";
          startIndex = -1;
        }
      }
    });

    return positions;
  };

  /**
   * 하이라이트 적용
   */
  const applyHighlights = (
    searchResults: SearchResult[],
    pdfTextContent: any[],
  ) => {
    highlights.value = generateHighlights(searchResults, pdfTextContent);
  };

  /**
   * 하이라이트 초기화
   */
  const clearHighlights = () => {
    highlights.value = [];
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
    pdfScale.value = 1.5;
  };

  /**
   * 특정 하이라이트로 스크롤
   */
  const scrollToHighlight = (highlightIndex: number) => {
    const highlight = highlights.value[highlightIndex];
    if (!highlight) return;

    // 해당 페이지로 이동
    goToPage(highlight.pageNumber);

    // 하이라이트 위치로 스크롤 (실제 구현은 PDF 렌더링 컴포넌트와 연동 필요)
    setTimeout(() => {
      const element = document.querySelector(
        `[data-highlight-index="${highlightIndex}"]`,
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

    // 메서드
    applyHighlights,
    clearHighlights,
    goToPage,
    zoomIn,
    zoomOut,
    resetZoom,
    scrollToHighlight,
  };
};
