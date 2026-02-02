<template>
  <!-- [S] skip menu -->
  <ul class="skip_menu">
    <li><a href="#contents_wrap">검색 바로가기</a></li>
  </ul>
  <!-- [E] skip menu -->

  <!-- [S] contents_wrap -->
  <div class="contents_wrap" id="contents_wrap">
    <!-- [S] left_menu_wrap -->
    <div class="left_menu_wrap">
      <div class="left_menu_hd">
        <img
          src="/img/layout/hd_logo.svg"
          alt="법원도서관 AI 헌법 특화 에이전트"
          class="hd_logo view_ctr"
        />
        <a href="#;" class="left_menu_trigger" aria-label="메뉴 열기"></a>
      </div>

      <div class="left_menu_con_wrap view_ctr">
        <div class="left_menu_con">
          <!-- [S] 스크롤되는 영역 -->
          <div class="tab_con_wrap">
            <!-- [S] 질의 히스토리 -->
            <div class="tab_history tab_con on">
              <div class="con_tit ty_01 mt_20i">질의 히스토리</div>
              <div class="history_con_wrap">
                <div class="history_con">
                  <div class="history_con_date">오늘</div>
                  <ul class="history_con_list">
                    <li class="history_con_item">
                      <a href="#;" class="history_con_inn">
                        <div class="txt">
                          인간의 존엄성과 관련된 각 국의<br />
                          헌법 조항 알려줘.
                        </div>
                        <button
                          class="ic_del"
                          aria-label="삭제"
                          onclick="fn_del(this)"
                        ></button>
                      </a>
                    </li>
                    <li class="history_con_item">
                      <a href="#;" class="history_con_inn">
                        <div class="txt">
                          주요 국가 헌법 '표현의 자유' 조항 비교 해줘.<br />
                          (한국·미국·독일·일본 중심)
                        </div>
                        <button
                          class="ic_del"
                          aria-label="삭제"
                          onclick="fn_del(this)"
                        ></button>
                      </a>
                    </li>
                    <li class="history_con_item">
                      <a href="#;" class="history_con_inn">
                        <div class="txt">
                          주요 국가 헌법 비상사태 조항 비교 해줘.
                        </div>
                        <button
                          class="ic_del"
                          aria-label="삭제"
                          onclick="fn_del(this)"
                        ></button>
                      </a>
                    </li>
                  </ul>
                </div>
              </div>
            </div>
            <!-- [E] 질의 히스토리 -->
          </div>
          <!-- [E] 스크롤되는 영역 -->

          <div class="left_menu_btm_info">
            <div class="left_menu_btm_txt">
              AI가 생성한 콘텐츠입니다. 품질이 달라질 수 있으니 정확성을 확인해
              주세요.
            </div>
            <div class="info_wrap ty_01">
              <span class="info">
                <a href="#;" class="info_item ty_01"
                  ><img src="/img/icon/ic_q.svg" alt="" />Ai 헌법특화 어시스턴트
                  소개</a
                >
              </span>
              <span class="info">
                <a href="#;" class="info_item ty_01"
                  ><img src="/img/icon/ic_privacy.svg" alt="" />개인정보 보호
                  방침 및 면책 조항</a
                >
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
    <!-- [E] left_menu_wrap -->

    <!-- [S] search_wrap -->
    <div class="search_wrap search_main_wrap">
      <div class="search_wrap_hd">
        <div class="area">
          <img
            src="/img/layout/hd_logo.svg"
            alt="법원도서관 AI 헌법 특화 에이전트"
            class="hd_logo"
          />
        </div>

        <div
          class="member_util_wrap trigger_wrap"
          id="member_util_trigger_wrap"
        >
          <a
            href="#;"
            class="trigger member_util_trigger"
            id="member_util_trigger"
            ><img src="/img/icon/ic_member.svg" alt="" />최승환 님</a
          >
          <div
            class="trigger_toggle member_util_trigger_toggle"
            id="member_util_trigger_toggle"
          >
            <div class="member_wrap">
              <div class="member_info">
                <div class="member_name">최승환 님</div>
                <div class="member_email">test0505@ajou.ac.kr</div>
              </div>
              <a href="#;" class="logout btn sz_md"
                ><img src="/img/icon/ic_logout.svg" alt="" />로그아웃</a
              >
            </div>

            <ul class="member_util_list">
              <li class="member_util_item">
                <a href="#;" class="util_item_inn"
                  ><span class="ic ic_bookmark"></span
                  ><span class="txt">내 즐겨찾기</span></a
                >
              </li>
              <li class="member_util_item">
                <a href="#;" class="util_item_inn"
                  ><span class="ic ic_history"></span
                  ><span class="txt">내 검색기록</span></a
                >
              </li>

              <li
                class="member_util_item lang_trigger_wrap trigger_wrap"
                id="lang_trigger_wrap"
              >
                <a href="#;" class="util_item_inn trigger" id="lang_trigger"
                  ><span class="ic ic_lang"></span
                  ><span class="txt"
                    >표시언어: <span class="fw_b lang">한국어</span></span
                  ></a
                >
                <div
                  class="trigger_toggle lang_trigger_toggle"
                  id="lang_trigger_toggle"
                >
                  <div class="lang_trigger_toggle_hd">
                    <img src="/img/icon/ic_lang_b.svg" alt="" />표시언어
                  </div>
                  <ul class="lang_list">
                    <li class="lang_item">
                      <a href="#;" class="inn">English</a>
                    </li>
                    <li class="lang_item on">
                      <a href="#;" class="inn">한국어</a>
                    </li>
                  </ul>
                  <a
                    href="#;"
                    class="btn bg_black sz_md trigger_close"
                    data-target="lang_trigger"
                    >취소</a
                  >
                </div>
              </li>
            </ul>
          </div>
        </div>
      </div>

      <div class="search_main">
        <div class="inner">
          <img
            src="/img/main/txt_search_main.svg"
            alt="AI 헌법 특화 에이전트"
          />
          <div class="main_txt">
            우리나라 헌법과 각국의 헌법을 비교 분석해주는 법원도서관의 생성형
            인공지능 서비스입니다.
          </div>

          <div class="search_box">
            <div
              class="trigger_wrap search_condition_trigger_wrap"
              id="search_condition_trigger_wrap"
            >
              <a
                href="#;"
                aria-label="검색 조건 설정"
                class="trigger search_condition_trigger"
                id="search_condition_trigger"
              ></a>

              <div
                class="trigger_toggle search_condition_trigger_toggle"
                id="search_condition_trigger_toggle"
              >
                <div class="search_condition_wrap">
                  <div class="select_box">
                    <select name="" id="" title="양식 구분">
                      <option value="">모든 양식</option>
                    </select>
                  </div>
                  <div class="select_box">
                    <select name="" id="" title="날짜 구분">
                      <option value="">모든 날짜</option>
                    </select>
                  </div>
                  <div class="form_check ty_01">
                    <input type="checkbox" name="" id="online" />
                    <label for="online">온라인 이용가능</label>
                  </div>
                </div>
              </div>
            </div>

            <input
              type="text"
              title="검색어 입력"
              placeholder="질문을 입력해주세요."
              class="search_box_input"
            />
            <button class="search_box_btn" aria-label="검색"></button>
          </div>

          <div class="question_example">
            <div class="question_example_hd">
              <div class="con_tit ty_01">질문 예시</div>
              <a href="#;" class="info_item ty_01"
                ><img src="/img/icon/ic_q.svg" alt="" />Ai 헌법특화 어시스턴트
                소개</a
              >
            </div>

            <ul class="question_example_list">
              <li class="question_example_item">
                <a href="#;" class="inn">
                  <div class="item ellipsis line02">
                    인간의 존엄성과 관련된 각 국의 헌법 조항 알려줘.
                  </div>
                  <div class="arr"></div>
                </a>
              </li>
              <li class="question_example_item">
                <a href="#;" class="inn">
                  <div class="item ellipsis line02">
                    주요 국가 헌법 '표현의 자유' 조항 비교 해줘.
                    <br />(한국·미국·독일·일본 중심)
                  </div>
                  <div class="arr"></div>
                </a>
              </li>
              <li class="question_example_item">
                <a href="#;" class="inn">
                  <div class="item ellipsis line02">
                    주요 국가 헌법 비상사태 조항 비교 해줘.
                  </div>
                  <div class="arr"></div>
                </a>
              </li>
              <li class="question_example_item">
                <a href="#;" class="inn">
                  <div class="item ellipsis line02">
                    각 국 헌법의 대통령제 조항 비교 해줘.
                  </div>
                  <div class="arr"></div>
                </a>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
    <!-- [E] search_wrap -->
  </div>
  <!-- [E] contents_wrap -->
