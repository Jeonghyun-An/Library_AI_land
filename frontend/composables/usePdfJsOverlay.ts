// frontend/composables/usePdfJsOverlay.ts
/**
 * PDF.js iframe과 소통하여 하이라이트 오버레이를 관리하는 Composable
 *
 * 핵심 원리:
 * 1. PDF.js viewer iframe 내부의 .page[data-page-number] 요소들의 위치/크기를 추적
 * 2. bbox_info의 PDF pt 좌표 → iframe 내 canvas/page 좌표로 변환
 * 3. iframe 위에 절대 위치 div로 하이라이트를 표시
 *
 * 같은 origin이어야 iframe.contentDocument 접근 가능 (localhost:90 → localhost:90)
 */

import { ref, computed, onBeforeUnmount, type Ref } from "vue";

// ==================== 타입 정의 ====================

export interface PdfJsPageInfo {
  pageNumber: number;
  /** page div의 iframe 내 위치 (viewerContainer 기준) */
  offsetTop: number;
  offsetLeft: number;
  /** page div의 실제 렌더링 크기 (border/padding 제외) */
  clientWidth: number;
  clientHeight: number;
  /** CSS scale factor (PDF.js 줌에 의해) */
  scale: number;
  /** PDF 원본 크기 (pt, 72DPI 기준) */
  viewportWidth: number;
  viewportHeight: number;
}

export interface OverlayRect {
  /** iframe wrapper 기준 CSS 좌표 */
  left: number;
  top: number;
  width: number;
  height: number;
  /** 메타데이터 */
  pageNumber: number;
  score: number;
  text: string;
  articleLabel: string;
  resultIndex: number;
  level: "high" | "medium" | "low";
}

// ==================== Composable ====================

