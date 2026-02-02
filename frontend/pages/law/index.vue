<template>
  <!-- [S] skip menu -->
  <ul class="skip_menu">
    <li><a href="#contents_wrap">검색 바로가기</a></li>
  </ul>
  <!-- [E] skip menu -->

  <!-- [S] contents_wrap -->
  <div class="contents_wrap" id="contents_wrap">
    <!-- [S] left_menu_wrap -->
    <div class="left_menu_wrap" :class="{ open: hasSearched }">
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
                  <!-- 동적 히스토리 -->
                  <template v-if="searchHistory.length > 0">
                    <div v-for="(group, date) in groupedHistory" :key="date">
                      <div class="history_con_date">{{ date }}</div>
                      <ul class="history_con_list">
                        <li
                          v-for="item in group"
                          :key="item.id"
                          class="history_con_item"
                        >
                          <a
                            href="#;"
                            class="history_con_inn"
                            @click.prevent="loadHistoryQuery(item)"
                          >
                            <div class="txt" v-html="item.query"></div>
                            <button
                              class="ic_del"
                              aria-label="삭제"
                              @click.stop="deleteHistory(item.id)"
                            ></button>
                          </a>
                        </li>
                      </ul>
                    </div>
                  </template>

                  <!-- 기본 예시 -->
                  <template v-else>
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
                  </template>
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

    <!-- ========================================== -->
    <!-- 상태 1: 검색 전 (search_main_wrap) -->
    <!-- ========================================== -->
    <div v-if="!hasSearched" class="search_wrap search_main_wrap">
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
              v-model="searchQuery"
              @keyup.enter="handleSearch"
              type="text"
              title="검색어 입력"
              placeholder="질문을 입력해주세요."
              class="search_box_input"
            />
            <button
              class="search_box_btn"
              aria-label="검색"
              @click="handleSearch"
              :disabled="isSearching"
            ></button>
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
                <a
                  href="#;"
                  class="inn"
                  @click.prevent="
                    searchQuery =
                      '인간의 존엄성과 관련된 각 국의 헌법 조항 알려줘.';
                    handleSearch();
                  "
                >
                  <div class="item ellipsis line02">
                    인간의 존엄성과 관련된 각 국의 헌법 조항 알려줘.
                  </div>
                  <div class="arr"></div>
                </a>
              </li>
              <li class="question_example_item">
                <a
                  href="#;"
                  class="inn"
                  @click.prevent="
                    searchQuery =
                      '주요 국가 헌법 \'표현의 자유\' 조항 비교 해줘. (한국·미국·독일·일본 중심)';
                    handleSearch();
                  "
                >
                  <div class="item ellipsis line02">
                    주요 국가 헌법 '표현의 자유' 조항 비교 해줘.
                    <br />(한국·미국·독일·일본 중심)
                  </div>
                  <div class="arr"></div>
                </a>
              </li>
              <li class="question_example_item">
                <a
                  href="#;"
                  class="inn"
                  @click.prevent="
                    searchQuery = '주요 국가 헌법 비상사태 조항 비교 해줘.';
                    handleSearch();
                  "
                >
                  <div class="item ellipsis line02">
                    주요 국가 헌법 비상사태 조항 비교 해줘.
                  </div>
                  <div class="arr"></div>
                </a>
              </li>
              <li class="question_example_item">
                <a
                  href="#;"
                  class="inn"
                  @click.prevent="
                    searchQuery = '각 국 헌법의 대통령제 조항 비교 해줘.';
                    handleSearch();
                  "
                >
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

    <!-- ========================================== -->
    <!-- 상태 2/3: 검색 중 + 검색 결과 (search_result_wrap) -->
    <!-- ========================================== -->
    <div v-else class="search_wrap search_result_wrap open">
      <div class="search_wrap_hd">
        <div class="area"></div>
        <div
          class="member_util_wrap trigger_wrap"
          id="member_util_trigger_wrap2"
        >
          <a
            href="#;"
            class="trigger member_util_trigger"
            id="member_util_trigger2"
          >
            <img src="/img/icon/ic_member.svg" alt="" />최승환 님
          </a>
          <div
            class="trigger_toggle member_util_trigger_toggle"
            id="member_util_trigger_toggle2"
          >
            <div class="member_wrap">
              <div class="member_info">
                <div class="member_name">최승환 님</div>
                <div class="member_email">test0505@ajou.ac.kr</div>
              </div>
              <a href="#;" class="logout btn sz_md">
                <img src="/img/icon/ic_logout.svg" alt="" />로그아웃
              </a>
            </div>
            <ul class="member_util_list">
              <li class="member_util_item">
                <a href="#;" class="util_item_inn">
                  <span class="ic ic_bookmark"></span>
                  <span class="txt">내 즐겨찾기</span>
                </a>
              </li>
              <li class="member_util_item">
                <a href="#;" class="util_item_inn">
                  <span class="ic ic_history"></span>
                  <span class="txt">내 검색기록</span>
                </a>
              </li>
              <li
                class="member_util_item lang_trigger_wrap trigger_wrap"
                id="lang_trigger_wrap2"
              >
                <a href="#;" class="util_item_inn trigger" id="lang_trigger2">
                  <span class="ic ic_lang"></span>
                  <span class="txt"
                    >표시언어: <span class="fw_b lang">한국어</span></span
                  >
                </a>
                <div
                  class="trigger_toggle lang_trigger_toggle"
                  id="lang_trigger_toggle2"
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
                    data-target="lang_trigger2"
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
          <div class="search_q_tit">{{ currentSearchQuery }}</div>

          <!-- 로딩 중 -->
          <div v-if="isSearching" class="loading_wrap">
            <div class="circle_wrap">
              <img src="/img/icon/ic_ing.gif" alt="" class="circle_img" />
            </div>
            <div class="loading_txt">답변 생성 중 입니다...</div>
          </div>

          <!-- 검색 결과 -->
          <div v-else-if="searchResult" class="list_answer_list">
            <!-- 요약 -->
            <div v-if="searchResult.summary" class="list_answer_item">
              <div class="con_tit ty_02 mb_25i">
                <img src="/img/icon/ic_summary.svg" alt="" class="ic" />질의
                요약
              </div>
              <div class="summary_txt">{{ searchResult.summary }}</div>
            </div>

            <!-- 국가 선택 + PDF 뷰어 -->
            <div class="list_answer_item">
              <div class="con_tit ty_02 mb_15i">
                <img src="/img/icon/ic_country.svg" alt="" class="ic" />국가선택
              </div>

              <!-- 탭 (대륙별) -->
              <div class="sc_tab_wrap">
                <div class="sc_tab_btn_wrap">
                  <a
                    href="#;"
                    class="tab_btn"
                    :class="{ on: selectedContinent === 'korea' }"
                    data-target="#panel_korea"
                    @click.prevent="selectedContinent = 'korea'"
                    >대한민국</a
                  >
                  <a
                    href="#;"
                    class="tab_btn"
                    :class="{ on: selectedContinent === 'asia' }"
                    data-target="#panel_asia"
                    @click.prevent="selectedContinent = 'asia'"
                    >아시아</a
                  >
                  <a
                    href="#;"
                    class="tab_btn"
                    :class="{ on: selectedContinent === 'europe' }"
                    data-target="#panel_europe"
                    @click.prevent="selectedContinent = 'europe'"
                    >유럽</a
                  >
                  <a
                    href="#;"
                    class="tab_btn"
                    :class="{ on: selectedContinent === 'africa' }"
                    data-target="#panel_africa"
                    @click.prevent="selectedContinent = 'africa'"
                    >아프리카</a
                  >
                  <a
                    href="#;"
                    class="tab_btn"
                    :class="{ on: selectedContinent === 'oceania' }"
                    data-target="#panel_oceania"
                    @click.prevent="selectedContinent = 'oceania'"
                    >오세아니아</a
                  >
                </div>

                <div class="sc_tab_con_wrap">
                  <!-- 대한민국 (항상 표시) -->
                  <div
                    class="sc_menu_wrap"
                    :class="{ on: selectedContinent === 'korea' }"
                    id="panel_korea"
                  >
                    <div class="sc_menu">
                      <a
                        href="#;"
                        class="sc_menu_item"
                        @click.prevent="selectedForeignCountry = null"
                      >
                        <span class="inn_txt">대한민국</span>
                        <span class="flag"
                          ><img src="/img/sub/img_flag.svg" alt=""
                        /></span>
                      </a>
                    </div>
                  </div>

                  <!-- 아시아 -->
                  <div
                    class="sc_menu_wrap"
                    :class="{ on: selectedContinent === 'asia' }"
                    id="panel_asia"
                  >
                    <div class="sc_menu">
                      <a
                        v-for="country in getCountriesByContinent('asia')"
                        :key="country.code"
                        href="#;"
                        class="sc_menu_item"
                        :class="{ on: selectedForeignCountry === country.code }"
                        @click.prevent="selectedForeignCountry = country.code"
                      >
                        <span class="txt_underline"
                          ><span class="inn_txt">{{ country.name }}</span></span
                        >
                        <span class="flag"
                          ><img src="/img/sub/img_flag.svg" alt=""
                        /></span>
                      </a>
                    </div>
                  </div>

                  <!-- 유럽 -->
                  <div
                    class="sc_menu_wrap"
                    :class="{ on: selectedContinent === 'europe' }"
                    id="panel_europe"
                  >
                    <div class="sc_menu">
                      <a
                        v-for="country in getCountriesByContinent('europe')"
                        :key="country.code"
                        href="#;"
                        class="sc_menu_item"
                        :class="{ on: selectedForeignCountry === country.code }"
                        @click.prevent="selectedForeignCountry = country.code"
                      >
                        <span class="txt_underline"
                          ><span class="inn_txt">{{ country.name }}</span></span
                        >
                        <span class="flag"
                          ><img src="/img/sub/img_flag.svg" alt=""
                        /></span>
                      </a>
                    </div>
                  </div>

                  <!-- 아프리카 -->
                  <div
                    class="sc_menu_wrap"
                    :class="{ on: selectedContinent === 'africa' }"
                    id="panel_africa"
                  >
                    <div class="sc_menu">
                      <a
                        v-for="country in getCountriesByContinent('africa')"
                        :key="country.code"
                        href="#;"
                        class="sc_menu_item"
                        :class="{ on: selectedForeignCountry === country.code }"
                        @click.prevent="selectedForeignCountry = country.code"
                      >
                        <span class="txt_underline"
                          ><span class="inn_txt">{{ country.name }}</span></span
                        >
                        <span class="flag"
                          ><img src="/img/sub/img_flag.svg" alt=""
                        /></span>
                      </a>
                    </div>
                  </div>

                  <!-- 오세아니아 -->
                  <div
                    class="sc_menu_wrap"
                    :class="{ on: selectedContinent === 'oceania' }"
                    id="panel_oceania"
                  >
                    <div class="sc_menu">
                      <a
                        v-for="country in getCountriesByContinent('oceania')"
                        :key="country.code"
                        href="#;"
                        class="sc_menu_item"
                        :class="{ on: selectedForeignCountry === country.code }"
                        @click.prevent="selectedForeignCountry = country.code"
                      >
                        <span class="txt_underline"
                          ><span class="inn_txt">{{ country.name }}</span></span
                        >
                        <span class="flag"
                          ><img src="/img/sub/img_flag.svg" alt=""
                        /></span>
                      </a>
                    </div>
                  </div>
                </div>
              </div>

              <!-- PDF 뷰어 (좌우 비교) -->
              <div class="pdf_view_wrap">
                <div class="half">
                  <div class="pdf_view_tit">
                    <img src="/img/icon/ic_pdf.svg" alt="" />대한민국 헌법
                  </div>
                  <div class="pdf_view_con">
                    <div class="pdf_view_inn">
                      <!-- 한국 헌법 결과 -->
                      <div
                        v-for="(result, idx) in koreanResults"
                        :key="`kr-${idx}`"
                        style="padding: 15px; border-bottom: 1px solid #eee"
                      >
                        <div
                          style="
                            font-weight: bold;
                            color: #2563eb;
                            margin-bottom: 8px;
                          "
                        >
                          {{ result.structure.article_number || "조항" }}
                          <span
                            v-if="result.structure.chapter_title"
                            style="
                              font-size: 0.9em;
                              color: #666;
                              margin-left: 8px;
                            "
                          >
                            {{ result.structure.chapter_title }}
                          </span>
                        </div>
                        <div style="line-height: 1.6">
                          {{ result.korean_text || result.english_text }}
                        </div>
                        <div
                          style="
                            margin-top: 8px;
                            font-size: 0.85em;
                            color: #999;
                          "
                        >
                          유사도: {{ (result.score * 100).toFixed(1) }}% |
                          페이지: {{ result.page }}
                        </div>
                      </div>
                      <div
                        v-if="koreanResults.length === 0"
                        style="padding: 40px; text-align: center; color: #999"
                      >
                        검색 결과가 없습니다.
                      </div>
                    </div>
                  </div>
                </div>
                <div class="half">
                  <div class="pdf_view_tit">
                    <img src="/img/icon/ic_pdf.svg" alt="" />나라별 헌법({{
                      selectedCountryName
                    }})
                  </div>
                  <div class="pdf_view_con">
                    <div class="pdf_view_inn">
                      <!-- 외국 헌법 결과 -->
                      <div
                        v-for="(result, idx) in displayedForeignResults"
                        :key="`foreign-${idx}`"
                        style="padding: 15px; border-bottom: 1px solid #eee"
                      >
                        <div
                          style="
                            font-weight: bold;
                            color: #2563eb;
                            margin-bottom: 8px;
                          "
                        >
                          {{ result.structure.article_number || "Article" }}
                          <span
                            v-if="result.structure.chapter_title"
                            style="
                              font-size: 0.9em;
                              color: #666;
                              margin-left: 8px;
                            "
                          >
                            {{ result.structure.chapter_title }}
                          </span>
                        </div>
                        <div style="line-height: 1.6">
                          <div
                            v-if="result.has_korean"
                            style="margin-bottom: 8px"
                          >
                            {{ result.korean_text }}
                          </div>
                          <div
                            v-if="result.has_english"
                            style="color: #666; font-size: 0.95em"
                          >
                            {{ result.english_text }}
                          </div>
                        </div>
                        <div
                          style="
                            margin-top: 8px;
                            font-size: 0.85em;
                            color: #999;
                          "
                        >
                          유사도: {{ (result.score * 100).toFixed(1) }}% |
                          페이지: {{ result.page }}
                        </div>
                      </div>
                      <div
                        v-if="displayedForeignResults.length === 0"
                        style="padding: 40px; text-align: center; color: #999"
                      >
                        검색 결과가 없습니다.sdsd
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 유틸 버튼 -->
              <ul class="summary_util_list">
                <li class="summary_util_item">
                  <a
                    href="#;"
                    class="summary_util_inn util_good"
                    aria-label="좋아요"
                  ></a>
                </li>
                <li class="summary_util_item">
                  <a
                    href="#;"
                    class="summary_util_inn util_bad"
                    aria-label="싫어요"
                  ></a>
                </li>
                <li class="summary_util_item">
                  <a
                    href="#;"
                    class="summary_util_inn util_refresh"
                    aria-label="새로고침"
                    @click.prevent="handleSearch"
                  ></a>
                </li>
                <li class="summary_util_item">
                  <a
                    href="#;"
                    class="summary_util_inn util_copy"
                    aria-label="복사"
                  ></a>
                </li>
                <li class="summary_util_item">
                  <a
                    href="#;"
                    class="summary_util_inn util_more"
                    aria-label="더보기"
                  ></a>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>

      <!-- 하단 검색바 -->
      <div class="search_box_wrap">
        <div class="search_box">
          <div
            class="trigger_wrap search_condition_trigger_wrap"
            id="search_condition_trigger_wrap3"
          >
            <a
              href="#;"
              aria-label="검색 조건 설정"
              class="trigger search_condition_trigger"
              id="search_condition_trigger3"
            ></a>
            <div
              class="trigger_toggle search_condition_trigger_toggle"
              id="search_condition_trigger_toggle3"
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
                  <input type="checkbox" name="" id="online2" />
                  <label for="online2">온라인 이용가능</label>
                </div>
              </div>
            </div>
          </div>
          <input
            v-model="searchQuery"
            @keyup.enter="handleSearch"
            type="text"
            title="검색어 입력"
            placeholder="질문을 입력해주세요."
            class="search_box_input"
          />
          <button
            class="search_box_btn"
            aria-label="검색"
            @click="handleSearch"
            :disabled="isSearching"
          ></button>
        </div>
      </div>
    </div>
  </div>
  <!-- [E] contents_wrap -->
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from "vue";

