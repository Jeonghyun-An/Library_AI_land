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
          <div class="list_answer_list">
            <div class="list_answer_item">
              <div class="con_tit ty_02">
                <img src="/img/icon/ic_source.svg" alt="" class="ic" />출처
              </div>
              <ul class="source_list tab_menu">
                <li
                  class="source_item tab_item tab_link"
                  data-tab="info_con_01"
                >
                  <a href="#;" class="source_inn inn">
                    <div class="num_wrap"><span class="num">1</span> 도서</div>
                    <div class="tit ellipsis line02">군주론</div>
                    <div class="info">니콜로 마키아벨리 2008</div>
                  </a>
                </li>
                <li
                  class="source_item tab_item tab_link"
                  data-tab="info_con_02"
                >
                  <a href="#;" class="source_inn inn">
                    <div class="num_wrap">
                      <span class="num">2</span>
                      도서
                    </div>
                    <div class="tit ellipsis line02">
                      마키아벨리의 "시민형 군주" 사상과 현대대통령제의
                      마키아벨리의 "시민형 군주" 사상과 현대대통령제의
                    </div>
                    <div class="info">니콜로 마키아벨리 2008</div>
                  </a>
                </li>
                <li
                  class="source_item tab_item tab_link"
                  data-tab="info_con_03"
                >
                  <a href="#;" class="source_inn inn">
                    <div class="num_wrap">
                      <span class="num">3</span>
                      도서
                    </div>
                    <div class="tit ellipsis line02">군주론</div>
                    <div class="info">니콜로 마키아벨리 2008</div>
                  </a>
                </li>
                <li
                  class="source_item tab_item tab_link"
                  data-tab="info_con_04"
                >
                  <a href="#;" class="source_inn inn">
                    <div class="num_wrap">
                      <span class="num">4</span>
                      도서
                    </div>
                    <div class="tit ellipsis line02">군주론</div>
                    <div class="info">니콜로 마키아벨리 2008</div>
                  </a>
                </li>
                <li
                  class="source_item tab_item tab_link"
                  data-tab="info_con_05"
                >
                  <a href="#;" class="source_inn inn">
                    <div class="num_wrap">
                      <span class="num">5</span>
                      도서
                    </div>
                    <div class="tit ellipsis line02">군주론</div>
                    <div class="info">니콜로 마키아벨리 2008</div>
                  </a>
                </li>
                <li class="source_item">
                  <a href="#;" class="source_inn inn view_more"></a>
                </li>
              </ul>
              <div class="tab_con_wrap source_info_list">
                <div class="tab_con info_con_01">
                  <div class="source_info_wrap">
                    <div class="source_info_tit">군주론</div>
                    <div class="source_info_info">니콜로 마키아벨리 2008</div>
                    <div class="source_info_txt">
                      <div class="mb_5 fw_sb">초록 링크 :</div>
                      본 논문의 일차적 목표는 공화주의에서 윤리교육의 근거를
                      찾아보는데 있다. 윤리교육의 근거라는 것은 ‘윤리교육이 왜
                      필요할까?’에 대한 설득력 있는 답변을 제공하는 것이다.
                      ‘윤리’란어린아이부터 어른들까지의 모든 사람들이 자신이
                      지니고 있는 ‘자유’를 자신의 행위에 연결하고 적용시키는
                      ‘옳고 그름에 관한 삶의 지혜와 기술’라고 볼 수 있다. 우리는
                      자유주의와 민주주의라는 가치를 영유하고 있지만 시장과
                      자본이 주도하는 현대 사회에서 우리를 진정한 자유와 의미
                      있는 즐거움으로 이끌어주는 윤리라는 예술을 잃어버리고
                      자본과 권력에 ‘예속’된 삶을 살아가고 있다. 그래서
                      역설적으로 우리를 자유로 이끌어 주는 윤리와 윤리교육이
                      더욱 더 요청된다고 볼 수 있다. 논문의 전개 순서는 다음과
                      같다. 우선 공화주의의 기원으로서 아리스토텔레스와 키케로의
                      사상을 살펴보고, 마키아벨리, 해링턴, 몽테스키외, 루소,
                      칸트의 근대적 공화주의를 간략하게 정리하며, 최근 들어
                      ‘신아테네적 입장’을 펼치는 마이클 샌델과 ‘신로마적 입장’을
                      펼치는 필립 페팃과 모리치오 비롤리의 공화주의 이론을
                      고찰한다. 나아가 공화주의 이론이 제시하는 자유의 의미와
                      시민윤리에 입각하여 학교의 도덕?윤리교육에 다루어야 할
                      내용을 살펴본다. 마지막으로 필자는 자의적 권력에 노출되어
                      공포에 떠는 노예가 아니라 존엄함을 가지고 자기의 주인으로
                      살기 위해, 즉 ‘자유롭게 살기 위해’ 시민의 덕성이 필요하고,
                      윤리교육은 바로 그러한 시민의 덕성을 길러줄 수 있기 때문에
                      존립의 근거를 확보한다고 주장한다.
                    </div>
                    <div class="source_info_btn_wrap">
                      <a href="#;" class="btn sz_md bg_black"
                        >모든 상세정보 보기</a
                      >
                      <ul class="summary_util_list">
                        <li class="summary_util_item">
                          <a
                            href=""
                            class="summary_util_inn util_good"
                            aria-label="좋아요"
                          ></a>
                        </li>
                        <li class="summary_util_item">
                          <a
                            href=""
                            class="summary_util_inn util_bad"
                            aria-label="싫어요"
                          ></a>
                        </li>
                      </ul>
                    </div>
                    <a href="#;" class="tab_close"></a>
                  </div>
                </div>
                <div class="tab_con info_con_02">
                  <div class="source_info_wrap">
                    <a href="#;" class="tab_close"></a>
                  </div>
                </div>
                <div class="tab_con info_con_03">
                  <div class="source_info_wrap">
                    <a href="#;" class="tab_close"></a>
                  </div>
                </div>
                <div class="tab_con info_con_04">
                  <div class="source_info_wrap">
                    <a href="#;" class="tab_close"></a>
                  </div>
                </div>
                <div class="tab_con info_con_05">
                  <div class="source_info_wrap">
                    <a href="#;" class="tab_close"></a>
                  </div>
                </div>
              </div>
            </div>
            <div class="list_answer_item">
              <div class="con_tit ty_02">
                <img src="/img/icon/ic_summary.svg" alt="" class="ic" />개요
              </div>
              <div class="summary_txt">
                마키아벨리의 『군주론』은 출간 당시 유럽 사회에 큰 충격을
                주었으며, 절대 권력을 얻기 위한 무자비한 책략을 옹호하고 전통적
                도덕을 무시한다는 점에서 악마의 대리인으로 간주되기도 하였다.
                그러나 현대에 이르러서 는 단순히 전제정치를 찬양한 책으로만
                해석되지 않고, 정치 생활과 판단의 복잡성과 유동성을 강조하며
                보편적인 정치 규칙이 없음을 가르친 현실 정치의 경전으로
                받아들여지고 있다.
                <a
                  href="#;"
                  class="source_marker"
                  data-tab="info_con_01"
                  aria-label="출처: 군주론"
                  >1</a
                >
                <a
                  href="#;"
                  class="source_marker"
                  data-tab="info_con_04"
                  aria-label="출처: 군주론"
                  >4</a
                >
                <br /><br />
                마키아벨리의 『군주론』은 출간 당시 유럽 사회에 큰 충격을
                주었으며, 절대 권력을 얻기 위한 무자비한 책략을 옹호하고 전통적
                도덕을 무시한다는 점에서 악마의 대리인으로 간주되기도 하였다.
                그러나 현대에 이르러서 는 단순히 전제정치를 찬양한 책으로만
                해석되지 않고, 정치 생활과 판단의 복잡성과 유동성을 강조하며
                보편적인 정치 규칙이 없음을 가르친 현실 정치의 경전으로
                받아들여지고 있다.
                <a
                  href="#;"
                  class="source_marker"
                  data-tab="info_con_02"
                  aria-label="출처: 군주론"
                  >2</a
                >
              </div>
              <ul class="summary_util_list">
                <li class="summary_util_item">
                  <a
                    href=""
                    class="summary_util_inn util_good"
                    aria-label="좋아요"
                  ></a>
                </li>
                <li class="summary_util_item">
                  <a
                    href=""
                    class="summary_util_inn util_bad"
                    aria-label="싫어요"
                  ></a>
                </li>
                <li class="summary_util_item">
                  <a
                    href=""
                    class="summary_util_inn util_refresh"
                    aria-label="새로고침"
                  ></a>
                </li>
                <li class="summary_util_item">
                  <a
                    href=""
                    class="summary_util_inn util_copy"
                    aria-label="복사"
                  ></a>
                </li>
                <li class="summary_util_item">
                  <a
                    href=""
                    class="summary_util_inn util_more"
                    aria-label="더보기"
                  ></a>
                </li>
              </ul>
            </div>
            <div class="list_answer_item">
              <div class="con_tit ty_02">관련된 연구 질문</div>
              <div class="related_question_list">
                <div class="related_question_item">
                  <a href="#;" class="related_question_inn"
                    ><span class="txt"
                      >임상시험에서 인종 및 성별 다양성 증진 방법</span
                    ></a
                  >
                </div>
                <div class="related_question_item">
                  <a href="#;" class="related_question_inn"
                    ><span class="txt"
                      >임상시험에서 인종 및 성별 다양성 증진 방법</span
                    ></a
                  >
                </div>
                <div class="related_question_item">
                  <a href="#;" class="related_question_inn"
                    ><span class="txt"
                      >임상시험에서 인종 및 성별 다양성 증진 방법</span
                    ></a
                  >
                </div>
                <div class="related_question_item">
                  <a href="#;" class="related_question_inn"
                    ><span class="txt"
                      >임상시험에서 인종 및 성별 다양성 증진 방법임상시험에서
                      인종 및 성별 다양성 증진 방법임상시험에서 인종 및 성별
                      다양성 증진 방법</span
                    ></a
                  >
                </div>
                <div class="related_question_item">
                  <a href="#;" class="related_question_inn"
                    ><span class="txt"
                      >임상시험에서 인종 및 성별 다양성 증진 방법</span
                    ></a
                  >
                </div>
              </div>
            </div>
            <div class="list_answer_item">
              <div class="con_tit ty_02">추천도서</div>
              <div class="recommended_book_list">
                <div class="recommended_book_item">
                  <a
                    href="#;"
                    class="recommended_book_inn"
                    onclick="open_layer_pop('pop_book')"
                  >
                    <div class="wrap">
                      <div class="tit_wrap">
                        <div class="ctg">도서</div>
                        <div class="tit ellipsis">군주론</div>
                      </div>
                      <div class="con_wrap">
                        <div class="img_wrap">
                          <img src="/img/layout/img_book.jpg" alt="" />
                        </div>
                        <div class="txt_con_list">
                          <div class="txt_con_item">
                            <div class="txt_con_tit">표제/저자사항</div>
                            <div class="txt_con_txt ellipsis line02">
                              군주론 / 니콜로 마키아벨리 지음 ; 권혁 옮김
                              Machiavelli, Niccoló[1469-1527] 권혁
                            </div>
                          </div>
                          <div class="txt_con_item">
                            <div class="txt_con_tit">판사항</div>
                            <div class="txt_con_txt ellipsis">개정2판</div>
                          </div>
                          <div class="txt_con_item">
                            <div class="txt_con_tit">발행사항</div>
                            <div class="txt_con_txt ellipsis">
                              고양 : 돋을새김, 2025
                            </div>
                          </div>
                          <div class="txt_con_item">
                            <div class="txt_con_tit">형태사항</div>
                            <div class="txt_con_txt ellipsis">
                              312 p. : 삽화, 초상 ; 21 cm
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </a>
                </div>
                <div class="recommended_book_item">
                  <a
                    href="#;"
                    class="recommended_book_inn"
                    onclick="open_layer_pop('pop_book')"
                  >
                    <div class="wrap">
                      <div class="tit_wrap">
                        <div class="ctg">도서</div>
                        <div class="tit ellipsis">군주론</div>
                      </div>
                      <div class="con_wrap">
                        <div class="img_wrap">
                          <img src="/img/layout/img_book.jpg" alt="" />
                        </div>
                        <div class="txt_con_list">
                          <div class="txt_con_item">
                            <div class="txt_con_tit">표제/저자사항</div>
                            <div class="txt_con_txt ellipsis line02">
                              군주론 / 니콜로 마키아벨리 지음 ; 권혁 옮김
                              Machiavelli, Niccoló[1469-1527] 권혁
                            </div>
                          </div>
                          <div class="txt_con_item">
                            <div class="txt_con_tit">판사항</div>
                            <div class="txt_con_txt ellipsis">개정2판</div>
                          </div>
                          <div class="txt_con_item">
                            <div class="txt_con_tit">발행사항</div>
                            <div class="txt_con_txt ellipsis">
                              고양 : 돋을새김, 2025
                            </div>
                          </div>
                          <div class="txt_con_item">
                            <div class="txt_con_tit">형태사항</div>
                            <div class="txt_con_txt ellipsis">
                              312 p. : 삽화, 초상 ; 21 cm
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </a>
                </div>
                <div class="recommended_book_item">
                  <a
                    href="#;"
                    class="recommended_book_inn"
                    onclick="open_layer_pop('pop_book')"
                  >
                    <div class="wrap">
                      <div class="tit_wrap">
                        <div class="ctg">도서</div>
                        <div class="tit ellipsis">군주론</div>
                      </div>
                      <div class="con_wrap">
                        <div class="img_wrap">
                          <img src="/img/layout/img_book.jpg" alt="" />
                        </div>
                        <div class="txt_con_list">
                          <div class="txt_con_item">
                            <div class="txt_con_tit">표제/저자사항</div>
                            <div class="txt_con_txt ellipsis line02">
                              군주론 / 니콜로 마키아벨리 지음 ; 권혁 옮김
                              Machiavelli, Niccoló[1469-1527] 권혁
                            </div>
                          </div>
                          <div class="txt_con_item">
                            <div class="txt_con_tit">판사항</div>
                            <div class="txt_con_txt ellipsis">개정2판</div>
                          </div>
                          <div class="txt_con_item">
                            <div class="txt_con_tit">발행사항</div>
                            <div class="txt_con_txt ellipsis">
                              고양 : 돋을새김, 2025
                            </div>
                          </div>
                          <div class="txt_con_item">
                            <div class="txt_con_tit">형태사항</div>
                            <div class="txt_con_txt ellipsis">
                              312 p. : 삽화, 초상 ; 21 cm
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </a>
                </div>
                <div class="recommended_book_item">
                  <a
                    href="#;"
                    class="recommended_book_inn"
                    onclick="open_layer_pop('pop_book')"
                  >
                    <div class="wrap">
                      <div class="tit_wrap">
                        <div class="ctg">도서</div>
                        <div class="tit ellipsis">군주론</div>
                      </div>
                      <div class="con_wrap">
                        <div class="img_wrap">
                          <img src="/img/layout/img_book.jpg" alt="" />
                        </div>
                        <div class="txt_con_list">
                          <div class="txt_con_item">
                            <div class="txt_con_tit">표제/저자사항</div>
                            <div class="txt_con_txt ellipsis line02">
                              군주론 / 니콜로 마키아벨리 지음 ; 권혁 옮김
                              Machiavelli, Niccoló[1469-1527] 권혁
                            </div>
                          </div>
                          <div class="txt_con_item">
                            <div class="txt_con_tit">판사항</div>
                            <div class="txt_con_txt ellipsis">개정2판</div>
                          </div>
                          <div class="txt_con_item">
                            <div class="txt_con_tit">발행사항</div>
                            <div class="txt_con_txt ellipsis">
                              고양 : 돋을새김, 2025
                            </div>
                          </div>
                          <div class="txt_con_item">
                            <div class="txt_con_tit">형태사항</div>
                            <div class="txt_con_txt ellipsis">
                              312 p. : 삽화, 초상 ; 21 cm
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </a>
                </div>
                <div class="recommended_book_item">
                  <a
                    href="#;"
                    class="recommended_book_inn"
                    onclick="open_layer_pop('pop_book')"
                  >
                    <div class="wrap">
                      <div class="tit_wrap">
                        <div class="ctg">도서</div>
                        <div class="tit ellipsis">군주론</div>
                      </div>
                      <div class="con_wrap">
                        <div class="img_wrap">
                          <img src="/img/layout/img_book.jpg" alt="" />
                        </div>
                        <div class="txt_con_list">
                          <div class="txt_con_item">
                            <div class="txt_con_tit">표제/저자사항</div>
                            <div class="txt_con_txt ellipsis line02">
                              군주론 / 니콜로 마키아벨리 지음 ; 권혁 옮김
                              Machiavelli, Niccoló[1469-1527] 권혁
                            </div>
                          </div>
                          <div class="txt_con_item">
                            <div class="txt_con_tit">판사항</div>
                            <div class="txt_con_txt ellipsis">개정2판</div>
                          </div>
                          <div class="txt_con_item">
                            <div class="txt_con_tit">발행사항</div>
                            <div class="txt_con_txt ellipsis">
                              고양 : 돋을새김, 2025
                            </div>
                          </div>
                          <div class="txt_con_item">
                            <div class="txt_con_tit">형태사항</div>
                            <div class="txt_con_txt ellipsis">
                              312 p. : 삽화, 초상 ; 21 cm
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </a>
                </div>
                <div class="recommended_book_item">
                  <a
                    href="#;"
                    class="recommended_book_inn"
                    onclick="open_layer_pop('pop_book')"
                  >
                    <div class="wrap">
                      <div class="tit_wrap">
                        <div class="ctg">도서</div>
                        <div class="tit ellipsis">군주론</div>
                      </div>
                      <div class="con_wrap">
                        <div class="img_wrap">
                          <img src="/img/layout/img_book.jpg" alt="" />
                        </div>
                        <div class="txt_con_list">
                          <div class="txt_con_item">
                            <div class="txt_con_tit">표제/저자사항</div>
                            <div class="txt_con_txt ellipsis line02">
                              군주론 / 니콜로 마키아벨리 지음 ; 권혁 옮김
                              Machiavelli, Niccoló[1469-1527] 권혁
                            </div>
                          </div>
                          <div class="txt_con_item">
                            <div class="txt_con_tit">판사항</div>
                            <div class="txt_con_txt ellipsis">개정2판</div>
                          </div>
                          <div class="txt_con_item">
                            <div class="txt_con_tit">발행사항</div>
                            <div class="txt_con_txt ellipsis">
                              고양 : 돋을새김, 2025
                            </div>
                          </div>
                          <div class="txt_con_item">
                            <div class="txt_con_tit">형태사항</div>
                            <div class="txt_con_txt ellipsis">
                              312 p. : 삽화, 초상 ; 21 cm
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </a>
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
  <!-- [E] contents_wrap -->
  <!-- [S] popup::추천도서 -->
  <div class="dim">
    <div class="layer_popup" id="pop_book">
      <div class="popup_body">
        <div class="pop_book_wrap">
          <div class="img_wrap">
            <img src="/img/layout/img_book.jpg" alt="군주론 표지 이미지" />
          </div>
          <div class="txt_wrap">
            <div class="tit_wrap">
              <div class="left">
                <div class="ctg">도서</div>
                <div class="tit ellipsis">군주론</div>
              </div>

              <div class="info_wrap ty_01">
                <a href="#;" class="info info_item ty_01">
                  <img src="/img/icon/ic_scrap.svg" alt="" />
                  스크랩
                </a>
                <a href="#;" class="info info_item ty_01">
                  <img src="/img/icon/ic_exclam_mark.svg" alt="" />
                  오류신고
                </a>
              </div>
            </div>
            <div class="book_info_list">
              <div class="book_info_item">
                <div class="book_info_tit">표제/저자사항</div>
                <div class="book_info_txt">
                  군주론 / 니콜로 마키아벨리 지음 ; 권혁 옮김 Machiavelli,
                  Niccoló[1469-1527] 권혁
                </div>
              </div>
              <div class="book_info_item">
                <div class="book_info_tit">판사항</div>
                <div class="book_info_txt">개정2판</div>
              </div>
              <div class="book_info_item">
                <div class="book_info_tit">발행사항</div>
                <div class="book_info_txt">고양 : 돋을새김, 2025</div>
              </div>
              <div class="book_info_item">
                <div class="book_info_tit">형태사항</div>
                <div class="book_info_txt">312 p. : 삽화, 초상 ; 21 cm</div>
              </div>
              <div class="book_info_item">
                <div class="book_info_tit">총서사항</div>
                <div class="book_info_txt">
                  (돋을새김 푸른책장 시리즈 ; 004)
                </div>
              </div>
              <div class="book_info_item">
                <div class="book_info_tit">주기사항</div>
                <div class="book_info_txt">
                  원저자명: Niccoló Machiavelli<br />
                  권말부록: 역자주 ; 마키아벨리와 《군주론》 ; 《군주론》 속의
                  역사적 인물들<br />
                  원표제: Prince<br />
                  "니콜로 마키아벨리 연보" 수록<br />
                  영어 원작을 한국어로 번역
                </div>
              </div>
              <div class="book_info_item">
                <div class="book_info_tit">표준번호 / 부호</div>
                <div class="book_info_txt">
                  ISBN 9788961673600 03340: ₩14000
                </div>
              </div>
              <div class="book_info_item">
                <div class="book_info_tit">분류기호</div>
                <div class="book_info_txt">
                  한국십진분류법-> 340.265 듀이십진분류법-> 321.03
                </div>
              </div>
              <div class="book_info_item">
                <div class="book_info_tit">주제명</div>
                <div class="book_info_txt">군주론[君主論]</div>
              </div>
            </div>
            <div class="btn_wrap">
              <a href="#;" class="btn sz_md bg_primary"
                ><img src="/img/icon/ic_print.svg" alt="" />서지정보 출력</a
              >
              <a href="#;" class="btn sz_md bg_gray_01"
                ><img src="/img/icon/ic_down.svg" alt="" />MARC 보기/다운로드</a
              >
              <a href="#;" class="btn sz_md bg_gray_01"
                ><img src="/img/icon/ic_down.svg" alt="" />LOD
                보기/다운로드(txt)</a
              >
            </div>
          </div>
        </div>
      </div>
      <a href="#;" class="pop_close ic_close">
        <span class="hidden">레이어 팝업 닫기</span>
      </a>
    </div>
  </div>
</template>

<script setup lang="ts">
definePageMeta({
  layout: "search",
  layoutProps: { wrapClass: "search_wrap search_ctg_wrap open" },
});

useHead({ title: "리스트 형 | AI 도서정보 검색시스템" });
</script>