</template>

<script setup>
import { onMounted, onBeforeUnmount, useHead } from "#imports";
definePageMeta({
  layout: false,
});

// ✅ public 아래로 옮긴다고 했으니 /css, /img 로 고정
useHead({
  title: "AI 헌법 특화 에이전트",
  htmlAttrs: { lang: "ko" },
  meta: [
    { charset: "utf-8" },
    {
      name: "viewport",
      content:
        "width=device-width, user-scalable=no, initial-scale=1.0, maximum-scale=1.0, minimum-scale=1.0",
    },
  ],
  link: [
    { rel: "stylesheet", href: "/css/reset.css" },
    { rel: "stylesheet", href: "/css/common.css" },
    { rel: "stylesheet", href: "/css/layout.css" },
  ],
});

let cleanupFns = [];

/**
 * 아래 스크립트는 "요청받아온 그대로" 유지하되,
 * Vue 페이지 전환/언마운트에서도 이벤트가 남지 않도록 cleanup만 추가함.
 */
onMounted(() => {
  (function () {
    "use strict";

    const $ = (sel, ctx) => (ctx || document).querySelector(sel);
    const $$ = (sel, ctx) =>
      Array.from((ctx || document).querySelectorAll(sel));

    function on(parent, type, selector, handler) {
      const listener = function (e) {
        const el = e.target.closest(selector);
        if (!el || !parent.contains(el)) return;
        handler(e, el);
      };
      parent.addEventListener(type, listener);
      cleanupFns.push(() => parent.removeEventListener(type, listener));
    }

    function getTabContainer(menu) {
      // tab_menu를 기준으로 가장 가까운 래퍼(탭 컨텐츠 포함)를 잡아 스코프 고정
      return (
        menu.closest(".list_answer_item") ||
        menu.closest(".left_menu_wrap") ||
        menu.parentElement ||
        document
      );
    }

    function getConWrap(menu, container) {
      // menu 다음이 tab_con_wrap이면 우선(출처 구조)
      const next = menu.nextElementSibling;
      if (next && next.classList && next.classList.contains("tab_con_wrap"))
        return next;
      // 그 외는 container 내부의 첫 tab_con_wrap 사용(좌측 메뉴 구조)
      return $(".tab_con_wrap", container);
    }

    function setTabActive(tabLink) {
      const menu = tabLink.closest(".tab_menu");
      if (!menu) return;

      const dataTab = tabLink.getAttribute("data-tab");
      if (!dataTab) return;

      const container = getTabContainer(menu);
      const conWrap = getConWrap(menu, container);
      if (!conWrap) return;

      const targetCon = $(".tab_con." + dataTab, conWrap);
      if (!targetCon) return;

      // 메뉴 내부 버튼 초기화
      $$(".tab_link", menu).forEach((a) => a.classList.remove("on"));
      $$(".hidden", menu).forEach((n) => n.remove());

      // 현재 버튼 활성화
      tabLink.classList.add("on");
      const hidden = document.createElement("span");
      hidden.className = "hidden";
      hidden.textContent = "현재 선택됨";
      const inn = tabLink.querySelector(".inn") || tabLink;
      inn.appendChild(hidden);

      // 같은 conWrap 안의 tab_con 토글
      $$(".tab_con", conWrap).forEach((c) => c.classList.remove("on"));
      targetCon.classList.add("on");
    }

    /* tab */
    on(document, "click", ".tab_link", function (e, tabLink) {
      e.preventDefault();
      setTabActive(tabLink);
    });

    /* trigger (id 기반: *_wrap, *_toggle) */
    on(document, "click", ".trigger", function (e, trigger) {
      e.preventDefault();

      const id = trigger.getAttribute("id");
      if (!id) return;

      const wrap = document.getElementById(id + "_wrap");
      const toggle = document.getElementById(id + "_toggle");

      if (wrap) wrap.classList.toggle("open");
      if (toggle) toggle.classList.toggle("open");
      trigger.classList.toggle("open");

      const hideTxt = trigger.querySelector(".hide_txt");
      if (hideTxt) {
        const isOpen = wrap
          ? wrap.classList.contains("open")
          : trigger.classList.contains("open");
        hideTxt.innerHTML = isOpen ? "닫기" : "열기";
      }
    });

    /* trigger_close (data-target) */
    on(document, "click", ".trigger_close", function (e, btn) {
      e.preventDefault();

      const targetId = btn.getAttribute("data-target");
      if (!targetId) return;

      const target = document.getElementById(targetId);
      if (target) target.click();
    });

    /* 좌측 메뉴 열림/닫힘 */
    on(document, "click", ".left_menu_trigger", function (_e, trigger) {
      const targets = $$(".left_menu_wrap, .search_wrap");
      targets.forEach((t) => t.classList.toggle("open"));
      const isOpen = targets[0] ? targets[0].classList.contains("open") : false;
      trigger.setAttribute("aria-label", isOpen ? "메뉴 닫힘" : "메뉴 열림");
    });

    /* sc_menu drag scroll (원본 JS 유지 + 널 가드) */
    const tabs = $$(".sc_menu_wrap");
    const body = document.body;

    tabs.forEach((tab, index) => {
      tab.dataset.index = String(index + 1);
    });

    tabs.forEach((tab) => {
      const menuContainer = $(".sc_menu", tab);
      if (!menuContainer) return;

      let isMouseDown = false;
      let startX = 0;
      let scrollLeft = 0;

      const mousedown = (e) => {
        isMouseDown = true;
        menuContainer.classList.add("on");
        startX = e.pageX - menuContainer.offsetLeft;
        scrollLeft = menuContainer.scrollLeft;
        body.classList.add("no_scroll");
      };
      const mouseleave = () => {
        if (!isMouseDown) return;
        isMouseDown = false;
        menuContainer.classList.remove("on");
        body.classList.remove("no_scroll");
      };
      const mouseup = () => {
        if (!isMouseDown) return;
        isMouseDown = false;
        menuContainer.classList.remove("on");
        body.classList.remove("no_scroll");
      };
      const mousemove = (e) => {
        if (!isMouseDown) return;
        e.preventDefault();
        const x = e.pageX - menuContainer.offsetLeft;
        const walk = (x - startX) * 2;
        menuContainer.scrollLeft = scrollLeft - walk;
      };

      menuContainer.addEventListener("mousedown", mousedown);
      menuContainer.addEventListener("mouseleave", mouseleave);
      menuContainer.addEventListener("mouseup", mouseup);
      menuContainer.addEventListener("mousemove", mousemove);

      cleanupFns.push(() => {
        menuContainer.removeEventListener("mousedown", mousedown);
        menuContainer.removeEventListener("mouseleave", mouseleave);
        menuContainer.removeEventListener("mouseup", mouseup);
        menuContainer.removeEventListener("mousemove", mousemove);
      });

      let startTouchX = 0;
      const touchstart = (e) => {
        startTouchX = e.touches[0].clientX;
      };
      const touchmove = (e) => {
        const currentTouchX = e.touches[0].clientX;
        const diff = startTouchX - currentTouchX;
        menuContainer.scrollLeft += diff;
        startTouchX = currentTouchX;
      };
      menuContainer.addEventListener("touchstart", touchstart);
      menuContainer.addEventListener("touchmove", touchmove);

      cleanupFns.push(() => {
        menuContainer.removeEventListener("touchstart", touchstart);
        menuContainer.removeEventListener("touchmove", touchmove);
      });

      function scrollToActiveMenuItem() {
        const activeItem = $(".sc_menu_item.on", menuContainer);
        if (!activeItem) return;

        const containerRect = menuContainer.getBoundingClientRect();
        const itemRect = activeItem.getBoundingClientRect();
        const offset =
          itemRect.left - containerRect.left + menuContainer.scrollLeft;
        menuContainer.scrollLeft = offset;
      }

      const timer = setTimeout(scrollToActiveMenuItem, 100);
      cleanupFns.push(() => clearTimeout(timer));
    });

    /* sc_tab_btn_wrap 가로 드래그 스크롤 */
    $$(".sc_tab_btn_wrap").forEach((wrap) => {
      const body = document.body;

      let isMouseDown = false;
      let startX = 0;
      let scrollLeft = 0;

      const mousedown = (e) => {
        isMouseDown = true;
        wrap.classList.add("on");
        startX = e.pageX - wrap.offsetLeft;
        scrollLeft = wrap.scrollLeft;
        body.classList.add("no_scroll");
      };
      const mouseleave = () => {
        if (!isMouseDown) return;
        isMouseDown = false;
        wrap.classList.remove("on");
        body.classList.remove("no_scroll");
      };
      const mouseup = () => {
        if (!isMouseDown) return;
        isMouseDown = false;
        wrap.classList.remove("on");
        body.classList.remove("no_scroll");
      };
      const mousemove = (e) => {
        if (!isMouseDown) return;
        e.preventDefault();
        const x = e.pageX - wrap.offsetLeft;
        const walk = (x - startX) * 2;
        wrap.scrollLeft = scrollLeft - walk;
      };

      wrap.addEventListener("mousedown", mousedown);
      wrap.addEventListener("mouseleave", mouseleave);
      wrap.addEventListener("mouseup", mouseup);
      wrap.addEventListener("mousemove", mousemove);

      cleanupFns.push(() => {
        wrap.removeEventListener("mousedown", mousedown);
        wrap.removeEventListener("mouseleave", mouseleave);
        wrap.removeEventListener("mouseup", mouseup);
        wrap.removeEventListener("mousemove", mousemove);
      });

      let startTouchX = 0;
      const touchstart = (e) => {
        startTouchX = e.touches[0].clientX;
      };
      const touchmove = (e) => {
        const currentTouchX = e.touches[0].clientX;
        const diff = startTouchX - currentTouchX;
        wrap.scrollLeft += diff;
        startTouchX = currentTouchX;
      };

      wrap.addEventListener("touchstart", touchstart);
      wrap.addEventListener("touchmove", touchmove);

      cleanupFns.push(() => {
        wrap.removeEventListener("touchstart", touchstart);
        wrap.removeEventListener("touchmove", touchmove);
      });
    });

    /* 탭 버튼 패널 전환 - on + 버튼 위치 자동 스크롤 */
    const tabButtons = $$(".tab_btn");

    tabButtons.forEach((button) => {
      const click = () => {
        const sel = button.getAttribute("data-target");
        const targetTab = sel ? document.querySelector(sel) : null;
        if (!targetTab) return;

        // 탭 버튼 on 전환
        tabButtons.forEach((b) => b.classList.remove("on"));
        button.classList.add("on");

        // 패널 on 전환
        tabs.forEach((tab) => tab.classList.remove("on"));
        targetTab.classList.add("on");

        // 패널 열릴 때 활성 아이템 위치 맞춤
        const menuContainer = $(".sc_menu", targetTab);
        if (!menuContainer) return;

        const activeItem = $(".sc_menu_item.on", menuContainer);
        if (!activeItem) return;

        const containerRect = menuContainer.getBoundingClientRect();
        const itemRect = activeItem.getBoundingClientRect();
        const offset =
          itemRect.left - containerRect.left + menuContainer.scrollLeft;
        menuContainer.scrollLeft = offset;
      };

      button.addEventListener("click", click);
      cleanupFns.push(() => button.removeEventListener("click", click));
    });

    /* sc_menu_item 클릭 시 on 단독 적용 + 아이템 위치 자동 스크롤 */
    const scMenuItemClick = function (e) {
      const item = e.target.closest(".sc_menu_item");
      if (!item) return;

      e.preventDefault();

      const menu = item.closest(".sc_menu");
      if (!menu) return;

      // 형제 on 제거
      menu.querySelectorAll(".sc_menu_item.on").forEach((el) => {
        el.classList.remove("on");
      });

      // 본인 on 추가
      item.classList.add("on");
    };
    document.addEventListener("click", scMenuItemClick);
    cleanupFns.push(() =>
      document.removeEventListener("click", scMenuItemClick),
    );

    /* layer popup */
    window.open_layer_pop = function (pop) {
      setTimeout(function () {
        const popEl = document.getElementById(pop);
        if (!popEl) return;

        document.body.style.overflow = "hidden";
        const dim = popEl.closest(".dim");
        if (dim) dim.style.display = "block";
      }, 50);
    };

    /* pop_close */
    on(document, "click", ".pop_close", function (e, btn) {
      e.preventDefault();
      document.body.style.overflow = "visible";
      const dim = btn.closest(".dim");
      if (dim) dim.style.display = "none";
    });

    /* 연구 히스토리 삭제 */
    window.fn_del = function (el) {
      const item = el ? el.closest(".history_con_item") : null;
      if (!item) return;

      const list = item.closest(".history_con_list");
      const group = item.closest(".history_con");

      item.remove();

      if (list && !list.querySelector(".history_con_item")) {
        if (group) group.remove();
      }
    };
  })();
});

onBeforeUnmount(() => {
  cleanupFns.forEach((fn) => {
    try {
      fn();
    } catch {
      // noop
    }
  });
  cleanupFns = [];
});
</script>
