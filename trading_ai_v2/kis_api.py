"""
kis_api.py v4 -- 주식 참고용 데이터 조회 전용

[ v4 변경사항 -- 자동매매 → 재무제표 참고용 전환 ]
  - [삭제] 매수/매도 주문 기능 전부 제거 (_order, buy, sell, cancel_order)
    이유: 이 프로그램은 더 이상 실제로 사고 팔지 않습니다. 조회만 합니다.
  - [삭제] best_bid/best_ask (호가창 기반 주문가 계산) -- 주문이 없으니 불필요
  - [삭제] balance() (계좌 잔고 조회) -- 매매 안 하므로 잔고 확인 불필요
  - [삭제] get_credit_balance() (신용잔고), get_foreign_net() (외국인 수급)
    이유: 둘 다 "지금 사야 하나?" 타이밍용 데이터라 재무제표 분석과 무관
  - [삭제] _tick() (호가 단위 계산) -- 주문 가격 계산용이라 불필요
  - [추가] get_balance_sheet()   -- 대차대조표 (자산/부채/자본)
  - [추가] get_income_statement() -- 손익계산서 (매출/영업이익/순이익)
  - [추가] get_profit_ratio()    -- 수익성비율 (ROE/ROA/순이익률)
  - [추가] get_growth_ratio()    -- 성장성비율 (매출/영업이익 증가율)

[ v4.1 변경사항 -- 전체 종목 스캔 + 미국장 지원 ]
  - [추가] get_market_cap_ranking()          -- 국내 시가총액 상위 (KOSPI/KOSDAQ, 최대 30건/호출)
    ※ KIS API 제약: 이 랭킹 API는 30건까지만 주고 "다음 조회"를 지원하지 않음.
       그래서 full_universe.py 가 가격대를 나눠서 여러 번 호출 + 종목코드 중복 제거로
       200~400개 규모의 유니버스를 만듭니다. (코스피/코스닥 전체 2500여개는 아님)
  - [추가] get_overseas_market_cap_ranking() -- 해외(미국 등) 시가총액 상위 (최대 100건/호출)
  - [추가] get_overseas_price_detail()       -- 해외 종목 PER/PBR/EPS/BPS 조회
  - [기존유지] get_token 캐시, current_price, get_fundamentals(PER/PBR/부채비율),
              get_financial_ratio(ROE/EPS/BPS), get_invest_opinion(애널리스트 목표가),
              get_daily_ohlcv(일봉)

[ 초보자 설명 ]
이 파일은 한국투자증권(KIS) Open API 에 "질문만" 던지는 창구입니다.
"이 종목 지금 얼마야?", "이 회사 작년에 얼마 벌었어?" 같은 걸 물어보고
답을 받아올 뿐, "사줘" / "팔아줘" 라고 시키는 기능은 이제 없습니다.
"""
import requests, logging, json, os
from datetime import datetime, timedelta
from config import BASE_URL, APP_KEY, APP_SECRET

logger = logging.getLogger(__name__)

TOKEN_FILE = "token_cache.json"


