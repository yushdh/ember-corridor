"""Original bell-foundry armour, drawn at world-pixel scale around the planted soles."""
from PIL import Image, ImageDraw

SIZE = (224, 148)
SOLE = (69, 132)
INK = "#192a35"
SHADOW = "#334752"
STEEL = "#657e84"
PATINA = "#597e79"
COPPER = "#a4734f"
GILT = "#dec090"
# Chest offset and height, rear/front boot and lifted toe, elbow, hand, bell centre.
POSES = (
    (0,61,-17,16,0,(19,46),(30,45),(46,40)),
    (1,59,-17,16,0,(20,44),(32,42),(49,37)),
    (4,57,-23,21,0,(15,46),(26,44),(42,38)),
    (-2,64,-12,6,6,(21,57),(33,53),(49,47)),
    (-4,61,-22,17,0,(10,66),(9,82),(-4,95)),
    (-9,56,-23,20,0,(-17,72),(-27,89),(-39,104)),
    (10,53,-25,28,0,(39,39),(56,29),(91,19)),
    (6,52,-22,26,0,(25,32),(36,23),(55,14)),
    (-3,60,-20,17,0,(14,67),(26,79),(30,95)),
    (-4,64,-22,17,0,(9,78),(22,91),(22,111)),
    (3,58,-23,21,0,(23,76),(36,89),(42,106)),
    (2,54,-19,18,0,(21,51),(32,49),(46,42)),
    (-4,60,-22,19,0,(26,69),(42,77),(58,86)),
    (-4,47,-19,23,0,(21,34),(33,24),(47,13)),
    (-11,32,-24,22,0,(1,22),(24,16),(48,12)),
    (-20,19,-27,19,0,(-7,12),(16,10),(42,11)),
    (3,57,-24,22,0,(16,78),(38,75),(62,65)),
    (8,54,-24,26,0,(30,44),(46,33),(74,23)),
    (-6,55,-20,17,0,(2,49),(21,51),(36,43)),
)


