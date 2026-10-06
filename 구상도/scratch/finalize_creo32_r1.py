"""Finalize only after fresh Creo session validates saved native geometry."""
from pathlib import Path
import json,hashlib,zipfile,shutil
import cadquery as cq
r=Path(__file__).resolve().parents[1];source=r/'outputs/panel_8faces_32ch_R1';d=source/'mechanical/creo32_R1';stage=r/'scratch/creo32_session'
report=json.loads((stage/'build_report.json').read_text());assert report['ok'] and report['freshSession'] and report['placementVerified'] and report['fixConstraintsVerified'],report
assert len(report['parts'])==10 and len(report['panelComponents'])==149 and len(report['tunnelComponents'])==8
geo=json.loads((d/'geometry_checks.json').read_text());digest=hashlib.sha256((source/'panel_8faces_32ch_R1.kicad_pcb').read_bytes()).hexdigest();assert digest==geo['source_pcb_sha256'],'PCB was changed during modeling'
roundtrip=[]
for p in geo['parts']:
 matches=list((d/'validation/native_reexport').glob(p['name']+'.*'))
 matches=[f for f in matches if f.suffix.lower() in ('.stp','.step')]
 assert len(matches)==1,(p['name'],matches)
 shape=cq.importers.importStep(str(matches[0])).val();assert shape.isValid() and len(shape.Solids())==1,p['name']
 bb=shape.BoundingBox();actual=[[bb.xmin,bb.ymin,bb.zmin],[bb.xmax,bb.ymax,bb.zmax]]
 assert abs(shape.Volume()-p['volume_mm3'])<.01,(p['name'],shape.Volume(),p['volume_mm3'])
 assert all(abs(actual[i][j]-p['bounds_mm'][i][j])<.01 for i in range(2) for j in range(3)),(p['name'],actual,p['bounds_mm'])
 roundtrip.append({'name':p['name'],'solids':1,'volumeMm3':shape.Volume(),'boundsMm':actual})
