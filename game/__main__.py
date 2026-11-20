import arcade
import argparse
from .window import QuayWindow
from .campaign import CampaignWindow

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="余烬回廊")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--practice", action="store_true", help="仅练习移动与碰撞")
    modes.add_argument("--skirmish", action="store_true", help="盐炉渡口三敌交锋")
    options = parser.parse_args()
    if options.practice or options.skirmish:
        QuayWindow(practice=options.practice)
    else:
        CampaignWindow()
    arcade.run()
