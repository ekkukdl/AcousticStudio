// Concept envelope, not an external frame design. Dimensions in mm.
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
