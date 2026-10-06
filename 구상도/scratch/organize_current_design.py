"""Copy current deliverables into the user-requested workspace-root folder."""
from pathlib import Path
import shutil,json,hashlib,re
project=Path(__file__).resolve().parents[2]
workspace=project.parents[1]
source=project/'구상도/outputs/panel_8faces_32ch_R1'
model=source/'mechanical/creo32_frame_R2'
dest=workspace/'8면_256채널_PCB_프레임_2026-10-06'
assert workspace.name=='제개설'
dest.mkdir(exist_ok=False)
pcb=dest/'01_PCB_KiCad10';creo=dest/'02_Creo_프레임포함';preview=dest/'03_미리보기'
for p in (pcb,creo,preview):p.mkdir()
records=[]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def copy(src,target):
 target.parent.mkdir(parents=True,exist_ok=True)
 before=digest(src);shutil.copy2(src,target)
 assert digest(target)==before and digest(src)==before,str(src)
 records.append({'source':str(src),'destination':str(target.relative_to(dest)),'sha256':before})
for p in source.rglob('*'):
 if not p.is_file():continue
 rel=p.relative_to(source)
 if rel.parts[:2] in [('mechanical','creo32_R1'),('mechanical','creo32_frame_R2')]:continue
 if p.name in ('README.md','SHA256.json','Design_R1_complete.zip') or p.suffix in ('.kicad_prl','.lck'):continue
 copy(p,pcb/rel)
for p in model.rglob('*'):
 if p.is_file() and p.suffix not in ('.zip','.lck'):copy(p,creo/p.relative_to(model))
for p in ['schematic_preview.png','pcb_top.png','pcb_bottom.png','geometry_preview.png']:
 copy(source/p,preview/p)
for p in ['panel32_model_preview.png','tunnel8_model_preview.png']:copy(model/p,preview/p)
# Preserve the source explanatory README with links adapted to this layout.
text=(source/'README.md').read_text(encoding='utf-8')
text=text.replace('mechanical/creo32_frame_R2/Creo32_frame_R2_models.zip','../02_Creo_프레임포함/사용안내.md')
text=text.replace('mechanical/creo32_frame_R2','../02_Creo_프레임포함')
text=text.replace('[모델 ZIP]','[모델 폴더 안내]').replace('Design_R1_complete.zip','원본 위치의 Design_R1_complete.zip')
(pcb/'README.md').write_text(text,encoding='utf-8')
readme='''# 8면 256채널 PCB 및 외부 프레임

2026-10-06 제작분을 모은 독립 복사본입니다. 원본은 AcousticStudio_ver2/구상도/outputs/panel_8faces_32ch_R1에 보존했습니다.

## 바로 열기

- [KiCad 10 프로젝트](01_PCB_KiCad10/panel_8faces_32ch_R1.kicad_pro)
- [회로도](01_PCB_KiCad10/panel_8faces_32ch_R1.kicad_sch)
- [PCB 배치/배선](01_PCB_KiCad10/panel_8faces_32ch_R1.kicad_pcb)
- [프레임 포함 전체 Creo 조립체](02_Creo_프레임포함/native/tunnel8_32_r2.asm)
- [전체 STEP](02_Creo_프레임포함/geometry/tunnel8_32_r2.step)
- [전체 모델 미리보기](03_미리보기/tunnel8_model_preview.png)

## 폴더 구성

| 폴더 | 내용 |
|---|---|
| 01_PCB_KiCad10 | 32채널 R1 회로도·PCB·프로젝트, 로컬 심볼/풋프린트/3D 모델, Gerber/드릴, BOM/실장 좌표, 채널 맵, 설계/검증 자료 |
| 02_Creo_프레임포함 | 진녹색 PCB와 회색 상하 링을 포함한 R2 모델. native에 모든 참조 PRT/ASM, geometry에 STEP, validation에 검증 기록 |
| 03_미리보기 | 회로도·PCB 앞뒤·배열·기판 모델·전체 조립체 이미지 |

KiCad 프로젝트와 로컬 라이브러리는 폴더 구조를 유지해 사용하세요. Creo에서는 `02_Creo_프레임포함/native`를 작업 디렉터리로 지정하세요. ASM만 따로 옮기면 참조 PRT가 누락됩니다. 상하 링은 동일 단품을 2회 사용합니다.

면당 4×8=32개, 8면 총 256개. PCB 84×224×1.6 mm, 발진면 간격 210 mm, 프레임 포함 외형 265×265×224 mm입니다. 이전 R1 프레임 없는 Creo 버전은 이 폴더에 섞지 않았습니다. 중복 전체 ZIP과 프로그램 임시 설정 파일도 제외했습니다.

파일 복사마다 원본과 복사본의 SHA-256 일치를 확인했습니다. `정리_검증.json`에 원본 위치 및 복사 기록, `SHA256.json`에 새 폴더 전체 파일의 해시를 기록했습니다. 이번 확인은 파일 보존 및 로컬 참조 대상 존재 확인이며 회로/기구의 추가 성능 검증은 아닙니다. 기존 제작·촬영·공차 관련 한계는 [PCB 검토](01_PCB_KiCad10/DESIGN_REVIEW.md)와 [Creo 사용안내](02_Creo_프레임포함/사용안내.md)를 참고하세요.
'''
(dest/'읽어주세요.md').write_text(readme,encoding='utf-8')
# Every project-local KiCad library/model resolves inside the copied project.
refs=[]
for f in ('fp-lib-table','sym-lib-table','panel_8faces_32ch_R1.kicad_pcb'):
 for rel in re.findall(r'\$\{KIPRJMOD\}/([^"\r\n]+)',(pcb/f).read_text(encoding='utf-8')):
  assert (pcb/rel).exists(),rel
  refs.append(rel)
