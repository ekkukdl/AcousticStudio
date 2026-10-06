"""Produce BOM, engineering geometry previews, Korean review, and release ZIPs."""
from pathlib import Path
import csv, json, math, hashlib, zipfile
from collections import Counter, defaultdict
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

root=Path(__file__).resolve().parents[1];d=root/'outputs/panel_8faces_32ch_R1';name=d.name
parts=json.loads((d/'component_manifest.json').read_text());params=json.loads((d/'parameters.json').read_text());geo=json.loads((d/'geometry_summary.json').read_text())
stitch_count=json.loads((d/'analysis/stitching.json').read_text())['added_ground_vias']
groups=defaultdict(list)
for p in parts:groups[(p['value'],p['kind'],p['mpn'],p['manufacturer'],p['lcsc'])].append(p['ref'])
rows=[]
packages={'595':'SOIC-16 narrow 3.9mm','DRV':'SOIC-8','Q':'SOT-23','R':'0805','C':'0805','CP':'Radial D6.3mm P2.5mm','T':'D16mm / pin pitch 10mm','JLOG':'2x5 2.54mm','JPWR':'1x3 2.54mm'}
for (val,kind,mpn,mfr,lcsc),refs in groups.items():
    rows.append({'Designator':','.join(sorted(refs,key=lambda s:(s[0],int(s[1:])))),'Value':val,'Package':packages[kind],'Qty_per_PCB':len(refs),'Qty_8_PCB':len(refs)*8,'Assembly':'THT' if kind in ('T','CP','JLOG','JPWR') else 'SMT','Manufacturer':mfr,'MPN_candidate':mpn,'LCSC_candidate':lcsc,'Status':'confirm exact part and availability before purchase'})
for file,subset in [('BOM_ALL.csv',rows),('BOM_SMT.csv',[r for r in rows if r['Assembly']=='SMT']),('BOM_THT.csv',[r for r in rows if r['Assembly']=='THT'])]:
    with (d/file).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(subset)
with (d/'THT_Placement.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.writer(f);w.writerow(['Ref','Value','X_mm','Y_mm_down_from_top','Rotation_KiCad_deg','Side','Note'])
    for p in parts:
        if p['kind'] in ('T','CP','JLOG','JPWR'):w.writerow([p['ref'],p['value'],p['x'],p['y'],p['rot'],p['side'],'TX pin1 driven pin2 GND; bulk capacitor pin1 positive'])

plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10})
fig,axes=plt.subplots(1,2,figsize=(12,9),gridspec_kw={'width_ratios':[1,1.8]});fig.suptitle('R1  |  8 panels / 256 transducers  |  flexible prototype geometry',fontsize=16,y=.97)
ax=axes[0];ax.add_patch(Rectangle((0,0),84,224,facecolor='#dcefe6',edgecolor='#205949',lw=2))
for y in (0,202):ax.add_patch(Rectangle((0,y),84,22,facecolor='#f5dfae',edgecolor='none'))
for x,y in geo['mount_holes_mm']:ax.add_patch(Circle((x,y),1.6,facecolor='white',edgecolor='black'))
for i in range(32):
    r,c=divmod(i,4);x=[13,31,53,71][c];y=42+r*20
    ax.add_patch(Circle((x,y),8,facecolor='#527d91',edgecolor='white'));ax.text(x,y,f'T{i+1}',ha='center',va='center',fontsize=7,color='white')
ax.text(42,11,'22 mm mounting strip',ha='center',va='center',fontsize=9);ax.text(42,213,'22 mm mounting strip',ha='center',va='center',fontsize=9)
ax.set(xlim=(-8,92),ylim=(230,-6),aspect='equal',xlabel='X (mm)',ylabel='Y from top edge (mm)',title='Single PCB: 84 x 224 x 1.6 mm\nPitch X: 18 / 22 / 18 mm; Y: 20 mm')
ax.grid(alpha=.15)
ax=axes[1];apothem=117.5;width=84
for face in range(8):
    a=face*math.pi/4;n=np.array([math.cos(a),math.sin(a)]);t=np.array([-n[1],n[0]])
    ends=np.array([n*apothem-t*width/2,n*apothem+t*width/2]);ax.plot(ends[:,0],ends[:,1],color='#205949',lw=5)
    front=np.array([n*105-t*37,n*105+t*37]);ax.plot(front[:,0],front[:,1],color='#527d91',lw=3)
    ax.text(*(n*132),f'F{face}',ha='center',va='center',color='#205949')
    for x in (-29,-11,11,29):
        p=n*111.25+t*x;corners=[p-t*8-n*6.25,p+t*8-n*6.25,p+t*8+n*6.25,p-t*8+n*6.25];ax.fill(*np.array(corners).T,color='#527d91',alpha=.55)
