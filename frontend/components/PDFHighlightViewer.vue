<template>
  <div class="pdf_hl_viewer" ref="viewerRoot">
    <!-- 헤더 -->
    <div class="pdf_hl_header">
      <div class="pdf_hl_title">
        <h3>{{ title }}</h3>
        <span v-if="countryCode" class="pdf_hl_badge">{{ countryCode }}</span>
      </div>

      <!-- 페이지 네비게이션 -->
      <div class="pdf_hl_controls">
        <button
          @click="prevPage"
          :disabled="currentPage <= 1"
          class="pdf_hl_btn"
        >
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
          >
            <path d="M15 18l-6-6 6-6" />
          </svg>
        </button>
        <span class="pdf_hl_page_info"
          >{{ currentPage }} / {{ totalPages }}</span
        >
        <button
          @click="nextPage"
          :disabled="currentPage >= totalPages"
          class="pdf_hl_btn"
        >
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
          >
            <path d="M9 18l6-6-6-6" />
          </svg>
        </button>

        <!-- 하이라이트 페이지 점프 -->
        <template v-if="highlightedPageList.length > 0">
          <span class="pdf_hl_divider">|</span>
          <button
            v-for="hlPage in highlightedPageList"
            :key="hlPage"
            @click="goToPage(hlPage)"
            :class="['pdf_hl_page_jump', { active: currentPage === hlPage }]"
            :title="`하이라이트 페이지 ${hlPage}`"
          >
            {{ hlPage }}p
          </button>
        </template>
      </div>
    </div>

    <!-- 이미지 + 오버레이 영역 -->
    <div class="pdf_hl_canvas_wrap" ref="canvasWrap">
      <!-- 로딩 -->
      <div v-if="isPageLoading" class="pdf_hl_loading">
        <div class="pdf_hl_spinner"></div>
        <p>페이지 로딩 중...</p>
      </div>

      <!-- 에러 -->
      <div v-else-if="pageError" class="pdf_hl_error">
        <svg
          width="48"
          height="48"
          viewBox="0 0 24 24"
          fill="none"
          stroke="#ef4444"
          stroke-width="2"
        >
          <circle cx="12" cy="12" r="10" />
          <path d="M12 8v4m0 4h.01" />
        </svg>
        <p>{{ pageError }}</p>
      </div>

      <!-- 이미지 + 하이라이트 -->
      <div
        v-else
        class="pdf_hl_image_container"
        ref="imageContainer"
        :style="imageContainerStyle"
      >
        <img
          v-if="currentPageImageUrl"
          :src="currentPageImageUrl"
          class="pdf_hl_page_image"
          @load="onImageLoaded"
          @error="onImageError"
          ref="pageImage"
          draggable="false"
        />

        <!-- 하이라이트 오버레이 레이어 -->
        <div class="pdf_hl_overlay" v-if="currentPageRects.length > 0">
          <div
            v-for="(rect, idx) in currentPageRects"
            :key="idx"
            :data-highlight-result="rect.resultIndex"
            :style="{
              left: rect.left + 'px',
              top: rect.top + 'px',
              width: rect.width + 'px',
              height: rect.height + 'px',
            }"
            :class="[
              'pdf_hl_rect',
              `pdf_hl_rect_${rect.level}`,
              { pdf_hl_rect_active: rect.resultIndex === activeHighlightIndex },
            ]"
            @click="onRectClick(rect)"
            @mouseenter="hoveredRect = idx"
            @mouseleave="hoveredRect = null"
          >
            <!-- 툴팁 -->
            <div v-if="hoveredRect === idx" class="pdf_hl_tooltip">
              <strong>{{ rect.articleLabel }}</strong>
              <span class="pdf_hl_tooltip_score">
                {{ Math.round(rect.score * 100) }}%
              </span>
              <p>
                {{ rect.text.substring(0, 120)
                }}{{ rect.text.length > 120 ? "..." : "" }}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 하이라이트 목록 (하단) -->
    <div v-if="highlightDataList.length > 0" class="pdf_hl_sidebar">
      <h4>검색 결과 하이라이트 ({{ highlightDataList.length }}건)</h4>
      <div class="pdf_hl_list">
        <div
          v-for="(hl, index) in highlightDataList"
          :key="index"
          :class="[
            'pdf_hl_item',
            { active: activeHighlightIndex === hl.resultIndex },
          ]"
          @click="onHighlightItemClick(hl)"
        >
          <div class="pdf_hl_item_score" :class="`level_${getLevel(hl.score)}`">
            {{ Math.round(hl.score * 100) }}%
          </div>
          <div class="pdf_hl_item_info">
            <p class="pdf_hl_item_label">
              {{ hl.articleLabel || "(조항 미상)" }}
            </p>
            <p class="pdf_hl_item_text">
              {{ hl.displayText.substring(0, 80)
              }}{{ hl.displayText.length > 80 ? "..." : "" }}
            </p>
            <small>페이지 {{ hl.bboxList[0]?.page || "?" }}</small>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, nextTick } from "vue";
