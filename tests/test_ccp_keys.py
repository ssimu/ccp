"""ccp_keys — 터미널 키 읽기. 화살표 시퀀스 뒤에 Enter 가 붙어 들어와도(빠른 연타·키 반복) 키를 잃지 않아야 한다."""
import os, sys, threading, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ccp_keys  # noqa: E402


def reader_with(data, esc_wait=0.05):
    r, w = os.pipe()
    os.write(w, data)
    os.close(w)                      # 더 올 게 없다 — 단독 Esc 판정은 select 시간 초과로 난다
    return ccp_keys.KeyReader(r, esc_wait=esc_wait)


def drain(k, n):
    return [k.next() for _ in range(n)]


def test_화살표_두_번과_Enter_가_한_번에_와도_셋으로_나눈다():
    k = reader_with(b"\x1b[B\x1b[B\r")
    assert drain(k, 3) == ["down", "down", "enter"]


def test_한_글자씩_와도_같다():
    r, w = os.pipe()
    k = ccp_keys.KeyReader(r, esc_wait=0.5)
    def feed():
        for b in (b"\x1b", b"[", b"A", b"\n", b"3", b"q"):
            os.write(w, b); time.sleep(0.02)
    threading.Thread(target=feed, daemon=True).start()
    assert drain(k, 4) == ["up", "enter", "3", "q"]


def test_단독_Esc_는_esc():
    r, w = os.pipe()
    os.write(w, b"\x1b")
    k = ccp_keys.KeyReader(r, esc_wait=0.05)
    assert k.next() == "esc"


def test_모르는_시퀀스는_other_로_통째로_버린다():
    k = reader_with(b"\x1b[1;5A\r")      # Ctrl+↑ 같은 것
    assert drain(k, 2) == ["other", "enter"]


def test_O_꼴_화살표와_j_k_와_Ctrl_C():
    k = reader_with(b"\x1bOB\x1bOAjk\x03")
    assert drain(k, 5) == ["down", "up", "j", "k", "\x03"]


def test_입력이_끊기면_eof():
    k = reader_with(b"")
    assert k.next() == "eof"
