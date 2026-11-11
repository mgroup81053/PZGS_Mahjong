/* 손탁 중앙 정렬판 — 130mm 시제품, 방위 표시 포함
본체 노랑 / 주사위 바닥 녹색. part에서 색상별 부품을 선택해 같은 좌표로 내보내세요.
단위 mm. 리치봉 홈 80 x 12 x 깊이 3, 바닥 패드 홈 없음.
東: 빨간 바탕 / 검정 글자, 南西北: 짙은 회색 바탕 / 옅은 회색 글자.
표시를 윗면과 같은 높이의 인레이로 구성. 출력 시 다색 재료 또는 도색 필요.
STL은 색상 정보를 저장하지 않음. part 선택으로 같은 원점의 부품을 내보낼 수 있음.
별도 접착 조립용 공차는 넣지 않았으며 다색 출력/도색을 위한 설계임.
글자 윤곽이 내장되어 폰트 설치 불필요. Noto Sans CJK KR Bold (SIL OFL) 윤곽 사용.
*/
/* [기본 치수 / mm] */
// 전체 가로·세로
side = 130;
// 전체 높이
height = 8;
// 외곽 모서리 반경. 정렬 직선 구간 120mm
corner_radius = 5;
// 주사위 트레이 내부 가로·세로
tray_size = 96;
// 주사위 트레이 바닥 두께. 기본 트레이 깊이 5.6mm
floor_thickness = 2.4;
// 트레이 내부 모서리 반경
tray_radius = 10;

/* [표시용 얕은 홈] */
label_recesses = true;
label_depth = 3.0;
dealer_width = 80;
dealer_length = 12;
wind_width = 26;
wind_length = 8;

/* [바닥 패드 홈] */
pad_recesses = false;
pad_diameter = 10.4;
pad_depth = 0.5;
pad_inset = 12;

/* [방위 표시] */
// 각 자리에서 왼쪽 아래. 아래 東, 오른쪽 南, 위 西, 왼쪽 北.
// assembled: 색상 미리보기. 나머지는 동일 원점의 다색 출력용 부품.
part = "assembled"; // [assembled,body,tray,east_background,other_backgrounds,east_letter,other_letters,backgrounds,letters]
// 녹색 주사위 바닥 표면층 두께
tray_color_depth = 0.6;
badge_size = dealer_length * 1.5;
// 중앙을 향하는 모서리의 둥근 처리 반경
badge_inner_radius = 3;
badge_depth = 1;
letter_depth = 0.6;
letter_size = 10;

/* [Hidden] */
$fn = 64;
eps = 0.02;
rim = (side - tray_size)/2;
label_y = tray_size/2 + rim/2;

assert(side > 0 && height > 0);
assert(corner_radius > 0 && corner_radius < side/2);
assert(tray_radius > 0 && tray_radius < tray_size/2);
assert(tray_size > 0 && rim >= 3, "트레이 주변 벽 두께는 최소 3mm로 설정하세요.");
assert(floor_thickness >= 1.2 && floor_thickness < height);
assert(side - 2*corner_radius >= 120, "정렬 직선 구간은 120mm 이상으로 설정하세요.");
assert(!label_recesses || (rim >= 16 && label_depth > 0 && label_depth < height-1));
assert(!label_recesses || (dealer_length <= rim-4 && wind_length <= rim-4));
assert(!label_recesses || (dealer_width <= tray_size-4 && wind_width <= tray_size/2-10));
assert(!pad_recesses || (pad_depth > 0 && pad_depth < floor_thickness));
assert(!pad_recesses || (pad_inset > corner_radius+pad_diameter/2 && pad_inset < side/2-pad_diameter/2));

module rounded_rect(w, d, r) {
    hull()
        for (x=[-1,1], y=[-1,1])
            translate([x*(w/2-r), y*(d/2-r)])
                circle(r=r);
}

module shallow_slot(w,d) {
    translate([0,0,height-label_depth])
        linear_extrude(height=label_depth+eps)
            rounded_rect(w,d,1);
}

module center_body() {
    difference() {
        linear_extrude(height=height)
            rounded_rect(side,side,corner_radius);
        translate([0,0,floor_thickness-tray_color_depth])
            linear_extrude(height=height-floor_thickness+tray_color_depth+eps)
                rounded_rect(tray_size,tray_size,tray_radius);
        if (label_recesses) {
            for (a=[0,90,180,270])
                rotate([0,0,a])
                    translate([0,label_y,0])
                        shallow_slot(dealer_width,dealer_length);
            // 동/남 표식은 친 표시 홈과 겹치지 않게 한쪽으로 배치
            /*translate([tray_size/2-wind_width/2,label_y,0])
                shallow_slot(wind_width,wind_length);*/
        }
        for (i=[0:3])
            translate([0,0,height-badge_depth])
                linear_extrude(height=badge_depth+eps) badge_shape(i);
        if (pad_recesses)
            for (x=[-1,1], y=[-1,1])
                translate([x*(side/2-pad_inset),y*(side/2-pad_inset),-eps])
                    cylinder(d=pad_diameter,h=pad_depth+eps);
    }
}