import { usePDFHighlight } from "~/composables/usePDFHighlight";
import type {
  HighlightData,
  HighlightRect,
} from "~/composables/usePDFHighlight";

// ==================== Props ====================
interface Props {
  /** 문서 ID (MinIO 저장 키) */
  docId: string;
  /** PDF 제목 */
  title: string;
  /** 국가 코드 */
  countryCode?: string;
  /** 검색 결과 배열 (bbox_info 포함) */
  searchResults?: any[];
  /** 초기 페이지 번호 */
  initialPage?: number;
  /** 이미지 DPI */
  dpi?: number;
  /** API 베이스 URL */
  apiBase?: string;
}

const props = withDefaults(defineProps<Props>(), {
  countryCode: "",
  searchResults: () => [],
  initialPage: 1,
  dpi: 150,
  apiBase: "",
});

// ==================== Emits ====================
const emit = defineEmits<{
  (e: "highlight-click", result: any): void;
  (e: "page-change", page: number): void;
}>();

// ==================== Composable ====================
const {
  highlights,
  currentPage,
  totalPages,
  activeHighlightIndex,
  highlightedPages,
  pageDimensionsCache,
  setAllPageDimensions,
  applyHighlightsFromResults,
  getHighlightRectsForPage,
  goToFirstHighlight,
  goToHighlight,
  clearHighlights,
  goToPage,
} = usePDFHighlight();

// ==================== Refs ====================
const viewerRoot = ref<HTMLDivElement | null>(null);
const canvasWrap = ref<HTMLDivElement | null>(null);
const imageContainer = ref<HTMLDivElement | null>(null);
const pageImage = ref<HTMLImageElement | null>(null);

const isPageLoading = ref(false);
const pageError = ref<string | null>(null);
const hoveredRect = ref<number | null>(null);

// 이미지 실제 표시 크기
const displayWidth = ref(0);
const displayHeight = ref(0);

// ==================== API Base ====================
const resolvedApiBase = computed(() => {
  if (props.apiBase) return props.apiBase;
  try {
    const config = useRuntimeConfig();
    const base = config.public.apiBase || "http://localhost:8000";
    // trailing slash 제거
    return base.replace(/\/+$/, "");
  } catch {
    return "http://localhost:8000";
  }
});

// ==================== Computed ====================

/** 현재 페이지 이미지 URL */
const currentPageImageUrl = computed(() => {
  if (!props.docId || currentPage.value < 1) return "";
  const base = resolvedApiBase.value;
  const path = `/constitution/pdf/${props.docId}/page/${currentPage.value}?format=png&dpi=${props.dpi}`;
  // base가 이미 /api 로 끝나면 중복 방지
  if (base.endsWith("/api")) {
    return `${base}${path}`;
  }
  return `${base}/api${path}`;
});
/** 이미지 컨테이너 스타일 */
const imageContainerStyle = computed(() => {
  return {
    position: "relative" as const,
    display: "inline-block",
  };
});

