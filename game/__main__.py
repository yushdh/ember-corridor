import arcade
import argparse
from .window import QuayWindow
from .campaign import CampaignWindow

def main():
    parser = argparse.ArgumentParser(description="余烬回廊")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--practice", action="store_true", help="仅练习移动与碰撞")
    modes.add_argument("--skirmish", action="store_true", help="盐炉渡口三敌交锋")
    modes.add_argument("--classic", action="store_true", help="使用原版手工五室")
    modes.add_argument("--first-play", action="store_true", help="用独立新档试玩手工五室并在本机记录用时")
    modes.add_argument("--seed", type=int, help="按十进制潮图种子重走同一条路线")
    options = parser.parse_args()
    if options.seed is not None and not 0 <= options.seed <= 0xffffffff:
        parser.error("种子范围为 0 到 4294967295")
    if options.first_play:
        from .first_play import FirstPlayWindow
        FirstPlayWindow()
    elif options.practice or options.skirmish:
        QuayWindow(practice=options.practice)
    else:
        CampaignWindow(seed=options.seed, classic=options.classic)
    arcade.run()


if __name__ == "__main__":
    main()
