"""Read-only PCB/netlist comparison; run with KiCad's bundled Python."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import xml.etree.ElementTree as ET
import pcbnew

root = Path(__file__).resolve().parents[1]
dest = root / "outputs/pcb_review_2026-10-06"
summary = {"kicad_version": pcbnew.Version(), "panels": {}}
for faces in (6, 8):
    name = f"panel_{faces}faces_16ch"
    source = root / "outputs/polygon_panels" / name
    pcb_path = source / f"{name}.kicad_pcb"
    board = pcbnew.LoadBoard(str(pcb_path))
    sch = ET.parse(dest / f"netlist_{faces}f.xml").getroot()
    sch_pads = {(n.get("ref"), n.get("pin")): net.get("name")
                for net in sch.findall("./nets/net") for n in net.findall("node")}
    pcb_pads = {(fp.GetReference(), pad.GetNumber()): pad.GetNetname()
                for fp in board.GetFootprints() for pad in fp.Pads()
                if pad.GetNetname()}
    differences = [{"pad": key, "sch": sch_pads.get(key), "pcb": pcb_pads.get(key)}
                   for key in sorted(sch_pads.keys() | pcb_pads.keys())
                   if sch_pads.get(key) != pcb_pads.get(key)]
    parts = [{"ref": fp.GetReference(), "value": fp.GetValue(),
              "side": board.GetLayerName(fp.GetLayer()),
              "x_mm": pcbnew.ToMM(fp.GetPosition().x),
              "y_mm": pcbnew.ToMM(fp.GetPosition().y),
              "smd": bool(fp.GetAttributes() & pcbnew.FP_SMD)}
             for fp in board.GetFootprints() if not fp.GetReference().startswith("H")]
    tracks = [t for t in board.GetTracks() if not isinstance(t, pcbnew.PCB_VIA)]
    nets = {net.get("name"): [{"ref": n.get("ref"), "pin": n.get("pin")}
                              for n in net.findall("node")]
            for net in sch.findall("./nets/net")}
    item = {"source_sha256": hashlib.sha256(pcb_path.read_bytes()).hexdigest(),
            "connected_pads": len(pcb_pads), "net_differences": differences,
            "electrical_parts": len(parts), "smd_parts": sum(p["smd"] for p in parts),
            "parts_by_side": dict(Counter(p["side"] for p in parts)),
            "tracks": len(tracks),
            "vias": sum(isinstance(t, pcbnew.PCB_VIA) for t in board.GetTracks()),
            "minimum_track_width_mm": min(pcbnew.ToMM(t.GetWidth()) for t in tracks),
            "parts": parts, "nets": nets}
    for kind in ("ERC", "DRC"):
        report = json.loads((dest / f"{kind}_{faces}f.json").read_text(encoding="utf-8"))
        item[kind] = {k: report[k] for k in ("violations", "unconnected_items", "schematic_parity", "ignored_checks") if k in report}
    summary["panels"][str(faces)] = item

quote_info = json.loads((root / "outputs/polygon_panels/pcba_8faces_16boards/validation_and_sources.json").read_text(encoding="utf-8"))
summary["quotation_hash_matches"] = {
    rel: hashlib.sha256((root / rel).read_bytes()).hexdigest() == expected
    for rel, expected in quote_info["source_hashes"].items()
}
(dest / "connectivity_review.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
for faces, item in summary["panels"].items():
    print(faces, json.dumps({k: item[k] for k in ("connected_pads", "net_differences", "electrical_parts", "smd_parts", "parts_by_side", "tracks", "vias", "minimum_track_width_mm")}))
print("quotation hashes", summary["quotation_hash_matches"])