definePageMeta({
  layout: false,
});

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

// ==================== 상태 관리 ====================
const searchQuery = ref("");
const currentSearchQuery = ref("");
const hasSearched = ref(false);
const isSearching = ref(false);
const searchResult = ref(null);
const searchHistory = ref([]);
const selectedContinent = ref("africa"); // 기본값
const selectedForeignCountry = ref(null);

// ==================== Computed ====================
const groupedHistory = computed(() => {
  const groups = {};
  searchHistory.value.forEach((item) => {
    const date = formatDate(item.timestamp);
    if (!groups[date]) groups[date] = [];
    groups[date].push(item);
  });
  return groups;
});

const koreanResults = computed(() => {
  return searchResult.value?.korean_results || [];
});

const foreignResults = computed(() => {
  return searchResult.value?.foreign_results || [];
});

const foreignCountries = computed(() => {
  const countryMap = new Map();
  foreignResults.value.forEach((result) => {
    if (!countryMap.has(result.country)) {
      countryMap.set(result.country, {
        code: result.country,
        name: result.country_name,
        continent: result.continent || "asia",
      });
    }
  });
  return Array.from(countryMap.values());
});

const displayedForeignResults = computed(() => {
  if (!selectedForeignCountry.value) {
    if (foreignCountries.value.length > 0) {
      selectedForeignCountry.value = foreignCountries.value[0].code;
    }
    return [];
  }
  return foreignResults.value.filter(
    (result) => result.country === selectedForeignCountry.value,
  );
});

