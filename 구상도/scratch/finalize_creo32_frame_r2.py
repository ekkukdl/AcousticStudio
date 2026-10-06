from pathlib import Path
import json,re,hashlib,zipfile,csv,math
import cadquery as cq
r=Path(__file__).resolve().parents[1];d=r/'outputs/panel_8faces_32ch_R1/mechanical/creo32_frame_R2';a=d/'validation';stage=r/'scratch/creo32_frame_session';old=d.parent/'creo32_R1'
data=json.loads((d/'geometry_checks.json').read_text(encoding='utf-8'))
reopen=json.loads((stage/'build_report.json').read_text(encoding='utf-8'));assert reopen['ok'] and reopen['freshSession'] and len(reopen['parts'])==11 and len(reopen['tunnelComponents'])==10
(a/'native_reopen_report.json').write_text(json.dumps(reopen,indent=2),encoding='utf-8')
checks=[];color_checks=[]
for p in data['parts']:
 path=a/'native_reexport'/(p['name']+'.stp');s=cq.importers.importStep(str(path)).val();b=s.BoundingBox()
 bb=[[b.xmin,b.ymin,b.zmin],[b.xmax,b.ymax,b.zmax]]
 assert s.isValid() and len(s.Solids())==1 and abs(s.Volume()-p['volume_mm3'])<.01,p['name']
 assert max(abs(bb[i][j]-p['bounds_mm'][i][j]) for i in range(2) for j in range(3))<.01,p['name']
 checks.append(dict(name=p['name'],valid=True,solids=1,volume_mm3=s.Volume(),bounds_mm=bb))
 # Follow actual solid's appearance references, rather than merely finding a
 # color in the exported palette (which contains unused default colors).
 text=path.read_text(encoding='utf-8');entities={int(k):v for k,v in re.findall(r'#(\d+)\s*=\s*(.*?);',text,re.S)}
 def color_refs(idx,seen=None):
  seen=set() if seen is None else seen
  if idx in seen:return []
  seen.add(idx);v=entities[idx]
  if v.startswith('COLOUR_RGB'):
   vals=v[v.index(',')+1:v.rindex(')')].split(',');return [[float(x) for x in vals]]
  return [c for sub in re.findall(r'#(\d+)',v) for c in color_refs(int(sub),seen)]
 bindings=[]
 for idx,v in entities.items():
  if not v.startswith('STYLED_ITEM'):continue
  refs=[int(x) for x in re.findall(r'#(\d+)',v)]
  if entities[refs[-1]].startswith('MANIFOLD_SOLID_BREP'):
   bindings.extend(c for ref in refs[:-1] for c in color_refs(ref))
 expected=data['colors_rgb'][p['name']]
 assert bindings and all(max(abs(x-y) for x,y in zip(c,expected))<1e-6 for c in bindings),(p['name'],bindings,expected)
 color_checks.append(dict(name=p['name'],native_solid_color_rgb=bindings,expected_rgb=expected,solid_style_binding_verified=True))
