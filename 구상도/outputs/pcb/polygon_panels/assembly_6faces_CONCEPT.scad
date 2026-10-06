// CONCEPT assembly. Frame mounting/cable clearance is not final.
faces=6; panel_width=60; board_length=180;
face_apothem=75; body_height=12.5; board_thickness=1.6;
$fn=48;
module polygon_prism(apothem,h) {
  linear_extrude(height=h) polygon([for(i=[0:faces-1])
    [apothem/cos(180/faces)*cos((i+0.5)*360/faces),
     apothem/cos(180/faces)*sin((i+0.5)*360/faces)]]);
}
module end_ring(z) { translate([0,0,z]) difference() {
  polygon_prism(face_apothem+body_height+15,8);
  translate([0,0,-1]) polygon_prism(face_apothem+body_height-2,10);
} }
for(p=[0:faces-1]) rotate([0,0,p*360/faces]) {
  color([0.1,0.4,0.2]) translate([face_apothem+body_height,-panel_width/2,0])
    cube([board_thickness,panel_width,board_length]);
  for(r=[0:7],c=[0:1])
    color([0.7,0.7,0.72]) translate([face_apothem,(c-0.5)*18,20+r*20])
      rotate([0,90,0]) cylinder(d=16,h=body_height);
}
color([0.45,0.48,0.5]) {end_ring(0);end_ring(board_length-8);}
