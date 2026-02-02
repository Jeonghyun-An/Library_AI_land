<!-- frontend/layouts/law.vue -->
<!-- 
  헌법 비교 검색 전용 레이아웃
  - 전체 화면 사용
  - 헤더/푸터 없음
  - 퍼블리싱 CSS와 완전히 통합
-->
<template>
  <div class="law-layout">
    <slot />
  </div>
</template>

<script setup>
import { useHead } from "#imports";

// 전체 화면을 위한 메타 설정
useHead({
  title: "AI 헌법 특화 에이전트 - 법원도서관",
  htmlAttrs: {
    lang: "ko",
    class: "h-full", // HTML 전체 높이
  },
  bodyAttrs: {
    class: "h-full m-0 p-0 overflow-hidden", // Body 전체 높이, 여백 제거
  },
  meta: [
    { charset: "utf-8" },
    {
      name: "viewport",
      content:
        "width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no",
    },
    {
      name: "description",
      content: "대한민국 헌법과 세계 각국 헌법을 비교 분석하는 AI 검색 시스템",
    },
  ],
  link: [
    // 퍼블리싱 CSS (순서 중요!)
    { rel: "stylesheet", href: "/css/reset.css" },
    { rel: "stylesheet", href: "/css/common.css" },
    { rel: "stylesheet", href: "/css/layout.css" },
  ],
});
</script>

<style scoped>
.law-layout {
  width: 100vw;
  height: 100vh;
  margin: 0;
  padding: 0;
  overflow: hidden;
}

/* 전역 스타일 재설정 */
:global(html, body, #__nuxt, #__layout) {
  width: 100%;
  height: 100%;
  margin: 0;
  padding: 0;
  overflow: hidden;
}
</style>