(a/'native_STEP_roundtrip.json').write_text(json.dumps(dict(ok=True,parts=checks,colors=color_checks),indent=2),encoding='utf-8')
for rel,sha in data['R1_protected_sha256'].items():assert hashlib.sha256((old/rel).read_bytes()).hexdigest()==sha,rel
pcb=r/'outputs/panel_8faces_32ch_R1/panel_8faces_32ch_R1.kicad_pcb';assert hashlib.sha256(pcb.read_bytes()).hexdigest()==data['source_pcb_sha256']
# Manufacturing coordinates: one shared ring, local Z=0..8; repeat twice.
with (d/'frame_mount_bores.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.writer(f);w.writerow(['face','tangent_mm','axis_start_x_mm','axis_start_y_mm','local_z_mm','axis_dx','axis_dy','diameter_mm','outer_face_to_inner_face_mm'])
 for k in range(8):
  nx,ny=math.cos(k*math.pi/4),math.sin(k*math.pi/4)
  for t in (-36,36):w.writerow([k+1,t,132.5*nx-t*ny,132.5*ny+t*nx,4,-nx,-ny,3.2,17])
readme='''# 32채널 PCB + 외부 프레임 Creo R2

기존 `creo_tunnel_reused_v2/build_geometry.py` 방식과 색상값을 사용했습니다. 기판 RGB(0.04,0.35,0.16), 프레임 RGB(0.30,0.32,0.36). 단품 STEP에도 색상을 넣어 Creo로 가져왔으며, 네이티브 저장→새 세션 재조회→STEP 재내보내기에서 실제 솔리드에 연결된 색상을 확인했습니다. 색상은 기구 모델의 외관 설정이며 PCB 제조업체의 솔더마스크 주문 설정은 별도입니다.

## 열 파일

- 전체 조립체: [native/tunnel8_32_r2.asm](native/tunnel8_32_r2.asm)
- 기판 조립체: [native/panel32_r2.asm](native/panel32_r2.asm)
- 진녹색 기판 단품: [native/pcb32_r2.prt](native/pcb32_r2.prt)
- 프레임 링 단품(동일 부품 2개): [native/ring8_32_r2.prt](native/ring8_32_r2.prt)
- 교환용 STEP: [geometry/tunnel8_32_r2.step](geometry/tunnel8_32_r2.step), [geometry/ring8_32_r2.step](geometry/ring8_32_r2.step)
- 미리보기: [tunnel8_model_preview.png](tunnel8_model_preview.png)

Creo의 작업 디렉터리를 `native`로 지정하고 전체 조립체를 여세요. 조립체와 모든 PRT를 같은 폴더에 두세요. Creo 9.0.10에서 생성·재조회했습니다. STEP에서 가져온 형상 피처이며 치수 구속 스케치로 만든 완전 파라메트릭 모델은 아닙니다. 부품 11종/조립체 2종, 기판 조립체 149개 구성요소, 최상위 조립체 8개 기판 조립체 + 링 2개입니다.

## 프레임 치수와 고정 방식

| 항목 | 치수 / 배치 |
|---|---|
| PCB | 84 × 224 × 1.6 mm, 위아래 고정 영역 22 mm |
| 발진면 사이 간격 | 기존 R1 선택값 210 mm 유지 |
| PCB 앞면 반경(아포템) | 117.5 mm |
| 팔각 링 외측/내측 대변 거리 | 265 / 231 mm |
| 링 두께 | 8 mm, 동일 부품 2개 |
| 링 배치 Z | 아래 −105..−97 mm, 위 97..105 mm |
| PCB 삽입 슬롯 | 각 링 8개, 길이 84.6 × 두께 2.2 mm, 링 높이 관통 |
| 슬롯 여유 | PCB 양면 및 양끝 각각 0.3 mm |
| M3 체결 구멍 | Ø3.2 mm, 각 링 16개 / 총 32개, 방사 방향 관통 |
| 구멍 위치 | 각 면 중앙에서 접선 방향 ±36 mm, 조립체 Z ±101 mm |
| 전체 프레임 포함 외형 | 265 × 265 × 224 mm; 볼트·너트 제외 |
| 링 사이 열린 높이 | 194 mm |

팔각형 꼭짓점 간 최대 폭은 대변 거리보다 큽니다(약 286.83 mm). 265 × 265 mm는 모델 X/Y축의 외접 치수입니다. 링 하나의 방사 방향 벽 폭은 17 mm입니다. 체결 위치는 PCB의 (6,11), (78,11), (6,213), (78,213) 구멍에 맞췄습니다. Z=0은 기판 높이의 중앙이고 +Z가 위쪽입니다. 링 단품 좌표는 Z=0..8 mm이며 체결 구멍 중심은 Z=4 mm입니다. `frame_mount_bores.csv`에 단품의 16개 구멍 축 좌표가 있습니다.

상하 링을 기판 고정 영역에 끼우고 M3 볼트/너트로 방사 방향 구멍과 PCB 구멍을 관통 체결하는 구조입니다. 재질, 와셔, 볼트 길이, 체결 토크는 확정하지 않았고 체결 부품은 모델에 포함하지 않았습니다. 슬롯은 끼움 여유를 가지므로 실물 치수와 재질에 따라 얇은 시임으로 유격을 조절할 수 있습니다. 가공 시 방사 방향 구멍은 측면 가공이 필요합니다. 밀링 슬롯의 코너 반경/끝단 여유는 공구와 PCB 모서리 형상에 맞춰 제조업체에서 검토해야 합니다. 3D 프린팅은 수축/공차를 반영한 시험 조립이 필요합니다.

## 촬영용 틈과 확인 범위

중간 높이에 세로 프레임 기둥을 넣지 않았으며, R1의 인접 PCB 앞면 모서리 사이 약 12.325 mm 틈을 유지했습니다. 연속 팔각 링은 상하 끝의 고정 영역만 감쌉니다. 전체 물체가 보이는지는 물체 크기·위치, 카메라 렌즈·궤적이 정해져야 확인할 수 있습니다. 회전 카메라, 케이블, 베어링/구동 장치는 포함하지 않았습니다.

기판과 부품에 대한 링 교차 체적 0건, 고정 구멍 축 정렬, STEP 재조회 1194개 솔리드, Creo 새 세션의 단위·외형·149/10개 참조·배치·고정 상태, 네이티브 단품 11종의 실제 STEP 외형/체적/솔리드 색상 연결을 확인했습니다. 검증 기록은 `geometry_checks.json`, `validation/native_reopen_report.json`, `validation/native_STEP_roundtrip.json`에 있습니다. 실제 Creo 창의 화면 캡처 대신 API 저장·조회와 STEP 재내보내기로 검증했으며 PNG는 STEP 형상을 렌더한 미리보기입니다.

기판 외곽과 98개 부품/고정 구멍은 기존 R1 데이터를 그대로 사용했습니다. 부품 몸체는 근사 외형이며 동박/실크/비아 구멍은 이 모델에 포함하지 않았습니다. 실제 부품·커넥터·납땜·전선의 공차 및 강도/진동/열/음향 성능은 미검증입니다. 이전 Creo R1 폴더와 원본 KiCad PCB의 SHA-256 불변을 확인했습니다.

재생성 스크립트: `구상도/scratch/build_creo32_frame_r2.py`, `prepare_creo32_frame_r2.py`, `verify_creo32_frame_r2.py`, `render_creo32_frame_r2.py`, `finalize_creo32_frame_r2.py`. 형상/렌더링은 프로젝트의 `creo32_env` 환경을 사용하며, Creo API HTML/스크립트는 `creo32_frame_session`에 있습니다.
'''
(d/'사용안내.md').write_text(readme,encoding='utf-8')
manifest=dict(ok=True,source_pcb_sha256=data['source_pcb_sha256'],previous_R1_files_preserved=True,native_count=13,frame_collisions=[],native_color_binding_verified=True,files={str(p.relative_to(d)):hashlib.sha256(p.read_bytes()).hexdigest() for p in d.rglob('*') if p.is_file() and p.suffix not in ('.zip','.lck') and p.name!='manifest.json'})
(d/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
with zipfile.ZipFile(d/'Creo32_frame_R2_models.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in d.rglob('*'):
  if p.is_file() and p.suffix not in ('.zip','.lck'):z.write(p,'creo32_frame_R2/'+str(p.relative_to(d)).replace('\\','/'))
with zipfile.ZipFile(d/'Creo32_frame_R2_models.zip') as z:
 assert z.testzip() is None
 for name,sha in manifest['files'].items():assert hashlib.sha256(z.read('creo32_frame_R2/'+name.replace('\\','/'))).hexdigest()==sha
status=r.parent/'docs/project_status.txt';heading='### 2026-10-06 PCB 색상 및 외부 프레임 Creo R2'
entry='''\n\n### 2026-10-06 PCB 색상 및 외부 프레임 Creo R2
- `구상도/outputs/panel_8faces_32ch_R1/mechanical/creo32_frame_R2`에 기존 팔각 링·공유 부품 방식으로 새 조립체 생성. 기존 R1 전체 폴더 및 KiCad PCB SHA-256 불변 확인.
- 기존 V2 RGB 적용: PCB(0.04,0.35,0.16), 프레임(0.30,0.32,0.36). 색상 있는 STEP를 Creo 단품으로 가져와 저장 후 새 세션 재조회·AP214 재내보내기에서 실제 솔리드의 색상 연결 확인.
- 상하 팔각 링 2개, 대변 거리 외측265/내측231 mm, 두께8 mm, 각 슬롯84.6×2.2 mm×8면. 고정 구멍Ø3.2×16개/링을 PCB 기존 4개 고정 구멍에 정렬. 링 중심 Z±101, 열린 높이194 mm. 발진면210 mm 및 인접 PCB 틈12.325 mm 유지. 외형265×265×224 mm(체결 부품 제외).
- 링/기판·부품 간 형상 교차체적0건, STEP1194솔리드, Creo 새 세션 11단품/149·10조립구성/배치행렬/고정상태/단위·외형과 네이티브 STEP 외형·체적·실제색상 검증. GUI 캡처 대신 Creo API 및 STEP 재내보내기를 근거로 사용. 미리보기/단품STEP/드릴축CSV/사용안내/검증기록/모델ZIP 제공.
- 재질·공구 코너 여유·가공 및 프린팅 공차·실제 체결 길이/토크·구조 강도는 미확정. 회전 카메라/케이블/베어링/구동부 미포함이며 전체 물체 촬영 및 음향/실물 성능은 미검증.
'''
text=status.read_text(encoding='utf-8')
if heading not in text:status.write_text(text+entry,encoding='utf-8')
print('PASS: native geometry/colors, R1 preservation, frame clearance, archive CRC and hashes.')
