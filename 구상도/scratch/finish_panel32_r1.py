"""Record release and validate actual archive bytes against current native files."""
from pathlib import Path
import hashlib,json,zipfile,subprocess,sys
root=Path(__file__).resolve().parents[2];d=root/'구상도/outputs/panel_8faces_32ch_R1'
status=root/'docs/project_status.txt';heading='### 2026-10-06 8면 32채널 PCB R1 새 설계'
entry='''

### 2026-10-06 8면 32채널 PCB R1 새 설계
- 사용자 제작 요청으로 `구상도/outputs/panel_8faces_32ch_R1`에 독립 KiCad 10 회로도·배선 PCB·로컬 라이브러리·Gerber/드릴·BOM/PnP·256채널 좌표/맵·STEP·미리보기·검토 문서와 ZIP을 생성.
- 면당 4×8=32개, 동일PCB8장/총256채널. PCB84×224×1.6 mm, 위아래 무부품/무배선/무동박22 mm와 M3 NPTH4개. 열간격18–22–18 mm, 행20 mm. 내부 슬롯 제거. 발진면 간격210 mm에서 인접PCB 앞면 모서리 틈12.325 mm. 수치는 수정 가능한 시제품 선택값.
- 16채널 A/B 셀은 GND만 공통이고 전원·SHIFT/LATCH/ARM은 외부 분배 필요. 기존배선 재사용 후 GND 비아92개 추가(최종 전체206개); 부품 패드에서 비아를 떨어뜨려 조립성 경고 제거.
- KiCad 10.0.6 ERC/DRC/미연결/회로도패리티0. 전기패드468개(XML/PCB전수), 연결432/명시NC36, 32출력경로와256채널맵 및SMT110개좌표, 무동박고정여백 확인. 기존PCB SHA-256 불변.
- 기존5종DRC ignore/4종ERC ignore유지, 상세 검토범위 문서화. 제조업체DFM·FPGA비트순서/헤더연결·TX정확한MPN/정격·전류/온도/EMC·음향부상·전체물체촬영은 미검증. 카메라/외부프레임 제작 범위는 포함하지 않음. 자동분석의 실제잔여위험과keepout/레이어높이 오탐을 DESIGN_REVIEW.md에 분리 기록.
'''
old=status.read_text(encoding='utf-8')
if heading not in old:status.write_text(old+entry,encoding='utf-8')
subprocess.run([sys.executable,str(root/'구상도/scratch/package_panel32_r1.py')],check=True)
hashes=json.loads((d/'SHA256.json').read_text(encoding='utf-8'))
for rel,digest in hashes.items():assert hashlib.sha256((d/rel).read_bytes()).hexdigest()==digest,rel
with zipfile.ZipFile(d/'Design_R1_complete.zip') as z:
    assert z.testzip() is None
    for rel,digest in hashes.items():assert hashlib.sha256(z.read(d.name+'/'+rel)).hexdigest()==digest,rel
with zipfile.ZipFile(d/'Gerber_R1_PCB_only.zip') as z:
    assert z.testzip() is None and len(z.namelist())==12
    assert sum(n.endswith('.drl') for n in z.namelist())==2
    for name in z.namelist():assert z.read(name)==(d/'gerbers_R1'/name).read_bytes()
for name in ('panel_8faces_32ch_R1.kicad_pro','panel_8faces_32ch_R1.kicad_sch','panel_8faces_32ch_R1.kicad_pcb','mechanical/panel_board_only.step'):
    assert (d/name).stat().st_size>1000
a=json.loads((d/'analysis/pcb.json').read_text())
assert not any(f['rule_id']=='VP-001' for f in a['findings'])
print('Release PASS: native files, SHA256, Gerber 12-file ZIP, complete ZIP, no added via-in-pad warnings.')
