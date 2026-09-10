#!/usr/bin/env python3
"""ccp 메뉴 렌더러 — 계정별 사용량을 카드/표로 그리고 대화형으로 하나를 고르게 한다.

claude 프로필(CLAUDE_CONFIG_DIR)과 codex 프로필(CODEX_HOME)을 한 화면에 같이 세운다.
입력은 tmp 디렉터리에 계정 순서대로 놓인 TSV 12칸 (claude-profiles.zsh 의 파서 / ccp_codex.py 가 만든다):
  0 주간%  1 주간리셋(분)  2 세션%  3 세션리셋(분)  4 모델명  5 모델%
  6 상태(ok/nologin/fail)  7 주간리셋시각  8 세션리셋시각  9 주간창(분)  10 세션창(분)  11 메모

  argv: <tmpdir> <num|-> <현재프로필 tool:이름> <tool:이름>...
  결과: <tmpdir>/_meta 에 'i\tgrp' 줄들 + 'rec\tN' + (대화형이면) 'sel\tN' (-1 = 취소)
"""
import os,sys,unicodedata,shutil

tmp=sys.argv[1]; numbered=(sys.argv[2]=='num'); cur_raw=sys.argv[3]; specs=sys.argv[4:]
# 인자는 'tool:이름' 꼴 — claude 프로필과 codex 프로필을 한 화면에 같이 세운다.
def split_spec(s):
    t,_,nm=s.partition(':')
    return (t,nm) if nm else ('claude',s)
cur_tool,cur=split_spec(cur_raw) if cur_raw else ('','')
names=[split_spec(s)[1] for s in specs]
tools=[split_spec(s)[0] for s in specs]
TOOLS=['claude','codex']
TOOLNAME={'claude':'Claude','codex':'Codex'}
tty=sys.stdout.isatty()
def C(s,code): return f'\033[{code}m{s}\033[0m' if (tty and code) else s
def dw(s): return sum(2 if unicodedata.east_asian_width(c) in 'WF' else 1 for c in s)
def pad(s,n): return s+' '*max(0,n-dw(s))
def rpad(s,n): return ' '*max(0,n-dw(s))+s
def cut(s,n):
    # 표시 폭 n 안으로 자른다(끝에 …).
    if n<=0: return ''
    if dw(s)<=n: return s
    out=''
    for c in s:
        if dw(out+c)>n-1: break
        out+=c
    return out+'…'

def gi(x): return int(x) if x.strip().lstrip('-').isdigit() else None

rows=[]
for i,nm in enumerate(names):
    try: raw=open(os.path.join(tmp,str(i))).read().strip('\n')
    except Exception: raw=''
    p=(raw.split('\t')+['']*12)[:12]
    rows.append(dict(i=i,name=nm,tool=tools[i],w=gi(p[0]),wm=gi(p[1]),s=gi(p[2]),sm=gi(p[3]),
                     mn=p[4] or '',mp=gi(p[5]),st=p[6] or 'fail',wt=p[7],stt=p[8],
                     ww=gi(p[9]) or 7*1440,sw=gi(p[10]) or 5*60,extra=p[11] or '',
                     tl=nm if tools[i]=='claude' else 'cx·'+nm))

# grp 0=지금 사용 가능 1=세션만 소진(곧 풀림) 2=주간 소진 3=미로그인/실패
# slack = 남은 여유(%)의 최소값(주간·세션·모델). 막힘 판정과 표시용.
# rate  = 주간 리셋 전에 써도 되는 양 / 남은 시간 (%/시간). 추천 순서의 기준.
#         리셋이 가까운 계정의 남은 양은 안 쓰면 사라지므로, 그걸 먼저 쓰는 게 이득이다.
#         모델(Fable) 한도가 주간 한도보다 먼저 막으면 그쪽이 "남은 양"이다.
mlabel=next((r['mn'] for r in rows if r['mn']),'모델')
for r in rows:
    if r['st']!='ok':
        r['grp']=3; r['slack']=-1; r['rate']=-1; r['remain']=None; r['bind']='주간'; r['bindp']=None; r['flag']=False; continue
    w=r['w'] if r['w'] is not None else 0
    s=r['s'] if r['s'] is not None else 0
    cands=[100-w,100-s]
    if r['mp'] is not None: cands.append(100-r['mp'])
    r['slack']=min(cands)
    mrem=100-r['mp'] if r['mp'] is not None else 100
    r['remain']=min(100-w, mrem)
    # bind = 주간·모델 중 먼저 막는 한도. 주간 50%인데 Fable 97%면 실제 남은 건 Fable 3%다.
    r['bind']=mlabel if mrem<100-w else '주간'
    r['bindp']=r['mp'] if r['bind']==mlabel else w
    r['flag']=r['bind']==mlabel and r['bindp']>=70     # 모델 한도가 먼저 막고 이미 빠듯할 때만 표식
    hours=(r['wm'] if r['wm'] is not None else 7*1440)/60.0
    r['rate']=r['remain']/max(hours,1.0)
    r['grp']=2 if w>=100 else (1 if s>=100 else 0)

