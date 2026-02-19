<!-- frontend/components/PdfHighlightOverlay.vue -->
<!--
  PDF.js iframe 위에 bbox 하이라이트를 표시하는 오버레이 컴포넌트

    1. pdf_viewer_area에 position:relative가 있고, 이 컴포넌트는 그 안에 position:absolute
    2. iframe 내부 PDF.js의 canvasWrapper 위치를 getBoundingClientRect로 추적
    3. iframe 자체의 getBoundingClientRect를 빼서 → pdf_viewer_area 기준 좌표로 변환
    4. 스크롤/줌 시 자동으로 좌표 재계산
-->
<template>
  <div class="pdf_overlay_root" ref="overlayRoot">
    <!-- 하이라이트 오버레이 레이어 (iframe 위에 겹침) -->
    <div
      v-if="iframeReady && overlayRects.length > 0"
      class="pdf_overlay_layer"
    >
      <div
        v-for="(rect, idx) in overlayRects"
        :key="`hl-${rect.resultIndex}-${rect.pageNumber}-${idx}`"
        :data-highlight-result="rect.resultIndex"
        :style="{
          left: rect.left + 'px',
          top: rect.top + 'px',
          width: rect.width + 'px',
          height: rect.height + 'px',
        }"
        :class="[
          'pdf_overlay_rect',
          `pdf_overlay_rect_${rect.level}`,
          {
            pdf_overlay_rect_active: rect.resultIndex === activeResultIndex,
          },
        ]"
        @click.stop="onRectClick(rect)"
        @mouseenter="hoveredIdx = idx"
        @mouseleave="hoveredIdx = null"
      >
        <!-- 툴팁 -->
        <div v-if="hoveredIdx === idx" class="pdf_overlay_tooltip">
          <strong>{{ rect.articleLabel || "조항" }}</strong>
          <span class="pdf_overlay_tooltip_score">
            {{ Math.round(rect.score * 100) }}%
          </span>
          <p v-if="rect.text">
            {{ rect.text.substring(0, 100)
            }}{{ rect.text.length > 100 ? "..." : "" }}
          </p>
        </div>
      </div>
    </div>

    <!-- 연결 상태 표시 -->
    <div v-if="!iframeReady && hasResults" class="pdf_overlay_status">
      <div class="pdf_overlay_status_dot"></div>
      PDF 연결 중...
    </div>
  </div>
</template>

<script setup lang="ts">
import {
  ref,
  computed,
  watch,
  onMounted,
  onBeforeUnmount,
  nextTick,
} from "vue";
import {
  usePdfJsOverlay,
  type OverlayRect,
} from "~/composables/usePdfJsOverlay";

// ==================== Props ====================
interface Props {
  /** PDF.js iframe의 DOM id */
  iframeId: string;
  /** 검색 결과 배열 (bbox_info 포함) */
  searchResults?: any[];
  /** 현재 활성화된 결과 인덱스 */
  activeResultIndex?: number | null;
}

const props = withDefaults(defineProps<Props>(), {
  searchResults: () => [],
  activeResultIndex: null,
});

// ==================== Emits ====================
const emit = defineEmits<{
  (e: "highlight-click", result: any, rectInfo: OverlayRect): void;
}>();

// ==================== Composable ====================
const {
  iframeReady,
  visiblePages,
  attachToIframe,
  bboxToOverlayRect,
  detach,
  refreshPageInfo,
} = usePdfJsOverlay();

// ==================== Refs ====================
const overlayRoot = ref<HTMLDivElement | null>(null);
const hoveredIdx = ref<number | null>(null);

// 오버레이 갱신 트리거 (스크롤/줌 시마다 증가)
const updateTrigger = ref(0);

// iframe의 뷰포트 기준 오프셋 (좌표 보정용)
const iframeOffsetX = ref(0);
const iframeOffsetY = ref(0);

// ==================== Computed ====================

const hasResults = computed(() => {
  return (props.searchResults?.length || 0) > 0;
});

/**
 * 검색 결과에서 유효한 bbox를 가진 하이라이트 데이터 추출
 */
