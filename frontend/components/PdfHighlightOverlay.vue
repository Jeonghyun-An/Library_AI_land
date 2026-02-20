<!-- frontend/components/PdfHighlightOverlay.vue -->
<!--
  PDF.js iframe 위에 bbox 하이라이트를 표시하는 오버레이 컴포넌트 (v3.8)

  2중 레이어:
    Layer 1 (article): article_bbox_info → 조 전체 영역, 연한 노란 배경
    Layer 2 (para):    bbox_info         → 해당 항 영역, 진한 주황 강조

  항 없는 단문 조의 경우 bbox_info == article_bbox_info이므로
  두 레이어가 겹쳐 단일 강조처럼 보임.
-->
<template>
  <div class="pdf_overlay_root" ref="overlayRoot">
    <div
      v-if="
        iframeReady && (articleRects.length > 0 || paragraphRects.length > 0)
      "
      class="pdf_overlay_layer"
    >
      <!-- Layer 1: 조 전체 배경 (연한 노란) -->
      <div
        v-for="(rect, idx) in articleRects"
        :key="`art-${rect.resultIndex}-${rect.pageNumber}-${idx}`"
        :style="{
          left: rect.left + 'px',
          top: rect.top + 'px',
          width: rect.width + 'px',
          height: rect.height + 'px',
        }"
        :class="[
          'pdf_overlay_rect',
          'pdf_overlay_rect_article',
          { pdf_overlay_rect_active: rect.resultIndex === activeResultIndex },
        ]"
        @click.stop="onRectClick(rect)"
      />

      <!-- Layer 2: 항 강조 (진한 주황) -->
      <div
        v-for="(rect, idx) in paragraphRects"
        :key="`para-${rect.resultIndex}-${rect.pageNumber}-${idx}`"
        :style="{
          left: rect.left + 'px',
          top: rect.top + 'px',
          width: rect.width + 'px',
          height: rect.height + 'px',
        }"
        :class="[
          'pdf_overlay_rect',
          'pdf_overlay_rect_paragraph',
          { pdf_overlay_rect_active: rect.resultIndex === activeResultIndex },
        ]"
        @click.stop="onRectClick(rect)"
        @mouseenter="hoveredIdx = `para-${idx}`"
        @mouseleave="hoveredIdx = null"
      >
        <!-- 툴팁은 항 레이어에만 -->
        <div v-if="hoveredIdx === `para-${idx}`" class="pdf_overlay_tooltip">
          <strong>{{ rect.articleLabel || "조항" }}</strong>
          <span
            v-if="rect.isParagraphLevel"
            class="pdf_overlay_tooltip_tag para"
            >항</span
          >
          <span v-else class="pdf_overlay_tooltip_tag article">단문 조</span>
          <span class="pdf_overlay_tooltip_score"
            >{{ Math.round(rect.score * 100) }}%</span
          >
          <p v-if="rect.text">
            {{ rect.text.substring(0, 120)
            }}{{ rect.text.length > 120 ? "..." : "" }}
          </p>
        </div>
      </div>
    </div>

    <!-- 연결 대기 표시 -->
    <div v-if="!iframeReady && hasResults" class="pdf_overlay_status">
      <div class="pdf_overlay_status_dot" />
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
  iframeId: string;
  searchResults?: any[];
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

// ==================== State ====================
const overlayRoot = ref<HTMLDivElement | null>(null);
const hoveredIdx = ref<string | null>(null);
const updateTrigger = ref(0);
const iframeOffsetX = ref(0);
const iframeOffsetY = ref(0);

// ==================== Computed ====================
const hasResults = computed(() => (props.searchResults?.length || 0) > 0);

/** 렌더링 대상 페이지 집합 (보이는 페이지 ± 1) */
const renderPages = computed<Set<number>>(() => {
  const s = new Set<number>();
  for (const p of visiblePages.value) {
    s.add(p - 1);
    s.add(p);
    s.add(p + 1);
  }
  return s;
});

