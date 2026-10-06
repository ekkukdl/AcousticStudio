from pathlib import Path
import json,shutil,hashlib

workspace=Path(__file__).resolve().parents[3]
repo=workspace/'AcousticStudio'
dest=repo/'구상도/creo_tunnel'
single=dest/'v1_single_panel'
dual=dest/'v2_dual_panel'

def copy_file(source,target):
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists() and target.read_bytes()!=source.read_bytes():
        raise RuntimeError(f'Refusing to overwrite different existing file: {target}')
    shutil.copy2(source,target)
    assert hashlib.sha256(source.read_bytes()).digest()==hashlib.sha256(target.read_bytes()).digest()

source=workspace/'outputs/cad_generation/creo_tunnel_models'
for n in (6,8):
    folder=source/f'{n}faces'
    for f in folder.rglob('*'):
        if f.is_file() and f.suffix.lower() in {'.prt','.asm','.step','.json','.png'}:
            copy_file(f,single/f'{n}faces'/f.relative_to(folder))
for name in ('사용안내.md','pcb_geometry.json','native_generation_report.json','native_reopen_report.json'):
    copy_file(source/name,single/name)

source=workspace/'outputs/cad_generation/creo_tunnel_reused_v2'
for name in ('native','geometry'):
    for f in (source/name).rglob('*'):
        if f.is_file():copy_file(f,dual/name/f.relative_to(source/name))
for name in ('사용안내.md','preview_6f.png','preview_8f.png','native_build_report.json','native_reopen_report.json'):
    copy_file(source/name,dual/name)
# Coordinate source accompanies both revisions without relying on files outside Git.
copy_file(workspace/'outputs/cad_generation/creo_tunnel_models/pcb_geometry.json',dual/'pcb_geometry.json')

