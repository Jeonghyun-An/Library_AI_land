<template>
  <div class="law-layout">
    <slot />
  </div>
</template>

<script setup lang="ts">
useHead({
  title: "AI 헌법 특화 에이전트 - 헌법재판소도서관",
  htmlAttrs: {
    lang: "ko",
  },
  bodyAttrs: {
    class: "law-body",
  },
});
</script>

<style>
html,
body,
#__nuxt {
  width: 100%;
  height: 100%;
  margin: 0;
  padding: 0;
}

body.law-body {
  overflow: hidden;
}

.law-layout {
  width: 100vw;
  height: 100vh;
  margin: 0;
  padding: 0;
  overflow: hidden;
}
</style>