/** 검색 결과 파싱 */
const highlightData = computed(() => {
  if (!props.searchResults?.length) return [];
  return props.searchResults
    .map((result, index) => {
      const isValid = (b: any) =>
        b && typeof b.page === "number" && b.x1 > b.x0 && b.y1 > b.y0;

      const paraBoxes = (result.bbox_info || []).filter(isValid);
      const articleBoxes = (result.article_bbox_info || []).filter(isValid);

      // article_bbox_info 없으면 bbox_info로 fallback (단문 조 또는 구버전 데이터)
      const effectiveArticleBoxes =
        articleBoxes.length > 0 ? articleBoxes : paraBoxes;

      // 항 있는지 여부 (structure.paragraph 또는 두 bbox가 다른 경우)
      const isParagraphLevel = Boolean(result.structure?.paragraph);

      const displayText =
        result.korean_text || result.english_text || result.search_text || "";
      const articleLabel =
        result.display_path ||
        (result.structure?.article_number
          ? `${result.structure.article_number}조`
          : "") ||
        "";

      return {
        paraBoxes,
        articleBoxes: effectiveArticleBoxes,
        isParagraphLevel,
        score: result.score || result.display_score || 0,
        displayText: displayText.substring(0, 200),
        articleLabel,
        resultIndex: index,
      };
    })
    .filter((d) => d.paraBoxes.length > 0 || d.articleBoxes.length > 0);
});

/** 공통 rect 변환 */
function toRect(
  bbox: any,
  meta: {
    score: number;
    text: string;
    articleLabel: string;
    resultIndex: number;
  },
  extra?: Record<string, any>,
): (OverlayRect & Record<string, any>) | null {
  const _t = updateTrigger.value; // 의존성 트리거
  const rect = bboxToOverlayRect(bbox, meta);
  if (!rect) return null;
  rect.left += iframeOffsetX.value;
  rect.top += iframeOffsetY.value;
  const rh = overlayRoot.value?.clientHeight || 800;
  const rw = overlayRoot.value?.clientWidth || 600;
  if (
    rect.top + rect.height < -50 ||
    rect.top > rh + 50 ||
    rect.left + rect.width < -50 ||
    rect.left > rw + 50 ||
    rect.width < 3 ||
    rect.height < 3
  )
    return null;
  return { ...rect, ...extra };
}

/** Layer 1: 조 전체 배경 */
const articleRects = computed(() => {
  const _t = updateTrigger.value;
  if (!iframeReady.value) return [];
  const rects: any[] = [];
  for (const d of highlightData.value) {
    for (const bbox of d.articleBoxes) {
      if (!renderPages.value.has(bbox.page)) continue;
      const r = toRect(bbox, {
        score: d.score,
        text: d.displayText,
        articleLabel: d.articleLabel,
        resultIndex: d.resultIndex,
      });
      if (r) rects.push(r);
    }
  }
  return rects;
});

/** Layer 2: 항 강조 */
const paragraphRects = computed(() => {
  const _t = updateTrigger.value;
  if (!iframeReady.value) return [];
  const rects: any[] = [];
  for (const d of highlightData.value) {
    for (const bbox of d.paraBoxes) {
      if (!renderPages.value.has(bbox.page)) continue;
      const r = toRect(
        bbox,
        {
          score: d.score,
          text: d.displayText,
          articleLabel: d.articleLabel,
          resultIndex: d.resultIndex,
        },
        { isParagraphLevel: d.isParagraphLevel },
      );
      if (r) rects.push(r);
    }
  }
  return rects;
});

// ==================== Methods ====================
async function connectToIframe() {
  const iframe = document.getElementById(
    props.iframeId,
  ) as HTMLIFrameElement | null;
  if (!iframe) {
    console.warn(`[PdfHighlightOverlay] iframe '${props.iframeId}' 없음`);
    return;
  }
  updateIframeOffset(iframe);

  const onLoad = async () => {
    await new Promise((r) => setTimeout(r, 500));
    updateIframeOffset(iframe);
    const ok = await attachToIframe(iframe, () => {
      updateTrigger.value++;
    });
    if (ok) console.log(`[PdfHighlightOverlay] '${props.iframeId}' 연결 성공`);
  };

  if (iframe.contentDocument?.readyState === "complete") {
    await onLoad();
  } else {
    iframe.addEventListener("load", onLoad, { once: true });
    setTimeout(onLoad, 1500);
  }
}

function updateIframeOffset(iframe?: HTMLIFrameElement | null) {
  const el =
    iframe ||
    (document.getElementById(props.iframeId) as HTMLIFrameElement | null);
  if (!el || !overlayRoot.value) return;
  const ir = el.getBoundingClientRect();
  const rr = overlayRoot.value.getBoundingClientRect();
  iframeOffsetX.value = ir.left - rr.left;
  iframeOffsetY.value = ir.top - rr.top;
}