def keeper(index, tide=False):
    im = Image.new("RGBA", SIZE)
    d = ImageDraw.Draw(im)
    cx, h, back, front, toe, elbow, hand, head = POSES[index]
    def xy(point):
        return SOLE[0]+point[0], SOLE[1]-1-point[1]
    def face(points, color, edge=INK):
        d.polygon([xy(p) for p in points], fill=color, outline=edge)
    def line(points, color, width=1):
        d.line([xy(p) for p in points], fill=color, width=width, joint="curve")
    def plate(x, y, points, color, edge=INK):
        face([(x+a,y+b) for a,b in points], color, edge)
    def joint(x,y,r):
        plate(x,y,[(-r,1),(-r+2,r),(r-2,r),(r,1),(r-2,-r),(-r+2,-r)],COPPER)
        line([(x-r+2,y+2),(x-1,y+r-1),(x+2,y+r-1)],GILT)
        plate(x,y,[(-2,1),(0,3),(2,1),(1,-2),(-2,-1)],"#645752")
        line([(x-1,y+1),(x,y+2)],"#cfac80")
    def link(points, width, color):
        line(points,INK,width+3)
        line(points,color,width)
    # Splayed greaves with a piston behind each shin and a beveled toe on the floor.
    for foot,side,lift in ((back,-1,toe),(front,1,0)):
        knee = foot + side*4
        kh = max(lift+8, h//3+2)
        link([(cx+side*7,h-12),(knee,kh),(foot,lift+6)],10,SHADOW)
        if kh-lift >= 15:
            plate(knee,kh,[(-6,-2),(2,-4),(5,-2),(3,-9),(0,-14),(-4,-12)],
                  "#536873")
            line([(knee-5,kh-3),(knee-3,kh-9),(knee-1,kh-10)],"#92a69e")
        plate(knee,kh,[(-6,3),(-1,6),(6,4),(5,-3),(1,-6),(-6,-3)],
              STEEL if side>0 else PATINA)
        line([(knee-4,kh+2),(knee-1,kh+4),(knee+3,kh+3)],"#b4b8a3",2)
        line([(foot-3,lift+1),(foot+6,lift+1)],"#344755",2)
        line([(knee-3,kh-5),(foot-3,lift+6)],"#ae9f7e",2)
        plate(foot,lift,[(-7,8),(-2,11),(4,9),(7,5),(13,3),(13,0),(-8,0)],STEEL)
        line([(foot+1,lift+7),(foot+5,lift+4),(foot+11,lift+3)],"#abc1b4",2)
    # A forked, verdigris apron hangs clear of the articulated legs.
    for x,length in ((-10,22),(1,25)):
        length = min(length, h-6)
        plate(cx+x,h,[(-7,-5),(5,-6),(4,-length),(0,-length-5),(-7,-length+1)],"#33565e")
        line([(cx+x-4,h-10),(cx+x-4,h-length+2),(cx+x,h-length-2)],"#86a69a",2)
    # Two stave ends and the suspension yoke break the outline behind the helmet.
    for ox,dy in ((-23,1),(-17,7)):
        rise = 9 if tide and index<13 else 0
        plate(cx+ox,h,[(-4,2),(-5,23+dy+rise),(-2,29+dy+rise),(3,28+dy+rise),
                       (5,6)],"#536a6c")
        line([(cx+ox-2,h+22+dy+rise),(cx+ox+2,h+23+dy+rise)],GILT,2)
    # The counterweight hand hangs behind the shell and braces on the return stroke.
    far_x = cx-28 if index in (5,6,10,12,16,17) else cx-24
    far_y = max(10,h-20+(5 if index in (5,9,16) else 0))
    link([(cx-17,h+5),(far_x-3,h-5),(far_x,far_y)],8,"#4e6268")
    plate(far_x,far_y,[(-6,6),(0,9),(5,6),(5,-1),(2,-5),(-3,-5),(-7,0)],"#867261")
    line([(far_x-5,far_y+3),(far_x-2,far_y+6),(far_x+2,far_y+5)],"#c3ab84",2)
    # Bell cuirass: lit left shoulder, patinated waist and broad shadow under its lip.
    plate(cx,h,[(-25,-9),(-20,0),(-16,17),(-10,24),(3,25),(13,19),(17,5),
                (25,-8),(24,-13),(7,-18),(-14,-16),(-25,-13)],"#9d714f")
    plate(cx,h,[(-21,-8),(-16,3),(-13,16),(-7,20),(-4,20),(-9,5),(-11,-9)],"#cca375",None)
    plate(cx,h,[(4,22),(13,17),(17,3),(24,-8),(16,-9),(5,-3)],"#645452",None)
    plate(cx,h,[(-26,-8),(-9,-11),(5,-12),(23,-8),(26,-10),(24,-14),
                (5,-18),(-14,-16),(-26,-13)],SHADOW)
    line([(cx-23,h-9),(cx-10,h-11),(cx+5,h-13),(cx+19,h-10)],GILT,2)
    # The hammered lip has interrupted bronze bosses, not a continuous bright outline.
    for ox,oy in ((-17,-11),(-6,-14),(11,-13),(20,-11)):
        line([(cx+ox,h+oy),(cx+ox+2,h+oy)],"#a59574",2)
    plate(cx-12,h+12,[(-7,-1),(-3,7),(2,9),(7,7),(5,3),(-2,1),(-5,-4)],"#965f46")
    line([(cx-17,h+13),(cx-14,h+17),(cx-10,h+19)],"#e3c28a",2)
    # Phase two opens the real pressure shutters. Nothing marks a separate hitbox.
    for j in range(3):
        x=cx-7+6*j
        plate(x,h,[(-2,13),(2,14),(3,0),(0,-4),(-2,0)],INK)
        line([(x-2,h+11),(x-1,h+13),(x+1,h+13)],"#b59a75")
        if tide or index in (9,10,12):
            line([(x,h+9),(x+1,h+1)],"#8dd5bc" if tide else "#e5ac69",2)
        else:
            line([(x-1,h+11),(x+1,h+12)],"#ceb289")
    # Face is sunk inside a bronze coif. A brow and split lower jaw give it a direction.
    hx,hy=cx+4,h+25
    if index in (13,14,15):
        hx -= (2,7,12)[index-13]
        hy -= (2,8,16)[index-13]
    plate(hx,hy,[(-12,-5),(-14,7),(-10,14),(-2,19),(7,16),(11,11),(12,4),
                 (16,2),(11,-3),(6,-9),(-4,-10)],SHADOW)
    plate(hx,hy,[(-13,7),(-9,14),(-2,18),(6,15),(9,11),(1,13),(-6,11)],"#9aaca6")
    plate(hx,hy,[(-11,5),(-4,9),(9,10),(16,6),(12,4),(0,3)],COPPER)
    line([(hx-7,hy+7),(hx,hy+9),(hx+8,hy+9)],GILT,2)
    plate(hx,hy,[(-2,2),(13,5),(11,1),(3,-2),(-2,-1)],INK)
    line([(hx+3,hy+1),(hx+11,hy+3)],"#f6d59a",2)
    plate(hx,hy,[(3,-3),(11,0),(9,-4),(5,-8),(2,-7)],"#a4b7af")
    plate(hx,hy,[(-13,8),(-13,14),(-10,21),(-6,23),(-7,17),(-5,14)],COPPER)
    line([(hx-11,hy+15),(hx-9,hy+20)],GILT,2)
    plate(hx,hy,[(-10,1),(-5,2),(-3,-4),(-5,-9),(-10,-6)],"#667d7e")
    line([(hx-8,hy-2),(hx-5,hy-5)],"#abb8a8")
    plate(hx,hy,[(-13,0),(-8,-3),(-5,-9),(-7,-11),(-13,-7)],"#456477")
    line([(hx-11,hy-3),(hx-8,hy-5)],"#829fa3",2)
    # Far guard is a curved, segmented bell shoulder. Near gauntlet follows the haft.
    plate(cx-17,h+8,[(-12,1),(-8,12),(-2,17),(5,17),(12,11),(11,5),
                      (4,-1),(-5,-4)],"#527372")
    line([(cx-27,h+11),(cx-22,h+19),(cx-17,h+22),(cx-12,h+22)],"#b0c1aa",2)
    plate(cx-17,h+8,[(-9,1),(-5,8),(0,10),(6,9),(3,6),(-2,5),(-4,0)],"#71948a",None)
    line([(cx-24,h+7),(cx-19,h+6),(cx-13,h+8)],"#b0976a",2)
    link([(cx+10,h+9),elbow,hand],10,STEEL)
    line([(elbow[0]-2,elbow[1]+2),(hand[0]-2,hand[1]+1)],"#9aadaa",2)
    # Joint rings and the raised coaming catch light separately from the steel sleeves.
    joint(cx+10,h+9,6)
    joint(*elbow,5)
    link([hand,head],5,"#9c7c5e")
    joint(*hand,5)
    # The weapon is a flanged handbell; its rim turns into the sweeping trajectory.
    if tide and index in (6,17):
        head=(head[0]+15,head[1])
        link([hand, head],5,"#977454")
    angle = (-1 if index in (4,5,8,9,10,12) else 1)
    mx,my=head
    def mace(points,color,edge=INK):
        face([(mx+v*angle,my+u) for u,v in points],color,edge)
    mace([(-4,-9),(3,-10),(7,-4),(8,2),(11,7),(10,11),(-9,12),
          (-11,8),(-7,3),(-6,-4)],"#9b694d")
    mace([(-5,-5),(0,-7),(3,-4),(4,2),(7,5),(3,6),(-3,3)],"#766159")
    mace([(-6,1),(-4,-2),(-2,0),(0,3),(-3,4)],"#ccac7f")
    mace([(1,-7),(5,-3),(6,3),(9,7),(5,8),(2,3)],"#edbf81",None)
    mace([(-11,7),(10,6),(11,10),(8,13),(-9,13),(-12,11)],"#566a69")
    mace([(-8,8),(9,7),(9,9),(-8,10)],"#e2c79a",None)
    mace([(-4,13),(3,13),(2,16),(-1,17),(-4,16)],COPPER)
    mace([(-6,-2),(-2,-5),(1,-5),(-1,-2),(-3,0)],"#ddaa73",None)
    mace([(-2,1),(1,-1),(3,2),(1,5)],"#513e3d")
    return im,xy(hand)
