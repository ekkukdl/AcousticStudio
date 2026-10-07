"""Compile the untouched original Kinoforms with minimal adapters; no Java app/GPU.

The adapters supply T2-compatible point-source propagation, entities and math.
This verifies the original virtual-point construction and iterate(true), not
the Ultraino renderer or its full acoustic/material environment.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'src'))
from acousticstudio.field_model import FieldConfig
from acousticstudio.hologram import HologramSettings, HologramSolver, JAVA_TO_STUDIO, TrapTarget

STUBS = {
    'acousticfield3d/math/M.java': '''package acousticfield3d.math;
public class M { public static final float PI=(float)Math.PI,TWO_PI=2*PI;
public static float cos(float x){return (float)Math.cos(x);} public static float sin(float x){return (float)Math.sin(x);}
public static float sqrt(float x){return (float)Math.sqrt(x);} public static float max(float a,float b){return Math.max(a,b);} }''',
    'acousticfield3d/math/Vector2f.java': '''package acousticfield3d.math;
public class Vector2f { public float x,y; public Vector2f(){} public Vector2f(float a,float b){x=a;y=b;}
public Vector2f setAngle(float a){x=M.cos(a);y=M.sin(a);return this;} public Vector2f multLocal(float a){x*=a;y*=a;return this;}
public float length(){return M.sqrt(x*x+y*y);} public float getAngle(){return (float)Math.atan2(y,x);} }''',
    'acousticfield3d/math/Vector3f.java': '''package acousticfield3d.math;
public class Vector3f { public float x,y,z; public Vector3f(float a,float b,float c){x=a;y=b;z=c;} }''',
    'acousticfield3d/scene/Entity.java': '''package acousticfield3d.scene;
import acousticfield3d.math.Vector3f;
public class Entity { public final Transform transform; public int color;
public Entity(float x,float y,float z,int c){transform=new Transform(x,y,z);color=c;}
public Transform getTransform(){return transform;} public int getRealColor(){return color;}
public static class Transform { final Vector3f p; public Transform(float x,float y,float z){p=new Vector3f(x,y,z);}
public Vector3f getTranslation(){return p;} } }''',
    'acousticfield3d/simulation/Transducer.java': '''package acousticfield3d.simulation;
import acousticfield3d.scene.Entity; import acousticfield3d.math.M;
public class Transducer extends Entity { float amplitude=1,phase;
public Transducer(float x,float y,float z,float radians){super(x,y,z,0);phase=radians/M.PI;}
public float getpAmplitude(){return amplitude;} public float getPhase(){return phase;}
public void setpAmplitude(float a){amplitude=a;} public void setPhase(float p){phase=p;} }''',
    'acousticfield3d/simulation/Simulation.java': '''package acousticfield3d.simulation;
import java.util.ArrayList; import java.util.List;
public class Simulation { public final List<Transducer> transducers=new ArrayList<>();
public float getWavelenght(){return 343f/40000f;} }''',
    'acousticfield3d/gui/MainForm.java': '''package acousticfield3d.gui;
import acousticfield3d.simulation.Simulation;
public class MainForm { public final Simulation simulation=new Simulation(); public Simulation getSimulation(){return simulation;} }''',
    'acousticfield3d/utils/Color.java': '''package acousticfield3d.utils;
public class Color { public static int red(int c){return (c>>>16)&255;} public static int green(int c){return (c>>>8)&255;}
public static int blue(int c){return c&255;} }''',
    'acousticfield3d/algorithms/CalcField.java': '''package acousticfield3d.algorithms;
import acousticfield3d.math.*; import acousticfield3d.simulation.*;
public class CalcField { public static Vector2f calcFieldForTrans(Transducer t,float phase,float x,float y,float z,Simulation s){
Vector3f p=t.getTransform().getTranslation(); double dx=(double)x-p.x,dy=(double)y-p.y,dz=(double)z-p.z;
double r=Math.sqrt(dx*dx+dy*dy+dz*dz),k=2*Math.PI/(343.0/40000.0);
return new Vector2f((float)(Math.cos(k*r)/r),(float)(Math.sin(k*r)/r));} }''',
    'acousticfield3d/algorithms/KinoProbe.java': '''package acousticfield3d.algorithms;
import java.util.*; import acousticfield3d.gui.MainForm; import acousticfield3d.scene.Entity; import acousticfield3d.simulation.Transducer;
public class KinoProbe { public static void main(String[] args) {
String[] names={"focus","twin","standing_wave"}; int[] colors={0xffffff,64<<8,0};
float[][] sources={{-.02f,-.04f,.02f},{.02f,-.04f,.02f},{-.02f,.04f,-.02f},{.02f,.04f,-.02f}};
float[] phases={.2f,.9f,2.4f,3.2f};
for(int kind=0;kind<3;kind++){ MainForm mf=new MainForm();
for(int i=0;i<4;i++)mf.simulation.transducers.add(new Transducer(sources[i][0],sources[i][1],sources[i][2],phases[i]));
List<Entity> targets=Arrays.asList(new Entity(-.006f,0,0,colors[kind]),new Entity(.006f,.002f,-.001f,colors[kind]));
Kinoforms solver=new Kinoforms(mf,mf.simulation.transducers,targets);
for(int i=0;i<12;i++)solver.iterate(true); solver.applySolution();
System.out.print("{\\\"trap_type\\\":\\\""+names[kind]+"\\\",\\\"virtual_count\\\":"+solver.P+",\\\"phases_rad\\\":[");
for(int i=0;i<4;i++){if(i>0)System.out.print(",");System.out.print(mf.simulation.transducers.get(i).getPhase()*acousticfield3d.math.M.PI);}
System.out.println("]}"); } } }''',
}


def main():
    original = REPO.parent / 'simulations/Ultraino/AcousticFieldSim/src/acousticfield3d/algorithms/Kinoforms.java'
    java_version = subprocess.run(['java', '-version'], capture_output=True, text=True, check=True).stderr.splitlines()[0]
    with TemporaryDirectory(prefix='t4_java_', dir=Path(__file__).parent) as temporary:
        root = Path(temporary).resolve()
        assert root.parent == Path(__file__).resolve().parent  # cleanup stays inside this task's scratch directory
        for name, content in STUBS.items():
            target = root / name; target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding='utf-8')
        (root / 'acousticfield3d/algorithms/Kinoforms.java').write_bytes(original.read_bytes())
        source_files = sorted(str(path) for path in root.rglob('*.java'))
        subprocess.run(['javac', '-encoding', 'UTF-8', '-d', str(root / 'classes'), *source_files], check=True)
        result = subprocess.run(['java', '-cp', str(root / 'classes'), 'acousticfield3d.algorithms.KinoProbe'],
                                capture_output=True, text=True, check=True)
    rows = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
    sources = np.array([[-20., -20., -40.], [20., -20., -40.], [-20., 20., 40.], [20., 20., 40.]])
    normals = np.tile([0., 0., 1.], (4, 1))
    initial = np.array([.2, .9, 2.4, 3.2])
    settings = HologramSettings(iterations=12, phase_tolerance_rad=0., initialization='current')
    for row in rows:
        trap_type = row['trap_type']
        angle = 64 * 2 * np.pi / 255
        direction = JAVA_TO_STUDIO @ [np.cos(angle), 0., np.sin(angle)] if trap_type == 'twin' else (
            np.array([0., 0., 1.]) if trap_type == 'standing_wave' else np.array([1., 0., 0.]))
        targets = [TrapTarget((-6., 0., 0.), trap_type, direction=tuple(direction)),
                   TrapTarget((6., 1., 2.), trap_type, direction=tuple(direction))]
        actual = HologramSolver().solve(sources, normals, np.ones(4), FieldConfig(), targets, settings, initial_phases=initial)
        expected, observed = np.exp(1j * np.asarray(row['phases_rad'])), np.exp(1j * actual['phases_rad'])
        common = np.angle(np.vdot(expected, observed))
        error = float(np.max(np.abs(observed * np.exp(-1j * common) - expected)))
        assert error < 2e-5, (trap_type, error)
        assert row['virtual_count'] == len(actual['virtual_points_mm'])
        row['phase_phasor_error_after_common_phase'] = error
        row['targets_studio'] = [target.to_dict() for target in targets]
    report = dict(java_version=java_version, original_kinoforms_sha256=hashlib.sha256(original.read_bytes()).hexdigest(),
                  original_source_unchanged=True, iterations=12, source_gains=[1.] * 4,
                  propagation_adapter='T2-compatible point_source, float32 input/output; renderer/material model excluded',
                  comparisons=rows)
    Path(__file__).with_name('t4_java_result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
