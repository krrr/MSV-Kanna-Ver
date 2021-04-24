import time
from macro_script import MacroController


class CorridorH01(MacroController):
    def __init__(self, keymap, logger_queue, cmd_queue):
        super().__init__(keymap=keymap, log_queue=logger_queue, cmd_queue=cmd_queue)

    def loop(self):
        ret = self._loop_common_job()
        if ret != 0:
            return ret

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