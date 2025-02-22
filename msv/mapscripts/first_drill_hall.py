import time
from msv.macro_script import MacroController
import msv.directinput_constants as dc


class FirstDrillHall(MacroController):
    CENTER_X = 77
    LEFT_X = 67
    RIGHT_X = 87

    def loop(self):
        # ignore rune

        # set skills
        if self.set_skills(combine=True):
            return

        if self.current_platform_hash == '7e1401e3':  # bottom
            self.player_manager.shikigami_haunting_sweep_move(self.LEFT_X if self.player_manager.x < self.CENTER_X else self.RIGHT_X)
            time.sleep(0.2)
            self.player_manager.jump()
            time.sleep(0.3)
        elif self.current_platform_hash == '09e13898':  # the platform
            to_left = self.player_manager.x > self.CENTER_X
            self.keyhandler.single_press(dc.DIK_RIGHT if to_left else dc.DIK_LEFT)
            self.player_manager.shikigami_haunting()
            self.keyhandler.single_press(dc.DIK_LEFT if to_left else dc.DIK_RIGHT)
            self.player_manager.shikigami_haunting(wait_delay=False)
            time.sleep(0.1)
            self.player_manager.teleport_left() if to_left else self.player_manager.teleport_right()
            self.update()
            self.player_manager.horizontal_move_goal(self.LEFT_X if to_left else self.RIGHT_X)
        else:
            self.navigate_to_platform('09e13898')  # the platform

        ### Other buffs
        self.buff_skills(yuki=False)

        # Finished
        return 0
