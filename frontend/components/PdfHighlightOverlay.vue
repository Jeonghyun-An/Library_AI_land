<!-- frontend/components/PdfHighlightOverlay.vue -->
<!--
  PDF.js iframe 위에 bbox 하이라이트를 표시하는 오버레이 컴포넌트
   - PDF.js의 페이지 위치/크기 정보를 활용하여 bbox 좌표를 오버레이 좌표로 변환
   - 스크롤/줌 시 자동으로 하이라이트 위치 갱신
   - 검색 결과의 유사도에 따라 색상/투명도 조절
   - 클릭 시 해당 검색 결과 정보 emit
-->
<template>
  <div class="pdf_overlay_root" ref="overlayRoot">
    <!-- 하이라이트 오버레이 레이어 (iframe 위에 겹침) -->
    <div
      v-if="iframeReady && overlayRects.length > 0"
      class="pdf_overlay_layer"
      ref="overlayLayer"
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

    <!-- 연결 상태 표시 (디버그용, 운영 시 숨김 가능) -->
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
  currentScale,
  visiblePages,
  pageInfoCache,
  scrollTop,
  scrollLeft,
  attachToIframe,
  bboxToOverlayRect,
  scrollToPage,
  detach,
} = usePdfJsOverlay();

// ==================== Refs ====================
const overlayRoot = ref<HTMLDivElement | null>(null);
const overlayLayer = ref<HTMLDivElement | null>(null);
const hoveredIdx = ref<number | null>(null);

// 오버레이 갱신 트리거 (스크롤/줌 시마다 증가)
const updateTrigger = ref(0);

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

    // bbox 유효성 검사
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
 * scrollTop/scrollLeft/updateTrigger가 바뀔 때마다 재계산
 */
const overlayRects = computed<OverlayRect[]>(() => {
  // 의존성 트리거
  const _ = updateTrigger.value;
  const _st = scrollTop.value;
  const _sl = scrollLeft.value;

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

      // 뷰포트 밖은 스킵 (여유 100px)
      if (
        rect.top + rect.height < -100 ||
        rect.top > (overlayRoot.value?.clientHeight || 800) + 100
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

  // iframe 로드 완료 대기
  const onLoad = async () => {
    // PDF.js 초기화 시간 대기
    await new Promise((r) => setTimeout(r, 500));

    const success = await attachToIframe(iframe, () => {
      // 스크롤/줌 변경 콜백 → 오버레이 갱신
      updateTrigger.value++;
    });

    if (success) {
      console.log(`[PdfHighlightOverlay] iframe '${props.iframeId}' 연결 성공`);
    }
  };

  // iframe이 이미 로드되었는지 확인
  if (iframe.contentDocument?.readyState === "complete") {
    await onLoad();
  } else {
    iframe.addEventListener("load", onLoad, { once: true });
    // 이미 로드 시작된 경우 대비
    setTimeout(onLoad, 1000);
  }
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
  () => {
    updateTrigger.value++;
  },
  { deep: true },
);

// ==================== 생명주기 ====================

onMounted(async () => {
  // DOM 렌더링 후 약간 대기
  await nextTick();
  await connectToIframe();
});

onBeforeUnmount(() => {
  detach();
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
  /* 기본 스타일 */
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
