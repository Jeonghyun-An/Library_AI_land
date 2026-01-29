<template>
  <div class="pdf_viewer_wrap">
    <!-- 헤더 -->
    <div class="pdf_viewer_header">
      <div class="pdf_title">
        <h3>{{ title }}</h3>
        <span v-if="countryCode" class="country_badge">{{ countryCode }}</span>
      </div>

      <!-- 페이지 네비게이션 -->
      <div class="pdf_controls">
        <button @click="previousPage" :disabled="currentPage <= 1">
          <i class="fas fa-chevron-left"></i>
        </button>
        <span class="page_info"> {{ currentPage }} / {{ totalPages }} </span>
        <button @click="nextPage" :disabled="currentPage >= totalPages">
          <i class="fas fa-chevron-right"></i>
        </button>

        <div class="zoom_controls">
          <button @click="zoomOut" :disabled="pdfScale <= 0.5">
            <i class="fas fa-search-minus"></i>
          </button>
          <span class="zoom_level">{{ Math.round(pdfScale * 100) }}%</span>
          <button @click="zoomIn" :disabled="pdfScale >= 3.0">
            <i class="fas fa-search-plus"></i>
          </button>
          <button @click="resetZoom">
            <i class="fas fa-undo"></i>
          </button>
        </div>
      </div>
    </div>

    <!-- PDF 캔버스 -->
    <div class="pdf_canvas_wrap" ref="canvasContainer">
      <div v-if="isLoading" class="pdf_loading">
        <div class="spinner"></div>
        <p>PDF 로딩 중...</p>
      </div>

      <div v-else-if="error" class="pdf_error">
        <i class="fas fa-exclamation-triangle"></i>
        <p>{{ error }}</p>
      </div>

      <canvas v-show="!isLoading && !error" ref="pdfCanvas"></canvas>

      <!-- 하이라이트 오버레이 -->
      <div class="highlight_layer">
        <div
          v-for="(highlight, index) in visibleHighlights"
          :key="index"
          :data-highlight-index="index"
          :style="getHighlightStyle(highlight)"
          :class="['highlight_region', getHighlightClass(highlight.score)]"
          @click="handleHighlightClick(highlight, index)"
        >
          <div class="highlight_tooltip">
            {{ highlight.text.substring(0, 100) }}...
            <br />
            <small>관련도: {{ Math.round(highlight.score * 100) }}%</small>
          </div>
        </div>
      </div>
    </div>

    <!-- 하이라이트 목록 -->
    <div v-if="highlights.length > 0" class="highlights_sidebar">
      <h4>검색 결과 ({{ highlights.length }}건)</h4>
      <div class="highlights_list">
        <div
          v-for="(highlight, index) in highlights"
          :key="index"
          :class="['highlight_item', { active: activeHighlight === index }]"
          @click="scrollToHighlight(index)"
        >
          <div class="highlight_score">
            {{ Math.round(highlight.score * 100) }}%
          </div>
          <div class="highlight_text">
            <p>{{ highlight.text.substring(0, 80) }}...</p>
            <small>페이지 {{ highlight.pageNumber }}</small>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, nextTick } from "vue";
import { usePDFHighlight } from "~/composables/usePDFHighlight";
import type { HighlightRegion } from "~/composables/usePDFHighlight";

interface PDFViewerProps {
  pdfUrl: string;
  title: string;
  countryCode?: string;
  searchResults?: any[];
}

const props = defineProps<PDFViewerProps>();

const {
  highlights,
  currentPage,
  totalPages,
  pdfScale,
  isLoading,
  applyHighlights,
  clearHighlights,
  goToPage,
  zoomIn,
  zoomOut,
  resetZoom,
  scrollToHighlight,
} = usePDFHighlight();

const pdfCanvas = ref<HTMLCanvasElement | null>(null);
const canvasContainer = ref<HTMLDivElement | null>(null);
const error = ref<string | null>(null);
const activeHighlight = ref<number | null>(null);

