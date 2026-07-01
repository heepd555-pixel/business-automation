"""
정부 지원사업 수집기 — GUI 실행 파일
tkinter 기반 (Python 기본 내장, 별도 설치 불필요)
"""

import json
import os
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

CONFIG_FILE = "gov_설정.json"


# ─── 설정 로드/저장 ───────────────────────────────────────────

def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_config(cfg: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


# ─── GUI ──────────────────────────────────────────────────────

class GovSupportApp:
    def __init__(self, root):
        self.root = root
        self.root.title("정부 지원사업 수집기")
        self.root.geometry("560x720")
        self.root.resizable(False, False)
        self.root.configure(bg="#f5f5f5")

        self.cfg = load_config()
        self._build_ui()
        self._load_values()

    def _section(self, parent, text):
        frame = tk.LabelFrame(
            parent, text=f"  {text}  ",
            bg="#f5f5f5", fg="#333",
            font=("맑은 고딕", 10, "bold"),
            padx=12, pady=8,
        )
        frame.pack(fill="x", padx=16, pady=(6, 0))
        return frame

    def _row(self, parent, label, widget_fn, **kw):
        row = tk.Frame(parent, bg="#f5f5f5")
        row.pack(fill="x", pady=3)
        tk.Label(row, text=label, width=12, anchor="w",
                 bg="#f5f5f5", font=("맑은 고딕", 9)).pack(side="left")
        w = widget_fn(row, **kw)
        w.pack(side="left", fill="x", expand=True)
        return w

    def _build_ui(self):
        # 타이틀
        title = tk.Frame(self.root, bg="#4472C4", height=50)
        title.pack(fill="x")
        tk.Label(title, text="정부 지원사업 통합 수집기",
                 bg="#4472C4", fg="white",
                 font=("맑은 고딕", 13, "bold")).pack(pady=12)

        # 스크롤 영역
        canvas = tk.Canvas(self.root, bg="#f5f5f5", highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=canvas.yview)
        self.scroll_frame = tk.Frame(canvas, bg="#f5f5f5")
        self.scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        self._build_profile()
        self._build_output()
        self._build_notification()
        self._build_buttons()

    def _build_profile(self):
        sec = self._section(self.scroll_frame, "내 프로필")

        self.age_var = tk.StringVar()
        self._row(sec, "나이", tk.Entry, textvariable=self.age_var, width=8)

        self.region_var = tk.StringVar()
        regions = ["", "전국", "서울", "부산", "대구", "인천", "광주",
                   "대전", "울산", "세종", "경기", "강원", "충북",
                   "충남", "전북", "전남", "경북", "경남", "제주"]
        self._row(sec, "거주지역", ttk.Combobox,
                  textvariable=self.region_var, values=regions, width=12, state="readonly")

        # 고용상태
        emp_frame = tk.Frame(sec, bg="#f5f5f5")
        emp_frame.pack(fill="x", pady=3)
        tk.Label(emp_frame, text="고용상태", width=12, anchor="w",
                 bg="#f5f5f5", font=("맑은 고딕", 9)).pack(side="left")
        self.emp_vars = {}
        for status in ["취업준비생", "재직자", "사업자", "프리랜서", "무직"]:
            var = tk.BooleanVar()
            self.emp_vars[status] = var
            tk.Checkbutton(emp_frame, text=status, variable=var,
                           bg="#f5f5f5", font=("맑은 고딕", 9)).pack(side="left", padx=4)

        # 관심 키워드
        interest_frame = tk.Frame(sec, bg="#f5f5f5")
        interest_frame.pack(fill="x", pady=3)
        tk.Label(interest_frame, text="관심키워드", width=12, anchor="w",
                 bg="#f5f5f5", font=("맑은 고딕", 9)).pack(side="left")
        self.interest_var = tk.StringVar()
        tk.Entry(interest_frame, textvariable=self.interest_var,
                 width=35).pack(side="left")
        tk.Label(interest_frame, text="  쉼표로 구분",
                 bg="#f5f5f5", fg="#888", font=("맑은 고딕", 8)).pack(side="left")

        # 제외 키워드
        exclude_frame = tk.Frame(sec, bg="#f5f5f5")
        exclude_frame.pack(fill="x", pady=3)
        tk.Label(exclude_frame, text="제외키워드", width=12, anchor="w",
                 bg="#f5f5f5", font=("맑은 고딕", 9)).pack(side="left")
        self.exclude_var = tk.StringVar()
        tk.Entry(exclude_frame, textvariable=self.exclude_var,
                 width=35).pack(side="left")
        tk.Label(exclude_frame, text="  쉼표로 구분",
                 bg="#f5f5f5", fg="#888", font=("맑은 고딕", 8)).pack(side="left")

        # 마감임박 기준
        deadline_frame = tk.Frame(sec, bg="#f5f5f5")
        deadline_frame.pack(fill="x", pady=3)
        tk.Label(deadline_frame, text="마감임박 기준", width=12, anchor="w",
                 bg="#f5f5f5", font=("맑은 고딕", 9)).pack(side="left")
        self.deadline_var = tk.StringVar(value="7")
        tk.Entry(deadline_frame, textvariable=self.deadline_var,
                 width=5).pack(side="left")
        tk.Label(deadline_frame, text="  일 이내",
                 bg="#f5f5f5", font=("맑은 고딕", 9)).pack(side="left")

    def _build_output(self):
        sec = self._section(self.scroll_frame, "출력 설정")

        self.csv_var    = tk.BooleanVar(value=True)
        self.sheets_var = tk.BooleanVar(value=False)
        self.email_var  = tk.BooleanVar(value=False)
        self.kakao_var  = tk.BooleanVar(value=False)

        for var, text in [
            (self.csv_var,    "CSV 파일 저장"),
            (self.sheets_var, "Google Sheets 업데이트"),
            (self.email_var,  "이메일 리포트 발송"),
            (self.kakao_var,  "카카오 마감임박 알림"),
        ]:
            tk.Checkbutton(sec, text=text, variable=var,
                           bg="#f5f5f5", font=("맑은 고딕", 9)).pack(anchor="w")

        self.email_addr_var = tk.StringVar()
        self._row(sec, "수신 이메일", tk.Entry,
                  textvariable=self.email_addr_var, width=30)

        self.phone_var = tk.StringVar()
        self._row(sec, "카카오 전화번호", tk.Entry,
                  textvariable=self.phone_var, width=20)

    def _build_notification(self):
        sec = self._section(self.scroll_frame, "실행 로그")
        self.log_box = scrolledtext.ScrolledText(
            sec, height=8, font=("Consolas", 9),
            bg="#1e1e1e", fg="#d4d4d4", state="disabled"
        )
        self.log_box.pack(fill="x")

    def _build_buttons(self):
        btn_frame = tk.Frame(self.scroll_frame, bg="#f5f5f5")
        btn_frame.pack(fill="x", padx=16, pady=12)

        tk.Button(
            btn_frame, text="설정 저장", width=12,
            bg="#888", fg="white", relief="flat",
            font=("맑은 고딕", 10),
            command=self._save_only,
        ).pack(side="left", padx=(0, 8))

        tk.Button(
            btn_frame, text="▶  수집 시작", width=16,
            bg="#4472C4", fg="white", relief="flat",
            font=("맑은 고딕", 11, "bold"),
            command=self._run,
        ).pack(side="left")

    # ─── 값 로드/저장 ─────────────────────────────────────────

    def _load_values(self):
        p = self.cfg.get("내_프로필", {})
        self.age_var.set(str(p.get("나이", "") or ""))
        self.region_var.set(p.get("거주지역", ""))
        for status, var in self.emp_vars.items():
            var.set(p.get("고용상태", {}).get(status, False))
        self.interest_var.set(", ".join(p.get("관심키워드", [])))
        self.exclude_var.set(", ".join(p.get("제외키워드", [])))

        f = self.cfg.get("필터조건", {})
        self.deadline_var.set(str(f.get("마감일_임박_알림_기준(일)", 7)))

        out = self.cfg.get("출력설정", {})
        self.csv_var.set(out.get("CSV저장", True))
        self.sheets_var.set(out.get("Google_Sheets_업데이트", False))
        self.email_var.set(out.get("이메일_리포트_발송", False))
        self.kakao_var.set(out.get("카카오_마감임박_알림", False))

        self.email_addr_var.set(self.cfg.get("이메일설정", {}).get("수신_이메일", ""))
        self.phone_var.set(self.cfg.get("카카오설정", {}).get("수신_전화번호", ""))

    def _collect_config(self) -> dict:
        def parse_keywords(s):
            return [k.strip() for k in s.split(",") if k.strip()]

        try:
            age = int(self.age_var.get()) if self.age_var.get().strip() else 0
        except ValueError:
            age = 0

        try:
            deadline = int(self.deadline_var.get())
        except ValueError:
            deadline = 7

        return {
            "_설명": "GUI에서 자동 저장된 설정입니다.",
            "내_프로필": {
                "나이": age,
                "거주지역": self.region_var.get(),
                "고용상태": {k: v.get() for k, v in self.emp_vars.items()},
                "관심키워드": parse_keywords(self.interest_var.get()),
                "제외키워드": parse_keywords(self.exclude_var.get()),
            },
            "필터조건": {
                "마감일_임박_알림_기준(일)": deadline,
                "최대_출력_건수": 100,
            },
            "출력설정": {
                "CSV저장":                self.csv_var.get(),
                "Google_Sheets_업데이트": self.sheets_var.get(),
                "이메일_리포트_발송":      self.email_var.get(),
                "카카오_마감임박_알림":    self.kakao_var.get(),
            },
            "이메일설정":      {"수신_이메일": self.email_addr_var.get()},
            "카카오설정":      {"수신_전화번호": self.phone_var.get()},
            "Google_Sheets설정": {"시트명": "정부지원사업"},
        }

    def _save_only(self):
        save_config(self._collect_config())
        messagebox.showinfo("저장 완료", "설정이 저장됐습니다.")

    # ─── 로그 출력 ────────────────────────────────────────────

    def _log(self, text: str):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _clear_log(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    # ─── 실행 ─────────────────────────────────────────────────

    def _run(self):
        save_config(self._collect_config())
        self._clear_log()
        self._log("설정 저장 완료. 수집을 시작합니다...\n")
        threading.Thread(target=self._run_bg, daemon=True).start()

    def _run_bg(self):
        import io
        import sys
        from gov_support import run_gov_support

        # 터미널 출력을 GUI 로그로 리다이렉트
        class LogRedirect(io.StringIO):
            def __init__(self, callback):
                super().__init__()
                self.callback = callback
            def write(self, s):
                if s.strip():
                    self.callback(s.rstrip())
            def flush(self):
                pass

        old_stdout = sys.stdout
        sys.stdout = LogRedirect(self._log)
        try:
            run_gov_support()
            self._log("\n✅ 수집 완료!")
        except Exception as e:
            self._log(f"\n❌ 오류 발생: {e}")
        finally:
            sys.stdout = old_stdout


# ─── 메인 ─────────────────────────────────────────────────────

if __name__ == "__main__":
    root = tk.Tk()
    app = GovSupportApp(root)
    root.mainloop()