BIG=10**9
def key(r):
    g=r['grp']
    if g==0:
        s=r['s'] if r['s'] is not None else 0
        return (0, 1 if s>=90 else 0, -r['rate'], -r['slack'], r['i'])   # 세션 90%↑는 곧 막히니 뒤로
    if g==1: return (1,0,r['sm'] if r['sm'] is not None else BIG,0,r['i'])
    if g==2: return (2,0,r['wm'] if r['wm'] is not None else BIG,0,r['i'])
    return (3,0,0,0,r['i'])
rows.sort(key=lambda r:(TOOLS.index(r['tool']) if r['tool'] in TOOLS else 9,)+key(r))

# 추천: 쓸 수 있는 계정 중 첫 번째. 모델 한도까지 찬 계정(slack 0)은 다른 후보가 없을 때만.
# claude 와 codex 는 한도 개념이 달라 섞어서 1등을 뽑는 게 의미가 없다 — 도구마다 따로 뽑는다.
def _pick(pool):
    return next((r for r in pool if r['grp']==0 and r['slack']>0),None) \
        or next((r for r in pool if r['grp']==0),None)
RECS={t:_pick([r for r in rows if r['tool']==t]) for t in TOOLS}
for r in rows: r['is_rec']=any(r is x for x in RECS.values() if x is not None)
HASTOOL=[t for t in TOOLS if any(r['tool']==t for r in rows)]
# 메뉴에서 엔터를 눌렀을 때의 기본값. ccp 의 본체는 claude 라 그쪽을 먼저 본다.
rec=RECS.get('claude') or RECS.get('codex')

def left(m):
    if m is None: return ''
    if m<=0: return '곧'
    d,h,mi=m//1440,(m%1440)//60,m%60
    if d: return f'{d}일{h}시간'
    if h: return f'{h}시간{mi}분'
    return f'{mi}분'
def clock(ts,m):
    # ts='09/08 01:19'. 하루 안이면 시각만, 그 뒤면 날짜만(남은 시간이 시각을 대신한다).
    if not ts: return ''
    d,t=ts.split(' ')
    if m is not None and m<1440: return t
    mo,da=d.split('/'); return f'{int(mo)}/{int(da)}'
def rst(m,ts,pct):
    # 리셋 칸: '2시간42분→01:19'. 남은 시간과 시각을 같이 둬야 Claude 화면과 바로 대조된다.
    if m is None:
        return '새 창' if pct==0 else '-'      # 세션 창이 아직 안 열렸으면 리셋 시각도 없다
    if m<=0: return '곧'
    c=clock(ts,m) if SHOWCLOCK else ''
    return left(m)+('→'+c if c else '')
def bar(p,n=5):
    if p is None: return '·'*n
    f=max(0,min(n,int(round(p/100*n))))
    if p>0 and f==0: f=1
    return '█'*f+'░'*(n-f)
def pctstr(v): return rpad(f'{v}%',4) if v is not None else rpad('-',4)

NUMW=4 if numbered else 0
NAMEW=14
BARW=5; PCTW=4; RSTW=17   # '18시간32분→03:59' 가 17폭이다 — 16이면 옆 칸을 먹는다
LEAD=2+2+NUMW+NAMEW               # 이름 칸까지의 폭
COLS=shutil.get_terminal_size((160,40)).columns if tty else 10**6