index='''# 초음파 부양 터널 Creo 모델

Creo Parametric 9.0.12.0에서 저장한 모델입니다. 길이 단위는 mm(mmNs)입니다.

## 최신 모델 열기

Creo 작업 폴더를 **`v2_dual_panel/native`**로 지정한 뒤 다음 조립품을 엽니다. ASM과 참조 PRT는 같은 폴더에 함께 보관해야 합니다.

- [8면 · 각 면에 PCB 두 장](v2_dual_panel/native/tunnel_8f_dual.asm)
- [6면 · 공통 패널 참조 구조](v2_dual_panel/native/tunnel_6f_v2.asm)
- [한 면의 PCB 두 장과 촬영 틈](v2_dual_panel/native/facepair_8f.asm)
- [최신 모델 사용 안내](v2_dual_panel/사용안내.md)

![8면 최신 모델](v2_dual_panel/preview_8f.png)

## 버전 구분

| 폴더 | 6면 | 8면 |
|---|---|---|
| `v1_single_panel` | 면당 PCB 1장, 총 6장·96개 | 면당 PCB 1장, 총 8장·128개 |
| `v2_dual_panel` | 치수 유지, 공통 패널 ASM 재사용 | 면당 PCB 2장, 총 16장·256개, 중앙 촬영 틈 20 mm |

6면 PCB는 60×180×1.6 mm, 8면 PCB는 48×180×1.6 mm입니다. 최신 8면은 각 면이 45° 간격인 정팔각형 배치이며, 마주 보는 방사면 간 거리는 300 mm, 전체 외곽은 약 355×355×180 mm입니다. 최신 두 조립품이 공유하는 네이티브 파일 종류는 총 10개입니다.

최신 8면은 `facepair_8f.asm` 하나를 8번 참조하고, 각 면은 `panel_8f.asm` 하나를 두 번 참조합니다. 동일한 PCB, 트랜스듀서 및 프레임 링도 공통 PRT를 참조합니다.

## 함께 보관한 자료

- `native`: 실제 Creo PRT/ASM. 재저장 시 붙는 `.1`, `.2` 등은 Creo 버전 번호입니다.
- `geometry`: 최신 모델의 STEP 형상 및 배치·간섭 검사 기록.
- `pcb_geometry.json`: 기존 KiCad PCB에서 추출한 외곽 치수, 관통 구멍 및 트랜스듀서 좌표.
- `native_*report.json`: Creo 저장 및 새 세션에서 다시 열어 확인한 기록.
- `preview_*.png`: STEP 형상을 렌더링한 미리보기이며 Creo 화면 캡처는 아닙니다.
- `manifest.json`: 이 폴더에 정리된 파일의 SHA-256과 크기.

초기 모델의 STEP과 미리보기는 각 `6faces`, `8faces` 폴더에 있습니다. 기존 `구상도/ver1`~`ver4`는 별도의 기존 사용자 모델입니다.

## 검증 범위

원본과 정리된 파일의 SHA-256 일치, 네이티브 참조 파일의 완비 및 mm 치수 정보를 확인했습니다. 최신 모델은 생성 당시 Creo 9에서 다시 열어 치수·반복 참조·배치 행렬·Fix 구속을 확인했고, 포함된 솔리드의 체적 간섭 검사도 수행했습니다.

PCB와 트랜스듀서는 가져온 솔리드이므로 스케치·돌출 피처 이력은 없습니다. 나사·브래킷·전자 부품·핀·배선은 생략되어 있습니다. 촬영 성능과 실제 부양 성능은 아직 검증하지 않았으며, 최신 8면은 넓어진 간격과 256채널 좌표로 음향 시뮬레이션 및 실험이 필요합니다.
'''
(dest/'README.md').write_text(index,encoding='utf-8')
# Remove only obsolete output-folder paths from the copied guide; retain the source report evidence.
guide=single/'사용안내.md'
text=guide.read_text(encoding='utf-8')
text=text.replace('`outputs/pcb/polygon_panels/panel_6faces_16ch/panel_6faces_16ch.kicad_pcb`와 8면에 대응하는 파일입니다.','원래 자료조사 작업 폴더의 `outputs/pcb/polygon_panels/panel_6faces_16ch/panel_6faces_16ch.kicad_pcb`와 8면에 대응하는 파일입니다. 이 저장소에 포함된 좌표 추출본은 `pcb_geometry.json`입니다.')
guide.write_text(text,encoding='utf-8')
files=[p for p in dest.rglob('*') if p.is_file() and p.name!='manifest.json']
manifest={p.relative_to(dest).as_posix():{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(files)}
(dest/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')

status=repo/'docs/project_status.txt'
entry='''

### 2026-10-05 Creo 부양 터널 모델 정리
- `구상도/creo_tunnel`에 초기 단일 패널 모델과 최신 공유 참조 모델을 분리해 보관. 기존 `구상도/ver1`~`ver4`는 변경하지 않음.
- 최신 6면: 60×180×1.6 mm PCB 6장, 트랜스듀서 96개. 기존 배치를 유지하며 공통 패널 ASM 재사용.
- 최신 8면: 정팔각형의 각 면에 48×180×1.6 mm PCB 2장, 중앙 틈 20 mm. PCB 총 16장·트랜스듀서 256개, 방사면 간 거리 300 mm, 외곽 약 355×355×180 mm.
- PCB/트랜스듀서/링 PRT, 패널/면 ASM을 공유하는 네이티브 파일 10개 및 STEP, 미리보기, 검증 기록, 사용 안내, SHA-256 목록을 정리.
- 이번 정리 검증: 원본 복사 파일의 SHA-256 일치, ASM 참조 파일 완비, 안내 문서 링크 및 UTF-8 확인. 앞선 생성 작업에서 수행한 Creo 9 재열기·mm 치수·반복 참조·배치·Fix 구속과 솔리드 간섭 검증 기록을 포함. 앱 실행 및 추가 부양 실험은 수행하지 않음.
- 남은 작업: 새 256채널 배치의 음향 시뮬레이션과 부양 실험, 실제 고정구·배선·부품 공차 확정. 3D 형상 확인을 부양 성능 검증으로 해석하지 않음.
'''
with status.open('a',encoding='utf-8',newline='') as f:f.write(entry.replace('\n','\r\n'))
print(json.dumps({'copiedFiles':len(files),'nativeV2':len(list((dual/'native').iterdir())),'bytes':sum(p.stat().st_size for p in files)},indent=2))
