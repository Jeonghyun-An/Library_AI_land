// frontend/composables/usePdfJsOverlay.ts
/**
 * v4.1 변경사항:
 * ─────────────────────────────────────────────────────────────
 * [버그픽스] 다음 페이지로 넘어가는 청크의 두 번째 페이지 bbox가
 *           페이지 전체(y0≈57, y1≈816)로 하이라이팅되는 문제 방어.
 *
 * bboxToOverlayRect() 내부에 "continuation page bbox" 감지 로직 추가:
 *   - bbox 목록에서 해당 bbox가 첫 번째가 아닌 경우(continuation page)
 *   - AND 해당 페이지의 height 비율(hRatio)이 CONTINUATION_MAX_H_RATIO 초과
 *   → y1을 페이지 하단 여백(FOOTER_MARGIN_RATIO) 기준으로 clamp
 *
 * 이 처리는 백엔드(v4.1 chunker)의 bbox clamp와 함께 동작하는 이중 방어선입니다.
 * 백엔드가 이미 올바른 y1을 내려보내면 이 로직은 아무런 영향을 미치지 않습니다.
 * ─────────────────────────────────────────────────────────────
 */
import { ref, onBeforeUnmount } from "vue";

export interface PdfJsPageInfo {
  pageNumber: number;
  canvasRect: DOMRect | null;
  viewportWidth: number;
  viewportHeight: number;
  scale: number;
}

export interface OverlayRect {
  left: number;
  top: number;
  width: number;
  height: number;
  pageNumber: number;
  score: number;
  text: string;
  articleLabel: string;
  resultIndex: number;
  level: "high" | "medium" | "low";
}

type BBox = {
  page: number;
  page_index?: number;
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  text?: string;
};

// ★ v4.1: continuation bbox 방어 상수
/**
 * continuation 페이지의 bbox height 비율이 이 값을 초과하면
 * 페이지 전체를 덮는 비정상 bbox로 간주하여 y1을 clamp한다.
 * (예: 0.80 → 페이지 높이의 80% 초과 시 clamp)
 */
const CONTINUATION_MAX_H_RATIO = 0.8;

/**
 * continuation bbox의 y1을 clamp할 때 사용하는 하단 여백 비율.
 * page_height * (1 - FOOTER_MARGIN_RATIO) 가 clamp 상한선.
 * (예: 0.06 → 페이지 하단 6% 여백 제외)
 */
const FOOTER_MARGIN_RATIO = 0.06;