(d/'validation/native_STEP_roundtrip.json').write_text(json.dumps({'ok':True,'parts':roundtrip},indent=2),encoding='utf-8')
assert not geo['panel_collisions'] and not geo['tunnel_collisions']
(d/'validation/native_reopen_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
readme='''# 32채널 PCB R1 — Creo 모델

KiCad R1의 현재 기판과 부품 배치를 사용한 새 모델입니다. 기존 Creo 파일과 KiCad 회로/배선은 변경하지 않았습니다. Creo Parametric Educational Edition 9.0.10.0에서 실제 `.prt`·`.asm`을 생성하고, 새 세션에서 저장 파일을 다시 불러와 검증했습니다.

## Creo에서 여는 파일

`native` 폴더를 작업 디렉터리로 지정하고 아래 파일을 엽니다. 조립 파일을 다른 곳으로 옮길 때는 `native`의 12개 파일을 모두 함께 복사하세요.

| 파일 | 내용 |
|---|---|
| `pcb32_r1.prt` | 84 × 224 × 1.6 mm 기판 단품, 고정홀4개 및 부품용 구멍94개 |
| `panel32_r1.asm` | PCB1장 + 트랜스듀서32개 + 후면부품116개, 직접 구성요소149개 |
| `tunnel8_32_r1.asm` | 위 기판 조립체8개, 트랜스듀서총256개, 총1192개 솔리드 |
| `tx16_r1.prt` | 지름16 mm·높이12.5 mm 트랜스듀서 몸체 근사 |
| 나머지7개 PRT | 저항·MLCC·SOIC16/8·SOT23·전해콘덴서·헤더2종의 공유 근사 외형 |

단품은10종, 조립체는2종입니다. 나머지 부품은8개 PRT가 맞으며 위 표의 분류 중 "나머지7개"는 TX 외 기판을 제외한 부품 종류8개를 뜻하도록 아래 목록을 기준으로 합니다:
`r0805_r1`, `c0805_r1`, `so16_r1`, `so8_r1`, `sot23_r1`, `cp63_r1`, `hdr10_r1`, `hdr3_r1`.

## 형상과 좌표

- 기판 로컬 좌표: X=폭0…84 mm, Y=길이0…224 mm, Z=두께0…1.6 mm. 안쪽/트랜스듀서 면은Z=0이며 소자는Z=-12.5…0 mm에 있습니다. 후면 부품은Z≥1.6 mm에 배치합니다.
- 트랜스듀서 열중심X=13,31,53,71 mm, 행중심Y=42,62,…182 mm. 열간격18–22–18 mm, 행간격20 mm.
- 위아래 고정여백은각22 mm. M3 고정홀은지름3.2 mm, (6,11),(78,11),(6,213),(78,213) mm입니다.
- 8면 조립체: 세계Z=0은기판높이중앙, 각면45°. PCB안쪽면의중심거리117.5 mm, 발진면은105 mm로 마주보는발진면간격210 mm입니다. 기판모서리틈약12.325 mm입니다.
- 후면부품 포함모델 외접크기는260.2 × 260.2 × 224 mm입니다. 부품 근사모델 기준이며 커넥터에 꽂히는 케이블/플러그는 미포함입니다.
- 기판에는실제부품패드/고정용98개구멍이있습니다. 전기설계의206개비아, 동박트랙, 솔더마스크표면텍스처와 실크는기계모델에서생략했습니다.

## 모델 정확도와 편집

기판 외곽·두께·부품구멍과실제풋프린트위치는KiCad로부터검증했습니다. 부품은기구배치를보는단순몸체모델입니다. TX캔/메시/내부진동판, IC리드, 헤더개별핀, 전해콘덴서극성표시, 소자납땜높이는정밀제조사CAD가아닙니다. 실제구매품으로체결/케이블간섭을최종확인해야합니다.

PRT는 STEP에서 가져온 솔리드와 가져오기 피처입니다. Creo의 네이티브 스케치·돌출 치수로 전체 설계가 파라미터화되어 있는 것은 아닙니다. 조립체는 같은 공유 PRT를 재사용하고 각 부품/면에 Fix 구속을 적용했습니다. 위치를 바꾸려면 해당 Fix 구속을 수정하거나 다른 구속으로 바꾸면 됩니다. 기판 치수나 부품 외형 변경은 제공 생성 스크립트에서 재생성하거나 Creo 직접 편집을 사용할 수 있습니다.

## STEP 및 미리보기

`geometry/pcb32_r1.step`, `panel32_r1.step`, `tunnel8_32_r1.step`도 제공합니다. 표준 교환형식 STEP는 [CadQuery 공식 내보내기 문서](https://cadquery.readthedocs.io/en/latest/importexport.html)의 방식으로 만들었습니다. `panel32_model_preview.png`는 실 STEP 솔리드의앞뒤외형, `tunnel8_model_preview.png`는8면배치입니다. PNG는 Creo 화면캡처가 아닌 실제STEP형상을렌더링한미리보기입니다. 색상은이해를돕는표시이며실물외관을보장하지않습니다.

## 검증

- CadQuery2.8.0/OCP7.9.3.1.1: 솔리드 유효성, 전부품/조립STEP재가져오기, 구멍98개와정확한기판체적, 모든TX발진면중심의음향좌표일치 확인.
- 기판조립체의모델솔리드교차체적검사0건. 인접면은전체모델을포함하는각도구간이겹치지않음을보수적외접범위로증명했습니다. 이는 모델에 포함된 형상에 대한 검사입니다.
- Creo새세션: 부품10종 단위·체적, 기판/상자외형치수, 원통높이·체적·중심, 기판조립체149개및면조립체8개의모델참조·행렬·비패키징상태를검증했습니다. 원통XY `GeomOutline`은 보수적경계를반환할수있어직경대신높이와체적/중심으로독립검증했습니다. 실제수치는`validation/native_reopen_report.json`에보관합니다.
- 기판및8면조립체외접치수는CreoAPI와STEP모델을대조했습니다. 실제CreoGUI화면캡처는환경의창검색제약으로확인하지않았으며CreoAPI의저장/재조회결과를사용했습니다.
- 원본KiCadPCB SHA-256 유지. 외부프레임/회전카메라/케이블이없는조건의기계형상검사이며열·음향부상·전체물체촬영검증은포함하지않습니다.

`geometry_checks.json`, `pcb_geometry_input.json`, `validation/`은좌표/단위/검증근거입니다. `Creo32_R1_models.zip`에는native·STEP·PNG·검증기록이함께들어있습니다. STEP에서읽은부품이름과부품방향을확인한뒤실제기구설계에사용하세요.

## 재생성

프로젝트 `구상도/scratch`의 `extract_creo32_r1.py`(KiCad내장Python), `prepare_creo32_r1.py`, `build_creo32_geometry.py`, `verify_creo32_native.py`, `render_creo32_vtk.py`, `finalize_creo32_r1.py`를사용했습니다. 기하생성/렌더에는같은위치의프로젝트전용 `creo32_env` 환경을사용했습니다. Creo생성용스크립트/HTML은 `creo32_session`에있고, 한글경로호환성을위해Temp의두ASCII정션으로동일프로젝트파일을참조했습니다. 산출물의원본파일은이프로젝트안에만있습니다.
'''
readme=readme.replace('나머지7개 PRT','나머지8개 PRT').replace('원통높이·체적·중심','원통의 정확한 STEP 외형·체적').replace('직경대신높이와체적/중심으로독립검증했습니다','Creo에서 부품을 다시 STEP로 내보내 정확한 외형과 체적을 독립검증했습니다').replace('체적·부품외형/원통높이/중심','체적·부품외형의 네이티브 STEP 재내보내기')
start=readme.index('단품은10종');end=readme.index('## 형상과 좌표')
readme=readme[:start]+'''단품은10종, 조립체는2종입니다. 후면공유부품은 `r0805_r1`, `c0805_r1`, `so16_r1`, `so8_r1`, `sot23_r1`, `cp63_r1`, `hdr10_r1`, `hdr3_r1`입니다.

'''+readme[end:]
(d/'사용안내.md').write_text(readme,encoding='utf-8')
native={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (d/'native').iterdir() if p.is_file()}
assert len(native)==12
manifest={'source_pcb_sha256':digest,'native_files':native,'reopen_verified':True,'native_STEP_roundtrip_verified':True,'components_per_panel':149,'panels':8,'STEP_solids':1192,'component_bodies':'approximate','board_holes':98,'overall_bounds_mm':geo['tunnel']['bounds_mm']}
(d/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
with zipfile.ZipFile(d/'Creo32_R1_models.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in sorted(d.rglob('*')):
  if p.is_file() and p.suffix!='.zip':z.write(p,Path('creo32_R1')/p.relative_to(d))
with zipfile.ZipFile(d/'Creo32_R1_models.zip') as z:assert z.testzip() is None
status=r.parent/'docs/project_status.txt';heading='### 2026-10-06 32채널 PCB R1 Creo 모델 생성'
old=status.read_text(encoding='utf-8')
if heading not in old:status.write_text(old+'\n\n'+heading+'''\n- 새 PCB의 실제 부품148개 및 부품/고정구멍98개를 추출하여 `구상도/outputs/panel_8faces_32ch_R1/mechanical/creo32_R1`에 Creo9.0.10교육용PRT10종/ASM2종, STEP/미리보기/검증/ZIP생성. pcb32_r1.prt, panel32_r1.asm, tunnel8_32_r1.asm 제공.
- PCB84×224×1.6 mm, TX4×8=32개/면, 총8면256개, 발진면간격210 mm, 위아래고정여백22 mm. 후면116개부품몸체를 포함하나 부품외형은근사, 전체외접260.2×260.2×224 mm. 외부프레임·카메라·케이블·비아/동박/실크텍스처는미포함.
- STEP재가져오기·솔리드수·정확한기판체적·32/256개위치·모델교차0 및보수적각도영역으로인접면분리확인. Creo새세션에서단위·체적·부품외형/원통높이/중심·149/8개참조·행렬·Fix유지확인. 원통보수적GeomOutline차이는높이/체적/중심으로판정. 실제GUI화면캡처검증은창검색제약으로미수행.
- 기존Creo및KiCad설계파일변경없음. PRT는가져오기피처기반으로완전한스케치/돌출파라미터모델이아님. 실제구매품/커넥터플러그·기구공차·전체물체촬영·음향/열검증은별도필요.
''',encoding='utf-8')
print('Finalized Creo native models, fresh-session report and model ZIP.')
