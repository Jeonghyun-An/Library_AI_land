// frontend/composables/usePdfJsOverlay.ts
/**
 * PDF.js iframe과 소통하여 하이라이트 오버레이를 관리하는 Composable
 *
 * 핵심 원리:
 * 1. PDF.js viewer iframe 내부의 .page[data-page-number] 요소들의 위치/크기를 추적
 * 2. bbox_info의 PDF pt 좌표 → iframe 기준 절대 좌표로 변환
 * 3. iframe 위에 절대 위치 div로 하이라이트를 표시
 */

import { ref, onBeforeUnmount } from "vue";

// ==================== 타입 정의 ====================

export interface PdfJsPageInfo {
  pageNumber: number;
  /**
   * canvasWrapper의 iframe 뷰포트 기준 위치
   * (getBoundingClientRect 사용 — 가장 정확)
   */
  canvasRect: DOMRect | null;
  /** PDF 원본 크기 (pt, 72DPI 기준) — viewport.viewBox에서 추출 */
  viewportWidth: number;
  viewportHeight: number;
  /** 현재 PDF.js 줌 스케일 */
  scale: number;
}

export interface OverlayRect {
  /** 오버레이 루트(= pdf_viewer_area) 기준 CSS 좌표 */
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
  // 상태
  const iframeReady = ref(false);
  const currentScale = ref(1.0);
  const visiblePages = ref<number[]>([]);
  const pageInfoCache = ref<Map<number, PdfJsPageInfo>>(new Map());

  // cleanup용
  let _scrollHandler: (() => void) | null = null;
  let _resizeObserver: ResizeObserver | null = null;
  let _pollInterval: ReturnType<typeof setInterval> | null = null;
  let _iframeRef: HTMLIFrameElement | null = null;
  let _onUpdateCallback: (() => void) | null = null;