# ── 화면 폭에 따라 세 가지 배치 ──────────────────────────────────────────────
#   wide  (≥120열): 막대 + % + 리셋, 메모 전문
#   nobar (≥ 90열): 막대 없이 % + 리셋, 메모 축약(리셋 칸이 같은 정보를 이미 준다)
#   two   (< 90열): 계정마다 두 줄 — 1줄 이름·상태, 2줄 주간·세션·모델
NOTEW=36
if COLS>=LEAD+(BARW+1+PCTW+1+RSTW)*2+6+2+NOTEW: LAYOUT='wide'
elif COLS>=LEAD+(PCTW+1+RSTW)*2+6+2+18:          LAYOUT='nobar'
else:                                             LAYOUT='two'
SHOWCLOCK=True
if LAYOUT=='two' and COLS<80: RSTW=10; SHOWCLOCK=False   # 아주 좁으면 남은 시간만
CELLW=(BARW+1 if LAYOUT=='wide' else 0)+PCTW+1+RSTW
LINEW=min(COLS-1,(LEAD+CELLW*2+6) if LAYOUT!='two' else 78)

GHEAD={0:('── 지금 쓸 수 있음 ','32'),
       1:('── 지금 못 씀 · 세션만 차면 풀린다 ','1;33'),
       2:('── 이번 주 못 씀 · 주간 한도 소진 ','1;31'),
       3:('── 확인 불가 · 로그인 필요 ','2')}

def rec_summary():
    # 도구가 둘 다 있을 때만. 어느 도구를 지금 어느 계정으로 써야 하는지 한 줄로.
    if len(HASTOOL)<2: return None
    parts=[]
    for t in HASTOOL:
        r=RECS.get(t)
        parts.append(f'{TOOLNAME[t]} → '+(f'{r["i"]}) {r["name"]}' if r else '없음'))
    return C(cut('  추천 · '+' · '.join(parts),COLS-1),'1;32')

def row_style(r):
    g=r['grp']; is_rec = r['is_rec']
    if   is_rec: base='1;32'
    elif g==0:   base=''
    elif g==1:   base='33'
    elif g==2:   base='2;31'
    else:        base='2'
    return base, g>=2, is_rec
def hot(v,base,dim):
    # 막고 있는 숫자를 튀게 한다 — 어느 쪽이 문제인지 한눈에 보이도록.
    if dim or v is None: return base
    if v>=100: return '1;31'
    if v>=90:  return '31'
    if v>=70:  return '33'
    return base
def note_col(r,base):
    # 메모 색: 실제 남은 양이 적으면 붉게 — 추천이 아닌 이유가 메모에서 바로 보이게
    if r['grp']!=0 or r['is_rec'] or r['remain'] is None: return base
    if r['remain']<=10: return '31'
    if r['remain']<=30: return '33'
    return base
def note_of(r,short,full=False):
    g=r['grp']; is_rec = r['is_rec']
    if g==0:
        # 어느 한도가 먼저 막는지 이름을 붙인다(주간 50%인데 Fable 97%면 실제 남은 건 Fable 3%)
        which=r['bind']
        why=f'{which} {r["remain"]}% 남음'
        if which==mlabel and full: why+=f'(주간은 {100-(r["w"] or 0)}%)'   # 카드에서만 — 표는 칸이 좁다
        if r['remain']<=10 and r['remain']>0: why+=' 거의 소진'
        why+=' · 리셋 '+(left(r['wm']) or '7일')+' 뒤'
    if is_rec: note='← 추천 · '+why if g==0 else '← 추천'
    elif g==0: note=why
    elif g==1: note='⏳ 세션 소진' + ('' if short else ' — '+(left(r['sm']) or '?')+' 뒤 풀림')
    elif g==2: note='✕ 주간 소진' + ('' if short else ' — '+(left(r['wm']) or '?')+' 뒤 풀림')
    else:      note='— '+('미로그인' if r['st']=='nologin' else '조회 실패')
    if g==0 and r['mp'] is not None and r['mp']>=100:
        note+=f' ({mlabel} 소진)'
    if r['extra']: note+=' · '+r['extra']
    if cur and r['name']==cur and r['tool']==cur_tool: note+='  [현재]'
    return note
def name_cell(r,is_rec):
    head='▸ ' if is_rec else '  '
    numc=(f'{r["i"]})'.rjust(NUMW-1)+' ') if numbered else ''
    return '  '+head+numc+pad(r['name'],NAMEW)

