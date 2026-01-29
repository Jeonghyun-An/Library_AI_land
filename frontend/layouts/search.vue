<template>
  <slot />
</template>

<script setup lang="ts">
useHead({
  script: [
    // jQuery 먼저
    { src: "/js/jquery-3.6.0.js", defer: true },
    { src: "/js/jquery-ui.js", defer: true },
    { src: "/js/slick.min.js", defer: true },
    { src: "/js/swiper.js", defer: true },
    // 퍼블 공통
    { src: "/js/common.js", defer: true },
  ],
  link: [
    { rel: "stylesheet", href: "/css/reset.css" },
    { rel: "stylesheet", href: "/css/common.css" },
    { rel: "stylesheet", href: "/css/layout.css" },
    { rel: "stylesheet", href: "/css/slick.css" },
    { rel: "stylesheet", href: "/css/swiper.css" },
  ],
});
</script>