ax.annotate('',xy=(105,0),xytext=(-105,0),arrowprops={'arrowstyle':'<->','color':'#aa5823','lw':2});ax.text(0,7,'210 mm emitting-plane separation',ha='center',color='#aa5823')
ax.text(0,-30,f'Adjacent PCB front-edge gap: {geo["pcb_edge_gap_mm"]:.2f} mm',ha='center',fontsize=10)
ax.text(0,-48,'Camera field of view requires object size + camera position',ha='center',fontsize=9)
ax.set(xlim=(-160,160),ylim=(-160,160),aspect='equal',xlabel='X (mm)',ylabel='Y (mm)',title='Octagonal tunnel cross-section\nPCB face apothem 117.5 mm; TX depth 12.5 mm');ax.grid(alpha=.15)
fig.tight_layout(rect=[0,0,1,.94]);fig.savefig(d/'geometry_preview.png',dpi=180);plt.close(fig)

fig=plt.figure(figsize=(10,9));ax=fig.add_subplot(111,projection='3d')
for face in range(8):
    a=face*math.pi/4;n=np.array([math.cos(a),math.sin(a),0]);t=np.array([-n[1],n[0],0]);z=np.array([0,0,112])
    vs=[n*117.5-t*42-z,n*117.5+t*42-z,n*117.5+t*42+z,n*117.5-t*42+z]
    ax.add_collection3d(Poly3DCollection([vs],facecolor='#286c51',alpha=.3,edgecolor='#286c51'))
    for r in range(8):
        for x in (-29,-11,11,29):
            p=n*105+t*x+np.array([0,0,42+20*r-112]);theta=np.linspace(0,2*math.pi,15);front=[p+t*(8*math.cos(q))+np.array([0,0,8*math.sin(q)]) for q in theta]
            ax.add_collection3d(Poly3DCollection([front],facecolor='#a1aeb9',alpha=.9,edgecolor='#506577',lw=.3))
ax.set(xlim=(-155,155),ylim=(-155,155),zlim=(-120,120),xlabel='X (mm)',ylabel='Y (mm)',zlabel='Z (mm)');ax.set_box_aspect((1,1,.8));ax.view_init(elev=28,azim=25)
ax.set_title('R1 assembly envelope: 8 PCBs + 256 emitting discs\nConcept geometry; frame and rotating camera excluded');fig.tight_layout();fig.savefig(d/'assembly_preview.png',dpi=180);plt.close(fig)

(d/'mechanical/tunnel_envelope.scad').write_text('''// Concept envelope, not an external frame design. Dimensions in mm.
// PCB board-only STEP in the same directory is the native board outline.
$fn=40;
w=84; length=224; thickness=1.6; separation=210; tx_h=12.5; tx_d=16;
for(face=[0:7]) rotate([0,0,face*45]) {
  color([0.12,0.4,0.28,0.5]) difference() {
    translate([separation/2+tx_h,-w/2,-length/2]) cube([thickness,w,length]);
    for(xx=[6,w-6],yy=[11,length-11]) translate([separation/2+tx_h-1,xx-w/2,yy-length/2]) rotate([0,90,0]) cylinder(h=thickness+2,d=3.2);
  }
  for(col=[-29,-11,11,29],row=[0:7]) color([0.6,0.65,0.7]) translate([separation/2,col,42+row*20-length/2]) rotate([0,90,0]) cylinder(h=tx_h,d=tx_d);
}
''',encoding='utf-8')

