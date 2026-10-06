// CONCEPT ONLY. No manufacturing approval, mounting hardware or PCB copper.
// Coordinates: tunnel axis Z; inward acoustic normals; channel p*32+c*8+j.
face_diameter = 100;
active_length = 160;
gap_arc_at_face = 8;
emitter_diameter = 16;
emitter_body_height = 12.5;
frame_thickness = 2;
seat_clearance = 0.4;
show_emitters = true;
show_ideal_flex_reference = false; // Smooth surface ONLY; real pads need flat stiffened islands.
$fn = 64;
R = face_diameter/2;
rear_R = R + emitter_body_height;
half_gap_deg = gap_arc_at_face/(2*R)*180/PI;
span_deg = 90 - 2*half_gap_deg;
module sector(r1,r2,p) {
  rotate([0,0,p*90+half_gap_deg])
    rotate_extrude(angle=span_deg,convexity=10)
      translate([r1,0]) square([r2-r1,active_length]);
}
module radial_body(a,z,r,d,h) {
  translate([r*cos(a),r*sin(a),z]) rotate([0,0,a]) rotate([0,90,0]) cylinder(d=d,h=h);
}
for (p=[0:3]) {
  color([0.55,0.60,0.65]) difference() {
    sector(rear_R-frame_thickness,rear_R,p);
    for(c=[0:3],j=[0:7])
      radial_body(p*90+half_gap_deg+(c+0.5)*span_deg/4,
        (j+0.5)*active_length/8,R-1,emitter_diameter+seat_clearance,emitter_body_height+3);
  }
  if(show_emitters) for(c=[0:3],j=[0:7]) {
    a=p*90+half_gap_deg+(c+0.5)*span_deg/4;
    z=(j+0.5)*active_length/8;
    color([0.76,0.77,0.78]) radial_body(a,z,R,emitter_diameter,emitter_body_height);
    color([0.86,0.69,0.30]) radial_body(a,z,R-0.05,emitter_diameter-1,0.1);
  }
  if(show_ideal_flex_reference) color([0.9,0.45,0.1,0.35]) sector(rear_R,rear_R+0.2,p);
}