def usage_segs(r,base,dim,with_bar):
    segs=[]
    for pct,m,ts in ((r['w'],r['wm'],r['wt']),(r['s'],r['sm'],r['stt'])):
        if with_bar: segs.append((bar(pct,BARW)+' ',base))
        segs.append((pctstr(pct),hot(pct,base,dim)))
        segs.append((' '+pad(rst(m,ts,pct),RSTW),base))
    segs.append((pad(pctstr(r['mp']),6),hot(r['mp'],base,dim)))
    return segs

def finish(segs,hl):
    # 터미널 폭을 넘으면 마지막 칸(메모)을 자른다 — 줄바꿈되면 화살표 재그리기가 어긋난다.
    for k in range(len(segs)-1,-1,-1):
        fixed=sum(dw(t) for t,_ in segs[:k])
        if fixed+dw(segs[k][0])<=COLS-1: break
        segs[k]=(cut(segs[k][0],max(0,COLS-1-fixed)),segs[k][1])
    if hl: return C(''.join(t for t,_ in segs),'7')       # 선택 행: 반전
    return ''.join(C(t,c) for t,c in segs)

def render_row(r,hl):
    base,dim,is_rec=row_style(r)
    if LAYOUT=='two':
        l1=[(name_cell(r,is_rec),base),(note_of(r,False),note_col(r,base))]
        if r['st']!='ok': return [finish(l1,hl)]          # 조회 못 한 계정은 수치 줄이 없다
        l2=[(' '*8+'주간 ',base)]+usage_segs(r,base,dim,False)
        # 2줄째 마지막 칸이 잘리지 않게 세션 라벨을 끼운다
        l2=[l2[0],l2[1],l2[2],(' · 세션 ',base),l2[3],l2[4],(' · '+mlabel+' ',base),l2[5]]
        return [finish(l1,hl),finish(l2,hl)]
    segs=[(name_cell(r,is_rec),base)]+usage_segs(r,base,dim,LAYOUT=='wide')+[(note_of(r,LAYOUT=='nobar'),note_col(r,base))]
    return [finish(segs,hl)]

def header_lines():
    if LAYOUT=='two':
        out=['  주간 = 7일 총량 · 세션 = 5시간 창 · 하나라도 100%면 못 쓴다',
             (f'  리셋 = 남은 시간→풀리는 시각 · {mlabel} = 이번 주 {mlabel} 한도' if SHOWCLOCK
              else f'  리셋 = 풀리기까지 남은 시간 · {mlabel} = 이번 주 {mlabel} 한도')]
    else:
        out=['  주간 = 7일 총량 · 세션 = 5시간 창 · 둘 중 하나라도 100%면 지금은 못 쓴다',
             f'  리셋 = 남은 시간→풀리는 시각(하루 넘으면 날짜) · {mlabel} = 이번 주 {mlabel} 전용 한도']
    out=[C(cut(x,COLS-1),'2') for x in out]
    if LAYOUT!='two':
        # 칸 구조를 그대로 따른다: [막대 ](wide만) + %(4) + ' '+리셋(16)
        barw=(BARW+1 if LAYOUT=='wide' else 0)
        lab=('주간 사용','세션 사용') if LAYOUT=='wide' else ('주간','세션')
        out.append(C(' '*LEAD
            +pad(lab[0],barw+PCTW)+pad(' ↻ 리셋',1+RSTW)
            +pad(lab[1],barw+PCTW)+pad(' ↻ 리셋',1+RSTW)
            +pad(mlabel,6),'2'))
    return out

