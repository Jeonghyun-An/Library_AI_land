<template>
  <div class="country_select_wrap">
    <!-- 국가별 탭 -->
    <div class="country_tabs">
      <button
        v-for="region in regions"
        :key="region.id"
        :class="['country_tab', { on: currentRegion === region.id }]"
        @click="selectRegion(region.id)"
      >
        {{ region.name }}
      </button>
    </div>

    <!-- 국가 목록 -->
    <div class="country_list_wrap">
      <div class="country_list">
        <button
          v-for="country in filteredCountries"
          :key="country.code"
          :class="['country_item', { selected: country.code === modelValue }]"
          @click="selectCountry(country.code)"
        >
          <img
            :src="`/img/flags/${country.code.toLowerCase()}.svg`"
            :alt="country.name"
            class="country_flag"
            @error="handleImageError"
          />
          <span class="country_name">{{ country.name }}</span>
          <span v-if="country.version" class="country_version">
            {{ country.version }}
          </span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from "vue";

interface Country {
  code: string;
  name: string;
  region: string;
  version?: string;
}

interface CountrySelectorProps {
  modelValue: string;
  countries: Country[];
}

interface CountrySelectorEmits {
  (e: "update:modelValue", value: string): void;
}

const props = defineProps<CountrySelectorProps>();
const emit = defineEmits<CountrySelectorEmits>();

// 지역 카테고리
const regions = ref([
  { id: "all", name: "전체" },
  { id: "asia", name: "아시아" },
  { id: "europe", name: "유럽" },
  { id: "americas", name: "아메리카" },
  { id: "africa", name: "아프리카" },
  { id: "oceania", name: "오세아니아" },
]);

const currentRegion = ref("all");

// 지역별 필터링
const filteredCountries = computed(() => {
  if (currentRegion.value === "all") {
    return props.countries;
  }
  return props.countries.filter((c) => c.region === currentRegion.value);
});

// 지역 선택
const selectRegion = (regionId: string) => {
  currentRegion.value = regionId;
};

// 국가 선택
const selectCountry = (countryCode: string) => {
  emit("update:modelValue", countryCode);
};

// 이미지 로드 실패 처리
const handleImageError = (event: Event) => {
  const target = event.target as HTMLImageElement;
  target.src = "/img/flags/default.svg"; // 기본 플래그 이미지
};
</script>

<style scoped>
.country_select_wrap {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  overflow: hidden;
}

.country_tabs {
  display: flex;
  border-bottom: 1px solid #e5e7eb;
  background: #f9fafb;
}

.country_tab {
  flex: 1;
  padding: 12px 16px;
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  color: #6b7280;
  transition: all 0.2s;
  border-bottom: 2px solid transparent;
}

.country_tab:hover {
  background: #f3f4f6;
  color: #374151;
}

.country_tab.on {
  color: #2563eb;
  border-bottom-color: #2563eb;
  background: white;
}

.country_list_wrap {
  max-height: 400px;
  overflow-y: auto;
  padding: 8px;
}

.country_list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 8px;
}

.country_item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: white;
  cursor: pointer;
  transition: all 0.2s;
}

.country_item:hover {
  border-color: #2563eb;
  background: #eff6ff;
}

.country_item.selected {
  border-color: #2563eb;
  background: #dbeafe;
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.1);
}

.country_flag {
  width: 24px;
  height: 18px;
  object-fit: cover;
  border-radius: 2px;
  border: 1px solid #e5e7eb;
}

.country_name {
  flex: 1;
  font-size: 14px;
  color: #374151;
  text-align: left;
}

.country_version {
  font-size: 11px;
  color: #9ca3af;
}
</style>
