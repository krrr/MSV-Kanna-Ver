import time
from macro_script import MacroController


class CorridorH01(MacroController):
    def loop(self):
        # ignore rune

        # set skills
        if not self.elite_boss_detected and self.set_skills(combine=True):
            return

        if self.current_platform_hash == '37b99a5f':  # center
            self.player_manager.shiki_exo_shiki(62, wait=False)
        elif self.current_platform_hash == 'f0097d64':  # bottom
            self.player_manager.shikigami_haunting_sweep_move(62)
            self.player_manager.teleport_up()
        else:
            self.navigate_to_platform('37b99a5f')  # center

        ### Other buffs
        self.buff_skills(yuki=False)
        time.sleep(0.05)

        # Finished
        self.loop_count += 1
        return 0