const selectedCountryName = computed(() => {
  const country = foreignCountries.value.find(
    (c) => c.code === selectedForeignCountry.value,
  );
  return country ? country.name : "외국";
});

function getCountriesByContinent(continent) {
  return foreignCountries.value.filter((c) => c.continent === continent);
}

// ==================== API 호출 ====================
async function handleSearch() {
  if (!searchQuery.value.trim() || isSearching.value) return;

  currentSearchQuery.value = searchQuery.value;
  hasSearched.value = true;
  isSearching.value = true;

  try {
    const config = useRuntimeConfig();
    const apiBase = config.public.apiBase || "/api";

    const response = await $fetch(
      `${apiBase}/constitution/comparative-search`,
      {
        method: "POST",
        body: {
          query: searchQuery.value,
          korean_top_k: 3,
          foreign_top_k: 10,
          generate_summary: true,
        },
      },
    );

    searchResult.value = response;
    addToHistory(searchQuery.value);

    // 첫 번째 외국 국가 자동 선택
    if (foreignCountries.value.length > 0) {
      selectedForeignCountry.value = foreignCountries.value[0].code;
      // 해당 국가의 대륙으로 탭 자동 전환
      const firstCountry = foreignCountries.value[0];
      selectedContinent.value = firstCountry.continent;
    }
  } catch (error) {
    console.error("검색 실패:", error);
    alert("검색 중 오류가 발생했습니다. 다시 시도해주세요.");
  } finally {
    isSearching.value = false;
  }
}