export const usePdfJsOverlay = () => {
  const iframeReady = ref(false);
  const currentScale = ref(1.0);
  const visiblePages = ref<number[]>([]);
  const pageInfoCache = ref<Map<number, PdfJsPageInfo>>(new Map());

  let _scrollHandler: (() => void) | null = null;
  let _resizeObserver: ResizeObserver | null = null;
  let _pollInterval: ReturnType<typeof setInterval> | null = null;
  let _iframeRef: HTMLIFrameElement | null = null;
  let _onUpdateCallback: (() => void) | null = null;

  /**
   * 좌표계 설정
   *
   * PyMuPDF(fitz)는 top-left origin, y 아래로 증가 → PDF.js canvas와 동일
   * → flip 불필요. "pdf-bottom-left" = flip 스킵
   *
   * 만약 좌표가 PDF 원본 스펙(bottom-left origin)이라면 "pdf-bottom-left"로
   * 설정해도 flip을 안 하므로 틀리지만, PyMuPDF 기반 백엔드라면 이 설정이 맞음.
   *
   * ⚠️ "pymupdf-top-left"로 설정하면 y flip이 실행되어 좌표가 뒤집힘 → 사용 금지
   */
  const bboxCoordOrigin = ref<"pymupdf-top-left" | "pdf-bottom-left">(
    "pdf-bottom-left", // ← v3.8 수정: flip 제거
  );

  /**
   * full-page bbox 필터링 임계값
   * article_bbox_info는 조 전체를 덮으므로 threshold를 높게 설정
   * (조가 페이지 전체를 차지하는 경우도 정상 표시)
   *
   * paragraph(항) bbox는 1이면 절대 full-page가 아니므로 이 필터가 거의 안 걸림
   */
  const fullPageRatioThreshold = ref(0.99); // 99% 이상만 제거 (사실상 제거 안 함)

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

          const pages = iframeDoc.querySelectorAll(".page[data-page-number]");
          if (pages.length === 0) return false;

          iframeReady.value = true;

          _scrollHandler = () => {
            refreshPageInfo();
            _onUpdateCallback?.();
          };
          viewerContainer.addEventListener("scroll", _scrollHandler, {
            passive: true,
          });

          const viewer = iframeDoc.getElementById("viewer");
          if (viewer) {
            _resizeObserver = new ResizeObserver(() => {
              refreshPageInfo();
              _onUpdateCallback?.();
            });
            _resizeObserver.observe(viewer);
          }

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
            pdfApp.eventBus.on("pagerendered", () => {
              refreshPageInfo();
              _onUpdateCallback?.();
            });
          }

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

        const canvasWrapper = pageEl.querySelector(
          ".canvasWrapper",
        ) as HTMLElement;
        const targetEl = canvasWrapper || (pageEl as HTMLElement);
        const canvasRect = targetEl.getBoundingClientRect();

        let viewportWidth = 595;
        let viewportHeight = 842;
        let scale = 1.0;

        try {
          if (pdfApp?.pdfViewer?._pages?.[pageNum - 1]) {
            const pdfPageView = pdfApp.pdfViewer._pages[pageNum - 1];
            if (pdfPageView.viewport) {
              const vp = pdfPageView.viewport;
              if (vp.viewBox && vp.viewBox.length >= 4) {
                viewportWidth = vp.viewBox[2] - vp.viewBox[0];
                viewportHeight = vp.viewBox[3] - vp.viewBox[1];
              } else {
                viewportWidth = vp.width / vp.scale;
                viewportHeight = vp.height / vp.scale;
              }
              scale = vp.scale || 1.0;
            }
          }
        } catch {
          // ignore
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
      _updateVisiblePages();
    } catch {
      // ignore
    }
  };

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
        if (cr.bottom > containerRect.top && cr.top < containerRect.bottom) {
          visible.push(pageNum);
        }
      });
      visiblePages.value = visible.sort((a, b) => a - b);
    } catch {
      // ignore
    }
  };

  /** bbox 숫자 정상화 + 페이지 내부로 클램프 */
  function normalizeAndClampBBox(b: BBox, vw: number, vh: number): BBox | null {
    if (!b) return null;
    let x0 = Number(b.x0),
      y0 = Number(b.y0);
    let x1 = Number(b.x1),
      y1 = Number(b.y1);
    if (![x0, y0, x1, y1].every((v) => Number.isFinite(v))) return null;

    // 정렬
    const nx0 = Math.min(x0, x1),
      nx1 = Math.max(x0, x1);
    const ny0 = Math.min(y0, y1),
      ny1 = Math.max(y0, y1);

    // 클램프
    x0 = Math.max(0, Math.min(vw, nx0));
    x1 = Math.max(0, Math.min(vw, nx1));
    y0 = Math.max(0, Math.min(vh, ny0));
    y1 = Math.max(0, Math.min(vh, ny1));

    if (x1 - x0 < 1 || y1 - y0 < 1) return null;
    return { ...b, x0, y0, x1, y1 };
  }

  /**
   * ★ v4.1: continuation bbox 방어 clamp
   *
   * 청크가 두 페이지에 걸칠 때, 두 번째(continuation) 페이지의 bbox가
   * 페이지 전체를 커버하는 경우(백엔드 clamp 미적용 구 데이터 포함)를 감지하여
   * y1을 페이지 콘텐츠 하단으로 제한한다.
   *
   * @param b         - 현재 처리 중인 bbox (normalizeAndClampBBox 적용 후)
   * @param vh        - 페이지 viewport 높이 (pt 단위)
   * @param isContinuation - 이 bbox가 청크의 첫 번째 페이지가 아닌지 여부
   * @returns clamp된 BBox 또는 원본 그대로
   */
  function clampContinuationBBox(
    b: BBox,
    vh: number,
    isContinuation: boolean,
  ): BBox {
    if (!isContinuation) return b;

    const hRatio = (b.y1 - b.y0) / vh;
    if (hRatio <= CONTINUATION_MAX_H_RATIO) return b;

    // 비정상적으로 큰 bbox → y1을 페이지 하단 여백 기준으로 clamp
    const clampedY1 = vh * (1 - FOOTER_MARGIN_RATIO);
    if (clampedY1 <= b.y0) return b; // clamp 후 높이가 0이 되면 원본 유지

    return { ...b, y1: clampedY1 };
  }

  /**
   * BBox → OverlayRect 변환
   *
   * @param bbox              - 변환할 bbox
   * @param meta              - 점수/텍스트 등 메타
   * @param bboxListLength    - ★ v4.1: 이 청크의 bbox 리스트 전체 개수
   * @param bboxIndexInList   - ★ v4.1: 이 bbox가 리스트에서 몇 번째인지 (0-based)
   */
  const bboxToOverlayRect = (
    bbox: BBox,
    meta: {
      score: number;
      text: string;
      articleLabel: string;
      resultIndex: number;
    },
    bboxListLength: number = 1, // ★ v4.1
    bboxIndexInList: number = 0, // ★ v4.1
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
    const vw = pageInfo.viewportWidth;
    const vh = pageInfo.viewportHeight;

    // 1) bbox 정규화 + 클램프
    let nb = normalizeAndClampBBox(bbox, vw, vh);
    if (!nb) return null;

    // ★ v4.1: continuation 페이지 방어 clamp
    // 청크의 bbox 리스트에서 두 번째 이후 bbox는 continuation page로 간주
    const isContinuation = bboxListLength > 1 && bboxIndexInList > 0;
    nb = clampContinuationBBox(nb, vh, isContinuation);

    // 2) full-page 박스 필터링 (99% 이상만 제거 — 사실상 실제 full-page만)
    const wRatio = (nb.x1 - nb.x0) / vw;
    const hRatio = (nb.y1 - nb.y0) / vh;
    if (
      wRatio >= fullPageRatioThreshold.value &&
      hRatio >= fullPageRatioThreshold.value
    ) {
      return null;
    }

    // 3) pt → px 스케일
    const scaleX = cr.width / vw;
    const scaleY = cr.height / vh;

    // 4) y 좌표 처리
    // PyMuPDF(top-left, y↓) = PDF.js canvas(top-left, y↓) → flip 불필요
    // "pymupdf-top-left" 선택 시에만 flip 실행 (레거시 호환용)
    let y0 = nb.y0,
      y1 = nb.y1;
    if (bboxCoordOrigin.value === "pymupdf-top-left") {
      y0 = vh - nb.y1;
      y1 = vh - nb.y0;
    }

    // 5) canvas 내 로컬 좌표
    const localLeft = nb.x0 * scaleX;
    const localTop = y0 * scaleY;
    const localWidth = (nb.x1 - nb.x0) * scaleX;
    const localHeight = (y1 - y0) * scaleY;

    // 6) iframe 뷰포트 기준 최종 좌표
    const absLeft = cr.left + localLeft;
    const absTop = cr.top + localTop;

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

  const scrollToPage = (pageNumber: number) => {
    if (!_iframeRef) return;
    try {
      const pdfApp = (_iframeRef.contentWindow as any)?.PDFViewerApplication;
      if (pdfApp?.page !== undefined) pdfApp.page = pageNumber;
    } catch (err) {
      console.warn("[usePdfJsOverlay] 페이지 이동 실패:", err);
    }
  };

  const detach = () => {
    if (_pollInterval) {
      clearInterval(_pollInterval);
      _pollInterval = null;
    }
    if (_scrollHandler && _iframeRef) {
      try {
        const iframeDoc = _iframeRef.contentDocument;
        const vc = iframeDoc?.getElementById("viewerContainer");
        vc?.removeEventListener("scroll", _scrollHandler);
      } catch {
        /* ignore */
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

  onBeforeUnmount(() => detach());

  return {
    iframeReady,
    currentScale,
    visiblePages,
    pageInfoCache,
    bboxCoordOrigin,
    fullPageRatioThreshold,
    attachToIframe,
    refreshPageInfo,
    bboxToOverlayRect,
    scrollToPage,
    detach,
  };
};
