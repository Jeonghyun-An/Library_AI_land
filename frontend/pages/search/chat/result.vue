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
      <div class="search_chat_wrap">
        <div class="inner">
          <div class="search_q_item">
            <div class="search_q_tit">
              마키아벨리의 『군주론』이 현대에 어떻게 받아들여졌는지 토론
            </div>
            <div class="chat_list">
              <div class="chat_item">
                <ul class="chat_util_list">
                  <li class="chat_util_item">
                    <a
                      href="#;"
                      class="chat_util_inn chat_util_copy"
                      aria-label=""
                    ></a>
                  </li>
                  <li class="chat_util_item">
                    <a
                      href="#;"
                      class="chat_util_inn chat_util_edit"
                      aria-label=""
                    ></a>
                  </li>
                </ul>
                <div class="chat">
                  마키아벨리의 『군주론』이 현대에 어떻게 받아들여졌는지 알려줘.
                </div>
              </div>
              <div
                class="answer_item trigger_wrap open"
                id="thinking_01_trigger_wrap"
              >
                <!--각 trigger ID_trigger_wrap/ID_trigger/ID_trigger_toggle 세트에 맞는 ID 맞춤 필요 -->
                <div class="thinking_wrap">
                  <img src="/img/icon/ic_thinking.svg" alt="" />
                  <a
                    href="#;"
                    class="thinking_txt trigger open"
                    id="thinking_01_trigger"
                    >생각하는 중
                  </a>
                </div>
                <div
                  class="trigger_toggle open"
                  id="thinking_01_trigger_toggle"
                >
                  <div class="answer_txt">
                    니콜로 마키아벨리(Niccolò Machiavelli)의 **《군주론(The
                    Prince)》**은 서양 정치철학사에서 가장 논쟁적이면서도 영향력
                    있는 고전 중 하나입니다. 1513년에 집필된 이 책은 이상적인
                    도덕보다 **'현실적인 권력의 획득과 유지'**에 초점을 맞춘
                    냉철한 정치 지침서입니다. 핵심 내용을 이해하기 쉽게 정리해
                    드리겠습니다.
                  </div>
                  <div class="con_line"></div>
                  <div class="answer_txt_list">
                    <div class="answer_txt_item">
                      <div class="txt_item_tit">
                        1. 집필 배경: 혼란스러운 이탈리아
                      </div>
                      <div class="answer_txt">
                        당시 이탈리아는 여러 도시 국가로 쪼개져 외세의 침략과
                        내부 분열로 매우 혼란스러운 상태였습니다. 마키아벨리는
                        강력한 군주가 나타나 이탈리아를 통일하고 안정을 되찾기를
                        간절히 원했습니다. 그는 피렌체의 지배자인 메디치
                        가문에게 자신을 등용해 달라는 목적(일종의
                        자기소개서)으로 이 책을 헌정했습니다.
                      </div>
                    </div>
                    <div class="answer_txt_item">
                      <div class="txt_item_tit">2. 《군주론》의 핵심 사상</div>
                      <div class="answer_txt">
                        마키아벨리는 정치를 종교나 도덕과 분리하여, **"권력은
                        어떻게 작동하는가"**를 있는 그대로 분석했습니다.
                      </div>
                      <ul class="numbered_list">
                        <li class="numbered_item">
                          <div class="numbered_item_tit">
                            ① 도덕적 이상보다 '현실적 유용성'
                          </div>
                          <div class="answer_txt">
                            <div class="fw_l mb_10">
                              "인간이 어떻게 살아야 하는가와 실제로 어떻게 살고
                              있는가는 매우 다르다."
                            </div>
                            그는 군주가 백성에게 착하고 도덕적인 사람으로 보이는
                            것은 좋지만, 실제로 항상 도덕적일 필요는 없다고
                            주장했습니다. 국가의 생존과 안정을 위해서라면
                            거짓말, 배신, 잔혹함도 **'필요악'**으로 사용할 수
                            있어야 한다고 보았습니다.
                          </div>
                        </li>
                        <li class="numbered_item">
                          <div class="numbered_item_tit">
                            ② 사자와 여우의 기질
                          </div>
                          <div class="answer_txt">
                            <div class="fw_l mb_10">
                              군주는 두 가지 야수의 기질을 모두 가져야 합니다.
                            </div>
                            <span class="fw_sb">- 사자:</span> 늑대(적)를 물리칠
                            수 있는 강력한 힘과 용기<br />
                            <span class="fw_sb">- 여우:</span> 함정을 알아채고
                            피할 수 있는 교활함과 지혜
                          </div>
                        </li>
                      </ul>
                    </div>
                  </div>
                </div>
              </div>
            </div>
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

useHead({ title: "채팅 형 | AI 도서정보 검색시스템" });
</script>
