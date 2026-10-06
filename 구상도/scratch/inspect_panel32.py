from pathlib import Path
import pcbnew

root = Path(__file__).resolve().parents[1]
b = pcbnew.LoadBoard(str(root / 'outputs/polygon_panels/panel_8faces_16ch/panel_8faces_16ch.kicad_pcb'))
for f in b.GetFootprints():
    if f.GetReference() in ('T1','T2','J1','J2','C19'):
        print(f.GetReference(),pcbnew.ToMM(f.GetPosition().x),pcbnew.ToMM(f.GetPosition().y),str(f.GetPath()))
ts=list(b.GetTracks())
print('tracksXY',min(pcbnew.ToMM(t.GetStart().x) for t in ts),max(pcbnew.ToMM(t.GetStart().x) for t in ts),min(pcbnew.ToMM(t.GetStart().y) for t in ts),max(pcbnew.ToMM(t.GetStart().y) for t in ts))
print('UUID', [x for x in dir(pcbnew) if 'KIID' in x])
print('zone',[x for x in dir(pcbnew.ZONE) if 'Keep' in x or 'Allowed' in x or 'Rule' in x])
print('fp',[x for x in dir(pcbnew.FOOTPRINT) if 'Path' in x or 'Uuid' in x or 'Property' in x])
print('dup',type(next(iter(b.GetFootprints())).Duplicate(False)))
print('path',dir(pcbnew.KIID_PATH))
print('zonekeep',[x for x in dir(pcbnew.ZONE) if 'Allow' in x or 'Keepout' in x or 'DoNot' in x])
print('pad',[x for x in dir(pcbnew.PAD) if 'Property' in x or 'Uuid' in x])