def build_table(hl_idx):
    # hl_idx: rows 안 인덱스(정렬 후) 또는 None
    lines=['']+header_lines()
    seen=set(); curtool=None
    for k,r in enumerate(rows):
        g=r['grp']
        if len(HASTOOL)>1 and r['tool']!=curtool:
            curtool=r['tool']; seen=set()
            if k: lines.append('')
            lines.append(C('  '+TOOLNAME.get(curtool,curtool),'1;36'))
        if g not in seen:
            seen.add(g)
            txt,gc=GHEAD[g]
            if len(seen)>1: lines.append('')
            lines.append(C('  '+txt+'─'*max(0,LINEW-dw(txt)-2),gc))
        lines+=render_row(r, hl_idx is not None and k==hl_idx)
        if LAYOUT=='two' and k+1<len(rows) and rows[k+1]['grp']==g: lines.append('')
    lines.append('')
    rs=rec_summary()
    if rs: lines.append(rs)
    if rec is None:
        soon=next((r for r in rows if r['grp'] in (1,2)),None)
        if soon is not None:
            when=left(soon['sm'] if soon['grp']==1 else soon['wm'])
            kind='세션' if soon['grp']==1 else '주간'
            lines.append(C(cut(f'  ⚠ 지금 바로 쓸 계정이 없다. 가장 빨리 풀리는 건 {soon["i"]}) {soon["name"]} — {kind} {when} 뒤.',COLS-1),'1;33'))
        else:
            lines.append(C('  ⚠ 사용 가능한 계정이 없다.','1;31'))
    return lines


# ── 그래프 보기(기본) ─────────────────────────────────────────────────────────
# 계정마다 카드 하나: 주간/세션/모델을 긴 막대 세 줄로 쌓는다.
# "언제 풀리는지"(리셋 시각·남은 시간)와 "얼마나 찼는지"(막대·색)를 한 줄에서 같이 읽게 하는 게 목적.
import datetime as _dt
WD='월화수목금토일'
ROWS_H=shutil.get_terminal_size((160,40)).lines if tty else 10**6
VIEWF=os.path.join(os.environ.get('CCP_CONFIG_DIR') or os.path.expanduser('~/.config/ccp'),'view')
try: VIEW=open(VIEWF).read().strip() or 'graph'
except Exception: VIEW='graph'
if VIEW not in ('graph','table'): VIEW='graph'
LABELS=['주간','세션',mlabel]
LABW=max(dw(x) for x in LABELS)
GBARW=max(10,min(24,COLS-(6+LABW+1+1+4+3+36)))

def when(m,ts):
    # 리셋 시각을 말로: '오늘 23:59' / '내일 02:40' / '9/14(일) 14:59'
    if m is None or not ts: return ''
    d,t=ts.split(' '); mo,da=int(d[:2]),int(d[3:])
    now=_dt.datetime.now()
    yr=now.year+1 if mo<now.month-6 else now.year
    try: dd=_dt.date(yr,mo,da)
    except ValueError: return t
    delta=(dd-now.date()).days
    if delta==0: return f'오늘 {t}'
    if delta==1: return f'내일 {t}'
    return f'{mo}/{da}({WD[dd.weekday()]}) {t}'
def reset_desc(m,ts,pct,room=10**6):
    if m is None: return '새 창 · 아직 시작 안 함' if pct==0 else '-'
    if m<=0: return '곧 리셋'
    for cand in (f'{when(m,ts)} 리셋 · {left(m)} 남음', f'{when(m,ts)} · {left(m)} 뒤', f'{left(m)} 뒤'):
        if dw(cand)<=room: return cand
    return cut(cand,room)
TICK,TICKC='┃','1;36'   # 경과 눈금: 굵은 세로선 + 밝은 청록(막대의 초록·노랑·빨강과 겹치지 않는 색)
def elapsed_frac(m,window):
    # 창 안에서 지금이 어디쯤인지(0=방금 시작, 1=리셋 직전). m=리셋까지 남은 분.
    if m is None: return None
    return max(0.0,min(1.0,1-m/window))
def gbar(p,n,t=None):
    # 찬 만큼 색이 짙어진다: 70% 노랑, 90% 빨강, 100% 굵은 빨강
    # t = 창의 경과 비율. 그 자리에 '│'를 겹쳐 "지금"을 표시한다 — 오른쪽 끝에 붙을수록 리셋 임박.
    #   막대가 │에 못 미치면 페이스보다 덜 쓴 것(여유), │를 넘으면 페이스보다 많이 쓴 것.
    if p is None: return C('·'*n,'2')
    f=max(0,min(n,int(round(p/100*n))))
    if p>0 and f==0: f=1
    col='1;31' if p>=100 else '31' if p>=90 else '33' if p>=70 else '32'
    cells=[('█',col)]*f+[('░','2')]*(n-f)
    if t is not None:
        k=min(n-1,int(t*n))
        cells[k]=(TICK,TICKC)
    out=''; run=''; rc=None
    for ch,c in cells+[(None,None)]:
        if c!=rc and run: out+=C(run,rc); run=''
        if ch is None: break
        run+=ch; rc=c
    return out