/** 현재 페이지의 하이라이트 사각형들 */
const currentPageRects = computed<HighlightRect[]>(() => {
  if (displayWidth.value === 0 || displayHeight.value === 0) return [];
  return getHighlightRectsForPage(
    currentPage.value,
    displayWidth.value,
    displayHeight.value,
  );
});

/** 하이라이트가 있는 페이지 목록 */
const highlightedPageList = computed(() => highlightedPages.value);

/** 하이라이트 데이터 목록 */
const highlightDataList = computed(() => highlights.value);

// ==================== 메서드 ====================

function getLevel(score: number): string {
  if (score >= 0.8) return "high";
  if (score >= 0.6) return "medium";
  return "low";
}

/** 페이지 치수 로드 */
async function loadPageDimensions() {
  if (!props.docId) return;
  try {
    const base = resolvedApiBase.value;
    const path = `/constitution/pdf/${props.docId}/all-page-dimensions?dpi=${props.dpi}`;
    const url = base.endsWith("/api") ? `${base}${path}` : `${base}/api${path}`;
    const response = await $fetch<any>(url, { method: "GET" });

    if (response?.pages) {
      setAllPageDimensions(response.pages);
      totalPages.value = response.total_pages || response.pages.length;
    }
  } catch (err: any) {
    console.warn("[PDFHighlightViewer] 페이지 치수 로드 실패:", err.message);
    // 치수 로드 실패 시에도 이미지는 표시됨, 하이라이트만 정확도 감소
  }
}

/** 이미지 로드 완료 */
function onImageLoaded() {
  isPageLoading.value = false;
  pageError.value = null;
  updateDisplayDimensions();
}

/** 이미지 로드 에러 */
function onImageError() {
  isPageLoading.value = false;
  pageError.value = `페이지 ${currentPage.value} 이미지를 불러올 수 없습니다.`;
}

/** 표시 크기 업데이트 */
function updateDisplayDimensions() {
  if (!pageImage.value) return;

  const img = pageImage.value;
  // 실제 화면에 표시된 크기 (CSS 적용 후)
  displayWidth.value = img.clientWidth;
  displayHeight.value = img.clientHeight;
}

/** 페이지 이동 */
function prevPage() {
  if (currentPage.value > 1) {
    currentPage.value--;
  }
}

function nextPage() {
  if (currentPage.value < totalPages.value) {
    currentPage.value++;
  }
}

/** 하이라이트 사각형 클릭 */
function onRectClick(rect: HighlightRect) {
  activeHighlightIndex.value = rect.resultIndex;
  const result = props.searchResults?.[rect.resultIndex];
  if (result) {
    emit("highlight-click", result);
  }
}

/** 하이라이트 목록 아이템 클릭 */
function onHighlightItemClick(hl: HighlightData) {
  goToHighlight(hl.resultIndex);
  const result = props.searchResults?.[hl.resultIndex];
  if (result) {
    emit("highlight-click", result);
  }
}

// ==================== 리사이즈 감지 ====================
let resizeObserver: ResizeObserver | null = null;

function setupResizeObserver() {
  if (!canvasWrap.value) return;
  resizeObserver = new ResizeObserver(() => {
    nextTick(() => updateDisplayDimensions());
  });
  resizeObserver.observe(canvasWrap.value);
}

// ==================== Watch ====================

// docId 변경 → 치수 재로드
watch(
  () => props.docId,
  async (newDocId) => {
    if (!newDocId) return;
    clearHighlights();
    displayWidth.value = 0;
    displayHeight.value = 0;
    await loadPageDimensions();

    // searchResults가 이미 있으면 하이라이트 적용
    if (props.searchResults && props.searchResults.length > 0) {
      applyHighlightsFromResults(props.searchResults);
    }
  },
  { immediate: false },
);

