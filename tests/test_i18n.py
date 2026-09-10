"""ccp_i18n — 네 언어 사전의 완결성과, 렌더러·statusline 이 각 언어로 실제 도는지."""
import os, re, subprocess, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ccp_i18n  # noqa: E402


def test_모든_키에_네_언어가_다_있다():
    for k, v in ccp_i18n.M.items():
        assert len(v) == 4 and all(isinstance(x, str) and x for x in v), k


def test_자리표시자는_언어마다_같다():
    """{name} 이나 %s 가 한 언어에서만 빠지면 .format/printf 가 깨진다."""
    for k, v in ccp_i18n.M.items():
        ph = [sorted(re.findall(r"\{(\w+)\}", x)) for x in v]
        assert all(p == ph[0] for p in ph), (k, ph)
        pf = [re.findall(r"%[sd]", x) for x in v]
        assert all(p == pf[0] for p in pf), (k, pf)


def test_zsh_사전_파일이_최신이다():
    gen = subprocess.run([sys.executable, str(ROOT / "ccp_i18n.py"), "--zsh"], capture_output=True, text=True, check=True).stdout
    assert gen == (ROOT / "ccp_i18n.zsh").read_text(), "python3 ccp_i18n.py --zsh > ccp_i18n.zsh 를 다시 돌릴 것"


def test_zsh_사전은_zsh_문법이다():
    subprocess.run(["zsh", "-n", str(ROOT / "ccp_i18n.zsh")], check=True)


def test_언어_감지():
    d = ccp_i18n.detect
    assert d({"CCP_LANG": "ja", "LANG": "ko_KR.UTF-8"}) == "ja"       # 명시가 우선
    assert d({"LANG": "ko_KR.UTF-8"}) == "ko"
    assert d({"LC_ALL": "zh_CN.UTF-8", "LANG": "en_US.UTF-8"}) == "zh"
    assert d({"LANG": "de_DE.UTF-8"}) == "en"
    assert d({}) == "en"


def test_left_형식():
    assert ccp_i18n.left(3 * 1440 + 22 * 60, "ko") == "3일22시간"
    assert ccp_i18n.left(3 * 1440 + 22 * 60, "en") == "3d22h"
    assert ccp_i18n.left(95, "ja") == "1時間35分"
    assert ccp_i18n.left(7, "zh") == "7分"
    assert ccp_i18n.left(0, "en") == "soon"
    assert ccp_i18n.left(None) == ""


def _fake_rows(tmp):
    # 12칸 TSV: 주간% 주간리셋분 세션% 세션리셋분 모델 모델% 상태 주간시각 세션시각 주간창 세션창 메모
    now = time.localtime()
    stamp = time.strftime("%m/%d %H:%M", now)
    rows = [
        ["21", "5600", "12", "270", "Fable", "38", "ok", stamp, stamp, "10080", "300", ""],
        ["100", "8000", "0", "", "Fable", "100", "ok", stamp, "", "10080", "300", ""],
        ["", "", "", "", "", "", "nologin", "", "", "", "", ""],
        ["41", "7000", "", "", "", "", "ok", stamp, "", "10080", "", "plus"],
    ]
    for i, r in enumerate(rows):
        (Path(tmp) / str(i)).write_text("\t".join(r))


def _render(lang, tmp, mode="-"):
    env = dict(os.environ, CCP_LANG=lang, CCP_CONFIG_DIR=tmp)
    return subprocess.run([sys.executable, str(ROOT / "ccp_render.py"), tmp, mode, "", "claude:x", "claude:team", "claude:old", "codex:work"],
                          capture_output=True, text=True, env=env)


def test_렌더러가_네_언어로_돈다():
    want = {"ko": "지금 쓸 수 있음", "en": "available now", "ja": "今使える", "zh": "现在可用"}
    for lang in ccp_i18n.LANGS:
        with tempfile.TemporaryDirectory() as tmp:
            _fake_rows(tmp)
            for mode in ("-", "num"):
                r = _render(lang, tmp, mode)
                assert r.returncode == 0, (lang, mode, r.stderr)
                assert want[lang] in r.stdout, (lang, mode, r.stdout[:500])
                assert "KeyError" not in r.stderr
            # 표 보기도
            (Path(tmp) / "view").write_text("table")
            r = _render(lang, tmp)
            assert r.returncode == 0 and want[lang] in r.stdout, (lang, r.stderr)


def test_statusline_이_네_언어로_돈다():
    want = {"ko": "주 ", "en": "wk ", "ja": "週 ", "zh": "周 "}
    payload = '{"rate_limits":{"seven_day":{"used_percentage":21,"resets_at":%d},"five_hour":{"used_percentage":12,"resets_at":%d}}}' % (
        time.time() + 90000, time.time() + 600)
    for lang in ccp_i18n.LANGS:
        env = dict(os.environ, CCP_LANG=lang, CLAUDE_CONFIG_DIR="/nonexistent")
        r = subprocess.run(["bash", str(ROOT / "statusline.sh")], input=payload, capture_output=True, text=True, env=env)
        assert r.returncode == 0, (lang, r.stderr)
        assert want[lang] in r.stdout and ccp_i18n.t("nologin", lang) in r.stdout, (lang, r.stdout)


def test_codex_메모도_언어를_따른다():
    import ccp_codex
    os.environ["CCP_LANG"] = "en"
    # ccp_codex 는 import 시점의 LANG 을 쓰므로 모듈 함수로 직접 확인
    assert ccp_i18n.t("cx_credits", "en") == "credits depleted"
    assert ccp_i18n.t("cx_tickets", "ja", n=3) == "リセット権 3"
