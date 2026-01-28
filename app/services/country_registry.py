# app/services/country_registry.py
"""
국가 코드 및 대륙 분류 관리
- ISO 3166-1 alpha-2 기반
- 대륙별 분류
- 한글/영문 국가명
"""
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class Country:
    """국가 정보"""
    code: str           # ISO 3166-1 alpha-2 (예: KR, US)
    name_ko: str        # 한글 국가명
    name_en: str        # 영문 국가명
    continent: str      # 대륙 (Asia, Europe, Africa, North America, South America, Oceania)
    region: str         # 지역 (동아시아, 서유럽 등)


# ==================== 아시아 ====================
ASIA_COUNTRIES = {
    # 동아시아
    "KR": Country("KR", "대한민국", "South Korea", "Asia", "East Asia"),
    "KP": Country("KP", "북한(조선민주주의인민공화국)", "North Korea", "Asia", "East Asia"),
    "JP": Country("JP", "일본", "Japan", "Asia", "East Asia"),
    "CN": Country("CN", "중국", "China", "Asia", "East Asia"),
    "TW": Country("TW", "대만", "Taiwan", "Asia", "East Asia"),
    "HK": Country("HK", "홍콩", "Hong Kong", "Asia", "East Asia"),
    "MO": Country("MO", "마카오", "Macau", "Asia", "East Asia"),
    "MN": Country("MN", "몽골", "Mongolia", "Asia", "East Asia"),
    
    # 동남아시아
    "VN": Country("VN", "베트남", "Vietnam", "Asia", "Southeast Asia"),
    "TH": Country("TH", "태국", "Thailand", "Asia", "Southeast Asia"),
    "PH": Country("PH", "필리핀", "Philippines", "Asia", "Southeast Asia"),
    "ID": Country("ID", "인도네시아", "Indonesia", "Asia", "Southeast Asia"),
    "MY": Country("MY", "말레이시아", "Malaysia", "Asia", "Southeast Asia"),
    "SG": Country("SG", "싱가포르", "Singapore", "Asia", "Southeast Asia"),
    "KH": Country("KH", "캄보디아", "Cambodia", "Asia", "Southeast Asia"),
    "LA": Country("LA", "라오스", "Laos", "Asia", "Southeast Asia"),
    "MM": Country("MM", "미얀마", "Myanmar", "Asia", "Southeast Asia"),
    
    # 남아시아
    "IN": Country("IN", "인도", "India", "Asia", "South Asia"),
    "PK": Country("PK", "파키스탄", "Pakistan", "Asia", "South Asia"),
    "BD": Country("BD", "방글라데시", "Bangladesh", "Asia", "South Asia"),
    "NP": Country("NP", "네팔", "Nepal", "Asia", "South Asia"),
    "LK": Country("LK", "스리랑카", "Sri Lanka", "Asia", "South Asia"),
    "AF": Country("AF", "아프가니스탄", "Afghanistan", "Asia", "South Asia"),
    
    # 서아시아 (중동)
    "IR": Country("IR", "이란", "Iran", "Asia", "West Asia"),
    "IQ": Country("IQ", "이라크", "Iraq", "Asia", "West Asia"),
    "SA": Country("SA", "사우디아라비아", "Saudi Arabia", "Asia", "West Asia"),
    "AE": Country("AE", "아랍에미리트", "United Arab Emirates", "Asia", "West Asia"),
    "QA": Country("QA", "카타르", "Qatar", "Asia", "West Asia"),
    "KW": Country("KW", "쿠웨이트", "Kuwait", "Asia", "West Asia"),
    "IL": Country("IL", "이스라엘", "Israel", "Asia", "West Asia"),
    "JO": Country("JO", "요르단", "Jordan", "Asia", "West Asia"),
    "TR": Country("TR", "터키", "Turkey", "Asia", "West Asia"),
}

