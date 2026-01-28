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


# ==================== 한국 (독립) ====================
KOREA_COUNTRIES = {
    "KR": Country("KR", "대한민국", "South Korea", "korea", "Korea"),
}

# ==================== 아시아 ====================
ASIA_COUNTRIES = {
    "MY": Country("MY", "말레이시아", "Malaysia", "asia", "Southeast Asia"),
    "MM": Country("MM", "미얀마", "Myanmar", "asia", "Southeast Asia"),
    "BD": Country("BD", "방글라데시", "Bangladesh", "asia", "South Asia"),
    "VN": Country("VN", "베트남", "Vietnam", "asia", "Southeast Asia"),
    "BN": Country("BN", "브루나이", "Brunei", "asia", "Southeast Asia"),
    "LK": Country("LK", "스리랑카", "Sri Lanka", "asia", "South Asia"),
    "SG": Country("SG", "싱가포르", "Singapore", "asia", "Southeast Asia"),
    "IN": Country("IN", "인도", "India", "asia", "South Asia"),
    "ID": Country("ID", "인도네시아", "Indonesia", "asia", "Southeast Asia"),
    "JP": Country("JP", "일본", "Japan", "asia", "East Asia"),
    "CN": Country("CN", "중국", "China", "asia", "East Asia"),
    "KH": Country("KH", "캄보디아", "Cambodia", "asia", "Southeast Asia"),
    "TH": Country("TH", "태국", "Thailand", "asia", "Southeast Asia"),
    "PK": Country("PK", "파키스탄", "Pakistan", "asia", "South Asia"),
    "PG": Country("PG", "파푸아뉴기니", "Papua New Guinea", "asia", "Oceania"),
    "PH": Country("PH", "필리핀", "Philippines", "asia", "Southeast Asia"),
}

# ==================== 유럽 ====================
EUROPE_COUNTRIES = {
    "IE": Country("IE", "아일랜드", "Ireland", "europe", "Western Europe"),
    "EE": Country("EE", "에스토니아", "Estonia", "europe", "Northern Europe"),
    "GB": Country("GB", "영국", "United Kingdom", "europe", "Western Europe"),
    "AT": Country("AT", "오스트리아", "Austria", "europe", "Central Europe"),
    "EU": Country("EU", "유럽연합", "European Union", "europe", "European Union"),
    "IT": Country("IT", "이탈리아", "Italy", "europe", "Southern Europe"),
    "CZ": Country("CZ", "체코", "Czech Republic", "europe", "Central Europe"),
    "HR": Country("HR", "크로아티아", "Croatia", "europe", "Southern Europe"),
    "CY": Country("CY", "키프로스", "Cyprus", "europe", "Southern Europe"),
    "PT": Country("PT", "포르투갈", "Portugal", "europe", "Southern Europe"),
    "PL": Country("PL", "폴란드", "Poland", "europe", "Central Europe"),
    "FR": Country("FR", "프랑스", "France", "europe", "Western Europe"),
    "FI": Country("FI", "핀란드", "Finland", "europe", "Northern Europe"),
    "HU": Country("HU", "헝가리", "Hungary", "europe", "Central Europe"),
}

# ==================== 북아메리카 ====================
NORTH_AMERICA_COUNTRIES = {
    "US": Country("US", "미국", "United States", "north_america", "North America"),
    "CA": Country("CA", "캐나다", "Canada", "north_america", "North America"),
}

# ==================== 아프리카 ====================
AFRICA_COUNTRIES = {
    "GH": Country("GH", "가나", "Ghana", "africa", "West Africa"),
    "GA": Country("GA", "가봉", "Gabon", "africa", "Central Africa"),
    "NG": Country("NG", "나이지리아", "Nigeria", "africa", "West Africa"),
    "ZA": Country("ZA", "남아프리카공화국", "South Africa", "africa", "Southern Africa"),
    "RW": Country("RW", "르완다", "Rwanda", "africa", "East Africa"),
    "LY": Country("LY", "리비아", "Libya", "africa", "North Africa"),
    "MA": Country("MA", "모로코", "Morocco", "africa", "North Africa"),
    "SN": Country("SN", "세네갈", "Senegal", "africa", "West Africa"),
    "SD": Country("SD", "수단", "Sudan", "africa", "North Africa"),
    "DZ": Country("DZ", "알제리", "Algeria", "africa", "North Africa"),
    "AO": Country("AO", "앙골라", "Angola", "africa", "Central Africa"),
    "ET": Country("ET", "에티오피아", "Ethiopia", "africa", "East Africa"),
    "EG": Country("EG", "이집트", "Egypt", "africa", "North Africa"),
    "KE": Country("KE", "케냐", "Kenya", "africa", "East Africa"),
    "CI": Country("CI", "코트디부아르", "Côte d'Ivoire", "africa", "West Africa"),
    "CD": Country("CD", "콩고민주공화국", "Democratic Republic of the Congo", "africa", "Central Africa"),
    "TZ": Country("TZ", "탄자니아", "Tanzania", "africa", "East Africa"),
    "TN": Country("TN", "튀니지", "Tunisia", "africa", "North Africa"),
}

# ==================== 오세아니아 ====================
OCEANIA_COUNTRIES = {
    "NZ": Country("NZ", "뉴질랜드", "New Zealand", "oceania", "Oceania"),
    "AU": Country("AU", "호주", "Australia", "oceania", "Oceania"),
}