const highlightData = computed(() => {
  if (!props.searchResults || props.searchResults.length === 0) return [];

  const data: Array<{
    bboxList: Array<{
      page: number;
      x0: number;
      y0: number;
      x1: number;
      y1: number;
      text: string;
    }>;
    score: number;
    displayText: string;
    articleLabel: string;
    resultIndex: number;
  }> = [];

  props.searchResults.forEach((result, index) => {
    const bboxInfoRaw = result.bbox_info || [];
    if (bboxInfoRaw.length === 0) return;

    const validBboxes = bboxInfoRaw.filter(
      (b: any) =>
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
      result.display_path ||
      (result.structure?.article_number
        ? `${result.structure.article_number}조`
        : "") ||
      "";

    data.push({
      bboxList: validBboxes,
      score: result.score || result.display_score || 0,
      displayText: displayText.substring(0, 200),
      articleLabel,
      resultIndex: index,
    });
  });

  return data;
});

/**
 * 현재 보이는 페이지에 해당하는 오버레이 사각형 목록
 *
 * 좌표 흐름:
 *   bboxToOverlayRect → iframe 뷰포트 기준 좌표
 *   - iframeOffsetX/Y 보정 → overlayRoot(pdf_viewer_area) 기준 좌표
 */
const overlayRects = computed<OverlayRect[]>(() => {
  // 의존성 트리거
  const _trigger = updateTrigger.value;

  if (!iframeReady.value || highlightData.value.length === 0) return [];

  const rects: OverlayRect[] = [];
  const visible = visiblePages.value;

  // 성능: 보이는 페이지 ± 1 범위만 계산
  const renderPages = new Set<number>();
  for (const p of visible) {
    renderPages.add(p - 1);
    renderPages.add(p);
    renderPages.add(p + 1);
  }

  const rootHeight = overlayRoot.value?.clientHeight || 800;
  const rootWidth = overlayRoot.value?.clientWidth || 600;

  for (const hlData of highlightData.value) {
    for (const bbox of hlData.bboxList) {
      if (!renderPages.has(bbox.page)) continue;

      const rect = bboxToOverlayRect(bbox, {
        score: hlData.score,
        text: hlData.displayText,
        articleLabel: hlData.articleLabel,
        resultIndex: hlData.resultIndex,
      });

      if (!rect) continue;

      // ★ 핵심 보정: iframe 뷰포트 좌표 → overlayRoot 기준 좌표
      // bboxToOverlayRect가 반환하는 좌표는 iframe 내부의 getBoundingClientRect 기준
      // 이를 overlayRoot(= pdf_viewer_area) 기준으로 변환
      rect.left = rect.left + iframeOffsetX.value;
      rect.top = rect.top + iframeOffsetY.value;

      // 뷰포트 밖은 스킵 (여유 50px)
      if (
        rect.top + rect.height < -50 ||
        rect.top > rootHeight + 50 ||
        rect.left + rect.width < -50 ||
        rect.left > rootWidth + 50
      ) {
        continue;
      }

      // 너무 작은 영역은 스킵
      if (rect.width < 3 || rect.height < 3) continue;

      rects.push(rect);
    }
  }

  return rects;
});

// ==================== 메서드 ====================

/**
 * iframe을 찾아서 연결
 */
async function connectToIframe() {
  const iframe = document.getElementById(
    props.iframeId,
  ) as HTMLIFrameElement | null;
  if (!iframe) {
    console.warn(
      `[PdfHighlightOverlay] iframe '${props.iframeId}' 를 찾을 수 없습니다.`,
    );
    return;
  }

  // iframe의 overlayRoot 기준 오프셋 계산
  updateIframeOffset(iframe);

  const onLoad = async () => {
    // PDF.js 초기화 시간 대기
    await new Promise((r) => setTimeout(r, 500));

    // iframe 오프셋 재계산
    updateIframeOffset(iframe);

    const success = await attachToIframe(iframe, () => {
      // 스크롤/줌 변경 콜백 → 오버레이 갱신
      updateTrigger.value++;
    });

    if (success) {
      console.log(`[PdfHighlightOverlay] iframe '${props.iframeId}' 연결 성공`);
    }
  };

  if (iframe.contentDocument?.readyState === "complete") {
    await onLoad();
  } else {
    iframe.addEventListener("load", onLoad, { once: true });
    // 이미 로드 시작된 경우 대비
    setTimeout(onLoad, 1500);
  }
}

/**
 * iframe의 overlayRoot 기준 오프셋 계산
 *
 * iframe 내부의 getBoundingClientRect는 iframe 뷰포트 기준이므로,
 * 오버레이 div의 기준점(pdf_viewer_area)과의 차이를 계산
 *
 * iframe.getBoundingClientRect → 외부 문서 기준 iframe 위치
 * overlayRoot.getBoundingClientRect → 외부 문서 기준 오버레이 위치
 * → 둘의 차이 = iframe 내부 좌표를 overlayRoot 좌표로 변환할 때 더해야 할 값
 */
function updateIframeOffset(iframe?: HTMLIFrameElement | null) {
  const iframeEl =
    iframe ||
    (document.getElementById(props.iframeId) as HTMLIFrameElement | null);
  if (!iframeEl || !overlayRoot.value) return;

  const iframeRect = iframeEl.getBoundingClientRect();
  const rootRect = overlayRoot.value.getBoundingClientRect();

  // iframe이 overlayRoot의 (0,0) 기준으로 어디에 있는지
  iframeOffsetX.value = iframeRect.left - rootRect.left;
  iframeOffsetY.value = iframeRect.top - rootRect.top;
}

/**
 * 하이라이트 rect 클릭
 */
function onRectClick(rect: OverlayRect) {
  const result = props.searchResults?.[rect.resultIndex];
  if (result) {
    emit("highlight-click", result, rect);
  }
}

// ==================== Watch ====================

// iframe id 변경 → 재연결
watch(
  () => props.iframeId,
  async () => {
    detach();
    await nextTick();
    await connectToIframe();
  },
);

// searchResults 변경 → 오버레이 갱신
watch(
  () => props.searchResults,
  async () => {
    // 검색 결과 변경 시 iframe 재연결 시도 (새 PDF 로드 가능성)
    await nextTick();

    // iframe offset 재계산
    updateIframeOffset();

    // 이미 연결된 상태면 페이지 정보만 갱신
    if (iframeReady.value) {
      refreshPageInfo();
    }

    updateTrigger.value++;
  },
  { deep: true },
);

// ==================== 생명주기 ====================

// iframe src 변경 감지를 위한 MutationObserver
let _srcObserver: MutationObserver | null = null;

onMounted(async () => {
  await nextTick();
  await connectToIframe();

  // iframe의 src 변경을 감지해서 재연결
  const iframe = document.getElementById(props.iframeId);
  if (iframe) {
    _srcObserver = new MutationObserver((mutations) => {
      for (const m of mutations) {
        if (m.type === "attributes" && m.attributeName === "src") {
          // src 변경됨 → 재연결
          detach();
          setTimeout(() => connectToIframe(), 1000);
          break;
        }
      }
    });
    _srcObserver.observe(iframe, {
      attributes: true,
      attributeFilter: ["src"],
    });
  }

  // 윈도우 리사이즈 시 오프셋 재계산
  window.addEventListener("resize", () => updateIframeOffset());
});

onBeforeUnmount(() => {
  detach();
  if (_srcObserver) {
    _srcObserver.disconnect();
    _srcObserver = null;
  }
  window.removeEventListener("resize", () => updateIframeOffset());
});
</script>

<style scoped>
/* ==================== 오버레이 루트 ==================== */
.pdf_overlay_root {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  /* iframe 클릭 가능하도록 이벤트 통과 */
  pointer-events: none;
  overflow: hidden;
  z-index: 10;
}

/* ==================== 오버레이 레이어 ==================== */
.pdf_overlay_layer {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
}

/* ==================== 하이라이트 사각형 ==================== */
.pdf_overlay_rect {
  position: absolute;
  border-radius: 2px;
  cursor: pointer;
  /* 하이라이트 rect만 클릭 가능 */
  pointer-events: auto;
  transition:
    opacity 0.15s ease,
    box-shadow 0.15s ease;
  border: 2px solid transparent;
  box-sizing: border-box;
}

/* 유사도 등급별 색상 */
.pdf_overlay_rect_high {
  background-color: rgba(37, 99, 235, 0.18);
  border-color: rgba(37, 99, 235, 0.5);
}

.pdf_overlay_rect_high:hover {
  background-color: rgba(37, 99, 235, 0.3);
  box-shadow: 0 0 8px rgba(37, 99, 235, 0.4);
}

.pdf_overlay_rect_medium {
  background-color: rgba(234, 179, 8, 0.18);
  border-color: rgba(234, 179, 8, 0.5);
}

.pdf_overlay_rect_medium:hover {
  background-color: rgba(234, 179, 8, 0.3);
  box-shadow: 0 0 8px rgba(234, 179, 8, 0.4);
}

.pdf_overlay_rect_low {
  background-color: rgba(107, 114, 128, 0.12);
  border-color: rgba(107, 114, 128, 0.35);
}

.pdf_overlay_rect_low:hover {
  background-color: rgba(107, 114, 128, 0.25);
  box-shadow: 0 0 6px rgba(107, 114, 128, 0.3);
}

/* 활성 하이라이트 */
.pdf_overlay_rect_active {
  border-width: 3px;
  z-index: 5;
}

.pdf_overlay_rect_active.pdf_overlay_rect_high {
  background-color: rgba(37, 99, 235, 0.3);
  border-color: rgba(37, 99, 235, 0.8);
  box-shadow: 0 0 12px rgba(37, 99, 235, 0.5);
}

.pdf_overlay_rect_active.pdf_overlay_rect_medium {
  background-color: rgba(234, 179, 8, 0.3);
  border-color: rgba(234, 179, 8, 0.8);
  box-shadow: 0 0 12px rgba(234, 179, 8, 0.5);
}

.pdf_overlay_rect_active.pdf_overlay_rect_low {
  background-color: rgba(107, 114, 128, 0.25);
  border-color: rgba(107, 114, 128, 0.7);
  box-shadow: 0 0 10px rgba(107, 114, 128, 0.4);
}

/* ==================== 툴팁 ==================== */
.pdf_overlay_tooltip {
  position: absolute;
  bottom: calc(100% + 8px);
  left: 50%;
  transform: translateX(-50%);
  background: rgba(15, 23, 42, 0.95);
  color: #f1f5f9;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.4;
  white-space: nowrap;
  max-width: 320px;
  z-index: 100;
  pointer-events: none;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.pdf_overlay_tooltip::after {
  content: "";
  position: absolute;
  top: 100%;
  left: 50%;
  margin-left: -5px;
  border-width: 5px;
  border-style: solid;
  border-color: rgba(15, 23, 42, 0.95) transparent transparent transparent;
}

.pdf_overlay_tooltip strong {
  color: #93c5fd;
  margin-right: 6px;
}

.pdf_overlay_tooltip_score {
  background: rgba(37, 99, 235, 0.3);
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 600;
}

.pdf_overlay_tooltip p {
  margin: 4px 0 0;
  white-space: normal;
  word-break: break-word;
  color: #cbd5e1;
  font-size: 11px;
}

/* ==================== 연결 상태 ==================== */
.pdf_overlay_status {
  position: absolute;
  top: 8px;
  right: 8px;
  display: flex;
  align-items: center;
  gap: 6px;
  background: rgba(0, 0, 0, 0.6);
  color: #fbbf24;
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 11px;
  pointer-events: none;
  z-index: 20;
}

.pdf_overlay_status_dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #fbbf24;
  animation: pdf_overlay_pulse 1.5s ease-in-out infinite;
}

@keyframes pdf_overlay_pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.3;
  }
}
</style>
