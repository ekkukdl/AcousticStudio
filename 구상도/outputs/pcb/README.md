# PCB 설계 및 업체 제출 자료

## 현재 8면 8기판 32채널 구성

현재 개발 기준은 한 기판 32채널, 같은 기판 8장, 총 256송신기입니다. [32채널 PCB R1 제작 자료](../panel_8faces_32ch_R1/README.md)와 [프레임 포함 Creo R2](../panel_8faces_32ch_R1/mechanical/creo32_frame_R2/사용안내.md)를 사용하세요. 아래 16채널 기판 16장의 업체 제출 자료는 이전 구성으로 보존한 것입니다.

## 이전 8면 16기판 요청

한 기판 16채널, 동일 기판 총 16장, 송신기 총 256개 구성입니다.

- [전체 납땜 요청 안내](polygon_panels/pcba_8faces_16boards/README_업로드_및_납땜요청.md)
- [DOILLABS 업로드 사용 안내](polygon_panels/pcba_8faces_16boards/DOILLABS/사용안내.txt)
- [업로드 BOM CSV](polygon_panels/pcba_8faces_16boards/DOILLABS/DOILLABS_BOM_8faces_16ch_UPLOAD.csv)
- [업로드 PnP CSV](polygon_panels/pcba_8faces_16boards/DOILLABS/DOILLABS_PnP_8faces_16ch_UPLOAD.csv)
- [업로드 BOM XLSX](polygon_panels/pcba_8faces_16boards/DOILLABS/DOILLABS_BOM_8faces_16ch_UPLOAD.xlsx)
- [업로드 PnP XLSX](polygon_panels/pcba_8faces_16boards/DOILLABS/DOILLABS_PnP_8faces_16ch_UPLOAD.xlsx)
- [8면용 Gerber ZIP](polygon_panels/pcba_8faces_16boards/panel_8faces_16ch_Gerber_P0_quote.zip)

DOILLABS에는 안내에 따라 `*_UPLOAD` 파일을 사용하세요. CSV와 같은 내용의 XLSX를 중복 제출하지 마세요. 접미사 없는 기존 XLSX와 기존 견적 ZIP은 이전 작성본으로 보존했으며 최신 UPLOAD 파일을 포함한다고 간주하지 마세요. 초음파 송신기 등 THT는 별도 수삽 작업으로 요청해야 합니다.

## KiCad 원본과 초기안

- [6면용 기판 원본](polygon_panels/panel_6faces_16ch/)
- [8면용 기판 원본](polygon_panels/panel_8faces_16ch/)
- [설계 설명](polygon_panels/설계설명_및_확인방법.md)
- [초기 Gerber ZIP](polygon_panels/gerber_quotes/)
- [초기 부품 견적](polygon_panels/부품견적_6면_8면.md)
- [초기 제조 및 추가 구매품 견적](polygon_panels/제작및추가부품견적_센서제외.md)

KiCad 프로젝트와 전용 심볼·풋프린트·3D 모델은 함께 보존했습니다. 기존 견적은 6면 6장 / 8면 8장 기준입니다. 현재 P0 자료의 간격 경고와 부품 방향 검토는 제조 승인 전에 필요합니다.
