
$(document).ready(function(){
  //tab
  $(".tab_link").off("click").on("click", function (e) {
    e.preventDefault();

    var $link = $(this);
    var $menu = $link.closest(".tab_menu");
    var dataTab = $link.attr("data-tab");
    var thisCon = "." + dataTab;

    $menu.find(".tab_link").removeClass("on");
    $menu.find(".hidden").remove();
    $link.addClass("on");
    $link.append('<span class="hidden">현재 선택됨</span>');

    $(thisCon).siblings(".tab_con").removeClass("on");
    $(thisCon).addClass("on");

    if ($menu.hasClass("source_list")) {
      $(".source_marker").removeClass("on");
      $('.source_marker[data-tab="' + dataTab + '"]').addClass("on");
    }

    if ($menu.hasClass("trigger_toggle")) {
      var target = "#" + $link.attr("target");
      var menu_txt = $link.find(".inn").text();
      if (window.innerWidth <= 1024) {
        $(target).trigger("click");
      }
      $(target).html(menu_txt);
    }

    if ($(".tab_con .slick-slider").length != 0) {
      $(".slick-slider").resize();
      $(".slick-slider").slick("refresh");
    }
  });

  $(".tab_close").off("click").on("click", function (e) {
    e.preventDefault();

    var $menu = $(".tab_menu.source_list").first();
    var $on = $menu.find(".tab_link.on").first();
    var dataTab = $on.attr("data-tab");

    // tab 버튼 초기화
    $menu.find(".tab_link").removeClass("on");
    $menu.find(".hidden").remove();

    // 컨텐츠 초기화
    $(".source_info_list .tab_con").removeClass("on");

    // source_marker 초기화
    if (dataTab) {
      $('.source_marker[data-tab="' + dataTab + '"]').removeClass("on");
    } else {
      $(".source_marker").removeClass("on");
    }
  });

  /* source_marker 클릭 시 tab_link와 동일 동작 */
  $(".source_marker").off("click").on("click", function (e) {
    e.preventDefault();
    var dataTab = $(this).attr("data-tab");
    $('.tab_link[data-tab="' + dataTab + '"]').trigger("click");
  });


  // trigger
  $(".trigger").off("click").on("click", function (event) {
    event.preventDefault();

    var id = $(this).attr("id");
    var wrap = "#" + id + "_wrap";
    var toggle = "#" + id + "_toggle";

    $(wrap).toggleClass("open");
    $(toggle).toggleClass("open");
    $(this).toggleClass("open");

    if ($(wrap).hasClass("open")) {
      $(this).find(".hide_txt").html("닫기");
    } else {
      $(this).find(".hide_txt").html("열기");
    }
  });

  // 외부 닫기 버튼
  $(".trigger_close").off().on("click", function (event) {
    event.preventDefault();
    var target = "#" + $(this).attr("data-target");
    $(target).trigger("click");
  });


  // 좌측 메뉴 열림/닫힘
  $(".left_menu_trigger").off("click").on("click", function () {
    const $trigger = $(this);
    const $targets = $(".left_menu_wrap, .search_wrap");

    $targets.toggleClass("open");

    const isOpen = $targets.first().hasClass("open");

    $trigger.attr("aria-label", isOpen ? "메뉴 닫힘" : "메뉴 열림");
  });

  /*acodian menu*/
  $(".acodian_trigger").off("click").on("click",function(){
    $(this).parents(".acodian_tit").toggleClass("open");
  })

  //  카테고리 검색
  $(".ctg_txt").off("click").on("click", function (e) {
    e.preventDefault();

    var $txt = $(this);
    var $item = $txt.closest(".ctg_item");
    var depthClass = ($item.attr("class").match(/ctg_depth_\d+/) || [])[0];

    // depthClass 못 잡으면 종료
    if (!depthClass) {
      return;
    }

    // 같은 depth 레벨 형제 on 제거 + 하위 전부 닫기
    $item.siblings("." + depthClass)
        .removeClass("on")
        .find(".ctg_item").removeClass("on");

    // has_child 항목일 경우
    if ($item.hasClass("has_child")) {

      if ($item.hasClass("on")) {
        $item.removeClass("on")
            .find(".ctg_item").removeClass("on");
      } else {
        $item.addClass("on");
      }

    } else {
      // leaf 항목: 같은 depth 내에서만 단독 선택 (부모 on 유지)
      $item.siblings("." + depthClass).removeClass("on");
      $item.addClass("on");
    }
  });

  /*mo menu*/
  $(".mo_menu_trigger").off("click").on("click", function(){
    $("body").toggleClass("mo_open");
  })

  /* [S] lnb */
  $(".has_depth3 .lnb_depth2__a").off().on("click",function(){
    $(".menu-lnb-depth2__item").removeClass("on");
    $(this).closest(".menu-lnb-depth2__item").addClass("on");
  })

  $(".has_depth4 .lnb_depth3__a").off().on("click",function(){
    $(".menu-lnb-depth3__item").removeClass("on");
    $(this).closest(".menu-lnb-depth3__item").addClass("on");
  })
  /* [E] lnb */

  /* [S] datepicker_open */
  $( ".datepicker_open" ).datepicker();
  /* [E] datepicker_open */


  if ($(".tab_slide").length !== 0) {
    $(".tab_slide").each(function(index, element) {
      // 기본 옵션 객체 생성
      var swiperOptions = {
        slidesPerView: 'auto',
        spaceBetween: 10,
        simulateTouch: true,
        observer: true,
        observeParents: true,
        breakpoints: {
          1024: {
            spaceBetween: 10,
          }
        }
      };

      // 네비게이션 버튼이 있는 경우 옵션에 추가
      if ($(element).find(".swiper-button-next").length > 0 && $(element).find(".swiper-button-prev").length > 0) {
        swiperOptions.navigation = {
          nextEl: $(element).find(".swiper-button-next")[0],
          prevEl: $(element).find(".swiper-button-prev")[0]
        };
      }

      // Swiper 초기화
      var tab_slide = new Swiper(element, swiperOptions);

      // 'on' 클래스가 있는 슬라이드의 인덱스 찾기
      var indexWithOnClass = $(element).find(".swiper-slide.on").index();

      // 해당 슬라이드로 이동 (만약 'on' 클래스가 있다면)
      if (indexWithOnClass !== -1) {
        tab_slide.slideTo(indexWithOnClass);
      } else {
        console.log(`tab_slide ${index + 1}: on 클래스를 찾을 수 없습니다.`);
      }
    });
  }


})