function onRectClick(rect: OverlayRect) {
  const result = props.searchResults?.[rect.resultIndex];
  if (result) emit("highlight-click", result, rect);
}

// ==================== Watchers ====================
watch(
  () => props.searchResults,
  async () => {
    await nextTick();
    refreshPageInfo();
    updateTrigger.value++;
  },
  { deep: true },
);

watch(
  () => props.iframeId,
  async (newId) => {
    if (newId) {
      detach();
      await nextTick();
      await connectToIframe();
    }
  },
);

// ==================== Lifecycle ====================
onMounted(async () => {
  if (props.iframeId) await connectToIframe();
  window.addEventListener("resize", () => {
    updateIframeOffset();
    updateTrigger.value++;
  });
});
onBeforeUnmount(() => {
  detach();
});
</script>

<style scoped>
.pdf_overlay_root {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
  z-index: 10;
}

.pdf_overlay_layer {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.pdf_overlay_rect {
  position: absolute;
  border-radius: 2px;
  cursor: pointer;
  pointer-events: auto;
  transition:
    opacity 0.12s ease,
    box-shadow 0.12s ease;
  box-sizing: border-box;
}

/* ── Layer 1: 조 전체 배경 (연한 노란) ── */
.pdf_overlay_rect_article {
  background-color: rgba(253, 224, 71, 0.18);
  border: 1.5px solid rgba(202, 138, 4, 0.3);
  z-index: 1;
}
.pdf_overlay_rect_article:hover {
  background-color: rgba(253, 224, 71, 0.28);
}
.pdf_overlay_rect_article.pdf_overlay_rect_active {
  background-color: rgba(253, 224, 71, 0.28);
  border-color: rgba(202, 138, 4, 0.5);
  box-shadow: 0 0 8px rgba(202, 138, 4, 0.25);
}

/* ── Layer 2: 항 강조 (진한 주황) ── */
.pdf_overlay_rect_paragraph {
  background-color: rgba(249, 115, 22, 0.28);
  border: 2px solid rgba(234, 88, 12, 0.7);
  z-index: 2;
}
.pdf_overlay_rect_paragraph:hover {
  background-color: rgba(249, 115, 22, 0.42);
  box-shadow: 0 0 10px rgba(234, 88, 12, 0.4);
}
.pdf_overlay_rect_paragraph.pdf_overlay_rect_active {
  background-color: rgba(249, 115, 22, 0.45);
  border-color: rgba(234, 88, 12, 0.95);
  box-shadow: 0 0 14px rgba(234, 88, 12, 0.55);
}

/* ── 툴팁 ── */
.pdf_overlay_tooltip {
  position: absolute;
  bottom: calc(100% + 6px);
  left: 0;
  background: rgba(15, 23, 42, 0.95);
  color: #f1f5f9;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 12px;
  max-width: 280px;
  min-width: 140px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
  z-index: 100;
  pointer-events: none;
  line-height: 1.5;
}
.pdf_overlay_tooltip strong {
  display: block;
  font-size: 13px;
  margin-bottom: 4px;
  color: #fde68a;
}
.pdf_overlay_tooltip_tag {
  display: inline-block;
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 3px;
  margin-right: 5px;
  font-weight: 600;
  vertical-align: middle;
}
.pdf_overlay_tooltip_tag.para {
  background: rgba(249, 115, 22, 0.85);
  color: #fff;
}
.pdf_overlay_tooltip_tag.article {
  background: rgba(202, 138, 4, 0.75);
  color: #fff;
}
.pdf_overlay_tooltip_score {
  display: inline-block;
  background: rgba(99, 102, 241, 0.7);
  color: #fff;
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 3px;
  font-weight: 600;
}
.pdf_overlay_tooltip p {
  margin: 5px 0 0;
  font-size: 11px;
  color: #cbd5e1;
  line-height: 1.4;
}

/* ── 연결 대기 ── */
.pdf_overlay_status {
  position: absolute;
  bottom: 16px;
  right: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(15, 23, 42, 0.85);
  color: #94a3b8;
  padding: 6px 12px;
  border-radius: 20px;
  font-size: 12px;
  pointer-events: none;
}
.pdf_overlay_status_dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #f59e0b;
  animation: overlay_pulse 1.2s ease-in-out infinite;
}
@keyframes overlay_pulse {
  0%,
  100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.4;
    transform: scale(0.8);
  }
}
</style>