def card(r,hl,fold=False):
    base,dim,is_rec=row_style(r)
    title=[(name_cell(r,is_rec).rstrip()+'  ',base),(note_of(r,False,True),note_col(r,base))]
    out=[finish(title,hl)]
    # fold = 막대를 접고 제목 줄만. 화면이 낮을 때 '못 쓰는 계정'부터 접는다 — 어차피 볼 게 없다.
    if r['st']!='ok' or fold: return out
    ind=' '*6
    room=COLS-1-dw(ind+pad(LABELS[0],LABW)+' ')-GBARW-1-4-3
    tw=elapsed_frac(r['wm'],r['ww']); ts_=elapsed_frac(r['sm'],r['sw'])
    trip=[(LABELS[0],r['w'],tw,reset_desc(r['wm'],r['wt'],r['w'],room)),
          (LABELS[1],r['s'],ts_,reset_desc(r['sm'],r['stt'],r['s'],room)),
          (LABELS[2],r['mp'],tw,('주간과 함께 리셋'+(' · ◀ 주간보다 먼저 막음' if r['flag'] else '')) if r['mp'] is not None else '-')]
    if r['tool']!='claude':
        # codex 는 모델별 한도가 없고, 요금제에 따라 5시간 창도 없다 — 없는 줄은 아예 안 그린다.
        trip=[x for x in trip[:2] if x[1] is not None] or trip[:1]
    for lab,pct,t,desc in trip:
        left_=ind+pad(lab,LABW)+' '
        line=C(left_,base)+gbar(pct,GBARW,t)+' '+C(pctstr(pct),hot(pct,base,dim))+'   '+C(cut(desc,max(0,room)),base if not dim else '2')
        out.append(line)
    return out

def build_graph(hl_idx,terse=False,fold=False,tight=False):
    # terse/fold/tight = 화면이 낮을 때 순서대로 조여 카드 보기를 지켜내는 단계.
    #   표로 떨어지는 것보다 압축된 카드가 낫다 — 막대를 보려고 그래프를 쓰는 것이므로.
    leg=(f'  주간 = 7일 총량 · 세션 = 5시간 창 · {mlabel} = 이번 주 {mlabel} 한도 · 하나라도 100%면 그때까지 못 쓴다' if COLS>=100
         else f'  주간 = 7일 총량 · 세션 = 5시간 창 · {mlabel} = 이번 주 한도')
    if terse:
        lines=['',C(cut(f'  주간 7일 · 세션 5시간 · {mlabel} 주간 · {TICK} 지금 위치 · 100%면 못 씀',COLS-1),'2')]
    else:
        lines=['',C(cut(leg,COLS-1),'2'),
               C(cut(f'  추천 = 주간 리셋이 가까운데 남은 양이 많은 계정부터 — 남은 양은 주간·{mlabel} 중 먼저 막는 쪽(◀) 기준',COLS-1),'2'),
               C(cut(f'  {TICK} = 지금(창의 경과 위치, 오른쪽 끝 = 리셋 직전) — 막대가 {TICK}에 못 미치면 페이스보다 덜 써서 여유, 넘으면 빠듯',COLS-1),'2')]
        if 'codex' in HASTOOL:
            lines.append(C(cut('  codex = 주간(+5시간) 한도만 있고 모델별 한도는 없다 · 전환은 프로필별 CODEX_HOME',COLS-1),'2'))
    global LEGN
    LEGN=len(lines)
    seen=set(); curtool=None
    for k,r in enumerate(rows):
        g=r['grp']
        if len(HASTOOL)>1 and r['tool']!=curtool:
            curtool=r['tool']; seen=set()
            if k and not tight: lines.append('')
            lines.append(C('  '+TOOLNAME.get(curtool,curtool),'1;36'))
        if g not in seen:
            seen.add(g)
            txt,gc=GHEAD[g]
            if len(seen)>1 and not tight: lines.append('')
            lines.append(C('  '+txt+'─'*max(0,min(COLS-1,78)-dw(txt)-2),gc))
        elif not tight and (r['st']=='ok' or rows[k-1]['st']=='ok'): lines.append('')
        lines+=card(r, hl_idx is not None and k==hl_idx, fold and g>=2)
    lines.append('')
    rs=rec_summary()
    if rs: lines.append(rs)
    if rec is None:
        soon=next((r for r in rows if r['grp'] in (1,2)),None)
        if soon is not None:
            when_=left(soon['sm'] if soon['grp']==1 else soon['wm'])
            kind='세션' if soon['grp']==1 else '주간'
            lines.append(C(cut(f'  ⚠ 지금 바로 쓸 계정이 없다. 가장 빨리 풀리는 건 {soon["i"]}) {soon["name"]} — {kind} {when_} 뒤.',COLS-1),'1;33'))
        else:
            lines.append(C('  ⚠ 사용 가능한 계정이 없다.','1;31'))
    return lines