// ==================== 히스토리 관리 ====================
function addToHistory(query) {
  const newItem = {
    id: Date.now(),
    query: query,
    timestamp: new Date().toISOString(),
  };
  searchHistory.value.unshift(newItem);
  if (searchHistory.value.length > 50) {
    searchHistory.value = searchHistory.value.slice(0, 50);
  }
  saveHistoryToStorage();
}

function loadHistoryQuery(item) {
  searchQuery.value = item.query;
  handleSearch();
}

function deleteHistory(id) {
  searchHistory.value = searchHistory.value.filter((item) => item.id !== id);
  saveHistoryToStorage();
}

function saveHistoryToStorage() {
  if (typeof window !== "undefined") {
    localStorage.setItem(
      "constitution_search_history",
      JSON.stringify(searchHistory.value),
    );
  }
}

function loadHistoryFromStorage() {
  if (typeof window !== "undefined") {
    const stored = localStorage.getItem("constitution_search_history");
    if (stored) {
      try {
        searchHistory.value = JSON.parse(stored);
      } catch (e) {
        console.error("히스토리 로드 실패:", e);
      }
    }
  }
}

// ==================== 유틸리티 ====================
function formatDate(timestamp) {
  const date = new Date(timestamp);
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  if (date.toDateString() === today.toDateString()) return "오늘";
  if (date.toDateString() === yesterday.toDateString()) return "어제";
  return `${date.getMonth() + 1}월 ${date.getDate()}일`;
}