let pdfDoc: any = null;
let pdfTextContent: any[] = [];

// 현재 페이지의 하이라이트만 필터링
const visibleHighlights = computed(() => {
  return highlights.value.filter((h) => h.pageNumber === currentPage.value);
});

/**
 * PDF 로드
 */
const loadPDF = async () => {
  if (!props.pdfUrl) return;

  isLoading.value = true;
  error.value = null;

  try {
    // PDF.js 동적 import (Nuxt 3 환경)
    const pdfjsLib = await import("pdfjs-dist");
    const pdfjsWorker = await import("pdfjs-dist/build/pdf.worker.entry");
    pdfjsLib.GlobalWorkerOptions.workerSrc = pdfjsWorker.default;

    // PDF 문서 로드
    const loadingTask = pdfjsLib.getDocument(props.pdfUrl);
    pdfDoc = await loadingTask.promise;
    totalPages.value = pdfDoc.numPages;

    // 텍스트 컨텐츠 추출 (모든 페이지)
    await extractAllTextContent();

    // 첫 페이지 렌더링
    await renderPage(1);
  } catch (err: any) {
    error.value = `PDF 로드 실패: ${err.message}`;
    console.error("PDF load error:", err);
  } finally {
    isLoading.value = false;
  }
};

/**
 * 모든 페이지의 텍스트 컨텐츠 추출
 */
const extractAllTextContent = async () => {
  if (!pdfDoc) return;

  pdfTextContent = [];
  for (let i = 1; i <= pdfDoc.numPages; i++) {
    const page = await pdfDoc.getPage(i);
    const textContent = await page.getTextContent();
    pdfTextContent.push(textContent);
  }
};

/**
 * 페이지 렌더링
 */
const renderPage = async (pageNum: number) => {
  if (!pdfDoc || !pdfCanvas.value) return;

  try {
    const page = await pdfDoc.getPage(pageNum);
    const viewport = page.getViewport({ scale: pdfScale.value });

    const canvas = pdfCanvas.value;
    const context = canvas.getContext("2d");
    if (!context) return;

    canvas.height = viewport.height;
    canvas.width = viewport.width;

    const renderContext = {
      canvasContext: context,
      viewport: viewport,
    };

    await page.render(renderContext).promise;
  } catch (err) {
    console.error("Page render error:", err);
  }
};

/**
 * 페이지 이동
 */
const nextPage = async () => {
  if (currentPage.value < totalPages.value) {
    currentPage.value++;
    await renderPage(currentPage.value);
  }
};

const previousPage = async () => {
  if (currentPage.value > 1) {
    currentPage.value--;
    await renderPage(currentPage.value);
  }
};

/**
 * 하이라이트 스타일 계산
 */
const getHighlightStyle = (highlight: HighlightRegion) => {
  return {
    left: `${highlight.x}px`,
    top: `${highlight.y}px`,
    width: `${highlight.width}px`,
    height: `${highlight.height}px`,
  };
};

/**
 * 스코어에 따른 하이라이트 클래스
 */
const getHighlightClass = (score: number) => {
  if (score >= 0.9) return "high";
  if (score >= 0.7) return "medium";
  return "low";
};

/**
 * 하이라이트 클릭 핸들러
 */
const handleHighlightClick = (highlight: HighlightRegion, index: number) => {
  activeHighlight.value = index;
};

/**
 * 검색 결과 변경 시 하이라이트 적용
 */
watch(
  () => props.searchResults,
  (newResults) => {
    if (newResults && newResults.length > 0) {
      applyHighlights(newResults, pdfTextContent);
    } else {
      clearHighlights();
    }
  },
);

/**
 * 줌 레벨 변경 시 재렌더링
 */
watch(pdfScale, async () => {
  await renderPage(currentPage.value);
});

/**
 * PDF URL 변경 시 재로드
 */
watch(
  () => props.pdfUrl,
  async () => {
    await loadPDF();
  },
);