  /**
   * iframe이 로드된 후 PDF.js와 연결
   */
  const attachToIframe = (
    iframe: HTMLIFrameElement,
    onUpdate?: () => void,
  ): Promise<boolean> => {
    return new Promise((resolve) => {
      _iframeRef = iframe;
      _onUpdateCallback = onUpdate || null;

      const tryAttach = () => {
        try {
          const iframeDoc =
            iframe.contentDocument || iframe.contentWindow?.document;
          if (!iframeDoc) return false;

          const viewerContainer = iframeDoc.getElementById("viewerContainer");
          if (!viewerContainer) return false;

          const pdfApp = (iframe.contentWindow as any)?.PDFViewerApplication;
          if (!pdfApp) return false;

          // PDF 로드 여부 확인 - 페이지가 하나라도 렌더링되었는지
          const pages = iframeDoc.querySelectorAll(".page[data-page-number]");
          if (pages.length === 0) return false;

          iframeReady.value = true;

          // ────── 스크롤 이벤트 ──────
          _scrollHandler = () => {
            refreshPageInfo();
            _onUpdateCallback?.();
          };
          viewerContainer.addEventListener("scroll", _scrollHandler, {
            passive: true,
          });

          // ────── ResizeObserver (줌 변경 감지) ──────
          const viewer = iframeDoc.getElementById("viewer");
          if (viewer) {
            _resizeObserver = new ResizeObserver(() => {
              refreshPageInfo();
              _onUpdateCallback?.();
            });
            _resizeObserver.observe(viewer);
          }

          // ────── PDF.js 이벤트 ──────
          if (pdfApp.eventBus) {
            pdfApp.eventBus.on("scalechanging", () => {
              setTimeout(() => {
                refreshPageInfo();
                _onUpdateCallback?.();
              }, 150);
            });

            pdfApp.eventBus.on("pagechanging", () => {
              refreshPageInfo();
              _onUpdateCallback?.();
            });

            pdfApp.eventBus.on("pagesloaded", () => {
              setTimeout(() => {
                refreshPageInfo();
                _onUpdateCallback?.();
              }, 200);
            });

            // 페이지 렌더링 완료 (개별 페이지)
            pdfApp.eventBus.on("pagerendered", () => {
              refreshPageInfo();
              _onUpdateCallback?.();
            });
          }

          // 초기 수집
          refreshPageInfo();

          return true;
        } catch (err) {
          console.warn("[usePdfJsOverlay] iframe 접근 실패:", err);
          return false;
        }
      };

      if (tryAttach()) {
        resolve(true);
        return;
      }

      // 폴링으로 재시도 (최대 15초)
      let retryCount = 0;
      const maxRetries = 75;
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
   * 모든 페이지의 실시간 위치/크기 정보 갱신
   *
   * 핵심: getBoundingClientRect()를 사용해서
   *       iframe 뷰포트 기준의 정확한 위치를 가져옴.
   *       toolbar, border, scroll 모두 자동 반영!
   */
  const refreshPageInfo = () => {
    if (!_iframeRef) return;

    try {
      const iframeDoc = _iframeRef.contentDocument;
      if (!iframeDoc) return;

      const pages = iframeDoc.querySelectorAll(".page[data-page-number]");
      const newCache = new Map<number, PdfJsPageInfo>();

      const pdfApp = (_iframeRef.contentWindow as any)?.PDFViewerApplication;

      pages.forEach((pageEl) => {
        const pageNum = parseInt(
          pageEl.getAttribute("data-page-number") || "0",
        );
        if (pageNum <= 0) return;

        // canvasWrapper가 실제 렌더링 영역 (page div의 border 내부)
        const canvasWrapper = pageEl.querySelector(
          ".canvasWrapper",
        ) as HTMLElement;
        const targetEl = canvasWrapper || (pageEl as HTMLElement);

        // getBoundingClientRect는 iframe 뷰포트 기준 좌표를 반환
        // → toolbar, border, margin, scroll 모두 자동 반영됨!
        const canvasRect = targetEl.getBoundingClientRect();

        // PDF 원본 크기 (pt, 72DPI)
        let viewportWidth = 595; // A4 기본값
        let viewportHeight = 842;
        let scale = 1.0;

        try {
          if (pdfApp?.pdfViewer?._pages?.[pageNum - 1]) {
            const pdfPageView = pdfApp.pdfViewer._pages[pageNum - 1];
            if (pdfPageView.viewport) {
              const vp = pdfPageView.viewport;
              // viewBox는 [x, y, width, height] 형태의 원본 PDF 크기
              if (vp.viewBox && vp.viewBox.length >= 4) {
                viewportWidth = vp.viewBox[2] - vp.viewBox[0];
                viewportHeight = vp.viewBox[3] - vp.viewBox[1];
              } else {
                // fallback: scale로 역산
                viewportWidth = vp.width / vp.scale;
                viewportHeight = vp.height / vp.scale;
              }
              scale = vp.scale || 1.0;
            }
          }
        } catch {
          // fallback 사용
        }

        currentScale.value = scale;

        newCache.set(pageNum, {
          pageNumber: pageNum,
          canvasRect,
          viewportWidth,
          viewportHeight,
          scale,
        });
      });

      pageInfoCache.value = newCache;

      // 보이는 페이지 갱신
      _updateVisiblePages();
    } catch (err) {
      // iframe이 해제된 경우 등
    }
  };

  /**
   * 현재 보이는 페이지 번호 목록 갱신
   * (iframe 뷰포트 내에 보이는 페이지)
   */
  const _updateVisiblePages = () => {
    if (!_iframeRef) return;

    try {
      const iframeDoc = _iframeRef.contentDocument;
      if (!iframeDoc) return;

      const viewerContainer = iframeDoc.getElementById("viewerContainer");
      if (!viewerContainer) return;

      const containerRect = viewerContainer.getBoundingClientRect();

      const visible: number[] = [];
      pageInfoCache.value.forEach((info, pageNum) => {
        if (!info.canvasRect) return;
        const cr = info.canvasRect;
        // 페이지가 viewerContainer 뷰포트와 겹치는지
        if (cr.bottom > containerRect.top && cr.top < containerRect.bottom) {
          visible.push(pageNum);
        }
      });

      visiblePages.value = visible.sort((a, b) => a - b);
    } catch {
      // ignore
    }
  };

  /**
   * bbox (PDF pt 좌표) → 오버레이 rect (iframe 뷰포트 기준 px 좌표) 변환
   *
   * 좌표 변환 과정:
   *   1. canvasRect = canvasWrapper의 iframe 뷰포트 기준 getBoundingClientRect
   *   2. scaleX = canvasRect.width / viewportWidth(pt)
   *   3. localX = bbox.x0 * scaleX   (canvasWrapper 내 로컬 좌표)
   *   4. 최종 left = canvasRect.left + localX
   *
   * canvasRect.left/top은 getBoundingClientRect에서 오므로
   * 스크롤, toolbar 높이, border, margin 등이 모두 자동 반영!
   */
  const bboxToOverlayRect = (
    bbox: {
      page: number;
      page_index?: number; // 0-based (optional)
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
    const pageNumber =
      typeof bbox.page === "number" && bbox.page > 0
        ? bbox.page
        : typeof bbox.page_index === "number" && bbox.page_index >= 0
          ? bbox.page_index + 1
          : 0;

    const pageInfo = pageInfoCache.value.get(pageNumber);
    if (!pageInfo || !pageInfo.canvasRect) return null;

    const cr = pageInfo.canvasRect;

    // PDF pt → canvas px 스케일
    const scaleX = cr.width / pageInfo.viewportWidth;
    const scaleY = cr.height / pageInfo.viewportHeight;

    // bbox의 canvas 내 로컬 좌표
    const localLeft = bbox.x0 * scaleX;
    const localTop = bbox.y0 * scaleY;
    const localWidth = (bbox.x1 - bbox.x0) * scaleX;
    const localHeight = (bbox.y1 - bbox.y0) * scaleY;

    // iframe 뷰포트 기준 최종 좌표
    // cr.left/top은 getBoundingClientRect → 스크롤/toolbar/border 모두 반영됨
    const absLeft = cr.left + localLeft;
    const absTop = cr.top + localTop;

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
      pageNumber,
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
    _onUpdateCallback = null;
    iframeReady.value = false;
    pageInfoCache.value.clear();
    visiblePages.value = [];
  };

  onBeforeUnmount(() => {
    detach();
  });

  return {
    // 상태
    iframeReady,
    currentScale,
    visiblePages,
    pageInfoCache,

    // 메서드
    attachToIframe,
    refreshPageInfo,
    bboxToOverlayRect,
    scrollToPage,
    detach,
  };
};