class KIS:

    def __init__(self):
        self.token            = None
        self.token_expires_at = None

    def get_token(self):
        # 1. 파일 캐시 확인
        if os.path.exists(TOKEN_FILE):
            try:
                with open(TOKEN_FILE, encoding="utf-8") as f:
                    cache = json.load(f)
                expires = datetime.fromisoformat(cache["expires_at"])
                if datetime.now() < expires:
                    self.token            = cache["access_token"]
                    self.token_expires_at = expires
                    logger.info(f"토큰 캐시 재사용 (만료: {expires.strftime('%H:%M')})")
                    return self.token
            except Exception as e:
                logger.debug(f"토큰 캐시 로드 실패: {e}")

        # 2. 새로 발급
        res = requests.post(BASE_URL + "/oauth2/tokenP", json={
            "grant_type": "client_credentials",
            "appkey": APP_KEY, "appsecret": APP_SECRET
        }, timeout=10)
        res.raise_for_status()
        self.token            = res.json()["access_token"]
        self.token_expires_at = datetime.now() + timedelta(hours=23)

        # 3. 파일에 저장
        try:
            with open(TOKEN_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "access_token": self.token,
                    "expires_at":   self.token_expires_at.isoformat()
                }, f)
            logger.info(f"토큰 신규 발급 + 저장 완료 (만료: {self.token_expires_at.strftime('%H:%M')})")
        except Exception as e:
            logger.warning(f"토큰 파일 저장 실패: {e}")

        return self.token

    def _ensure_token(self):
        """토큰 유효성 확인 후 필요 시 재발급."""
        if (not self.token
                or self.token_expires_at is None
                or datetime.now() >= self.token_expires_at):
            self.get_token()

    def headers(self, tr_id):
        self._ensure_token()
        return {
            "authorization": f"Bearer {self.token}",
            "appkey":        APP_KEY,
            "appsecret":     APP_SECRET,
            "tr_id":         tr_id,
            "content-type":  "application/json"
        }

    # ── 시세 ────────────────────────────────────────────────────────────────

    def current_price(self, code: str) -> float:
        """현재가 조회 (FHKST01010100)."""
        try:
            url    = BASE_URL + "/uapi/domestic-stock/v1/quotations/inquire-price"
            params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code}
            data   = requests.get(url, headers=self.headers("FHKST01010100"),
                                  params=params, timeout=5).json()
            return float(data.get("output", {}).get("stck_prpr", 0) or 0)
        except Exception as e:
            logger.warning(f"[KIS] 현재가 조회 실패 {code}: {e}")
            return 0.0

    def get_daily_ohlcv(self, code: str, days: int = 260) -> list:
        """
        일봉 OHLCV 조회 (최근 N일).
        KIS: /uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice
        반환: [{"date","open","high","low","close","volume"}, ...] 오래된 것 먼저

        [ 용도 ] 52주 고점/저점 대비 현재가 위치 계산 (참고용)
        """
        try:
            from datetime import date
            end_dt   = date.today().strftime("%Y%m%d")
            url      = BASE_URL + "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
            params   = {
                "fid_cond_mrkt_div_code": "J",
                "fid_input_iscd":          code,
                "fid_input_date_1":        "",
                "fid_input_date_2":        end_dt,
                "fid_period_div_code":     "D",
                "fid_org_adj_prc":         "0",
            }
            raw = requests.get(url, headers=self.headers("FHKST03010100"),
                               params=params, timeout=10).json()
            rows = raw.get("output2", []) or []
            result = []
            for r in rows:
                try:
                    result.append({
                        "date":   r.get("stck_bsop_date", ""),
                        "open":   float(r.get("stck_oprc", 0) or 0),
                        "high":   float(r.get("stck_hgpr", 0) or 0),
                        "low":    float(r.get("stck_lwpr", 0) or 0),
                        "close":  float(r.get("stck_clpr", 0) or 0),
                        "volume": int(r.get("acml_vol", 0) or 0),
                    })
                except Exception:
                    continue
            result.reverse()          # 오래된 것 먼저 정렬
            return result[-days:]     # 최근 N일
        except Exception as e:
            logger.debug(f"[KIS] 일봉 조회 실패 {code}: {e}")
            return []

    # ── 재무제표 / 재무비율 ───────────────────────────────────────────────────

    def get_fundamentals(self, code: str) -> dict:
        """
        PER / PBR / 부채비율 조회.
        - PER/PBR: FHKST01010100 (주식 현재가 시세) 응답에 포함.
        - 부채비율: FHKST66430600 (국내주식 안정성비율) -- lblt_rate 필드.

        Returns
        -------
        {"per": float, "pbr": float, "debt_ratio": float}
        값을 못 구하면 0.0 반환 (스크리너가 0 을 "데이터 없음"으로 처리)
        """
        per = pbr = debt_ratio = 0.0
        try:
            url    = BASE_URL + "/uapi/domestic-stock/v1/quotations/inquire-price"
            params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code}
            out    = requests.get(url, headers=self.headers("FHKST01010100"),
                                  params=params, timeout=5).json().get("output", {})
            per = float(out.get("per", 0) or 0)
            pbr = float(out.get("pbr", 0) or 0)
        except Exception as e:
            logger.warning(f"[KIS] PER/PBR 조회 실패 {code}: {e}")

        try:
            url2    = BASE_URL + "/uapi/domestic-stock/v1/finance/stability-ratio"
            params2 = {
                "fid_cond_mrkt_div_code": "J",
                "fid_input_iscd":          code,
                "fid_div_cls_code":        "1",   # 1=분기 (최신 분기)
            }
            out2 = requests.get(url2, headers=self.headers("FHKST66430600"),
                                params=params2, timeout=5).json().get("output", [])
            row = out2[0] if isinstance(out2, list) and out2 else {}
            debt_ratio = float(row.get("lblt_rate", 0) or 0)
        except Exception:
            pass   # 부채비율 조회 실패 시 0 유지

        return {"per": per, "pbr": pbr, "debt_ratio": debt_ratio}

    def get_financial_ratio(self, code: str) -> dict:
        """
        재무비율 조회 (FHKST66430300).
        URL: /uapi/domestic-stock/v1/finance/financial-ratio
        응답 필드: roe_val(ROE), eps(EPS), bps(BPS), grs(매출액증가율),
                   bsop_prfi_inrt(영업이익증가율)
        fid_div_cls_code: 1=분기 (최신 분기 기준)
        """
        try:
            url    = BASE_URL + "/uapi/domestic-stock/v1/finance/financial-ratio"
            params = {
                "FID_DIV_CLS_CODE":       "1",
                "fid_cond_mrkt_div_code": "J",
                "fid_input_iscd":          code,
            }
            out = requests.get(url, headers=self.headers("FHKST66430300"),
                               params=params, timeout=5).json().get("output", [])
            row = out[0] if isinstance(out, list) and out else {}
            return {
                "roe":       float(row.get("roe_val",        0) or 0),
                "eps":       float(row.get("eps",             0) or 0),
                "bps":       float(row.get("bps",             0) or 0),
                "grs":       float(row.get("grs",             0) or 0),  # 매출액 증가율
                "op_growth": float(row.get("bsop_prfi_inrt", 0) or 0),   # 영업이익 증가율
            }
        except Exception as e:
            logger.warning(f"[KIS] 재무비율 조회 실패 {code}: {e}")
            return {"roe": 0, "eps": 0, "bps": 0, "grs": 0, "op_growth": 0}

    def get_profit_ratio(self, code: str) -> dict:
        """
        수익성비율 조회 (FHKST66430400).
        URL: /uapi/domestic-stock/v1/finance/profit-ratio
        응답 필드: cptl_ntin_rate(총자본순이익율), self_cptl_ntin_inrt(자기자본순이익율=ROE),
                   sale_ntin_rate(매출액순이익율), sale_totl_rate(매출액총이익율)
        """
        try:
            url    = BASE_URL + "/uapi/domestic-stock/v1/finance/profit-ratio"
            params = {
                "fid_input_iscd":          code,
                "fid_div_cls_code":        "1",
                "fid_cond_mrkt_div_code": "J",
            }
            out = requests.get(url, headers=self.headers("FHKST66430400"),
                               params=params, timeout=5).json().get("output", [])
            row = out[0] if isinstance(out, list) and out else {}
            return {
                "roa":            float(row.get("cptl_ntin_rate",      0) or 0),  # 총자본순이익율
                "roe":            float(row.get("self_cptl_ntin_inrt", 0) or 0),  # 자기자본순이익율
                "net_margin":     float(row.get("sale_ntin_rate",      0) or 0),  # 매출액순이익율
                "gross_margin":   float(row.get("sale_totl_rate",      0) or 0),  # 매출액총이익율
            }
        except Exception as e:
            logger.warning(f"[KIS] 수익성비율 조회 실패 {code}: {e}")
            return {"roa": 0, "roe": 0, "net_margin": 0, "gross_margin": 0}

    def get_growth_ratio(self, code: str) -> dict:
        """
        성장성비율 조회 (FHKST66430800).
        URL: /uapi/domestic-stock/v1/finance/growth-ratio
        응답 필드: grs(매출액증가율), bsop_prfi_inrt(영업이익증가율),
                   equt_inrt(자기자본증가율), totl_aset_inrt(총자산증가율)
        """
        try:
            url    = BASE_URL + "/uapi/domestic-stock/v1/finance/growth-ratio"
            params = {
                "fid_input_iscd":          code,
                "fid_div_cls_code":        "1",
                "fid_cond_mrkt_div_code": "J",
            }
            out = requests.get(url, headers=self.headers("FHKST66430800"),
                               params=params, timeout=5).json().get("output", [])
            row = out[0] if isinstance(out, list) and out else {}
            return {
                "revenue_growth": float(row.get("grs",            0) or 0),  # 매출액 증가율
                "op_growth":      float(row.get("bsop_prfi_inrt", 0) or 0),  # 영업이익 증가율
                "equity_growth":  float(row.get("equt_inrt",      0) or 0),  # 자기자본 증가율
                "asset_growth":   float(row.get("totl_aset_inrt", 0) or 0),  # 총자산 증가율
            }
        except Exception as e:
            logger.warning(f"[KIS] 성장성비율 조회 실패 {code}: {e}")
            return {"revenue_growth": 0, "op_growth": 0, "equity_growth": 0, "asset_growth": 0}

    def get_balance_sheet(self, code: str, yearly: bool = False) -> list:
        """
        대차대조표 조회 (FHKST66430100) -- 재무상태표.
        URL: /uapi/domestic-stock/v1/finance/balance-sheet
        분기(기본) 또는 연간(yearly=True) 기준, 최근 4개 결산기 반환 (최신이 먼저).

        각 원소: {
            "period":        "202412" (결산년월),
            "current_asset": 유동자산, "fixed_asset": 고정자산, "total_asset": 자산총계,
            "current_liab":  유동부채, "fixed_liab":  고정부채, "total_liab":  부채총계,
            "capital_stock": 자본금,   "total_equity": 자본총계,
        }
        (단위: API 응답 그대로 -- 보통 백만원 단위)
        """
        try:
            url    = BASE_URL + "/uapi/domestic-stock/v1/finance/balance-sheet"
            params = {
                "fid_input_iscd":          code,
                "fid_div_cls_code":        "0" if yearly else "1",
                "fid_cond_mrkt_div_code": "J",
            }
            out = requests.get(url, headers=self.headers("FHKST66430100"),
                               params=params, timeout=5).json().get("output", [])
            result = []
            for row in out:
                result.append({
                    "period":        row.get("stac_yymm",   ""),
                    "current_asset": float(row.get("cras",       0) or 0),
                    "fixed_asset":   float(row.get("fxas",       0) or 0),
                    "total_asset":   float(row.get("total_aset", 0) or 0),
                    "current_liab":  float(row.get("flow_lblt",  0) or 0),
                    "fixed_liab":    float(row.get("fix_lblt",   0) or 0),
                    "total_liab":    float(row.get("total_lblt", 0) or 0),
                    "capital_stock": float(row.get("cpfn",       0) or 0),
                    "total_equity":  float(row.get("total_cptl", 0) or 0),
                })
            return result
        except Exception as e:
            logger.warning(f"[KIS] 대차대조표 조회 실패 {code}: {e}")
            return []

    def get_income_statement(self, code: str, yearly: bool = False) -> list:
        """
        손익계산서 조회 (FHKST66430200).
        URL: /uapi/domestic-stock/v1/finance/income-statement
        분기(기본) 또는 연간(yearly=True) 기준, 최근 4개 결산기 반환 (최신이 먼저).
        분기 데이터는 KIS 응답 특성상 "연초 누적 합산" 값입니다.

        각 원소: {
            "period":     "202412" (결산년월),
            "revenue":    매출액, "cost_of_sales": 매출원가, "gross_profit": 매출총이익,
            "op_profit":  영업이익, "ordinary_profit": 경상이익, "net_income": 당기순이익,
        }
        (단위: API 응답 그대로 -- 보통 백만원 단위)
        """
        try:
            url    = BASE_URL + "/uapi/domestic-stock/v1/finance/income-statement"
            params = {
                "fid_input_iscd":          code,
                "fid_div_cls_code":        "0" if yearly else "1",
                "fid_cond_mrkt_div_code": "J",
            }
            out = requests.get(url, headers=self.headers("FHKST66430200"),
                               params=params, timeout=5).json().get("output", [])
            result = []
            for row in out:
                result.append({
                    "period":          row.get("stac_yymm",       ""),
                    "revenue":         float(row.get("sale_account",   0) or 0),
                    "cost_of_sales":   float(row.get("sale_cost",      0) or 0),
                    "gross_profit":    float(row.get("sale_totl_prfi", 0) or 0),
                    "op_profit":       float(row.get("bsop_prti",      0) or 0),
                    "ordinary_profit": float(row.get("op_prfi",        0) or 0),
                    "net_income":      float(row.get("thtr_ntin",      0) or 0),
                })
            return result
        except Exception as e:
            logger.warning(f"[KIS] 손익계산서 조회 실패 {code}: {e}")
            return []

    def get_invest_opinion(self, code: str) -> dict:
        """
        종목투자의견 조회 (FHKST663300C0) -- 증권사 애널리스트 목표가 참고용.
        URL: /uapi/domestic-stock/v1/quotations/invest-opinion
        응답 필드: invt_opnn(투자의견), hts_goal_prc(목표가), stck_prdy_clpr(전일종가)
        최근 6개월치 중 가장 최신 데이터 사용.

        투자의견 코드 (invt_opnn): 1=매수강화, 2=매수, 3=중립, 4=매도, 5=매도강화
        """
        try:
            from datetime import date, timedelta as _td
            today = date.today()
            url   = BASE_URL + "/uapi/domestic-stock/v1/quotations/invest-opinion"
            params = {
                "fid_cond_mrkt_div_code": "J",
                "fid_cond_scr_div_code":  "16633",
                "fid_input_iscd":          code,
                "fid_input_date_1":        (today - _td(days=180)).strftime("%Y%m%d"),
                "fid_input_date_2":        today.strftime("%Y%m%d"),
            }
            out = requests.get(url, headers=self.headers("FHKST663300C0"),
                               params=params, timeout=5).json().get("output", [])
            if not out:
                return {}
            row      = out[0] if isinstance(out, list) else out
            goal_prc = float(row.get("hts_goal_prc",  0) or 0)
            cur_prc  = float(row.get("stck_prdy_clpr", 0) or 0)
            opinion  = row.get("invt_opnn", "")
            upside = ((goal_prc - cur_prc) / cur_prc * 100) if cur_prc > 0 and goal_prc > 0 else 0.0
            return {
                "opinion":  opinion,
                "goal_prc": goal_prc,
                "cur_prc":  cur_prc,
                "upside":   round(upside, 2),  # 목표가 대비 상승 여력 (%)
            }
        except Exception as e:
            logger.warning(f"[KIS] 종목투자의견 조회 실패 {code}: {e}")
            return {}

    # ── 대량 조회 (전체 종목 유니버스 구성용) ──────────────────────────────────

    def get_market_cap_ranking(self, market_code: str, price_min: str = "", price_max: str = "") -> list:
        """
        국내주식 시가총액 상위 조회 (FHPST01740000) -- 최대 30건.
        URL: /uapi/domestic-stock/v1/ranking/market-cap

        market_code: "0001"=거래소(코스피), "1001"=코스닥
        price_min/price_max: 가격대 필터 (문자열, 빈 값이면 무제한)
            -- 30건 제한을 넘어서기 위해 full_universe.py 가 가격대를 나눠 여러 번 호출함

        Returns: [{"code","name","price","market_cap"}, ...] 시가총액 내림차순
        """
        try:
            url = BASE_URL + "/uapi/domestic-stock/v1/ranking/market-cap"
            params = {
                "fid_cond_mrkt_div_code": "J",
                "fid_cond_scr_div_code":  "20174",
                "fid_div_cls_code":       "0",     # 0: 전체(보통주+우선주)
                "fid_input_iscd":         market_code,
                "fid_trgt_cls_code":      "0",
                "fid_trgt_exls_cls_code": "0",
                "fid_input_price_1":      price_min,
                "fid_input_price_2":      price_max,
                "fid_vol_cnt":            "",
            }
            out = requests.get(url, headers=self.headers("FHPST01740000"),
                               params=params, timeout=10).json().get("output", [])
            return [
                {
                    "code":       row.get("mksc_shrn_iscd", ""),
                    "name":       row.get("hts_kor_isnm",   ""),
                    "price":      float(row.get("stck_prpr", 0) or 0),
                    "market_cap": float(row.get("stck_avls", 0) or 0),
                }
                for row in out
            ]
        except Exception as e:
            logger.warning(f"[KIS] 시가총액 순위 조회 실패 ({market_code}, {price_min}~{price_max}): {e}")
            return []

    def get_overseas_market_cap_ranking(self, excd: str, vol_rang: str = "0") -> list:
        """
        해외주식 시가총액순위 조회 (HHDFS76350100) -- 최대 100건.
        URL: /uapi/overseas-stock/v1/ranking/market-cap

        excd: "NAS"=나스닥, "NYS"=뉴욕, "AMS"=아멕스
        vol_rang: 거래량 조건 (0=전체)

        [ 참고 ] 문서에는 없지만 실제로는 CURR_GB(통화구분) 파라미터가 필수라
        "0"으로 고정 전달 -- 이 값을 안 보내면 API가 에러를 반환함(문서-실제 API 불일치).

        Returns: [{"code","name","price","market_cap"}, ...] 시가총액 내림차순 (최대 100개)
        """
        try:
            url = BASE_URL + "/uapi/overseas-stock/v1/ranking/market-cap"
            params = {
                "KEYB":     "",
                "AUTH":     "",
                "EXCD":     excd,
                "VOL_RANG": vol_rang,
                "CURR_GB":  "0",
            }
            out = requests.get(url, headers=self.headers("HHDFS76350100"),
                               params=params, timeout=10).json().get("output2", [])
            return [
                {
                    "code":       row.get("symb", ""),
                    "name":       row.get("name", ""),
                    "price":      float(row.get("last", 0) or 0),
                    "market_cap": float(row.get("tomv", 0) or 0),
                }
                for row in out
            ]
        except Exception as e:
            logger.warning(f"[KIS] 해외 시가총액 순위 조회 실패 ({excd}): {e}")
            return []

    def get_overseas_trade_value_ranking(self, excd: str, price_min: str = "", price_max: str = "",
                                          vol_rang: str = "0") -> list:
        """
        해외주식 거래대금순위 조회 (HHDFS76320010) -- 최대 100건, 가격대 필터 지원.
        URL: /uapi/overseas-stock/v1/ranking/trade-pbmn

        시가총액순위(get_overseas_market_cap_ranking)와 달리 이 API는 PRC1/PRC2 로
        가격대를 나눠 여러 번 호출할 수 있어서, full_universe.py 가 이 방식으로
        거래소당 100개보다 훨씬 많은 종목을 모을 수 있습니다.
        (거래대금 기준이라 실제로 활발히 거래되는 종목 위주로 잡힘)

        excd: "NAS"=나스닥, "NYS"=뉴욕, "AMS"=아멕스
        price_min/price_max: 가격대 필터 (문자열, 빈 값이면 무제한)

        Returns: [{"code","name","price","trade_value"}, ...] 거래대금 내림차순 (최대 100개)
        """
        try:
            url = BASE_URL + "/uapi/overseas-stock/v1/ranking/trade-pbmn"
            params = {
                "KEYB":     "",
                "AUTH":     "",
                "EXCD":     excd,
                "NDAY":     "0",     # 0 = 당일 기준
                "VOL_RANG": vol_rang,
                "PRC1":     price_min,
                "PRC2":     price_max,
                "CURR_GB":  "0",     # market-cap 랭킹과 동일하게 실제로는 필수 (문서 누락)
            }
            out = requests.get(url, headers=self.headers("HHDFS76320010"),
                               params=params, timeout=10).json().get("output2", [])
            return [
                {
                    "code":        row.get("symb", ""),
                    "name":        row.get("name", ""),
                    "price":       float(row.get("last", 0) or 0),
                    "trade_value": float(row.get("tamt", 0) or 0),
                }
                for row in out
            ]
        except Exception as e:
            logger.warning(f"[KIS] 해외 거래대금 순위 조회 실패 ({excd}, {price_min}~{price_max}): {e}")
            return []

    def get_overseas_price_detail(self, excd: str, symbol: str) -> dict:
        """
        해외주식 현재가상세 조회 (HHDFS76200200).
        URL: /uapi/overseas-price/v1/quotations/price-detail
        응답 필드: perx(PER), pbrx(PBR), epsx(EPS), bpsx(BPS), last(현재가)

        [ 참고 ] 미국 주식은 KIS 가 대차대조표/손익계산서를 제공하지 않아서
        ROE 는 EPS/BPS 로 근사치를 계산합니다 (value_screener_us.py 참고).
        """
        try:
            url    = BASE_URL + "/uapi/overseas-price/v1/quotations/price-detail"
            params = {"AUTH": "", "EXCD": excd, "SYMB": symbol}
            out = requests.get(url, headers=self.headers("HHDFS76200200"),
                               params=params, timeout=5).json().get("output", {})
            return {
                "price": float(out.get("last", 0) or 0),
                "per":   float(out.get("perx", 0) or 0),
                "pbr":   float(out.get("pbrx", 0) or 0),
                "eps":   float(out.get("epsx", 0) or 0),
                "bps":   float(out.get("bpsx", 0) or 0),
            }
        except Exception as e:
            logger.warning(f"[KIS] 해외 현재가상세 조회 실패 {excd}/{symbol}: {e}")
            return {"price": 0.0, "per": 0.0, "pbr": 0.0, "eps": 0.0, "bps": 0.0}