# ==================== 유럽 ====================
EUROPE_COUNTRIES = {
    # 서유럽
    "DE": Country("DE", "독일", "Germany", "Europe", "Western Europe"),
    "FR": Country("FR", "프랑스", "France", "Europe", "Western Europe"),
    "GB": Country("GB", "영국", "United Kingdom", "Europe", "Western Europe"),
    "NL": Country("NL", "네덜란드", "Netherlands", "Europe", "Western Europe"),
    "BE": Country("BE", "벨기에", "Belgium", "Europe", "Western Europe"),
    "CH": Country("CH", "스위스", "Switzerland", "Europe", "Western Europe"),
    "AT": Country("AT", "오스트리아", "Austria", "Europe", "Western Europe"),
    "IE": Country("IE", "아일랜드", "Ireland", "Europe", "Western Europe"),
    
    # 남유럽
    "IT": Country("IT", "이탈리아", "Italy", "Europe", "Southern Europe"),
    "ES": Country("ES", "스페인", "Spain", "Europe", "Southern Europe"),
    "PT": Country("PT", "포르투갈", "Portugal", "Europe", "Southern Europe"),
    "GR": Country("GR", "그리스", "Greece", "Europe", "Southern Europe"),
    "HR": Country("HR", "크로아티아", "Croatia", "Europe", "Southern Europe"),
    "RS": Country("RS", "세르비아", "Serbia", "Europe", "Southern Europe"),
    "SI": Country("SI", "슬로베니아", "Slovenia", "Europe", "Southern Europe"),
    
    # 북유럽
    "SE": Country("SE", "스웨덴", "Sweden", "Europe", "Northern Europe"),
    "NO": Country("NO", "노르웨이", "Norway", "Europe", "Northern Europe"),
    "FI": Country("FI", "핀란드", "Finland", "Europe", "Northern Europe"),
    "DK": Country("DK", "덴마크", "Denmark", "Europe", "Northern Europe"),
    
    # 동유럽
    "PL": Country("PL", "폴란드", "Poland", "Europe", "Eastern Europe"),
    "CZ": Country("CZ", "체코", "Czech Republic", "Europe", "Eastern Europe"),
    "SK": Country("SK", "슬로바키아", "Slovakia", "Europe", "Eastern Europe"),
    "HU": Country("HU", "헝가리", "Hungary", "Europe", "Eastern Europe"),
    "RO": Country("RO", "루마니아", "Romania", "Europe", "Eastern Europe"),
    "BG": Country("BG", "불가리아", "Bulgaria", "Europe", "Eastern Europe"),
    "RU": Country("RU", "러시아", "Russia", "Europe", "Eastern Europe"),
    "UA": Country("UA", "우크라이나", "Ukraine", "Europe", "Eastern Europe"),
    "LT": Country("LT", "리투아니아", "Lithuania", "Europe", "Eastern Europe"),
    "LV": Country("LV", "라트비아", "Latvia", "Europe", "Eastern Europe"),
    "EE": Country("EE", "에스토니아", "Estonia", "Europe", "Eastern Europe"),
}

# ==================== 북아메리카 ====================
NORTH_AMERICA_COUNTRIES = {
    "US": Country("US", "미국", "United States", "North America", "North America"),
    "CA": Country("CA", "캐나다", "Canada", "North America", "North America"),
    "MX": Country("MX", "멕시코", "Mexico", "North America", "Central America"),
    "CU": Country("CU", "쿠바", "Cuba", "North America", "Caribbean"),
    "JM": Country("JM", "자메이카", "Jamaica", "North America", "Caribbean"),
    "DO": Country("DO", "도미니카공화국", "Dominican Republic", "North America", "Caribbean"),
    "PA": Country("PA", "파나마", "Panama", "North America", "Central America"),
    "CR": Country("CR", "코스타리카", "Costa Rica", "North America", "Central America"),
}

# ==================== 남아메리카 ====================
SOUTH_AMERICA_COUNTRIES = {
    "BR": Country("BR", "브라질", "Brazil", "South America", "South America"),
    "AR": Country("AR", "아르헨티나", "Argentina", "South America", "South America"),
    "CL": Country("CL", "칠레", "Chile", "South America", "South America"),
    "PE": Country("PE", "페루", "Peru", "South America", "South America"),
    "CO": Country("CO", "콜롬비아", "Colombia", "South America", "South America"),
    "VE": Country("VE", "베네수엘라", "Venezuela", "South America", "South America"),
    "UY": Country("UY", "우루과이", "Uruguay", "South America", "South America"),
    "PY": Country("PY", "파라과이", "Paraguay", "South America", "South America"),
    "BO": Country("BO", "볼리비아", "Bolivia", "South America", "South America"),
    "EC": Country("EC", "에콰도르", "Ecuador", "South America", "South America"),
}

