from msv.macro_script import MacroController


class FoxTreeTopPath(MacroController):
    def loop(self):
        # ignore rune

        # set skills
        if self.set_skills(combine=True):
            return

        if self.current_platform_hash == '9404dc97':  # center
            self.player_manager.shiki_exo_shiki(50, wait=False)
        elif self.current_platform_hash == '3e457a07':  # bottom
            self.player_manager.shikigami_haunting_sweep_move(50)
            self.player_manager.teleport_up()
        else:
            self.navigate_to_platform('9404dc97')  # center

        ### Other buffs
        self.buff_skills(yuki=False)

        # Finished
        return 0