// 모서리 여백 0mm. 사각 영역을 판의 외곽으로 잘라 둥근 모서리까지 배경색이 이어집니다.
// x/y 기준점이 같아 판의 대각선에 대해 대칭입니다.
badge_anchor = -side/2;
tray_corner_center = -tray_size/2 + tray_radius;
assert(badge_anchor + badge_size < -dealer_width/2, "방위 표식이 리치봉 홈과 겹칩니다.");
assert(sqrt(2)*abs(badge_anchor + badge_size - tray_corner_center) >= tray_radius,
       "방위 표식이 주사위 트레이와 겹칩니다.");
assert(badge_depth > letter_depth && letter_depth > 0 && badge_depth < height);
assert(letter_size < badge_size-2);
assert(badge_inner_radius > 0 && badge_inner_radius < badge_size/2);

module badge_location(i) {
    rotate([0,0,90*i])
        translate([badge_anchor+badge_size/2,badge_anchor+badge_size/2,0]) children();
}
module badge_shape(i) {
    intersection() {
        rounded_rect(side,side,corner_radius);
        badge_location(i) difference() {
            square([badge_size,badge_size],center=true);
            // 기본 좌하단 표식의 우상단 모서리만 둥글게 처리하고 각 자리로 회전.
            translate([badge_size/2-badge_inner_radius,badge_size/2-badge_inner_radius])
                difference() {
                    square([badge_inner_radius+eps,badge_inner_radius+eps]);
                    circle(r=badge_inner_radius);
                }
        }
    }
}
module glyph(i) {
    scale([letter_size,letter_size]) glyph_outline(i);
}
module letter(i) {
    badge_location(i) translate([0,0,height-letter_depth])
        linear_extrude(height=letter_depth) glyph(i);
}
module background(i) {
    difference() {
        translate([0,0,height-badge_depth])
            linear_extrude(height=badge_depth) badge_shape(i);
        badge_location(i) translate([0,0,height-letter_depth])
            linear_extrude(height=letter_depth+eps) glyph(i);
    }
}
assert(tray_color_depth > 0 && tray_color_depth < floor_thickness);
// 녹색 표면층은 원래 바닥 높이와 일치하며, 아래 본체와 빈틈 없이 맞닿음.
module tray_surface() {
    translate([0,0,floor_thickness-tray_color_depth])
        linear_extrude(height=tray_color_depth)
            rounded_rect(tray_size,tray_size,tray_radius);
}
// 각 색상 부품의 불리언 연산을 먼저 확정하여 F5 미리보기의 동일 평면 잔상을 방지.
// 치수, 부품 경계, 출력용 형상은 변경하지 않습니다.
if (part=="assembled" || part=="body") color([1.0,0.82,0.05]) render(convexity=10) center_body();
if (part=="assembled" || part=="tray") color([0.53,0.72,0.18]) render(convexity=10) tray_surface();
for(i=[0:3]) {
    if(part=="assembled" || part=="backgrounds" || (part=="east_background" && i==0) || (part=="other_backgrounds" && i>0))
        color(i==0 ? [0.82,0.04,0.06] : [0.18,0.19,0.21]) render(convexity=10) background(i);
    if(part=="assembled" || part=="letters" || (part=="east_letter" && i==0) || (part=="other_letters" && i>0))
        color(i==0 ? [0.02,0.02,0.02] : [0.82,0.83,0.85]) render(convexity=10) letter(i);
}

