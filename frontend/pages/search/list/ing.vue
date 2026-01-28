<template>
  <ul class="skip_menu">
    <li><a href="#contents_wrap">검색 바로가기</a></li>
  </ul>
  <!-- [E] skip menu -->

  <!-- [S] contents_wrap -->
  <div class="contents_wrap" id="contents_wrap">
    <!-- [S] left_menu_wrap -->
    <div class="left_menu_wrap open">
      <div class="left_menu_hd">
        <img
          src="/img/layout/hd_logo.svg"
          alt="LANDSOFT AI 도서정보 검색시스템"
          class="hd_logo view_ctr"
        />
        <a href="#;" class="left_menu_trigger" aria-label="메뉴 열기"></a>
      </div>
      <div class="left_menu_con_wrap view_ctr">
        <div class="left_menu_con">
          <ul class="left_menu_tab tab_menu">
            <li class="tab_item tab_link on" data-tab="tab_history">
              <a href="#;" class="inn"
                >연구 히스토리<span class="hidden">현재 선택됨</span></a
              >
            </li>
            <li class="tab_item tab_link" data-tab="tab_category">
              <a href="#;" class="inn">카테고리 검색</a>
            </li>
          </ul>
          <!-- [S] 스크롤되는 영역 -->
          <div class="tab_con_wrap">
            <!-- [S] 연구 히스토리 -->
            <div class="tab_con tab_history on">
              <div class="con_tit ty_01">연구 히스토리</div>
              <div class="history_con_wrap">
                <div class="history_con">
                  <div class="history_con_date">오늘</div>
                  <ul class="history_con_list">
                    <li class="history_con_item">
                      <a href="#;" class="history_con_inn">
                        <div class="txt">
                          마키아벨리의 『군주론』이 현대에 어떻게 받아들여졌는지
                          토론
                          <span class="fw_sb">(3 질문)</span>
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
                          피카소는 파리 생활에서 자신의 예술적 스타일에 영향을
                          받았습니까?
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
                          마키아벨리의 『군주론』이 현대에 어떻게 받아들여졌는지
                          토론
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
                <div class="history_con">
                  <div class="history_con_date">지난 7일</div>
                  <ul class="history_con_list">
                    <li class="history_con_item">
                      <a href="#;" class="history_con_inn">
                        <div class="txt">
                          마키아벨리의 『군주론』이 현대에 어떻게 받아들여졌는지
                          토론
                          <span class="fw_sb">(2 질문)</span>
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
                <div class="history_con">
                  <div class="history_con_date">2025</div>
                  <ul class="history_con_list">
                    <li class="history_con_item">
                      <a href="#;" class="history_con_inn">
                        <div class="txt">
                          비타민 D 결핍은 전반적인 건강에 어떤 영향을 미칩니까?
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
                          do US corporations use Linux as an internal
                          workstation operating system?
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
                          앞 무릎 통증을 겪는 20-30대 여성들의 단계별 재활전략에
                          대해 알려줘
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
            <!-- [E] 연구 히스토리 -->
            <!-- [S] 카테고리 검색 -->
            <div class="tab_con tab_category">
              <div class="con_tit ty_01">카테고리 검색</div>
              <ul class="ctg_list ctg_depth_01">
                <li class="ctg_item ctg_depth_01 has_child on">
                  <a href="#;" class="ctg_txt ctg_depth_01">경영&middot;경제</a>
                  <ul class="ctg_list ctg_depth_02">
                    <li class="ctg_item ctg_depth_02 has_child on">
                      <a href="#;" class="ctg_txt ctg_depth_02">경영(관리)</a>
                      <ul class="ctg_list ctg_depth_03">
                        <li class="ctg_item ctg_depth_03 on">
                          <a href="#;" class="ctg_txt ctg_depth_03"
                            >경영(관리)01</a
                          >
                        </li>
                        <li class="ctg_item ctg_depth_03">
                          <a href="#;" class="ctg_txt ctg_depth_03"
                            >경영(관리)02</a
                          >
                        </li>
                        <li class="ctg_item ctg_depth_03">
                          <a href="#;" class="ctg_txt ctg_depth_03"
                            >경영(관리)03</a
                          >
                        </li>
                        <li class="ctg_item ctg_depth_03">
                          <a href="#;" class="ctg_txt ctg_depth_03"
                            >경영(관리)04</a
                          >
                        </li>
                      </ul>
                    </li>
                    <li class="ctg_item ctg_depth_02">
                      <a href="#;" class="ctg_txt ctg_depth_02">경제이론</a>
                    </li>
                    <li class="ctg_item ctg_depth_02">
                      <a href="#;" class="ctg_txt ctg_depth_02">경제사</a>
                    </li>
                    <li class="ctg_item ctg_depth_02">
                      <a href="#;" class="ctg_txt ctg_depth_02">교통 경제</a>
                    </li>
                    <li class="ctg_item ctg_depth_02 has_child">
                      <a href="#;" class="ctg_txt ctg_depth_02">금융</a>
                      <ul class="ctg_list ctg_depth_03">
                        <li class="ctg_item ctg_depth_03">
                          <a href="#;" class="ctg_txt ctg_depth_03">금융01</a>
                        </li>
                        <li class="ctg_item ctg_depth_03">
                          <a href="#;" class="ctg_txt ctg_depth_03">금융02</a>
                        </li>
                      </ul>
                    </li>
                    <li class="ctg_item ctg_depth_02">
                      <a href="#;" class="ctg_txt ctg_depth_02"
                        >노동&middot;노동자 경제학</a
                      >
                    </li>
                    <li class="ctg_item ctg_depth_02">
                      <a href="#;" class="ctg_txt ctg_depth_02">농업 경제학</a>
                    </li>
                    <li class="ctg_item ctg_depth_02">
                      <a href="#;" class="ctg_txt ctg_depth_02"
                        >부동산, 주택&middot;토지 이용</a
                      >
                    </li>
                    <li class="ctg_item ctg_depth_02">
                      <a href="#;" class="ctg_txt ctg_depth_02">산업</a>
                    </li>
                    <li class="ctg_item ctg_depth_02">
                      <a href="#;" class="ctg_txt ctg_depth_02">산업 교육</a>
                    </li>
                    <li class="ctg_item ctg_depth_02 has_child">
                      <a href="#;" class="ctg_txt ctg_depth_02">상업</a>
                      <ul class="ctg_list ctg_depth_03">
                        <li class="ctg_item ctg_depth_03">
                          <a href="#;" class="ctg_txt ctg_depth_03">상업01</a>
                        </li>
                        <li class="ctg_item ctg_depth_03">
                          <a href="#;" class="ctg_txt ctg_depth_03">상업02</a>
                        </li>
                      </ul>
                    </li>
                    <li class="ctg_item ctg_depth_02">
                      <a href="#;" class="ctg_txt ctg_depth_02">인구 통계학</a>
                    </li>
                  </ul>
                </li>
                <li class="ctg_item ctg_depth_01 has_child">
                  <a href="#;" class="ctg_txt ctg_depth_01"
                    >공학&middot;응용 과학</a
                  >
                  <ul class="ctg_list ctg_depth_02">
                    <li class="ctg_item ctg_depth_02 has_child">
                      <a href="#;" class="ctg_txt ctg_depth_02 on"
                        >경영(관리)</a
                      >
                      <ul class="ctg_list ctg_depth_03">
                        <li class="ctg_item ctg_depth_03 on">
                          <a href="#;" class="ctg_txt ctg_depth_03"
                            >경영(관리)01</a
                          >
                        </li>
                        <li class="ctg_item ctg_depth_03">
                          <a href="#;" class="ctg_txt ctg_depth_03"
                            >경영(관리)02</a
                          >
                        </li>
                        <li class="ctg_item ctg_depth_03">
                          <a href="#;" class="ctg_txt ctg_depth_03"
                            >경영(관리)03</a
                          >
                        </li>
                        <li class="ctg_item ctg_depth_03">
                          <a href="#;" class="ctg_txt ctg_depth_03"
                            >경영(관리)04</a
                          >
                        </li>
                      </ul>
                    </li>
                    <li class="ctg_item ctg_depth_02">
                      <a href="#;" class="ctg_txt ctg_depth_02">경제이론</a>
                    </li>
                    <li class="ctg_item ctg_depth_02">
                      <a href="#;" class="ctg_txt ctg_depth_02">경제사</a>
                    </li>
                    <li class="ctg_item ctg_depth_02">
                      <a href="#;" class="ctg_txt ctg_depth_02">교통 경제</a>
                    </li>
                    <li class="ctg_item ctg_depth_02 has_child">
                      <a href="#;" class="ctg_txt ctg_depth_02">금융</a>
                      <ul class="ctg_list ctg_depth_03">
                        <li class="ctg_item ctg_depth_03">
                          <a href="#;" class="ctg_txt ctg_depth_03">금융01</a>
                        </li>
                        <li class="ctg_item ctg_depth_03">
                          <a href="#;" class="ctg_txt ctg_depth_03">금융02</a>
                        </li>
                      </ul>
                    </li>
                    <li class="ctg_item ctg_depth_02">
                      <a href="#;" class="ctg_txt ctg_depth_02"
                        >노동&middot;노동자 경제학</a
                      >
                    </li>
                    <li class="ctg_item ctg_depth_02">
                      <a href="#;" class="ctg_txt ctg_depth_02">농업 경제학</a>
                    </li>
                    <li class="ctg_item ctg_depth_02">
                      <a href="#;" class="ctg_txt ctg_depth_02"
                        >부동산, 주택&middot;토지 이용</a
                      >
                    </li>
                    <li class="ctg_item ctg_depth_02">
                      <a href="#;" class="ctg_txt ctg_depth_02">산업</a>
                    </li>
                    <li class="ctg_item ctg_depth_02">
                      <a href="#;" class="ctg_txt ctg_depth_02">산업 교육</a>
                    </li>
                    <li class="ctg_item ctg_depth_02 has_child">
                      <a href="#;" class="ctg_txt ctg_depth_02">상업</a>
                      <ul class="ctg_list ctg_depth_03">
                        <li class="ctg_item ctg_depth_03">
                          <a href="#;" class="ctg_txt ctg_depth_03">상업01</a>
                        </li>
                        <li class="ctg_item ctg_depth_03">
                          <a href="#;" class="ctg_txt ctg_depth_03">상업02</a>
                        </li>
                      </ul>
                    </li>
                    <li class="ctg_item ctg_depth_02">
                      <a href="#;" class="ctg_txt ctg_depth_02">인구 통계학</a>
                    </li>
                  </ul>
                </li>
              </ul>
            </div>
            <!-- [E] 카테고리 검색 -->
          </div>
          <!-- [E] 스크롤되는 영역 -->
          <div class="left_menu_btm_info">
            <div class="left_menu_btm_txt">
              AI가 생성한 콘텐츠입니다. 품질이 달라질 수 있으니 정확성을 확인해
              주세요.
            </div>
            <div class="info_wrap ty_01">
              <a href="#;" class="info info_item ty_01"
                ><img src="/img/icon/ic_q.svg" alt="" />연구 어시스턴트 소개</a
              >
              <a href="#;" class="info info_item ty_01"
                ><img src="/img/icon/ic_privacy.svg" alt="" />개인정보 보호 방침
                및 면책 조항</a
              >
            </div>
          </div>
        </div>
      </div>
    </div>
    <!-- [E] left_menu_wrap -->
    <!-- [S] search_wrap -->
    <div class="search_wrap search_ctg_wrap open">
      <div class="search_wrap_hd">
        <div class="area"></div>
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
      <div class="search_list_wrap">
        <div class="search_q_item">
          <div class="search_q_tit">
            마키아벨리의 『군주론』이 현대에 어떻게 받아들여졌는지 토론
          </div>
          <div class="loading_wrap">
            <div class="circle_wrap">
              <img src="/img/icon/ic_ing.svg" alt="" class="circle_img" />
            </div>
            <div class="loading_txt">답변 생성 중 입니다...</div>
          </div>
        </div>
        <div class="search_q_item">
          <div class="search_q_tit">
            마키아벨리의 『군주론』이 현대에 어떻게 받아들여졌는지 토론
          </div>
          <div class="loading_wrap">
            <div class="circle_wrap">
              <img src="/img/icon/ic_ing.svg" alt="" class="circle_img" />
            </div>
            <div class="loading_txt">답변 생성 중 입니다...</div>
          </div>
        </div>
      </div>
      <div class="search_box_wrap">
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
            placeholder="연구 질문을 입력하세요."
            class="search_box_input"
          />
          <button class="search_box_btn" aria-label="검색"></button>
        </div>
      </div>
    </div>
    <!-- [E] search_wrap -->
  </div>
</template>

<script setup lang="ts">
definePageMeta({
  layout: "search",
  layoutProps: { wrapClass: "search_wrap search_ctg_wrap open" },
});

useHead({ title: "리스트 형(생성 중) | AI 도서정보 검색시스템" });
</script>