onMounted(async () => {
  await loadPDF();
});
</script>

<style scoped>
.pdf_viewer_wrap {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
}

.pdf_viewer_header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: white;
  border-bottom: 1px solid #e5e7eb;
}

.pdf_title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.pdf_title h3 {
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
  margin: 0;
}

.country_badge {
  display: inline-block;
  padding: 2px 8px;
  background: #dbeafe;
  color: #2563eb;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
}

.pdf_controls {
  display: flex;
  align-items: center;
  gap: 12px;
}

.pdf_controls button {
  padding: 6px 10px;
  border: 1px solid #d1d5db;
  border-radius: 4px;
  background: white;
  cursor: pointer;
  transition: all 0.2s;
}

.pdf_controls button:hover:not(:disabled) {
  background: #f3f4f6;
  border-color: #9ca3af;
}

.pdf_controls button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.page_info {
  font-size: 14px;
  color: #6b7280;
  min-width: 80px;
  text-align: center;
}

.zoom_controls {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-left: 12px;
  border-left: 1px solid #e5e7eb;
}

.zoom_level {
  font-size: 13px;
  color: #6b7280;
  min-width: 50px;
  text-align: center;
}

.pdf_canvas_wrap {
  position: relative;
  flex: 1;
  overflow: auto;
  padding: 20px;
  background: #e5e7eb;
}

.pdf_loading,
.pdf_error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #6b7280;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 4px solid #e5e7eb;
  border-top-color: #2563eb;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.pdf_error i {
  font-size: 48px;
  color: #ef4444;
  margin-bottom: 16px;
}

canvas {
  display: block;
  margin: 0 auto;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  background: white;
}

.highlight_layer {
  position: absolute;
  top: 20px;
  left: 20px;
  pointer-events: none;
}

.highlight_region {
  position: absolute;
  pointer-events: auto;
  cursor: pointer;
  transition: all 0.2s;
}

.highlight_region.high {
  background: rgba(239, 68, 68, 0.3);
  border: 2px solid rgba(239, 68, 68, 0.6);
}

.highlight_region.medium {
  background: rgba(251, 191, 36, 0.3);
  border: 2px solid rgba(251, 191, 36, 0.6);
}

.highlight_region.low {
  background: rgba(59, 130, 246, 0.3);
  border: 2px solid rgba(59, 130, 246, 0.6);
}

.highlight_region:hover {
  transform: scale(1.02);
}

.highlight_tooltip {
  position: absolute;
  bottom: 100%;
  left: 50%;
  transform: translateX(-50%);
  padding: 8px 12px;
  background: rgba(0, 0, 0, 0.9);
  color: white;
  font-size: 12px;
  border-radius: 4px;
  white-space: nowrap;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.2s;
  max-width: 300px;
  white-space: normal;
}

.highlight_region:hover .highlight_tooltip {
  opacity: 1;
}

.highlights_sidebar {
  width: 100%;
  max-height: 200px;
  overflow-y: auto;
  background: white;
  border-top: 1px solid #e5e7eb;
  padding: 12px;
}

.highlights_sidebar h4 {
  font-size: 14px;
  font-weight: 600;
  color: #1f2937;
  margin: 0 0 12px 0;
}

.highlights_list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.highlight_item {
  display: flex;
  gap: 12px;
  padding: 10px;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.highlight_item:hover {
  background: #f3f4f6;
  border-color: #2563eb;
}

.highlight_item.active {
  background: #dbeafe;
  border-color: #2563eb;
}

.highlight_score {
  flex-shrink: 0;
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: white;
  border: 2px solid #e5e7eb;
  border-radius: 50%;
  font-size: 12px;
  font-weight: 600;
  color: #2563eb;
}

.highlight_text {
  flex: 1;
}

.highlight_text p {
  font-size: 13px;
  color: #374151;
  margin: 0 0 4px 0;
  line-height: 1.4;
}

.highlight_text small {
  font-size: 11px;
  color: #9ca3af;
}
</style>