# ==================== 아프리카 ====================
AFRICA_COUNTRIES = {
    "EG": Country("EG", "이집트", "Egypt", "Africa", "North Africa"),
    "ZA": Country("ZA", "남아프리카공화국", "South Africa", "Africa", "Southern Africa"),
    "NG": Country("NG", "나이지리아", "Nigeria", "Africa", "West Africa"),
    "KE": Country("KE", "케냐", "Kenya", "Africa", "East Africa"),
    "ET": Country("ET", "에티오피아", "Ethiopia", "Africa", "East Africa"),
    "GH": Country("GH", "가나", "Ghana", "Africa", "West Africa"),
    "MA": Country("MA", "모로코", "Morocco", "Africa", "North Africa"),
    "DZ": Country("DZ", "알제리", "Algeria", "Africa", "North Africa"),
    "TN": Country("TN", "튀니지", "Tunisia", "Africa", "North Africa"),
    "TZ": Country("TZ", "탄자니아", "Tanzania", "Africa", "East Africa"),
}

# ==================== 오세아니아 ====================
OCEANIA_COUNTRIES = {
    "AU": Country("AU", "호주", "Australia", "Oceania", "Oceania"),
    "NZ": Country("NZ", "뉴질랜드", "New Zealand", "Oceania", "Oceania"),
    "PG": Country("PG", "파푸아뉴기니", "Papua New Guinea", "Oceania", "Melanesia"),
    "FJ": Country("FJ", "피지", "Fiji", "Oceania", "Melanesia"),
    "WS": Country("WS", "사모아", "Samoa", "Oceania", "Polynesia"),
}

# ==================== 통합 레지스트리 ====================
ALL_COUNTRIES = {
    **ASIA_COUNTRIES,
    **EUROPE_COUNTRIES,
    **NORTH_AMERICA_COUNTRIES,
    **SOUTH_AMERICA_COUNTRIES,
    **AFRICA_COUNTRIES,
    **OCEANIA_COUNTRIES,
}

# 대륙별 매핑
CONTINENT_MAPPING = {
    "Asia": ASIA_COUNTRIES,
    "Europe": EUROPE_COUNTRIES,
    "North America": NORTH_AMERICA_COUNTRIES,
    "South America": SOUTH_AMERICA_COUNTRIES,
    "Africa": AFRICA_COUNTRIES,
    "Oceania": OCEANIA_COUNTRIES,
}


# ==================== 유틸리티 함수 ====================

def get_country(code: str) -> Optional[Country]:
    """국가 코드로 국가 정보 조회"""
    return ALL_COUNTRIES.get(code.upper())


def get_country_name_ko(code: str) -> str:
    """국가 코드 → 한글 국가명"""
    country = get_country(code)
    return country.name_ko if country else code


def get_country_name_en(code: str) -> str:
    """국가 코드 → 영문 국가명"""
    country = get_country(code)
    return country.name_en if country else code


def get_continent(code: str) -> Optional[str]:
    """국가 코드 → 대륙"""
    country = get_country(code)
    return country.continent if country else None


def get_region(code: str) -> Optional[str]:
    """국가 코드 → 지역"""
    country = get_country(code)
    return country.region if country else None


def get_countries_by_continent(continent: str) -> Dict[str, Country]:
    """대륙별 국가 목록"""
    return CONTINENT_MAPPING.get(continent, {})


def get_all_continents() -> List[str]:
    """전체 대륙 목록"""
    return list(CONTINENT_MAPPING.keys())


def validate_country_code(code: str) -> bool:
    """국가 코드 유효성 검사"""
    return code.upper() in ALL_COUNTRIES


def get_country_metadata(code: str) -> Dict:
    """국가 메타데이터 전체 반환 (MinIO/Milvus 저장용)"""
    country = get_country(code)
    if not country:
        return {
            "country_code": code,
            "country_name_ko": code,
            "country_name_en": code,
            "continent": "Unknown",
            "region": "Unknown",
        }
    
    return {
        "country_code": country.code,
        "country_name_ko": country.name_ko,
        "country_name_en": country.name_en,
        "continent": country.continent,
        "region": country.region,
    }


def search_countries(query: str) -> List[Country]:
    """국가명 검색 (한글/영문)"""
    query_lower = query.lower()
    results = []
    
    for country in ALL_COUNTRIES.values():
        if (query_lower in country.name_ko.lower() or 
            query_lower in country.name_en.lower() or
            query_lower in country.code.lower()):
            results.append(country)
    
    return results