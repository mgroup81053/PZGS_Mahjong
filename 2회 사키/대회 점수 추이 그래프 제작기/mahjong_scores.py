"""Run: pip install matplotlib; python mahjong_scores.py
Optional Korean font: place NotoSansCJKkr-Regular.otf beside this script.
Each nonblank input line is one score update; ' //' starts a comment.
Scores carry over across hanchan. No inferred corrections are applied.
"""
from pathlib import Path
import re, csv
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager, ticker
ROOT = Path(__file__).resolve().parent
# 팀 이름은 아래 따옴표 안의 표시 이름만 바꾸세요. 왼쪽 ID는 유지합니다.
TEAM_NAMES = {
    '바': 'ヴァース 팀',
    '노': '노텐리치의 품격 팀',
    '마': '마작통신 팀',
    '랜': '랜덤2 팀',
}
TEAMS = list(TEAM_NAMES)
SESSION_LABELS = ['선봉', '차봉', '중견', '대장']
# 출력 크기(인치)와 해상도: 기본 1800 × 900 픽셀
FIGSIZE = (12, 6)
DPI = 150
SESSIONS = [
({'H':'바','J':'마','쿠':'노','송':'랜'}, '''H +3600, J -2600, 송 -1000
송 +2000, J -2000
H +4000, J -1000, 쿠 -1000, 송 -2000
H +13000, 송 -13000
쿠 +5500, J -5500
쿠 +8900, H -2000, J -3900, 송 -3000
송 +8000, J -8000
송 +7000, 쿠 -3000, J -2000, H -2000
J +2300, 송 -1300, 쿠 -1000
H +7700, 송 -7700'''),
({'비':'바','시':'노','하':'랜','닝':'마'}, '''닝 +12000, 비 -6000, 시 -3000, 하 -3000
비 +2600, 시 -2600
하 +12000, 비 -4000, 시 -4000, 닝 -4000
비 +3900, 시 -3900
닝 +2000, 하 -1000, 비 -1000, 시 -1000 // 닝 선수 리치 상태로 유국
닝 -9300, 시 -1000, 하 +11300
시 +8000, 하 -8000
닝 +8000, 시 -8000
하 +4000, 닝 -2000, 비 -1000, 시 -1000
하 +4500, 닝 -1500, 비 -1500, 시 -1500
닝 +8900, 하 -8900
비 +1600, 시 -1600'''),
({'아':'랜','타':'마','다':'바','라':'노'}, '''아 +7700, 타 -7700
라 +8200, 타 -2100, 다 -2100, 아 -4000
다 -1500, 타 -1500, 라 +500, 아 +500 // 라, 아 선수 리치 후 유국
타 +6200, 아 -4200
라 +2000, 아 -2000
라 +1000, 아 -1000
타 +2600, 아 -2600
타 +5200, 아 -5200
타 +3900, 아 -3900
다 -2300, 라 +2300
다 +5800, 아 -5800'''),
({'시':'랜','노':'마','이':'바','채':'노'}, '''채 +2000, 시 -2000
이 +4900, 채 -4900
채 +8000, 노 -8000
시 -7000, 채 -3000, 노 -4000, 이 +14000
이 +5900, 시 -1000, 채 -4900
채 -2900, 노 +2900
노 +6300, 채 -2100, 시 -2100, 이 -2100
채 +6800, 노 -3800, 시 -1500, 이 -1500
채 +2000, 노 -2000
시 +3000, 노 -3000
노 +8300, 시 -8300
채 -2000, 노 -2000, 이 -1000, 시 +5000''')]
EXPECTED = dict(zip(TEAMS,[139000,102800,92700,65500]))
scores = dict.fromkeys(TEAMS,100000)
rows = [dict(step=0,hanchan=0,round=0,**scores,total=400000,delta_sum=0,comment='초기값')]
ends=[]
for h,(players,raw) in enumerate(SESSIONS,1):
    for n,line in enumerate(filter(str.strip,raw.splitlines()),1):
        body,_,comment = line.partition(' //')
        change=0
        seen=set()
        for part in body.split(','):
            m=re.fullmatch(r'\s*(\S+)\s+([+-]\d+)\s*',part)
            if not m: raise ValueError(f'잘못된 입력: {part}')
            player,amount=m.groups()
            if player in seen: raise ValueError(f'중복 선수: {player}')
            seen.add(player)
            amount=int(amount)
            scores[players[player]]+=amount
            change+=amount
        row=dict(step=len(rows),hanchan=h,round=n,**scores,total=sum(scores.values()),delta_sum=change,comment=comment.strip())
        rows.append(row)
        if row['total']!=400000:
            print(f"합계 주의: {h}반장 {n}행 = {row['total']:,}점 ({row['total']-400000:+,}) / {comment.strip()}")
    ends.append(len(rows)-1)
    print(f'{h}반장 종료: {scores}')