# ── 주간 리셋 타임라인 ────────────────────────────────────────────────────────
# 계정끼리 "주간이 언제 풀리는지"를 한 축에서 비교한다: 지금부터 7일, 자정마다 요일 눈금, 계정별 ● 표시.
def timeline_lines():
    data=[r for r in rows if r['st']=='ok']
    if not data: return []
    now=_dt.datetime.now()
    TLW=max(21,min(63,COLS-1-(4+NAMEW+2+2+30)))
    SPAN=7*1440
    def pos(m): return max(0,min(TLW-1,int(m/SPAN*TLW)))
    # 자정 눈금
    first=1440-(now.hour*60+now.minute)
    ticks=[]; m=first; k=1
    while m<SPAN:
        ticks.append((pos(m),WD[(now.weekday()+k)%7])); m+=1440; k+=1
    hdr=[' ']*TLW
    for p_,lab in ticks:
        if p_+1<TLW: hdr[p_]=lab; hdr[p_+1]=''
    out=[C('  주간 리셋 시점 — 지금부터 7일 (● 리셋 · ┼ 자정)','2'),
         C(' '*(4+NAMEW+2)+''.join(hdr),'2')]
    data.sort(key=lambda r:(r['wm'] is None, r['wm'] if r['wm'] is not None else 0, r['i']))
    for r in data:
        base,dim,_=row_style(r)
        axis=['─']*TLW
        for p_,_l in ticks: axis[p_]='┼'
        w=r['w'] if r['w'] is not None else 0
        bp=r['bindp'] if r['bindp'] is not None else w
        col='1;31' if bp>=100 else '31' if bp>=90 else '33' if bp>=70 else '32'
        if r['wm'] is None:
            line=C(' '*4+pad(cut(r['tl'],NAMEW),NAMEW)+'  ',base)+C(''.join(axis),'2')+'  '+C('새 창 · 아직 시작 안 함' if w==0 else '-',base)
        else:
            p_=pos(r['wm']); axis[p_]='●'
            body=C(''.join(axis[:p_]),'2')+C('●',col)+C(''.join(axis[p_+1:]),'2')
            room=max(0,COLS-1-(4+NAMEW+2+TLW+2))
            wh=when(r['wm'],r['wt'])
            desc='곧 리셋'
            if r['wm']>0:
                cands=((f'{wh} · 주간 {w}% · {mlabel} {r["mp"]}% ◀', f'{wh} · {mlabel} {r["mp"]}% ◀', wh)
                       if r['flag'] else (f'{wh} · 주간 {w}% 사용', f'{wh} · {w}%', wh))
                for cand in cands:
                    desc=cand
                    if dw(cand)<=room: break
            line=C(' '*4+pad(cut(r['tl'],NAMEW),NAMEW)+'  ',base)+body+'  '+C(cut(desc,room),note_col(r,base))
        out.append(line)
    out.append('')
    return out

FORCED=False
LEGN=4
def with_timeline(lines):
    # 범례 뒤에 타임라인을 끼운다 (LEGN = build_graph 가 찍은 범례 줄 수)
    return lines[:LEGN]+timeline_lines()+lines[LEGN:]