/*layer popup*/
function open_layer_pop(pop){
  setTimeout(function (){
    var popId = $("#"+pop);
    $("body").css("overflow", "hidden");
    popId.closest(".dim").show();
    if($(".pop_body .slick-slider").length != 0){
      $('.slick-slider').resize();
      $('.slick-slider').slick('refresh');
    }
  },50)
}
$(document).ready(function(){
  $(".pop_close").off("click").on("click", function(){
    $("body").css("overflow", "visible");
    $(this).closest(".dim").hide();
  })
})

document.addEventListener('DOMContentLoaded', function () {
  const tabs = document.querySelectorAll('.sc_menu_wrap'); // 모든 탭 콘텐츠를 선택
  const body = document.body;  // 상위 요소의 스크롤을 비활성화하기 위해 사용

  // 각 탭에 순번을 자동으로 부여
  tabs.forEach((tab, index) => {
    tab.dataset.index = index + 1;
  });

  // 각 탭의 메뉴 컨테이너에 대해 스크롤 기능을 설정
  tabs.forEach(tab => {
    const menuContainer = tab.querySelector('.sc_menu'); // 탭 내의 메뉴 컨테이너
    let isMouseDown = false;
    let startX;
    let scrollLeft;

    // 마우스 클릭 시작 이벤트
    menuContainer.addEventListener('mousedown', (e) => {
      isMouseDown = true;
      menuContainer.classList.add('active');
      startX = e.pageX - menuContainer.offsetLeft;
      scrollLeft = menuContainer.scrollLeft;

      // 본문 스크롤 비활성화
      body.classList.add('no_scroll');
    });

    // 마우스가 컨테이너를 떠날 때 이벤트
    menuContainer.addEventListener('mouseleave', () => {
      if (isMouseDown) {
        isMouseDown = false;
        menuContainer.classList.remove('active');
        body.classList.remove('no_scroll');
      }
    });

    // 마우스 클릭을 해제할 때 이벤트
    menuContainer.addEventListener('mouseup', () => {
      if (isMouseDown) {
        isMouseDown = false;
        menuContainer.classList.remove('active');
        body.classList.remove('no_scroll');
      }
    });

    // 마우스 이동 이벤트
    menuContainer.addEventListener('mousemove', (e) => {
      if (!isMouseDown) return;
      e.preventDefault();
      const x = e.pageX - menuContainer.offsetLeft;
      const walk = (x - startX) * 2; // 스크롤 속도 조절
      menuContainer.scrollLeft = scrollLeft - walk;
    });

    // 모바일 터치 지원
    let startTouchX;
    menuContainer.addEventListener('touchstart', (e) => {
      startTouchX = e.touches[0].clientX;
    });

    menuContainer.addEventListener('touchmove', (e) => {
      const currentTouchX = e.touches[0].clientX;
      const diff = startTouchX - currentTouchX;
      menuContainer.scrollLeft += diff;
      startTouchX = currentTouchX;
    });

    // 페이지 로드 시 .on 클래스를 가진 메뉴 아이템으로 스크롤 이동
    function scrollToActiveMenuItem() {
      const activeItem = menuContainer.querySelector('.sc_menu_item.on');
      if (activeItem) {
        // 컨테이너와 메뉴 아이템의 위치를 가져옴
        const containerRect = menuContainer.getBoundingClientRect();
        const itemRect = activeItem.getBoundingClientRect();

        // 스크롤 오프셋 계산
        const offset = itemRect.left - containerRect.left + menuContainer.scrollLeft;

        // 메뉴 아이템이 컨테이너의 시작 위치에 오도록 스크롤
        menuContainer.scrollLeft = offset;
      }
    }

    // 페이지 로드 후 스크롤 이동 함수 호출
    // 요소가 완전히 렌더링된 후 스크롤이 적용되도록 지연 호출
    setTimeout(scrollToActiveMenuItem, 100);  // 100ms 지연
  });

  // 탭 변경 이벤트 처리
  const tabButtons = document.querySelectorAll('.tab-button');
  tabButtons.forEach(button => {
    button.addEventListener('click', () => {
      const targetTab = document.querySelector(button.getAttribute('data-target'));

      // 모든 탭 콘텐츠를 비활성화
      tabs.forEach(tab => {
        tab.classList.remove('active');
      });

      // 선택한 탭 콘텐츠를 활성화
      targetTab.classList.add('active');

      // 활성화된 탭의 메뉴로 스크롤 이동
      const menuContainer = targetTab.querySelector('.sc_menu');
      if (menuContainer) {
        const activeItem = menuContainer.querySelector('.sc_menu_item.on');
        if (activeItem) {
          // 컨테이너와 메뉴 아이템의 위치를 가져옴
          const containerRect = menuContainer.getBoundingClientRect();
          const itemRect = activeItem.getBoundingClientRect();

          // 스크롤 오프셋 계산
          const offset = itemRect.left - containerRect.left + menuContainer.scrollLeft;

          // 메뉴 아이템이 컨테이너의 시작 위치에 오도록 스크롤
          menuContainer.scrollLeft = offset;
        }
      }
    });
  });
});

