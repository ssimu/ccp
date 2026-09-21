#!/usr/bin/env python3
"""터미널 키 읽기 — ccp_render.py(계정 메뉴)와 ccp_pick.py(대화 선택)가 같이 쓴다.

한 번의 read 로 여러 키가 함께 들어올 수 있다(빠른 연타·키 반복·붙여넣기): b"\\x1b[B\\x1b[B\\r" 처럼.
바이트 버퍼를 두고 앞에서부터 한 키씩 잘라 낸다. 화살표(ESC [ A/B, ESC O A/B)는 끝 글자(0x40–0x7E)까지가 한 키.

  KeyReader(fd, esc_wait=0.1).next() → "up" "down" "enter" "esc" "other"(모르는 시퀀스) "eof" 또는 글자 하나(str)
단독 Esc 는 esc_wait 초 안에 다음 바이트가 없을 때만 esc 로 본다.
"""
import os
import select


class KeyReader:
    def __init__(self, fd, esc_wait=0.1):
        self.fd = fd
        self.esc_wait = esc_wait
        self.buf = b""

    def _fill(self, wait=None):
        """더 읽는다. wait 가 있으면 그 시간까지만 기다리고, 없으면 False."""
        if wait is not None:
            r, _, _ = select.select([self.fd], [], [], wait)
            if not r:
                return False
        try:
            chunk = os.read(self.fd, 256)
        except OSError:
            return False
        if not chunk:
            return False
        self.buf += chunk
        return True

    def next(self):
        while True:
            if not self.buf:
                if not self._fill():
                    return "eof"
                continue
            b0 = self.buf[0:1]
            if b0 != b"\x1b":
                self.buf = self.buf[1:]
                return "enter" if b0 in (b"\r", b"\n") else b0.decode("latin1")
            # ESC 로 시작 — 시퀀스가 완성될 때까지 조금 기다린다
            if len(self.buf) == 1:
                if not self._fill(self.esc_wait):
                    self.buf = b""
                    return "esc"
                continue
            if self.buf[1:2] not in (b"[", b"O"):
                self.buf = self.buf[1:]           # ESC + 다른 글자(Alt-x 따위) — Esc 로 보고 뒤는 다음 키로 남긴다
                return "esc"
            end = next((j for j in range(2, len(self.buf)) if 0x40 <= self.buf[j] <= 0x7E), None)
            if end is None:
                if not self._fill(self.esc_wait):
                    self.buf = b""
                    return "other"
                continue
            seq, self.buf = self.buf[:end + 1], self.buf[end + 1:]
            if seq in (b"\x1b[A", b"\x1bOA"):
                return "up"
            if seq in (b"\x1b[B", b"\x1bOB"):
                return "down"
            return "other"

    def name(self, k):
        """루프에서 쓰기 편한 이름: Enter/취소/이동 통합."""
        if k in ("esc", "q", "Q", "\x03", "\x04"):
            return "cancel"
        if k in ("up", "k", "K"):
            return "up"
        if k in ("down", "j", "J"):
            return "down"
        return k