// ==================== 기존 퍼블리싱 스크립트 ====================
let cleanupFns = [];

onMounted(() => {
  loadHistoryFromStorage();

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
      return (
        menu.closest(".list_answer_item") ||
        menu.closest(".left_menu_wrap") ||
        menu.parentElement ||
        document
      );
    }

    function getConWrap(menu, container) {
      const next = menu.nextElementSibling;
      if (next && next.classList && next.classList.contains("tab_con_wrap"))
        return next;
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

      $$(".tab_link", menu).forEach((a) => a.classList.remove("on"));
      $$(".hidden", menu).forEach((n) => n.remove());

      tabLink.classList.add("on");
      const hidden = document.createElement("span");
      hidden.className = "hidden";
      hidden.textContent = "현재 선택됨";
      const inn = tabLink.querySelector(".inn") || tabLink;
      inn.appendChild(hidden);

      $$(".tab_con", conWrap).forEach((c) => c.classList.remove("on"));
      targetCon.classList.add("on");
    }

    on(document, "click", ".tab_link", function (e, tabLink) {
      e.preventDefault();
      setTabActive(tabLink);
    });

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

    on(document, "click", ".trigger_close", function (e, btn) {
      e.preventDefault();
      const targetId = btn.getAttribute("data-target");
      if (!targetId) return;
      const target = document.getElementById(targetId);
      if (target) target.click();
    });

    on(document, "click", ".left_menu_trigger", function (_e, trigger) {
      const targets = $$(".left_menu_wrap, .search_wrap");
      targets.forEach((t) => t.classList.toggle("open"));
      const isOpen = targets[0] ? targets[0].classList.contains("open") : false;
      trigger.setAttribute("aria-label", isOpen ? "메뉴 닫힘" : "메뉴 열림");
    });

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

    const tabButtons = $$(".tab_btn");
    tabButtons.forEach((button) => {
      const click = () => {
        const sel = button.getAttribute("data-target");
        const targetTab = sel ? document.querySelector(sel) : null;
        if (!targetTab) return;

        tabButtons.forEach((b) => b.classList.remove("on"));
        button.classList.add("on");

        tabs.forEach((tab) => tab.classList.remove("on"));
        targetTab.classList.add("on");

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

    const scMenuItemClick = function (e) {
      const item = e.target.closest(".sc_menu_item");
      if (!item) return;
      e.preventDefault();
      const menu = item.closest(".sc_menu");
      if (!menu) return;
      menu.querySelectorAll(".sc_menu_item.on").forEach((el) => {
        el.classList.remove("on");
      });
      item.classList.add("on");
    };
    document.addEventListener("click", scMenuItemClick);
    cleanupFns.push(() =>
      document.removeEventListener("click", scMenuItemClick),
    );

    window.open_layer_pop = function (pop) {
      setTimeout(function () {
        const popEl = document.getElementById(pop);
        if (!popEl) return;
        document.body.style.overflow = "hidden";
        const dim = popEl.closest(".dim");
        if (dim) dim.style.display = "block";
      }, 50);
    };

    on(document, "click", ".pop_close", function (e, btn) {
      e.preventDefault();
      document.body.style.overflow = "visible";
      const dim = btn.closest(".dim");
      if (dim) dim.style.display = "none";
    });

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
    } catch {}
  });
  cleanupFns = [];

  if (typeof window !== "undefined") {
    delete window.fn_del;
    delete window.open_layer_pop;
  }
});
</script>
