"""
정부 지원사업 수집기 — GUI
tkinter 기반 (Python 기본 내장)
"""

import json
import os
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

CONFIG_FILE = "gov_설정.json"


def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_config(cfg: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


class GovSupportApp:
    def __init__(self, root):
        self.root = root
        self.root.title("정부 지원사업 수집기")
        self.root.geometry("600x820")
        self.root.resizable(False, False)
        self.root.configure(bg="#f5f5f5")
        self.cfg = load_config()
        self._build_ui()
        self._load_values()

    # ─── 공통 위젯 헬퍼 ──────────────────────────────────────

    def _section(self, parent, text):
        f = tk.LabelFrame(parent, text=f"  {text}  ",
                          bg="#f5f5f5", fg="#333",
                          font=("맑은 고딕", 10, "bold"),
                          padx=10, pady=6)
        f.pack(fill="x", padx=14, pady=(5, 0))
        return f

    def _row(self, parent, label, widget_cls, **kw):
        row = tk.Frame(parent, bg="#f5f5f5")
        row.pack(fill="x", pady=2)
        tk.Label(row, text=label, width=14, anchor="w",
                 bg="#f5f5f5", font=("맑은 고딕", 9)).pack(side="left")
        w = widget_cls(row, **kw)
        w.pack(side="left", fill="x", expand=True)
        return w

    def _check_row(self, parent, items: dict, cols=3):
        """체크박스 여러 개를 그리드로 배치"""
        row = tk.Frame(parent, bg="#f5f5f5")
        row.pack(fill="x", pady=2)
        for i, (key, var) in enumerate(items.items()):
            tk.Checkbutton(row, text=key, variable=var,
                           bg="#f5f5f5", font=("맑은 고딕", 9)
                           ).grid(row=i // cols, column=i % cols,
                                  sticky="w", padx=6, pady=1)
        return row

    def _label_checks(self, parent, label, items: dict, cols=3):
        row = tk.Frame(parent, bg="#f5f5f5")
        row.pack(fill="x", pady=2)
        tk.Label(row, text=label, width=14, anchor="nw",
                 bg="#f5f5f5", font=("맑은 고딕", 9)).pack(side="left")
        inner = tk.Frame(row, bg="#f5f5f5")
        inner.pack(side="left", fill="x", expand=True)
        for i, (key, var) in enumerate(items.items()):
            tk.Checkbutton(inner, text=key, variable=var,
                           bg="#f5f5f5", font=("맑은 고딕", 9)
                           ).grid(row=i // cols, column=i % cols,
                                  sticky="w", padx=4, pady=1)

    def _kw_row(self, parent, label):
        row = tk.Frame(parent, bg="#f5f5f5")
        row.pack(fill="x", pady=2)
        tk.Label(row, text=label, width=14, anchor="w",
                 bg="#f5f5f5", font=("맑은 고딕", 9)).pack(side="left")
        var = tk.StringVar()
        tk.Entry(row, textvariable=var, width=34).pack(side="left")
        tk.Label(row, text=" 쉼표 구분", bg="#f5f5f5",
                 fg="#888", font=("맑은 고딕", 8)).pack(side="left")
        return var

    # ─── UI 빌드 ─────────────────────────────────────────────

    def _build_ui(self):
        # 헤더
        hdr = tk.Frame(self.root, bg="#4472C4", height=46)
        hdr.pack(fill="x")
        tk.Label(hdr, text="정부 지원사업 통합 수집기",
                 bg="#4472C4", fg="white",
                 font=("맑은 고딕", 13, "bold")).pack(pady=10)

        # 탭
        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=8, pady=6)

        self.tab_profile = tk.Frame(nb, bg="#f5f5f5")
        self.tab_output  = tk.Frame(nb, bg="#f5f5f5")
        self.tab_run     = tk.Frame(nb, bg="#f5f5f5")

        nb.add(self.tab_profile, text="  내 프로필  ")
        nb.add(self.tab_output,  text="  출력 설정  ")
        nb.add(self.tab_run,     text="  실행 · 로그  ")

        self._build_profile_tab()
        self._build_output_tab()
        self._build_run_tab()

    def _scrollable(self, parent):
        canvas = tk.Canvas(parent, bg="#f5f5f5", highlightthickness=0)
        sb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        frame = tk.Frame(canvas, bg="#f5f5f5")
        frame.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=frame, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        return frame

    def _build_profile_tab(self):
        sf = self._scrollable(self.tab_profile)

        # 기본정보
        sec = self._section(sf, "기본정보")
        self.age_var    = tk.StringVar()
        self.gender_var = tk.StringVar()
        self.region_var = tk.StringVar()
        self._row(sec, "나이", tk.Entry, textvariable=self.age_var, width=6)
        self._row(sec, "성별", ttk.Combobox,
                  textvariable=self.gender_var,
                  values=["", "여성", "남성"], width=8, state="readonly")
        self._row(sec, "거주지역", ttk.Combobox,
                  textvariable=self.region_var,
                  values=["", "전국", "서울", "부산", "대구", "인천", "광주",
                          "대전", "울산", "세종", "경기", "강원", "충북",
                          "충남", "전북", "전남", "경북", "경남", "제주"],
                  width=10, state="readonly")

        # 가족상황
        sec = self._section(sf, "가족상황")
        self.marry_var   = tk.StringVar()
        self.pregnant_var = tk.BooleanVar()
        self.child_var   = tk.BooleanVar()
        self.child_cnt   = tk.StringVar()
        self._row(sec, "결혼여부", ttk.Combobox,
                  textvariable=self.marry_var,
                  values=["", "미혼", "기혼", "이혼", "사별"],
                  width=8, state="readonly")

        row = tk.Frame(sec, bg="#f5f5f5"); row.pack(fill="x", pady=2)
        tk.Label(row, text="임신여부", width=14, anchor="w",
                 bg="#f5f5f5", font=("맑은 고딕", 9)).pack(side="left")
        tk.Checkbutton(row, text="임신 중", variable=self.pregnant_var,
                       bg="#f5f5f5", font=("맑은 고딕", 9)).pack(side="left")

        row2 = tk.Frame(sec, bg="#f5f5f5"); row2.pack(fill="x", pady=2)
        tk.Label(row2, text="자녀", width=14, anchor="w",
                 bg="#f5f5f5", font=("맑은 고딕", 9)).pack(side="left")
        tk.Checkbutton(row2, text="자녀 있음", variable=self.child_var,
                       bg="#f5f5f5", font=("맑은 고딕", 9)).pack(side="left")
        tk.Label(row2, text="  명수:", bg="#f5f5f5",
                 font=("맑은 고딕", 9)).pack(side="left")
        tk.Entry(row2, textvariable=self.child_cnt, width=4).pack(side="left")

        self.child_age_vars = {}
        for age_group in ["영아(0-2세)", "유아(3-7세)", "초등(8-13세)", "청소년(14-18세)"]:
            self.child_age_vars[age_group] = tk.BooleanVar()
        self._label_checks(sec, "자녀나이대", self.child_age_vars, cols=4)

        self.family_vars = {}
        for item in ["한부모가족", "조손가족", "다문화가족"]:
            self.family_vars[item] = tk.BooleanVar()
        self._label_checks(sec, "가족형태", self.family_vars, cols=3)

        # 고용·소득
        sec = self._section(sf, "고용 · 소득")
        self.emp_vars = {}
        for s in ["취업준비생", "재직자", "사업자", "프리랜서",
                  "무직", "경력단절", "육아휴직중", "퇴직자"]:
            self.emp_vars[s] = tk.BooleanVar()
        self._label_checks(sec, "고용상태", self.emp_vars, cols=4)

        self.income_var = tk.StringVar()
        self._row(sec, "월소득(만원)", tk.Entry, textvariable=self.income_var, width=8)

        self.insurance_vars = {}
        for s in ["고용보험가입", "국민연금가입", "4대보험가입"]:
            self.insurance_vars[s] = tk.BooleanVar()
        self._label_checks(sec, "보험가입", self.insurance_vars, cols=3)

        # 건강·장애
        sec = self._section(sf, "건강 · 장애")
        self.health_vars = {}
        for s in ["장애인등록", "만성질환보유", "희귀질환보유",
                  "국가유공자", "보훈대상자"]:
            self.health_vars[s] = tk.BooleanVar()
        self._label_checks(sec, "해당항목", self.health_vars, cols=3)
        self.disability_var = tk.StringVar()
        self._row(sec, "장애등급", tk.Entry,
                  textvariable=self.disability_var, width=16)

        # 주거상황
        sec = self._section(sf, "주거상황")
        self.house_type_var = tk.StringVar()
        self._row(sec, "주거형태", ttk.Combobox,
                  textvariable=self.house_type_var,
                  values=["", "자가", "전세", "월세", "공공임대", "무주택"],
                  width=10, state="readonly")
        self.house_vars = {}
        for s in ["무주택", "청약통장보유", "기초생활수급자", "차상위계층"]:
            self.house_vars[s] = tk.BooleanVar()
        self._label_checks(sec, "해당항목", self.house_vars, cols=4)

        # 학력·교육
        sec = self._section(sf, "학력 · 교육")
        self.edu_var = tk.StringVar()
        self._row(sec, "학력", ttk.Combobox,
                  textvariable=self.edu_var,
                  values=["", "중졸이하", "고졸", "대학재학", "대졸", "대학원"],
                  width=10, state="readonly")
        self.edu_check_vars = {}
        for s in ["재학중", "휴학중", "국비교육수강중", "졸업후취업준비"]:
            self.edu_check_vars[s] = tk.BooleanVar()
        self._label_checks(sec, "현재상태", self.edu_check_vars, cols=4)

        # 사업·창업
        sec = self._section(sf, "사업 · 창업")
        self.biz_vars = {}
        for s in ["사업자등록", "예비창업자", "소상공인",
                  "중소기업", "여성기업인"]:
            self.biz_vars[s] = tk.BooleanVar()
        self._label_checks(sec, "해당항목", self.biz_vars, cols=3)
        self.biz_year_var = tk.StringVar()
        self._row(sec, "창업연차", tk.Entry, textvariable=self.biz_year_var, width=6)
        self.biz_type_var = tk.StringVar()
        self._row(sec, "업종", tk.Entry, textvariable=self.biz_type_var, width=20)

        # 특수상황
        sec = self._section(sf, "특수상황")
        self.special_vars = {}
        for s in ["북한이탈주민", "귀환동포", "외국인",
                  "농어업인", "청년농부", "사회적기업운영", "협동조합운영"]:
            self.special_vars[s] = tk.BooleanVar()
        self._label_checks(sec, "해당항목", self.special_vars, cols=3)

        # 키워드
        sec = self._section(sf, "키워드")
        self.interest_var = self._kw_row(sec, "관심키워드")
        self.exclude_var  = self._kw_row(sec, "제외키워드")

        tk.Frame(sf, height=10, bg="#f5f5f5").pack()

    def _build_output_tab(self):
        sf = self._scrollable(self.tab_output)

        sec = self._section(sf, "출력 방식")
        self.csv_var    = tk.BooleanVar(value=True)
        self.sheets_var = tk.BooleanVar()
        self.email_var  = tk.BooleanVar()
        self.kakao_var  = tk.BooleanVar()
        for var, text in [(self.csv_var,    "CSV 파일 저장"),
                          (self.sheets_var, "Google Sheets 업데이트"),
                          (self.email_var,  "이메일 리포트 발송"),
                          (self.kakao_var,  "카카오 마감임박 알림")]:
            tk.Checkbutton(sec, text=text, variable=var,
                           bg="#f5f5f5", font=("맑은 고딕", 9)).pack(anchor="w", pady=1)

        sec2 = self._section(sf, "알림 설정")
        self.email_addr_var = tk.StringVar()
        self.phone_var      = tk.StringVar()
        self.deadline_var   = tk.StringVar(value="7")
        self._row(sec2, "수신 이메일",    tk.Entry, textvariable=self.email_addr_var, width=28)
        self._row(sec2, "카카오 전화번호", tk.Entry, textvariable=self.phone_var,      width=16)
        self._row(sec2, "마감임박 기준",   tk.Entry, textvariable=self.deadline_var,   width=6)
        tk.Label(sec2, text="  * 마감임박 기준: 몇 일 이내인지 (기본 7)",
                 bg="#f5f5f5", fg="#888", font=("맑은 고딕", 8)).pack(anchor="w")

    def _build_run_tab(self):
        btn_frame = tk.Frame(self.tab_run, bg="#f5f5f5")
        btn_frame.pack(fill="x", padx=14, pady=10)
        tk.Button(btn_frame, text="설정 저장", width=12,
                  bg="#888", fg="white", relief="flat",
                  font=("맑은 고딕", 10),
                  command=self._save_only).pack(side="left", padx=(0, 8))
        tk.Button(btn_frame, text="▶  수집 시작", width=16,
                  bg="#4472C4", fg="white", relief="flat",
                  font=("맑은 고딕", 11, "bold"),
                  command=self._run).pack(side="left")

        self.log_box = scrolledtext.ScrolledText(
            self.tab_run, font=("Consolas", 9),
            bg="#1e1e1e", fg="#d4d4d4", state="disabled")
        self.log_box.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    # ─── 값 로드 ─────────────────────────────────────────────

    def _load_values(self):
        p  = self.cfg.get("내_프로필", {})
        기본 = p.get("기본정보", {})
        가족 = p.get("가족상황", {})
        고용 = p.get("고용소득", {})
        건강 = p.get("건강장애", {})
        주거 = p.get("주거상황", {})
        학력 = p.get("학력교육", {})
        사업 = p.get("사업창업", {})
        특수 = p.get("특수상황", {})

        self.age_var.set(str(기본.get("나이", "") or ""))
        self.gender_var.set(기본.get("성별", ""))
        self.region_var.set(기본.get("거주지역", ""))

        self.marry_var.set(가족.get("결혼여부", ""))
        self.pregnant_var.set(가족.get("임신여부", False))
        self.child_var.set(가족.get("자녀유무", False))
        self.child_cnt.set(str(가족.get("자녀수", "") or ""))
        for k, v in self.child_age_vars.items():
            v.set(k in 가족.get("자녀나이대", []))
        for k, v in self.family_vars.items():
            v.set(가족.get(k, False))

        emp = 고용.get("고용상태", {})
        for k, v in self.emp_vars.items():
            v.set(emp.get(k, False))
        self.income_var.set(str(고용.get("월소득(만원)", "") or ""))
        for k, v in self.insurance_vars.items():
            key = k.replace("가입", "가입")
            v.set(고용.get(key, False))

        for k, v in self.health_vars.items():
            v.set(건강.get(k, False))
        self.disability_var.set(건강.get("장애등급", ""))

        self.house_type_var.set(주거.get("주거형태", ""))
        for k, v in self.house_vars.items():
            v.set(주거.get(k, False))

        self.edu_var.set(학력.get("학력", ""))
        for k, v in self.edu_check_vars.items():
            v.set(학력.get(k, False))

        for k, v in self.biz_vars.items():
            v.set(사업.get(k, False))
        self.biz_year_var.set(str(사업.get("창업연차", "") or ""))
        self.biz_type_var.set(사업.get("업종", ""))

        for k, v in self.special_vars.items():
            v.set(특수.get(k, False))

        self.interest_var.set(", ".join(p.get("관심키워드", [])))
        self.exclude_var.set(", ".join(p.get("제외키워드", [])))

        out = self.cfg.get("출력설정", {})
        self.csv_var.set(out.get("CSV저장", True))
        self.sheets_var.set(out.get("Google_Sheets_업데이트", False))
        self.email_var.set(out.get("이메일_리포트_발송", False))
        self.kakao_var.set(out.get("카카오_마감임박_알림", False))
        self.email_addr_var.set(self.cfg.get("이메일설정", {}).get("수신_이메일", ""))
        self.phone_var.set(self.cfg.get("카카오설정", {}).get("수신_전화번호", ""))
        try:
            self.deadline_var.set(str(self.cfg.get("필터조건", {}).get("마감일_임박_알림_기준(일)", 7)))
        except Exception:
            self.deadline_var.set("7")

    # ─── 설정 수집 ───────────────────────────────────────────

    def _collect_config(self) -> dict:
        def kws(s): return [k.strip() for k in s.split(",") if k.strip()]
        def intv(v, default=0):
            try: return int(v.get())
            except: return default

        child_ages = [k for k, v in self.child_age_vars.items() if v.get()]

        return {
            "내_프로필": {
                "기본정보": {
                    "나이":     intv(self.age_var),
                    "성별":     self.gender_var.get(),
                    "거주지역": self.region_var.get(),
                },
                "가족상황": {
                    "결혼여부":   self.marry_var.get(),
                    "임신여부":   self.pregnant_var.get(),
                    "자녀유무":   self.child_var.get(),
                    "자녀수":     intv(self.child_cnt),
                    "자녀나이대": child_ages,
                    **{k: v.get() for k, v in self.family_vars.items()},
                },
                "고용소득": {
                    "고용상태":     {k: v.get() for k, v in self.emp_vars.items()},
                    "월소득(만원)": intv(self.income_var),
                    **{k: v.get() for k, v in self.insurance_vars.items()},
                },
                "건강장애": {
                    **{k: v.get() for k, v in self.health_vars.items()},
                    "장애등급": self.disability_var.get(),
                },
                "주거상황": {
                    "주거형태": self.house_type_var.get(),
                    **{k: v.get() for k, v in self.house_vars.items()},
                },
                "학력교육": {
                    "학력": self.edu_var.get(),
                    **{k: v.get() for k, v in self.edu_check_vars.items()},
                },
                "사업창업": {
                    **{k: v.get() for k, v in self.biz_vars.items()},
                    "창업연차": intv(self.biz_year_var),
                    "업종":     self.biz_type_var.get(),
                },
                "특수상황": {k: v.get() for k, v in self.special_vars.items()},
                "관심키워드": kws(self.interest_var.get()),
                "제외키워드": kws(self.exclude_var.get()),
            },
            "필터조건": {
                "마감일_임박_알림_기준(일)": intv(self.deadline_var, 7),
                "최대_출력_건수": 100,
            },
            "출력설정": {
                "CSV저장":                self.csv_var.get(),
                "Google_Sheets_업데이트": self.sheets_var.get(),
                "이메일_리포트_발송":      self.email_var.get(),
                "카카오_마감임박_알림":    self.kakao_var.get(),
            },
            "이메일설정":      {"수신_이메일":    self.email_addr_var.get()},
            "카카오설정":      {"수신_전화번호":  self.phone_var.get()},
            "Google_Sheets설정": {"시트명": "정부지원사업"},
        }

    def _save_only(self):
        save_config(self._collect_config())
        messagebox.showinfo("저장 완료", "설정이 저장됐습니다.")

    # ─── 로그 ────────────────────────────────────────────────

    def _log(self, text: str):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _clear_log(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    # ─── 실행 ────────────────────────────────────────────────

    def _run(self):
        save_config(self._collect_config())
        self._clear_log()
        self._log("설정 저장 완료. 수집을 시작합니다...\n")
        threading.Thread(target=self._run_bg, daemon=True).start()

    def _run_bg(self):
        import io, sys
        from gov_support import run_gov_support

        class LogRedirect(io.StringIO):
            def __init__(self, cb): super().__init__(); self.cb = cb
            def write(self, s):
                if s.strip(): self.cb(s.rstrip())
            def flush(self): pass

        old = sys.stdout
        sys.stdout = LogRedirect(self._log)
        try:
            run_gov_support()
            self._log("\n✅ 수집 완료!")
        except Exception as e:
            self._log(f"\n❌ 오류: {e}")
        finally:
            sys.stdout = old


if __name__ == "__main__":
    root = tk.Tk()
    GovSupportApp(root)
    root.mainloop()