// searchResults 변경 → 하이라이트 재적용
watch(
  () => props.searchResults,
  (newResults) => {
    if (newResults && newResults.length > 0) {
      applyHighlightsFromResults(newResults);
      // 첫 번째 하이라이트 페이지로 이동
      nextTick(() => {
        goToFirstHighlight();
      });
    } else {
      clearHighlights();
    }
  },
  { deep: true },
);

// initialPage 변경 → 페이지 이동
watch(
  () => props.initialPage,
  (newPage) => {
    if (newPage && newPage >= 1) {
      currentPage.value = newPage;
    }
  },
);

// 페이지 변경 → emit
watch(currentPage, (page) => {
  isPageLoading.value = true;
  pageError.value = null;
  emit("page-change", page);
});

// ==================== 초기화 ====================
onMounted(async () => {
  if (props.initialPage) {
    currentPage.value = props.initialPage;
  }

  setupResizeObserver();

  if (props.docId) {
    isPageLoading.value = true;
    await loadPageDimensions();

    if (props.searchResults && props.searchResults.length > 0) {
      applyHighlightsFromResults(props.searchResults);
      nextTick(() => goToFirstHighlight());
    }
  }
});

// 클린업
import { onBeforeUnmount } from "vue";
onBeforeUnmount(() => {
  if (resizeObserver) {
    resizeObserver.disconnect();
    resizeObserver = null;
  }
});
</script>

<style scoped>
/* ==================== 뷰어 컨테이너 ==================== */
.pdf_hl_viewer {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
}

/* ==================== 헤더 ==================== */
.pdf_hl_header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: white;
  border-bottom: 1px solid #e5e7eb;
  flex-shrink: 0;
}

.pdf_hl_title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.pdf_hl_title h3 {
  font-size: 14px;
  font-weight: 600;
  color: #1f2937;
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 200px;
}

.pdf_hl_badge {
  display: inline-block;
  padding: 2px 6px;
  background: #dbeafe;
  color: #2563eb;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
}

.pdf_hl_controls {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.pdf_hl_btn {
  padding: 4px 8px;
  border: 1px solid #d1d5db;
  border-radius: 4px;
  background: white;
  cursor: pointer;
  transition: all 0.15s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.pdf_hl_btn:hover:not(:disabled) {
  background: #f3f4f6;
  border-color: #9ca3af;
}

.pdf_hl_btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.pdf_hl_page_info {
  font-size: 12px;
  color: #6b7280;
  min-width: 60px;
  text-align: center;
}

.pdf_hl_divider {
  color: #d1d5db;
  margin: 0 2px;
}

.pdf_hl_page_jump {
  padding: 2px 6px;
  border: 1px solid #fbbf24;
  border-radius: 3px;
  background: #fffbeb;
  color: #92400e;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.15s;
}

.pdf_hl_page_jump:hover,
.pdf_hl_page_jump.active {
  background: #fbbf24;
  color: white;
}

/* ==================== 캔버스 영역 ==================== */
.pdf_hl_canvas_wrap {
  flex: 1;
  overflow: auto;
  padding: 12px;
  background: #e5e7eb;
  display: flex;
  justify-content: center;
  align-items: flex-start;
}

.pdf_hl_loading,
.pdf_hl_error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 300px;
  color: #6b7280;
  gap: 12px;
}

.pdf_hl_spinner {
  width: 36px;
  height: 36px;
  border: 3px solid #e5e7eb;
  border-top-color: #2563eb;
  border-radius: 50%;
  animation: pdf_hl_spin 0.8s linear infinite;
}

@keyframes pdf_hl_spin {
  to {
    transform: rotate(360deg);
  }
}

/* ==================== 이미지 컨테이너 ==================== */
.pdf_hl_image_container {
  position: relative;
  display: inline-block;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  background: white;
}

.pdf_hl_page_image {
  display: block;
  max-width: 100%;
  height: auto;
  user-select: none;
  -webkit-user-drag: none;
}

/* ==================== 하이라이트 오버레이 ==================== */
.pdf_hl_overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.pdf_hl_rect {
  position: absolute;
  pointer-events: auto;
  cursor: pointer;
  transition: all 0.2s;
  border-radius: 2px;
}

/* 등급별 색상 */
.pdf_hl_rect_high {
  background: rgba(239, 68, 68, 0.25);
  border: 2px solid rgba(239, 68, 68, 0.6);
}

.pdf_hl_rect_medium {
  background: rgba(251, 191, 36, 0.25);
  border: 2px solid rgba(251, 191, 36, 0.6);
}

.pdf_hl_rect_low {
  background: rgba(59, 130, 246, 0.25);
  border: 2px solid rgba(59, 130, 246, 0.6);
}

/* 활성 상태 */
.pdf_hl_rect_active {
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.5);
  z-index: 10;
}