# ==================== 중동 ====================
MIDDLE_EAST_COUNTRIES = {
    "LB": Country("LB", "레바논", "Lebanon", "middle_east", "Middle East"),
    "BH": Country("BH", "바레인", "Bahrain", "middle_east", "Middle East"),
    "SA": Country("SA", "사우디아라비아", "Saudi Arabia", "middle_east", "Middle East"),
    "AE": Country("AE", "아랍에미리트", "United Arab Emirates", "middle_east", "Middle East"),
    "OM": Country("OM", "오만", "Oman", "middle_east", "Middle East"),
    "JO": Country("JO", "요르단", "Jordan", "middle_east", "Middle East"),
    "IQ": Country("IQ", "이라크", "Iraq", "middle_east", "Middle East"),
    "IR": Country("IR", "이란", "Iran", "middle_east", "Middle East"),
    "IL": Country("IL", "이스라엘", "Israel", "middle_east", "Middle East"),
    "QA": Country("QA", "카타르", "Qatar", "middle_east", "Middle East"),
    "KW": Country("KW", "쿠웨이트", "Kuwait", "middle_east", "Middle East"),
    "TR": Country("TR", "튀르키예", "Turkey", "middle_east", "Middle East"),
}

# ==================== 러시아/중앙아시아 ====================
RUSSIA_CENTRAL_ASIA_COUNTRIES = {
    "RU": Country("RU", "러시아", "Russia", "russia_central_asia", "Russia & Central Asia"),
    "MN": Country("MN", "몽골", "Mongolia", "russia_central_asia", "Central Asia"),
    "BY": Country("BY", "벨라루스", "Belarus", "russia_central_asia", "Eastern Europe"),
    "AM": Country("AM", "아르메니아", "Armenia", "russia_central_asia", "Caucasus"),
    "AZ": Country("AZ", "아제르바이잔", "Azerbaijan", "russia_central_asia", "Caucasus"),
    "UZ": Country("UZ", "우즈베키스탄", "Uzbekistan", "russia_central_asia", "Central Asia"),
    "UA": Country("UA", "우크라이나", "Ukraine", "russia_central_asia", "Eastern Europe"),
    "GE": Country("GE", "조지아", "Georgia", "russia_central_asia", "Caucasus"),
    "KZ": Country("KZ", "카자흐스탄", "Kazakhstan", "russia_central_asia", "Central Asia"),
    "KG": Country("KG", "키르기스스탄", "Kyrgyzstan", "russia_central_asia", "Central Asia"),
    "TJ": Country("TJ", "타지키스탄", "Tajikistan", "russia_central_asia", "Central Asia"),
    "TM": Country("TM", "투르크메니스탄", "Turkmenistan", "russia_central_asia", "Central Asia"),
}

# ==================== 중남미 ====================
LATIN_AMERICA_COUNTRIES = {
    "GT": Country("GT", "과테말라", "Guatemala", "latin_america", "Central America"),
    "DO": Country("DO", "도미니카공화국", "Dominican Republic", "latin_america", "Caribbean"),
    "MX": Country("MX", "멕시코", "Mexico", "latin_america", "Central America"),
    "VE": Country("VE", "베네수엘라", "Venezuela", "latin_america", "South America"),
    "BO": Country("BO", "볼리비아", "Bolivia", "latin_america", "South America"),
    "BR": Country("BR", "브라질", "Brazil", "latin_america", "South America"),
    "AR": Country("AR", "아르헨티나", "Argentina", "latin_america", "South America"),
    "EC": Country("EC", "에콰도르", "Ecuador", "latin_america", "South America"),
    "SV": Country("SV", "엘살바도르", "El Salvador", "latin_america", "Central America"),
    "HN": Country("HN", "온두라스", "Honduras", "latin_america", "Central America"),
    "UY": Country("UY", "우루과이", "Uruguay", "latin_america", "South America"),
    "CL": Country("CL", "칠레", "Chile", "latin_america", "South America"),
    "CR": Country("CR", "코스타리카", "Costa Rica", "latin_america", "Central America"),
    "CO": Country("CO", "콜롬비아", "Colombia", "latin_america", "South America"),
    "PA": Country("PA", "파나마", "Panama", "latin_america", "Central America"),
    "PY": Country("PY", "파라과이", "Paraguay", "latin_america", "South America"),
    "PE": Country("PE", "페루", "Peru", "latin_america", "South America"),
}

# ==================== 통합 레지스트리 ====================
ALL_COUNTRIES = {
    **KOREA_COUNTRIES,
    **ASIA_COUNTRIES,
    **EUROPE_COUNTRIES,
    **NORTH_AMERICA_COUNTRIES,
    **AFRICA_COUNTRIES,
    **OCEANIA_COUNTRIES,
    **MIDDLE_EAST_COUNTRIES,
    **RUSSIA_CENTRAL_ASIA_COUNTRIES,
    **LATIN_AMERICA_COUNTRIES,
}

# 대륙별 매핑
CONTINENT_MAPPING = {
    "korea": KOREA_COUNTRIES,
    "asia": ASIA_COUNTRIES,
    "europe": EUROPE_COUNTRIES,
    "north_america": NORTH_AMERICA_COUNTRIES,
    "africa": AFRICA_COUNTRIES,
    "oceania": OCEANIA_COUNTRIES,
    "middle_east": MIDDLE_EAST_COUNTRIES,
    "russia_central_asia": RUSSIA_CENTRAL_ASIA_COUNTRIES,
    "latin_america": LATIN_AMERICA_COUNTRIES,
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