def build(hl_idx):
    global VIEW,FORCED
    FORCED=False
    if VIEW=='graph':
        # 넉넉한 순서대로: 타임라인 포함 → 범례 축약 → 못 쓰는 계정 접기 → 줄간격 제거 → 표.
        g=build_graph(hl_idx)
        if len(with_timeline(g))+2<=ROWS_H: return with_timeline(g)
        for kw in ({}, {'terse':True}, {'terse':True,'fold':True}, {'terse':True,'fold':True,'tight':True}):
            g=build_graph(hl_idx,**kw) if kw else g
            if len(g)+2<=ROWS_H: return g
        # 여기까지 와도 안 들어가면 표로 떨어진다(재그리기가 화면 위로 넘치면 깨진다)
        FORCED=True
    t=build_table(hl_idx)
    # 표는 머리글이 2~3행이라 그 뒤에 끼운다
    h=3 if LAYOUT!='two' else 2
    tt=t[:1+h]+timeline_lines()+t[1+h:]
    return tt if len(tt)+2<=ROWS_H else t

def write_meta(sel):
    with open(os.path.join(tmp,'_meta'),'w') as f:
        for r in rows:
            f.write(f'{r["i"]}\t{r["grp"]}\n')
        f.write(f'rec\t{rec["i"] if rec else -1}\n')
        if sel is not None: f.write(f'sel\t{sel}\n')

# ── 대화형 선택 ──────────────────────────────────────────────────────────────
# ↑↓/j/k 이동 · 숫자 키 = 그 번호로 이동 · Enter 실행 · Esc/q 취소.
# 터미널이 아니면(파이프 등) 표만 찍고 끝낸다 — zsh 쪽이 예전 read 프롬프트로 받는다.
def interactive():
    return numbered and tty and os.path.exists('/dev/tty')

if not interactive():
    print('\n'.join(build(None)))
    write_meta(None)
    sys.exit(0)

import termios,tty as ttymod,select
hl=rows.index(rec) if rec is not None else 0
def target_line(k):
    r=rows[k]
    head=f'  ▶ {r["i"]}) {r["name"]}  '
    other='(화면이 낮아 표로 표시)' if FORCED else ('v 표 보기' if VIEW=='graph' else 'v 그래프 보기')
    return C(head,"1")+C(cut(f'Enter 실행 · ↑↓/j k 이동 · 숫자 = 번호로 · {other} · Esc/q 취소',COLS-1-dw(head)),'2')
def draw(k,first):
    lines=build(k)+[target_line(k)]
    out=sys.stdout
    if not first: out.write(f'\033[{len(lines)}A')
    for ln in lines: out.write('\r\033[2K'+ln+'\n')
    out.flush()
    return len(lines)

fd=os.open('/dev/tty',os.O_RDWR)
old=termios.tcgetattr(fd)
sel=-1
try:
    ttymod.setcbreak(fd)            # setraw 는 OPOST 까지 꺼서 출력 줄바꿈이 깨진다
    sys.stdout.write('\033[?25l'); n=draw(hl,True)
    while True:
        ch=os.read(fd,1)
        if ch==b'\x1b':
            r,_,_=select.select([fd],[],[],0.05)
            if not r: break                         # 단독 Esc = 취소
            seq=os.read(fd,8)
            if seq in (b'[A',b'OA'): hl=(hl-1)%len(rows)
            elif seq in (b'[B',b'OB'): hl=(hl+1)%len(rows)
            else: continue
        elif ch in (b'\r',b'\n'): sel=rows[hl]['i']; break
        elif ch in (b'q',b'Q',b'\x03',b'\x04'): break
        elif ch in (b'k',b'K'): hl=(hl-1)%len(rows)
        elif ch in (b'j',b'J'): hl=(hl+1)%len(rows)
        elif ch in (b'v',b'V'):
            VIEW='table' if VIEW=='graph' else 'graph'
            try:
                os.makedirs(os.path.dirname(VIEWF),exist_ok=True); open(VIEWF,'w').write(VIEW)
            except Exception: pass
            # 줄 수가 달라지므로 이전 블록을 지우고 다시 그린다
            sys.stdout.write(f'\033[{n}A'+'\r\033[J'); sys.stdout.flush()
            n=draw(hl,True); continue
        elif ch.isdigit():
            k=next((k for k,r in enumerate(rows) if r['i']==int(ch)),None)
            if k is None: continue
            hl=k
        else: continue
        n=draw(hl,False)
except KeyboardInterrupt:
    sel=-1
finally:
    termios.tcsetattr(fd,termios.TCSADRAIN,old)
    sys.stdout.write('\033[?25h'); sys.stdout.flush()
    os.close(fd)
write_meta(sel)