$.datepicker.setDefaults({
  closeText : "닫기",
  currentText : "오늘",
  prevText : '이전 달',
  nextText : '다음 달',
  monthNames : [ '1월', '2월', '3월', '4월', '5월', '6월', '7월', '8월', '9월', '10월', '11월', '12월' ],
  monthNamesShort : [ '1월', '2월', '3월', '4월', '5월', '6월', '7월', '8월', '9월', '10월', '11월', '12월' ],
  dayNames : [ '일', '월', '화', '수', '목', '금', '토' ],
  dayNamesShort : [ '일', '월', '화', '수', '목', '금', '토' ],
  dayNamesMin : [ '일', '월', '화', '수', '목', '금', '토' ],
  weekHeader : "주",
  // yearSuffix : '년',
  dateFormat:'yy-mm-dd',
  changeYear: true,  // 년도 선택 드롭다운 표시
  changeMonth: true, // 월 선택 드롭다운 표시
});

// 연구 히스토리 삭제
function fn_del(el) {
  var $item = $(el).closest(".history_con_item");
  var $list = $item.closest(".history_con_list");
  var $group = $item.closest(".history_con");

  // 현재 항목 삭제
  $item.remove();

  // 남은 항목 개수 확인
  if ($list.find(".history_con_item").length === 0) {
    $group.remove();
  }
}