// Embedded normalized CJK outlines, 東 南 西 北
module glyph_outline(i) {
    if(i==0) polygon(points=[[-0.380575, 0.230922], [-0.380575, -0.176082], [-0.165015, -0.176082], [-0.315576, -0.297076], [-0.5, -0.376941], [-0.452015, -0.427073], [-0.412289, -0.483647], [-0.227866, -0.388008], [-0.070862, -0.243641], [-0.070862, -0.496366], [0.061282, -0.496366], [0.061282, -0.238355], [0.220846, -0.388008], [0.409151, -0.485795], [0.449207, -0.426577], [0.5, -0.375785], [0.311282, -0.296498], [0.157417, -0.176082], [0.385861, -0.176082], [0.385861, 0.230922], [0.061282, 0.230922], [0.061282, 0.291212], [0.469277, 0.291212], [0.469277, 0.409647], [0.061282, 0.409647], [0.061282, 0.496366], [-0.070862, 0.496366], [-0.070862, 0.409647], [-0.469442, 0.409647], [-0.469442, 0.291212], [-0.070862, 0.291212], [-0.070862, 0.230922], [-0.256855, -0.016353], [-0.070862, -0.016353], [-0.070862, -0.080938], [-0.256855, -0.080938], [0.061282, -0.016353], [0.255864, -0.016353], [0.255864, -0.080938], [0.061282, -0.080938], [-0.256855, 0.135778], [-0.070862, 0.135778], [-0.070862, 0.072349], [-0.256855, 0.072349], [0.061282, 0.135778], [0.255864, 0.135778], [0.255864, 0.072349], [0.061282, 0.072349]], paths=[[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31], [32, 33, 34, 35], [36, 37, 38, 39], [40, 41, 42, 43], [44, 45, 46, 47]]);
    if(i==1) polygon(points=[[-0.068884, 0.5], [-0.068884, 0.418347], [-0.477487, 0.418347], [-0.477487, 0.297883], [-0.068884, 0.297883], [-0.068884, 0.217238], [-0.436492, 0.217238], [-0.436492, -0.5], [-0.30746, -0.5], [-0.30746, 0.098958], [-0.101142, 0.098958], [-0.199933, 0.069892], [-0.168263, 0.012349], [-0.146169, -0.044019], [-0.240927, -0.044019], [-0.240927, -0.143985], [-0.064516, -0.143985], [-0.064516, -0.215054], [-0.263441, -0.215054], [-0.263441, -0.318212], [-0.064516, -0.318212], [-0.064516, -0.471942], [0.056956, -0.471942], [0.056956, -0.318212], [0.263441, -0.318212], [0.263441, -0.215054], [0.056956, -0.215054], [0.056956, -0.143985], [0.239751, -0.143985], [0.239751, -0.044019], [0.146169, -0.044019], [0.177923, 0.00756], [0.211862, 0.067708], [0.103159, 0.09795], [0.074177, 0.026378], [0.037634, -0.041835], [0.045195, -0.044019], [-0.11828, -0.044019], [-0.036626, -0.017137], [-0.060736, 0.039819], [-0.096774, 0.098958], [0.305444, 0.098958], [0.305444, -0.370968], [0.302167, -0.389785], [0.27957, -0.392473], [0.229083, -0.393481], [0.142977, -0.390289], [0.169355, -0.444052], [0.18498, -0.5], [0.303763, -0.499412], [0.379536, -0.480679], [0.430108, -0.448337], [0.437668, -0.370968], [0.437668, 0.217238], [0.072077, 0.217238], [0.072077, 0.297883], [0.477487, 0.297883], [0.477487, 0.418347], [0.072077, 0.418347], [0.072077, 0.5]], paths=[[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59]]);
    if(i==2) polygon(points=[[-0.5, 0.490005], [-0.5, 0.361029], [-0.196332, 0.361029], [-0.196332, 0.240744], [-0.455501, 0.240744], [-0.455501, -0.490005], [-0.325482, -0.490005], [-0.325482, -0.426734], [0.326525, -0.426734], [0.326525, -0.487919], [0.462281, -0.487919], [0.462281, 0.240744], [0.181905, 0.240744], [0.181905, 0.361029], [0.5, 0.361029], [0.5, 0.490005], [-0.325482, -0.303146], [-0.325482, -0.146358], [-0.282027, -0.181384], [-0.250913, -0.215366], [-0.081783, -0.07118], [-0.065096, 0.105163], [-0.065096, 0.11733], [0.047193, 0.11733], [0.047193, -0.011646], [0.057796, -0.140709], [0.177386, -0.158526], [0.270902, -0.158526], [0.302016, -0.157396], [0.326525, -0.149661], [0.326525, -0.303146], [0.175126, 0.11733], [0.326525, 0.11733], [0.326525, -0.007301], [0.300278, 0.003911], [0.282027, 0.016165], [0.276464, -0.037806], [0.255258, -0.041717], [0.199635, -0.041717], [0.176256, -0.040588], [0.175126, -0.010603], [-0.065096, 0.240744], [-0.065096, 0.361029], [0.047193, 0.361029], [0.047193, 0.240744], [-0.325482, -0.118547], [-0.325482, 0.11733], [-0.189727, 0.11733], [-0.189727, 0.108465], [-0.198071, -0.008952]], paths=[[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15], [16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30], [31, 32, 33, 34, 35, 36, 37, 38, 39, 40], [41, 42, 43, 44], [45, 46, 47, 48, 49]]);
    if(i==3) polygon(points=[[-0.5, -0.22649], [-0.443804, -0.355449], [-0.216258, -0.258811], [-0.216258, -0.474013], [-0.086325, -0.474013], [-0.086325, 0.474013], [-0.216258, 0.474013], [-0.216258, 0.244356], [-0.462644, 0.244356], [-0.462644, 0.120594], [-0.216258, 0.120594], [-0.216258, -0.131964], [-0.375264, -0.18751], [0.388745, 0.31923], [0.293081, 0.240702], [0.175654, 0.160062], [0.175654, 0.474013], [0.04572, 0.474013], [0.04572, -0.274403], [0.062855, -0.443235], [0.199529, -0.465568], [0.338883, -0.465568], [0.471902, -0.427156], [0.5, -0.18816], [0.438119, -0.168345], [0.380461, -0.131964], [0.370067, -0.321098], [0.326376, -0.342943], [0.219344, -0.342943], [0.178252, -0.338314], [0.175654, -0.275378], [0.175654, 0.029154], [0.333198, 0.113854], [0.479211, 0.206838]], paths=[[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], [13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33]]);
}