summary={}
for key in ('schematic','pcb','emc','gerbers','cross_analysis'):
    a=json.loads((d/'analysis'/f'{key}.json').read_text());find=a.get('findings',[])
    summary[key]={'count':len(find),'severity':dict(Counter(f['severity'] for f in find)),'rules':dict(Counter(f['rule_id'] for f in find))}
(d/'analysis/findings_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
readme='''# 8면 터널용 32채널 PCB R1 — KiCad 10

기존 16채널 회로와 배선을 두 전기적 뱅크로 재사용해, 4열 × 8행의 트랜스듀서를 한 장에 배치한 새 설계입니다. 같은 PCB 8장으로 총 256채널을 구성합니다. 기존 설계 파일은 수정하지 않았습니다. 실제 PCB 발주·조립·구동은 수행하지 않았습니다.

## 파일 열기

`panel_8faces_32ch_R1.kicad_pro`를 KiCad 10에서 엽니다. 회로도와 PCB, 프로젝트 로컬 심벌/풋프린트 및 모델이 함께 들어 있습니다. 회로도는 620 × 460 mm 사용자 용지의 단일 시트입니다.

## 이번 시제품의 치수

| 항목 | R1 값 | 의미 |
|---|---:|---|
| PCB | 84 × 224 × 1.6 mm | 2층, 면마다 1장 |
| 발진면 맞은편 거리 | 210 mm | 기존 300 mm에서 축소한 시작점 |
| PCB 앞면의 중심까지 거리 | 117.5 mm | 발진면 거리 + 가정한 소자 높이 12.5 mm |
| 트랜스듀서 | 4 × 8, 지름 16 mm | 기존 풋프린트 사용, 정확한 구매품 확인 필요 |
| 열 중심 간격 | 18 / 22 / 18 mm | 두 기존 배선 셀 사이에 4 mm를 더 확보 |
| 행 중심 간격 | 20 mm | 기존과 동일 |
| 위·아래 고정 여백 | 각각 22 mm | 부품·배선·동박 채움 없는 영역 |
| 고정 구멍 | 4개, 지름 3.2 mm NPTH | (6,11), (78,11), (6,213), (78,213) mm |
| 인접 PCB 앞면 모서리 거리 | 약 12.325 mm | 광학 유효 개구 폭이나 시야각을 뜻하지 않음 |

기판 내부 슬롯은 없습니다. 기판 사이 틈을 남기는 정팔각형 터널 배치이며 외부 카메라와 회전 프레임 자체는 이번 설계 범위 밖입니다. 물체 전체가 보이는 조건은 유지해야 하지만 물체 크기와 촬영 위치가 없어 아직 증명되지 않았습니다.

200 mm가 절대 기준은 아니므로, 기존 셀 배선 유지와 틈 확보를 위해 210 mm를 선택했습니다. 같은 84 mm PCB를 발진면 거리 200 mm로 배치하면 앞면 모서리 거리는 약 8.498 mm로 줄어듭니다. 두 경우 모두 소자 외피는 단순 모델상 충돌하지 않지만 카메라 시야·음향 부상 성능은 별도 검증이 필요합니다. 기판 뒤 부품, 케이블, 프레임은 틈을 더 가릴 수 있습니다.

`parameters.json`은 현재 치수 기록입니다. 생성 스크립트는 보드 폭·길이와 발진면 거리를 조정할 수 있으나 열·행 간격, 소자 높이, 고정 여백 변경을 임의로 자동 배선하지 않습니다. 변경 후 네이티브 파일·간섭·ERC/DRC·제조 파일을 다시 검증해야 합니다. JSON 수치만 바꿔 기존 Gerber를 그대로 사용할 수 없습니다.

## 전기 구성과 연결

32채널을 16채널 A/B 뱅크로 나눕니다. 뱅크 사이에서 PCB 내부로 연결된 공통 전원망은 GND뿐입니다. +5V_A/B, DRV_VDD_A/B, SHIFT/LATCH/ARM_A/B는 각각 외부에서 공급합니다. 같은 공급원이나 클록을 쓰려면 외부 분배가 필요합니다. 한쪽 헤더만 연결하면 다른 뱅크가 자동 동작하지 않습니다.

| 핀 | J1: BANK A 신호 | J2: BANK B 신호 |
|---:|---|---|
|1|GND|GND|
|2|+5V_A|+5V_B|
|3|DATA_A0|DATA_B0|
|4|GND|GND|
|5|DATA_A1|DATA_B1|
|6|GND|GND|
|7|SHIFT_PIN_A|SHIFT_PIN_B|
|8|LATCH_PIN_A|LATCH_PIN_B|
|9|ARM_A|ARM_B|
|10|GND|GND|

J3(A), J4(B) 전원 헤더는 1=DRV_VDD, 2=GND, 3=+5V입니다. 실크와 패드 번호를 기준으로 확인하고 커넥터 뒷면 시점의 좌우를 추측하지 마세요. +5V는 5 V 로직 공급이며 TC4427A의 드라이버 전원 허용 범위는 4.5–18 V입니다. 실제 트랜스듀서의 연속 구동 정격 확인 전 드라이버 전압을 확정하지 않습니다.

ARM 기본 풀다운 → MMBT3904 OFF → 74HCT595 /OE 풀업으로 출력 비활성화합니다. 입력 풀다운으로 TC4427A 입력의 부유를 방지합니다. 전원 안정 후 ARM 비활성 상태에서 4개의 데이터 라인에 값을 시프트하고 래치한 다음 ARM을 활성화하는 순서를 사용합니다. 외부 FPGA와 헤더 배선은 이번에 변경하지 않았습니다.

T1…T32는 행 우선 순서입니다. QA…QH 출력 기준 `channel_map.csv`와 전체 256개 위치 `array_positions_256.json`을 제공합니다. `physical_to_software_channel_map.json`은 문서화한 DATA 순서에 대응하는 후보이며 FPGA의 실제 시프트 비트 방향과 헤더 배선을 확인하기 전 기존 프로그램에 바로 적용하지 않습니다.

## 제작·조립 자료

- `Gerber_R1_PCB_only.zip`: 동박·마스크·실크·페이스트·외곽, PTH/NPTH 드릴 및 Gerber job. PCB 1장 패턴이며 8장 주문 수량은 별도 지정합니다.
- `BOM_ALL.csv`, `BOM_SMT.csv`, `BOM_THT.csv`: 1장 및 8장 수량, 후보 MPN. 1장당 SMT 110개와 THT 38개입니다. M3 고정 나사·프레임·케이블은 포함하지 않습니다.
- `PnP_SMT_KiCad.csv`: KiCad 원본 좌표, mm, Bottom, X 양수/Y 음수. 임의 미러 변환을 하지 않았습니다. 업체의 바닥면 좌표 규약과 반드시 맞춰야 합니다.
- `THT_Placement.csv`: 트랜스듀서·헤더·전해콘덴서 수동 조립 위치. TX 패드1=출력/패드2=GND, 전해콘덴서 패드1=양극입니다.
- `mechanical/panel_board_only.step`: 실제 PCB 외곽·고정 구멍의 STEP. 부품 및 외부 프레임 미포함.
- `mechanical/tunnel_envelope.scad`: 8면 PCB/소자 외피의 치수 모델. 고정 구조 설계용 완성 프레임이 아닙니다.
- `geometry_preview.png`, `assembly_preview.png`, `pcb_top.png`, `pcb_bottom.png`, `schematic_preview.png`: 배치·실제 회로도·배선 미리보기.

PCB 제안 사양은 FR-4, 2층, 1.6 mm, 1 oz 동박이며 제작업체의 실제 공정 사양을 확인해야 합니다. 업체 패널라이징, 리플로우 캐리어, 스텐실 여백, 부품 대체 선정은 이번 패키지에 포함하지 않습니다. THT 트랜스듀서는 안쪽 F면, 구동 부품은 바깥쪽 B면에 배치합니다.

## 검증과 남은 사항

KiCad 10.0.6 ERC 0, DRC 위반 0, 미연결 0, 회로도/PCB 불일치 0. 별도 검증에서 전기 패드 468개(연결 432개/명시 NC 36개), 32개 출력 경로, 256채널 맵, SMT 좌표와 고정 여백을 확인했습니다. 원본 PCB의 SHA-256도 유지되었습니다. GND 비아 98개를 추가했습니다.

기존 프로젝트의 5개 DRC ignore 설정과 ERC ignore 설정은 유지되며 검증 범위는 `DESIGN_REVIEW.md`에 기록했습니다. 제조업체 DFM, 실제 전류·온도·신호 파형·음향 부상과 전체 물체 촬영은 검증되지 않았습니다. 자동 EMC 검토의 귀환 경로 및 외부 케이블 경고가 남아 있어 측정과 필요시 배선 수정이 필요합니다. 자세한 판단과 근거는 `DESIGN_REVIEW.md`, 기계 판정은 `geometry_summary.json`, 원시 검사 결과는 `analysis/`에 있습니다.

## 재생성

프로젝트 루트에서 `구상도/scratch/build_panel32_r1.py`와 `stitch_panel32_r1.py`, `verify_panel32_r1.py`를 KiCad 내장 Python으로 실행합니다. `export_panel32_r1.py`, `render_panel32_r1.py`, `package_panel32_r1.py`는 시스템 Python을 사용합니다. 검증은 ERC/DRC와 XML netlist 내보내기 뒤 수행합니다. 렌더에는 로컬 resvg-py/Pillow, 치수 미리보기에는 numpy/matplotlib이 필요합니다. 생성은 기존 16채널 소스 셀을 읽으므로 소스 폴더가 필요하며 새 설계를 편집한 뒤 생성 스크립트를 다시 실행하면 R1 편집 내용이 덮어써집니다.
'''
if (d/'mechanical/creo32_frame_R2/native/tunnel8_32_r2.asm').exists():
    readme+='\n## 색상 및 외부 프레임 포함 Creo 모델 R2\n\n[전체 조립체](mechanical/creo32_frame_R2/native/tunnel8_32_r2.asm)는 진녹색 PCB 8장과 회색 상하 팔각 링 2개를 포함합니다. 전체 외형 265×265×224 mm, 기존 PCB 고정 구멍에 맞춘 M3 체결 구멍 및 촬영용 면간 틈을 유지했습니다. [Creo R2 사용안내](mechanical/creo32_frame_R2/사용안내.md)에 치수·파일·검증 범위가 있으며, [모델 ZIP](mechanical/creo32_frame_R2/Creo32_frame_R2_models.zip)에 모든 참조 단품을 포함했습니다. 기판 조립체는 `panel32_r2.asm`, 기판 단품은 `pcb32_r2.prt`, 링 단품은 `ring8_32_r2.prt`입니다. 이전 R1 모델은 보존했습니다.\n'
elif (d/'mechanical/creo32_R1/native/panel32_r1.asm').exists():
    readme+='\n## 새 Creo 모델\n\n`mechanical/creo32_R1/native/panel32_r1.asm`은 기판과 트랜스듀서32개 및 후면부품을 포함한 조립체입니다. `tunnel8_32_r1.asm`은 8면 전체, `pcb32_r1.prt`는 기판 단품입니다. 부품 외형은 근사 모델이며 상세 형상·편집·검증 안내는 [Creo 사용안내](mechanical/creo32_R1/사용안내.md)에 있습니다. 같은 폴더에 STEP와 모델 ZIP도 제공합니다.\n'
(d/'README.md').write_text(readme.replace('98개',str(stitch_count)+'개'),encoding='utf-8')

review=f'''# R1 설계 검토 — KiCad 10.0.6 / 2026-10-06

## Overview / 판정

**새 네이티브 회로도·배선된 PCB·제작 출력의 시제품 설계가 완료되었습니다. 성능 및 생산 승인까지 검증한 설계는 아닙니다.** 원본 16채널 셀을 두 개 합쳐 32채널 한 장으로 만들었습니다. 외부 전원·FPGA·카메라·프레임은 별도 구성입니다.

## Critical Findings / 우선 확인

| 항목 | 판단·신뢰도 | 근거 및 영향 |
|---|---|---|
| FPGA 시프트 순서·헤더 분배 | 미확인 | 기존 펌웨어를 수정하지 않음. 맵은 QA…QH와 문서상 DATA 순서만 보장 |
| 트랜스듀서 정확한 제조사·연속 전압·정전용량 | 미확인 | D16/P10 기존 풋프린트만 유지. 전압과 열·전류 예산 확정 불가 |
| 물체 전체 촬영 | 미확인 | 물체 크기·카메라 위치 미정. 12.325 mm 기판 모서리 거리는 촬영 성립 증명이 아님 |
| 출력 귀환 경로·외부 케이블 EMC | heuristic / 중간 이하 | 자동 EMC가 92개 항목을 보고. 제조 연결 오류와 분리하여 파형·방사 실측 필요 |
| 전원 공급/커넥터 전류 용량 | inference-only | 동시 256채널 전류 미정. 보호·외부 분배·전압강하를 시스템에서 확인 |

## Previous Review Delta

기존 면당 16채널 PCB 2장/총16장에서 면당32채널 PCB1장/총8장으로 변경했습니다. 중앙 기판 슬롯을 제거하고 인접 면 틈은 유지했습니다. 기존 열18/행20 mm 간격을 유지하면서 두 셀 사이 열만22 mm로 조정했습니다. 발진면 거리300→210 mm, PCB84×224 mm, 고정 여백22 mm, GND 비아98개 추가. IC 구매 후보 표기를 Nexperia 74HCT595D,118로 통일했습니다. `delta_from_16ch.json`은 초기 분석 대비 자료이며 이후 GND 보강은 `stitching.json`에 별도 기록됩니다. 이전 업체의 0.002 mm 간격 지적은 원래 오류 좌표가 없어 해결을 단정하지 않습니다.

## Component Summary

74HCT595 4개, TC4427A16개, MMBT3904 2개, 저항50개, MLCC38개, 전해2개, 헤더4개, TX32개 = 전기부품148개/장. 고정홀4개 별도. SMT110/THT38. MPN은 BOM 후보이며 확정 구매 지시가 아닙니다. 제조사 미정 TX/헤더와 일부 배급사 번호가 없는 부품은 구매 확인이 필요합니다.

## Power Tree / Power Analysis

외부 +5V_A/B → 각 74HCT595 2개, OE/ARM 회로, 100 nF 2개 +10 µF 1개/뱅크.
외부 DRV_VDD_A/B → 각 TC4427A8개, 100 nF8개 +1 µF8개 +220 µF1개/뱅크.
GND는 두 뱅크 공통. 레귤레이터·전원 역접 보호·입력 퓨즈·전압감지 회로는 없음.
74HCT595은5 V 로직, TC4427A4.5–18 V 전원 범위(제조사 PDF p1), TTL 입력. TC4427A는 트랜스듀서 한쪽을 구동하는 비반전 듀얼 출력이며 브리지 구동이 아님. 1.5 A 표기는 드라이버의 피크 능력이며 연속 PCB 전류 정격으로 해석하지 않습니다. 용량성 전류/동적 소비는 주파수·부하 정전용량·전압·파형과 손실에 따라 달라 실측 예산이 필요합니다. 동박1oz는 제안값이며 실측 전류/허용 온도상승으로 재평가해야 합니다.

## Analyzer Verification / 핀 근거

별도 `verification.json` 검사는 원시 PCB 패드468개와 새 XML 네트리스트의 모든 핀을 대조하여 일치 확인(raw-file verified / 높음). 명시 NC36개와 기계NPTH4개는 구분했습니다. QA…QH→IN→TC4427A→OUT→TX32개 전부 검증했습니다.

| 부품 | 제조사 PDF / 페이지 | 검증 상태 |
|---|---|---|
| U1–U4 / 74HCT595D | Nexperia 74HC_HCT595, p5 핀 설명, p2 SO16 | datasheet-verified / 높음: 16VCC,8GND,14DATA,11SHIFT,12LATCH,13/OE,10/MR; 출력15,1…7 |
| U5–U20 / TC4427A | Microchip DS20001423, p8 핀 기능 | datasheet-verified / 높음: 2INA,3GND,4INB,5OUTB,6VDD,7OUTA,1/8NC |
| Q1–Q2 / MMBT3904 | Nexperia MMBT3904, p1 핀 표 | datasheet-verified / 높음: 1B,2E,3C |
| R1–R50,C1–C40 | 원시 패드/넷 대조; 후보 구매품 PDF 전수 검증 미실시 | raw-file verified / 높음; 제조사 공차·전압·패키지 전수는 미확인 |
| J1–J4 | 원시 번호/네트 대조 | raw-file verified / 높음; 구매 커넥터 방향·길이 미확인 |
| T1–T32 | 기존 D16/P10 모델 및 원시 패드 대조 | raw-file verified / 높음; 실제 송신기 데이터시트 미확인 |
| H1–H4 | PCB NPTH 지름3.2 mm | raw-file verified / 높음; 고정 하드웨어는 범위 밖 |

공식 PDF는 `datasheets/`에 보관했습니다. 구조화된 데이터시트 extraction 검증은 수행하지 않았으며 제조사 표를 직접 대조했습니다. 전체 부품의 제조사 데이터시트 검증이 완료되었다고 주장하지 않습니다.

## Signal Analysis Review

각 뱅크별 33 Ω 클록/래치 직렬 저항과 입력100 kΩ 풀다운을 유지했습니다. DATA0/1 각각8비트, SHIFT/LATCH/OE 공유인 두595 구성입니다. QA와 마지막에 시프트한 비트의 관계는 FPGA 구현에서 확인해야 합니다. ARM=LOW에서 Q OFF, OE HIGH,595출력고임피던스; 드라이버입력 풀다운으로 출력LOW가 의도됩니다(raw topology verified; 기동 과도파형 미측정). 출력 핀 접속만으로 FPGA 타이밍이나 음향 위상 보정까지 검증되지는 않습니다.

## PCB Layout Analysis

2층,84×224×1.6 mm. 트랙1408개, 비아212개(기존셀114+GND보강98). TX는 F면, 구동부 B면. 고정구간 y0–22 및202–224 mm는 전기 패드/배선 없는 것 확인. GND 두 면 채움, 뱅크 전원은 분리. 통합PCB 전체 시야·후면 하드웨어 간섭은 미검증.

## Thermal Analysis

`analyze_thermal.py`를 실행했으나 지원되는 발열부품/손실 데이터가 없어 분석이 SKIPPED되었습니다. TC4427A와 TX의 실제 손실·온도, 256채널 동시 동작 조건을 계산/측정하지 않았습니다. 열 안전 판정 없음.

## EMC / Cross-Domain Analysis

`analyze_emc.py` 재실행 {summary['emc']['count']}개: {summary['emc']['severity']}. 점수34/100은 해당 도구의 휴리스틱이며 인증 점수나 제조 합격 기준이 아닙니다. 출력 OUT의 참조면 공백과 층전환 귀환 경로, 드라이버 디커플링 거리, 외부커넥터 보호/필터를 주로 지적합니다. GND 비아를 추가한 후 cross_analysis의 접지 비아 밀도 경고는0개가 되었습니다. 다른 EMC 경고를 해결한 것으로 표시하지 않습니다. 짧은 드라이버-출력선도 빠른 에지가 있으므로 근거 없이 오탐 처리하지 않았습니다. 외부 케이블 길이, 스코프 입력/출력 파형, 링잉/그라운드바운스와 동시 스위칭을 확인하여 재배선 필요성을 판단합니다.

## Component Lifecycle

`lifecycle_audit.py --onlylcsc` 실행10개 후보 모두unknown. 이 모드는 수명상태를 확인할 수 없다는 도구 설명이 있어 공급/단종 상태로 해석하지 않습니다. 공식 제조사 생산 상태 및 실제 재고는 확인되지 않았습니다.

## Manufacturing / DFM / Testability

KiCad ERC0/DRC0/미연결0/패리티0. 9개 Gerber 및 독립 PTH/NPTH 드릴을 새 보드에서 출력했습니다. 정렬 경고는 동박영역 높이180 mm와 외곽224 mm의 의도된44 mm 차이이며 동일 좌표 원점을 유지합니다. 위·아래는 동박을 의도적으로 비웠으므로 레이어의 occupied bounding box가 같을 필요는 없습니다. Drill/outline/패드의 좌표 기준을 실제PCB 출력과 대조했습니다. SMT좌표110개를 manifest와 대조했으며 임의 bottom미러 변환 없음.

기존 커스텀 풋프린트에는 일부 courtyard가 없습니다. 업체 DFM과 조립방향·TX 극성·기구 높이 확인이 필요합니다. 전용 테스트 포인트/공장검사 지그는 추가하지 않았습니다. 헤더에서 전원·ARM·클록·데이터 확인, ARM off에서 전류 확인, 채널별 순차 활성화, 전체 동시 구동을 단계적으로 검증하는 것이 적절합니다(inference-only).

## False Positives / Reviewer Overrides

- KO-001 고정홀 keepout 오류4개: NPTH이며 KiCad rule-area가 패드/기계홀을 허용하고 트랙·비아·동박 채움만 금지합니다. 실제DRC0과 전기패드 부재 확인으로 오탐 판정(raw-file verified). 구멍을 전기적 접지 패드로 변경하지 않았습니다.
- GR-002 레이어 높이44 mm 차이: 고정용 무동박 영역 때문. 레이어 자동 bounding-box 비교에 따른 정렬 오탐이며 Gerber 원점이 다른 증거가 아님.
- 자동 lifecycle unknown 및 디커플링 거리 경고를 생산/전기 실패로 단정하지 않음. EMC 출력 참조면 경고는 남은 검토사항으로 보존.

## Not Performed / Review Limits

실행: KiCad ERC/DRC/패리티, XML netlist전수대조, analyze_schematic.py, analyze_pcb.py --full, analyze_gerbers.py, cross_analysis.py, analyze_emc.py, analyze_thermal.py(실행 후SKIPPED), lifecycle_audit.py(unknown), diff_analysis.py(16ch 초기분석 대비). 분석 결과는 `analysis/`에 보관.

미실행: SPICE(ngspice/상용엔진 설치없음, TX모델없음), 발주업체 DFM/패널화, FPGA 빌드·비트순서/배선 통합시험, 전체 제조사 부품 PDF확인, 열손실 계산/온도측정, 전류·EMI실측, 음향장/부상 실험, 카메라 광학 검증, 외부 프레임과 케이블 3D간섭 검사.

프로젝트 DRC ignore 유지: footprint_filters_mismatch, footprint_type_mismatch, missing_courtyard, track_not_centered_on_via, tuning_profile_track_geometries. ERC ignored_checks는 `ERC.json` 원문에 기록. 제외된 검사를 포함한 무조건 오류0 또는 양산 승인으로 해석하지 않습니다. 실제 위반을 항목별로 숨기는 DRC exclusions는 비어 있습니다.

## Final Verdict / trust_summary

원시파일·제조사 핵심IC 핀 연결: 신뢰 높음. 후보부품 완전성·열·EMC·FPGA 통합·음향/광학: 미확인 또는 휴리스틱. **KiCad 10에서 편집·검토할 수 있는 새 시제품 제작자료를 제공하며, 실물 성능·제조업체 승인 완료는 주장하지 않습니다.**
'''
(d/'DESIGN_REVIEW.md').write_text(review.replace('98개',str(stitch_count)+'개').replace('보강98','보강'+str(stitch_count)).replace('비아212개','비아'+str(114+stitch_count)+'개'),encoding='utf-8')
for filename in ('README.md','DESIGN_REVIEW.md'):assert (d/filename).read_text(encoding='utf-8')

with zipfile.ZipFile(d/'Gerber_R1_PCB_only.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted((d/'gerbers_R1').iterdir()):
        if p.suffix.lower() in ('.gbr','.gbrjob','.drl','.gtl','.gbl','.gts','.gbs','.gto','.gbo','.gtp','.gbp','.gm1'):z.write(p,p.name)
hashes={str(p.relative_to(d)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in d.rglob('*') if p.is_file() and p.suffix not in ('.zip','.pyc','.lck','.kicad_prl') and p.name!='SHA256.json' and not p.name.startswith('trail.txt.')}
(d/'SHA256.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2),encoding='utf-8')
with zipfile.ZipFile(d/'Design_R1_complete.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(d.rglob('*')):
        if p.is_file() and p.name!='Design_R1_complete.zip' and p.suffix not in ('.pyc','.lck','.kicad_prl') and not p.name.startswith('trail.txt.'):
            z.write(p,Path(name)/p.relative_to(d))
print('Package complete:',d)