native=list((creo/'native').iterdir());assert sum(p.suffix=='.prt' for p in native)==11 and sum(p.suffix=='.asm' for p in native)==2
for name in ('native_build_report.json','native_reopen_report.json'):
 report=json.loads((creo/'validation'/name).read_text(encoding='utf-8'));assert report['ok']
 for c in report['panelComponents']+report['tunnelComponents']:assert (creo/'native'/c['model']).is_file(),c['model']
# Validate all newly written Markdown links, including the adapted PCB README.
for f in (dest/'읽어주세요.md',pcb/'README.md',creo/'사용안내.md'):
 for target in re.findall(r'\]\(([^)]+)\)',f.read_text(encoding='utf-8')):
  if '://' not in target and not target.startswith('#'):assert (f.parent/target).exists(),(str(f),target)
(dest/'정리_검증.json').write_text(json.dumps({'ok':True,'operation':'copy','original_files_preserved':True,'copied_files':records,'KiCad_local_references_verified':sorted(set(refs)),'Creo_native_parts':11,'Creo_native_assemblies':2,'Creo_reference_files_present':True},ensure_ascii=False,indent=2),encoding='utf-8')
hashes={str(p.relative_to(dest)):digest(p) for p in dest.rglob('*') if p.is_file() and p.name!='SHA256.json'}
(dest/'SHA256.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2),encoding='utf-8')
assert all(digest(dest/name)==sha for name,sha in hashes.items())
status=project/'docs/project_status.txt'
with status.open('a',encoding='utf-8') as f:f.write('\n\n### 2026-10-06 최신 제작분 최상위 폴더 정리\n- 사용자 요청으로 제개설/8면_256채널_PCB_프레임_2026-10-06에 PCB KiCad10/프레임 포함 Creo R2/미리보기 3개 폴더로 독립 복사. 기존 파일 보존. 로컬 라이브러리/3D 모델 및 모든 Creo PRT/ASM 참조 포함. 이전 프레임 없는 Creo 버전과 중복 전체 ZIP 제외.\n- 복사 파일별 SHA-256 일치, KiCad 로컬 참조 존재, Creo 참조 파일 존재, 안내 Markdown 링크 및 정리 폴더 SHA256 확인. 추가 CAD/회로 재실행이나 실물 성능 검증은 수행하지 않음.\n')
print(json.dumps({'folder':str(dest),'copied_files':len(records),'total_files':len(hashes)+1,'verification':'PASS'},ensure_ascii=False))