.pdf_hl_rect:hover {
  filter: brightness(1.1);
  z-index: 20;
}

/* ==================== 툴팁 ==================== */
.pdf_hl_tooltip {
  position: absolute;
  bottom: calc(100% + 8px);
  left: 50%;
  transform: translateX(-50%);
  padding: 10px 14px;
  background: rgba(17, 24, 39, 0.95);
  color: white;
  font-size: 12px;
  border-radius: 6px;
  white-space: normal;
  max-width: 320px;
  min-width: 180px;
  z-index: 100;
  pointer-events: none;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.pdf_hl_tooltip strong {
  display: block;
  font-size: 13px;
  margin-bottom: 4px;
  color: #93c5fd;
}

.pdf_hl_tooltip_score {
  display: inline-block;
  padding: 1px 6px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 3px;
  font-size: 11px;
  margin-bottom: 6px;
}

.pdf_hl_tooltip p {
  margin: 4px 0 0;
  line-height: 1.4;
  color: #d1d5db;
  font-size: 11px;
}

/* ==================== 하이라이트 목록 (하단) ==================== */
.pdf_hl_sidebar {
  flex-shrink: 0;
  max-height: 180px;
  overflow-y: auto;
  background: white;
  border-top: 1px solid #e5e7eb;
  padding: 10px 12px;
}

.pdf_hl_sidebar h4 {
  font-size: 13px;
  font-weight: 600;
  color: #1f2937;
  margin: 0 0 8px 0;
}

.pdf_hl_list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.pdf_hl_item {
  display: flex;
  gap: 10px;
  padding: 8px 10px;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s;
}

.pdf_hl_item:hover {
  background: #f3f4f6;
  border-color: #2563eb;
}

.pdf_hl_item.active {
  background: #dbeafe;
  border-color: #2563eb;
}

.pdf_hl_item_score {
  flex-shrink: 0;
  width: 42px;
  height: 42px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: white;
  border: 2px solid #e5e7eb;
  border-radius: 50%;
  font-size: 11px;
  font-weight: 700;
}

.pdf_hl_item_score.level_high {
  color: #dc2626;
  border-color: #fca5a5;
}

.pdf_hl_item_score.level_medium {
  color: #d97706;
  border-color: #fcd34d;
}

.pdf_hl_item_score.level_low {
  color: #2563eb;
  border-color: #93c5fd;
}

.pdf_hl_item_info {
  flex: 1;
  min-width: 0;
}

.pdf_hl_item_label {
  font-size: 13px;
  font-weight: 600;
  color: #1f2937;
  margin: 0 0 2px 0;
}

.pdf_hl_item_text {
  font-size: 12px;
  color: #6b7280;
  margin: 0 0 2px 0;
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
}

.pdf_hl_item_info small {
  font-size: 11px;
  color: #9ca3af;
}
</style>