print('최종 검산:',{t:{'계산':scores[t],'제시':EXPECTED[t],'차이':scores[t]-EXPECTED[t]} for t in TEAMS})
assert scores==EXPECTED, '제시 최종값 불일치'
with (ROOT/'mahjong_scores.csv').open('w',encoding='utf-8-sig',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
font=ROOT/'NotoSansCJKkr-Regular.otf'
if font.exists():
    font_manager.fontManager.addfont(str(font))
    plt.rcParams['font.family']=font_manager.FontProperties(fname=str(font)).get_name()
plt.rcParams['axes.unicode_minus']=False
fig,ax=plt.subplots(figsize=FIGSIZE,dpi=DPI)
fig.patch.set_facecolor('#f7f9fc');ax.set_facecolor('#ffffff')
fig.subplots_adjust(left=.09,right=.80,top=.91,bottom=.08)
colors=['#2463c5','#159a86','#b54fad','#e78425']
x=[r['step'] for r in rows]
for t,c in zip(TEAMS,colors):
    y=[r[t] for r in rows]
    ax.plot(x,y,color=c,lw=2.4,marker='o',ms=3.2,label=TEAM_NAMES[t])
    ax.annotate(f'{TEAM_NAMES[t]}  {y[-1]:,}',(x[-1],y[-1]),xytext=(12,0),textcoords='offset points',va='center',color=c,fontsize=12,fontweight='bold')
start=0
for h,end in enumerate(ends,1):
    ax.axvspan(start,end,alpha=.035 if h%2 else .075,color='#2463c5',zorder=0)
    ax.text((start+end)/2,1.035,SESSION_LABELS[h-1],transform=ax.get_xaxis_transform(),ha='center',fontsize=12,color='#475569')
    if h<4: ax.axvline(end,color='#abb7c7',lw=1,ls='--')
    start=end
ax.axhline(100000,color='#8b98aa',lw=1,ls='--',alpha=.6)
ax.set_xlim(0,45);ax.set_ylim(60000,145000)
ax.set_xticks([0,5,10,15,20,22,25,30,33,40,45])
ax.set_xticklabels(['0','5','10','15','20','22','25','30','33','40','45'])
ax.yaxis.set_major_locator(ticker.MultipleLocator(20000))
ax.yaxis.set_major_formatter(ticker.StrMethodFormatter('{x:,.0f}'))
ax.set_ylabel('팀 누적 점수',fontsize=11)
ax.grid(axis='y',color='#dbe2eb',lw=.7);ax.set_axisbelow(True)
for sp in ax.spines.values():sp.set_visible(False)
ax.tick_params(length=0,labelsize=10,pad=8)
fig.add_artist(plt.Rectangle(
    (0, 0), 1, 1,
    transform=fig.transFigure,
    fill=False,
    edgecolor='black',
    linewidth=4,
    clip_on=False,
    zorder=100
))
fig.savefig(ROOT/'mahjong_scores_hd.png',dpi=DPI)
plt.close(fig)