export const usePdfJsOverlay = () => {
  // iframe 내부 상태 추적
  const iframeReady = ref(false);
  const currentScale = ref(1.0);
  const visiblePages = ref<number[]>([]);
  const pageInfoCache = ref<Map<number, PdfJsPageInfo>>(new Map());

  // 스크롤 오프셋 (viewerContainer)
  const scrollTop = ref(0);
  const scrollLeft = ref(0);
  const viewerHeight = ref(0);
  const viewerWidth = ref(0);

  // cleanup용
  let _scrollHandler: (() => void) | null = null;
  let _resizeObserver: ResizeObserver | null = null;
  let _pollInterval: ReturnType<typeof setInterval> | null = null;
  let _iframeRef: HTMLIFrameElement | null = null;

  /**
   * iframe이 로드된 후 PDF.js와 연결
   *
   * @param iframe - PDF.js viewer iframe 엘리먼트
   * @param onUpdate - 스크롤/줌 변경 시 호출되는 콜백 (오버레이 갱신용)
   */
  const attachToIframe = (
    iframe: HTMLIFrameElement,
    onUpdate?: () => void,
  ): Promise<boolean> => {
    return new Promise((resolve) => {
      _iframeRef = iframe;

      const tryAttach = () => {
        try {
          const iframeDoc =
            iframe.contentDocument || iframe.contentWindow?.document;
          if (!iframeDoc) return false;

          const viewerContainer = iframeDoc.getElementById("viewerContainer");
          if (!viewerContainer) return false;

          // PDF.js 앱 접근
          const pdfApp = (iframe.contentWindow as any)?.PDFViewerApplication;
          if (!pdfApp) return false;

          iframeReady.value = true;

          // 스크롤 이벤트 바인딩
          _scrollHandler = () => {
            scrollTop.value = viewerContainer.scrollTop;
            scrollLeft.value = viewerContainer.scrollLeft;
            viewerHeight.value = viewerContainer.clientHeight;
            viewerWidth.value = viewerContainer.clientWidth;
            updateVisiblePages(iframeDoc);
            onUpdate?.();
          };
          viewerContainer.addEventListener("scroll", _scrollHandler, {
            passive: true,
          });

          // 초기값
          scrollTop.value = viewerContainer.scrollTop;
          scrollLeft.value = viewerContainer.scrollLeft;
          viewerHeight.value = viewerContainer.clientHeight;
          viewerWidth.value = viewerContainer.clientWidth;

          // ResizeObserver로 줌 변경 감지
          const viewer = iframeDoc.getElementById("viewer");
          if (viewer) {
            _resizeObserver = new ResizeObserver(() => {
              refreshPageInfo(iframeDoc);
              onUpdate?.();
            });
            _resizeObserver.observe(viewer);
          }

          // PDF.js 이벤트 리스닝 (pagechanging, scalechanging)
          if (pdfApp.eventBus) {
            pdfApp.eventBus.on("scalechanging", (e: any) => {
              currentScale.value = e.scale || 1.0;
              // 줌 후 약간의 딜레이 후 페이지 정보 갱신
              setTimeout(() => {
                refreshPageInfo(iframeDoc);
                onUpdate?.();
              }, 100);
            });

            pdfApp.eventBus.on("pagechanging", () => {
              updateVisiblePages(iframeDoc);
              onUpdate?.();
            });

            pdfApp.eventBus.on("pagesloaded", () => {
              refreshPageInfo(iframeDoc);
              onUpdate?.();
            });
          }

          // 초기 페이지 정보 수집
          refreshPageInfo(iframeDoc);
          updateVisiblePages(iframeDoc);

          return true;
        } catch (err) {
          console.warn("[usePdfJsOverlay] iframe 접근 실패:", err);
          return false;
        }
      };

      // iframe 로드 대기 (PDF.js 초기화는 시간이 걸림)
      if (tryAttach()) {
        resolve(true);
        return;
      }

      // 폴링으로 재시도 (최대 10초)
      let retryCount = 0;
      const maxRetries = 50; // 200ms * 50 = 10초
      _pollInterval = setInterval(() => {
        retryCount++;
        if (tryAttach()) {
          if (_pollInterval) clearInterval(_pollInterval);
          _pollInterval = null;
          resolve(true);
        } else if (retryCount >= maxRetries) {
          if (_pollInterval) clearInterval(_pollInterval);
          _pollInterval = null;
          console.warn("[usePdfJsOverlay] PDF.js 연결 타임아웃");
          resolve(false);
        }
      }, 200);
    });
  };

  /**
   * 모든 페이지의 위치/크기 정보 갱신
   */
  const refreshPageInfo = (iframeDoc: Document) => {
    const newCache = new Map<number, PdfJsPageInfo>();
    const pages = iframeDoc.querySelectorAll(".page[data-page-number]");
    const viewerContainer = iframeDoc.getElementById("viewerContainer");

    if (!viewerContainer) return;

    pages.forEach((pageEl) => {
      const pageNum = parseInt(pageEl.getAttribute("data-page-number") || "0");
      if (pageNum <= 0) return;

      const el = pageEl as HTMLElement;

      // PDF.js는 page div 안에 canvas를 렌더링
      // page div의 크기 = canvas 크기 + border/padding
      const canvasWrapper = el.querySelector(".canvasWrapper") as HTMLElement;
      const targetEl = canvasWrapper || el;

      // PDF.js의 viewport 정보 (원본 PDF 크기)
      let viewportWidth = 595; // A4 기본값 (pt)
      let viewportHeight = 842;
      let scale = 1.0;

      try {
        const pdfApp = (_iframeRef?.contentWindow as any)?.PDFViewerApplication;
        if (pdfApp?.pdfViewer?._pages?.[pageNum - 1]) {
          const pdfPage = pdfApp.pdfViewer._pages[pageNum - 1];
          if (pdfPage.viewport) {
            // viewport는 이미 스케일 적용된 값
            viewportWidth =
              pdfPage.viewport.viewBox?.[2] ||
              pdfPage.viewport.width / pdfPage.viewport.scale;
            viewportHeight =
              pdfPage.viewport.viewBox?.[3] ||
              pdfPage.viewport.height / pdfPage.viewport.scale;
            scale = pdfPage.viewport.scale || 1.0;
          }
        }
      } catch {
        // fallback 사용
      }

      currentScale.value = scale;

      newCache.set(pageNum, {
        pageNumber: pageNum,
        offsetTop: el.offsetTop,
        offsetLeft: el.offsetLeft,
        clientWidth: targetEl.clientWidth,
        clientHeight: targetEl.clientHeight,
        scale,
        viewportWidth,
        viewportHeight,
      });
    });

    pageInfoCache.value = newCache;
  };

  /**
   * 현재 보이는 페이지 번호 목록 갱신
   */
  const updateVisiblePages = (iframeDoc: Document) => {
    const viewerContainer = iframeDoc.getElementById("viewerContainer");
    if (!viewerContainer) return;

    const containerTop = viewerContainer.scrollTop;
    const containerBottom = containerTop + viewerContainer.clientHeight;

    const visible: number[] = [];
    pageInfoCache.value.forEach((info, pageNum) => {
      const pageTop = info.offsetTop;
      const pageBottom = pageTop + info.clientHeight;

      // 페이지가 뷰포트와 겹치는지 확인
      if (pageBottom > containerTop && pageTop < containerBottom) {
        visible.push(pageNum);
      }
    });

    visiblePages.value = visible.sort((a, b) => a - b);
  };

  /**
   * bbox (PDF pt 좌표) → 오버레이 rect (iframe wrapper 기준 px 좌표) 변환
   *
   * @param bbox - { page, x0, y0, x1, y1 } (72 DPI pt 좌표)
   * @param meta - 추가 메타데이터 (score, text 등)
   * @returns OverlayRect | null
   */
  const bboxToOverlayRect = (
    bbox: {
      page: number;
      x0: number;
      y0: number;
      x1: number;
      y1: number;
      text?: string;
    },
    meta: {
      score: number;
      text: string;
      articleLabel: string;
      resultIndex: number;
    },
  ): OverlayRect | null => {
    const pageInfo = pageInfoCache.value.get(bbox.page);
    if (!pageInfo) return null;

    // PDF pt → 페이지 div 내 px 좌표
    // scaleX = page실제렌더링너비 / PDF원본너비(pt)
    const scaleX = pageInfo.clientWidth / pageInfo.viewportWidth;
    const scaleY = pageInfo.clientHeight / pageInfo.viewportHeight;

    const localLeft = bbox.x0 * scaleX;
    const localTop = bbox.y0 * scaleY;
    const localWidth = (bbox.x1 - bbox.x0) * scaleX;
    const localHeight = (bbox.y1 - bbox.y0) * scaleY;

    // 페이지 div의 offsetTop/Left → viewerContainer 기준 절대좌표
    // 그 다음 scrollTop/Left 빼서 → 현재 보이는 viewport 기준 좌표
    const absLeft = pageInfo.offsetLeft + localLeft - scrollLeft.value;
    const absTop = pageInfo.offsetTop + localTop - scrollTop.value;

    // 레벨 결정
    let level: "high" | "medium" | "low";
    if (meta.score >= 0.8) level = "high";
    else if (meta.score >= 0.6) level = "medium";
    else level = "low";

    return {
      left: absLeft,
      top: absTop,
      width: localWidth,
      height: localHeight,
      pageNumber: bbox.page,
      score: meta.score,
      text: meta.text,
      articleLabel: meta.articleLabel,
      resultIndex: meta.resultIndex,
      level,
    };
  };

  /**
   * 특정 페이지로 스크롤 (PDF.js API 사용)
   */
  const scrollToPage = (pageNumber: number) => {
    if (!_iframeRef) return;
    try {
      const pdfApp = (_iframeRef.contentWindow as any)?.PDFViewerApplication;
      if (pdfApp?.page !== undefined) {
        pdfApp.page = pageNumber;
      }
    } catch (err) {
      console.warn("[usePdfJsOverlay] 페이지 이동 실패:", err);
    }
  };

  /**
   * 리소스 정리
   */
  const detach = () => {
    if (_pollInterval) {
      clearInterval(_pollInterval);
      _pollInterval = null;
    }

    if (_scrollHandler && _iframeRef) {
      try {
        const iframeDoc = _iframeRef.contentDocument;
        const viewerContainer = iframeDoc?.getElementById("viewerContainer");
        viewerContainer?.removeEventListener("scroll", _scrollHandler);
      } catch {
        // iframe이 이미 해제된 경우
      }
      _scrollHandler = null;
    }

    if (_resizeObserver) {
      _resizeObserver.disconnect();
      _resizeObserver = null;
    }

    _iframeRef = null;
    iframeReady.value = false;
    pageInfoCache.value.clear();
    visiblePages.value = [];
  };

  // 컴포넌트 언마운트 시 정리
  onBeforeUnmount(() => {
    detach();
  });

  return {
    // 상태
    iframeReady,
    currentScale,
    visiblePages,
    pageInfoCache,
    scrollTop,
    scrollLeft,
    viewerHeight,
    viewerWidth,

    // 메서드
    attachToIframe,
    refreshPageInfo,
    bboxToOverlayRect,
    scrollToPage,
    detach,
  };
};
