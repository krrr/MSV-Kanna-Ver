import time, math, random
from msv.directinput_constants import DIK_RIGHT, DIK_DOWN, DIK_LEFT, DIK_UP
from msv.input_manager import DEFAULT_KEY_MAP
from msv.screen_processor import MiniMapError
from msv.util import random_number


# simple jump vertical distance: about 6 pixels
class PlayerController:
    TELEPORT_CD = 0.65
    TELEPORT_HORIZONTAL_RANGE = 18
    SHIKIGAMI_HAUNTING_RANGE = 18
    SET_SKILL_COMMON_DELAY = 0.35
    BUFF_COMMON_DELAY = 0.7

    """
    This class keeps track of character location and manages advanced movement and attacks.
    """
    def __init__(self, key_mgr, screen_processor, keymap=DEFAULT_KEY_MAP, poll_func=None):
        """
        Class Variables:

        self.x: Known player minimap x coord. Needs to be updated manually
        self.x: Known player minimap y coord. Needs tobe updated manually
        self.key_mgr: handle to KeyboardInputManager
        self.screen_processor: handle to StaticImageProcessor
        self.goal_x: If moving, destination x coord
        self.goal_y: If moving, destination y coord
        :param key_mgr: Handle to KeyboardInputManager
        :param screen_processor: Handle to StaticImageProcessor. Only used to call find_player_minimap_marker

        Bot States:
        Idle
        ChangePlatform
        AttackinPlatform
        """
        self.x = self.y = None
        self.last_teleport_time = 0

        self.keymap = keymap.copy()
        self.key_mgr = key_mgr
        self.screen_processor = screen_processor
        self.goal_x = self.goal_y = None

        self._poll_func = poll_func

        self.horizontal_goal_offset = 2

        self.x_movement_enforce_rate = 15  # refer to optimized_horizontal_move

        self.shikigami_haunting_delay = 0.37  # delay after using shikigami haunting where character is not movable

        self.horizontal_movement_threshold = 18  # teleport instead of walk if distance greater than threshold

        self.skill_cast_counter = 0
        self.skill_counter_time = 0

        self.skill_cooldown = {
            'yaksha_boss': 30, 'kishin_shoukan': 60, 'nightmare_invite': 60, 'true_arachnid_reflection': 250,
            'spirit_domain': 196
        }

        self.v_buff_cd = 180  # common cool down for v buff

        self.last_skill_use_time = {}

    def update(self, player_coords_x=None, player_coords_y=None):
        """
        Updates self.x, self.y to input coordinates
        :param player_coords_x: Coordinates to update self.x
        :param player_coords_y: Coordinates to update self.y
        :return: None
        """
        self._call_poll()
        if player_coords_x:
            self.x, self.y = player_coords_x, player_coords_y
        else:
            self.screen_processor.update_image()
            pos = self.screen_processor.find_player_minimap_marker()
            if not pos:
                raise MiniMapError("failed to find player pos in minimap")
            self.x, self.y = pos

    def distance(self, coord1, coord2):
        return math.sqrt((coord1[0]-coord2[0])**2 + (coord1[1]-coord2[1])**2)

    def shikigami_haunting_sweep_move(self, goal_x, no_attack_distance=0):
        """
        This function will, while moving towards goal_x, constantly use shikigami haunting and not overlapping
        X coordinate max error on flat surface: +- 5 pixels
        :param goal_x: minimap x goal coordinate.
        :param no_attack_distance: Distance in x pixels where any attack skill would not be used and just move
        """
        self.update()
        start_x = self.x
        loc_delta = self.x - goal_x
        if abs(loc_delta) < self.horizontal_goal_offset:
            return True

        if not no_attack_distance:
            self.key_mgr.single_press(DIK_LEFT if loc_delta > 0 else DIK_RIGHT)  # turn to correct direction

        start_time = time.time()
        time_limit = math.ceil(abs(loc_delta) / self.x_movement_enforce_rate) + 3

        last_teleport_x = None
        while True:
            dis = abs(self.x - goal_x)
            if dis <= self.horizontal_goal_offset:
                return True

            # skip shikigami if last teleport failed
            if abs(self.x - start_x) >= no_attack_distance and \
                    (last_teleport_x is None or abs(last_teleport_x-self.x) > self.horizontal_goal_offset):
                self.shikigami_haunting(False)

            if dis <= self.horizontal_movement_threshold:
                self.horizontal_move_goal(goal_x)
            else:
                last_teleport_x = self.x
                # can teleport immediately after 3rd hit of shikigami haunting
                if loc_delta > 0:
                    self.teleport_left()
                else:
                    self.teleport_right()
                time.sleep(0.12)  # not affected by latency anymore, can be very tight

            self.update()
            if time.time() - start_time > time_limit:
                return False

    def optimized_horizontal_move(self, goal_x):
        """
        Move from self.x to goal_x in as little time as possible. Uses multiple movement solutions for efficient paths.
        Blocking call. This function will stop moving after a time threshold is met and still haven't
        met the goal. Default threshold is 15 minimap pixels per second.
        :param goal_x: x coordinate to move to. This function only takes into account x coordinate movements.
        # :param ledge: If true, goal_x is an end of a platform, and additional movement solutions can be used. If not, precise movement is required.
        :return: None
        """
        loc_delta = self.x - goal_x
        abs_loc_delta = abs(loc_delta)
        start_time = time.time()
        time_limit = math.ceil(abs_loc_delta/self.x_movement_enforce_rate) + 3
        if loc_delta < 0:  # we need to move right
            if abs_loc_delta <= self.horizontal_movement_threshold:
                # Just walk if distance is less than threshold
                self.key_mgr.direct_press(DIK_RIGHT)

                # Below: use a loop to continuously press right until goal is reached or time is up
                while True:
                    if time.time()-start_time > time_limit:
                        break

                    self.update()
                    # Problem with synchonizing player_pos with self.x and self.y. Needs to get resolved.
                    # Current solution: Just call self.update() (not good for redundancy)
                    if self.x >= goal_x - self.horizontal_goal_offset:
                        # Reached or exceeded destination x coordinates
                        break

                self.key_mgr.direct_release(DIK_RIGHT)
            else:
                # Distance is quite big, so we teleport
                self.teleport_right()
                self.horizontal_move_goal(goal_x)
        elif loc_delta > 0:  # we are moving to the left
            if abs_loc_delta <= self.horizontal_movement_threshold:
                self.key_mgr.direct_press(DIK_LEFT)

                # Below: use a loop to continously press left until goal is reached or time is up
                while True:
                    if time.time()-start_time > time_limit:
                        break

                    self.update()
                    # Problem with synchonizing player_pos with self.x and self.y. Needs to get resolved.
                    # Current solution: Just call self.update() (not good for redundancy)
                    if self.x <= goal_x + self.horizontal_goal_offset:
                        # Reached or exceeded destination x coordinates
                        break

                self.key_mgr.direct_release(DIK_LEFT)
            else:
                # Distance is quite big, so we teleport
                self.teleport_left()
                self.horizontal_move_goal(goal_x)

    def horizontal_move_goal(self, goal_x, timeout=None, precise=False):
        """
        Blocking call to move from current x position(self.x) to goal_x. Only counts x coordinates.
        Refactor notes: This function references self.screen_processor
        :param goal_x: goal x coordinates
        :return: None
        """
        dis = abs(self.x - goal_x)
        if precise:
            offset = min(dis, self.horizontal_goal_offset)
            if offset == 0:
                return True
        else:
            offset = self.horizontal_goal_offset
            if dis <= offset:
                return True

        start_time = time.time()
        time_limit = timeout or math.ceil(dis / self.x_movement_enforce_rate) + 3
        right = goal_x - self.x > 0  # need to go right:

        self.key_mgr.direct_press(DIK_RIGHT if right else DIK_LEFT)
        while True:
            time.sleep(0.02)
            self.update()

            if (right and self.x >= goal_x - offset) or (not right and self.x <= goal_x + offset):
                self.key_mgr.direct_release(DIK_RIGHT if right else DIK_LEFT)
                return True

            if time.time() - start_time > time_limit:
                self.key_mgr.direct_release(DIK_RIGHT if right else DIK_LEFT)
                return False

    def stay(self, timeout, goal_x=None):
        start_time = time.time()

        while True:
            self.update()
            if goal_x is None:
                goal_x = self.x
                continue

            self.horizontal_move_goal(goal_x, time.time()-timeout)

            if time.time()-timeout > start_time:
                break

            time.sleep(0.02)

    def teleport_up(self):
        return self._do_teleport(DIK_UP)

    def teleport_down(self):
        return self._do_teleport(DIK_DOWN)

    def teleport_left(self):
        return self._do_teleport(DIK_LEFT)

    def teleport_right(self):
        return self._do_teleport(DIK_RIGHT)

    def _do_teleport(self, dir_key):
        """Warining: is a blocking call"""
        self.key_mgr.direct_press(dir_key)
        time.sleep(0.03)
        self.key_mgr.direct_press(self.keymap["teleport"])
        self.last_teleport_time = time.time()
        time.sleep(0.06 + random_number(0.02))
        self.key_mgr.direct_release(dir_key)
        time.sleep(0.03)
        self.key_mgr.direct_release(self.keymap["teleport"])
        return True

    def wait_teleport_cd(self):
        elapsed = time.time() - self.last_teleport_time
        if elapsed < self.TELEPORT_CD:
            self.stay(self.TELEPORT_CD - elapsed)

    def shikigami_charm(self):
        self.key_mgr.single_press(self.keymap["shikigami_charm"])

    def jump(self):
        self.key_mgr.single_press(self.keymap["jump"])

    def jump_left(self, wait=True):
        """Blocking call"""
        self._do_jump(DIK_LEFT, wait)

    def jump_right(self, wait=True):
        """Blocking call"""
        self._do_jump(DIK_RIGHT, wait)

    def _do_jump(self, dir_key, wait):
        self.key_mgr.direct_press(dir_key)
        time.sleep(0.1)
        self.key_mgr.direct_press(self.keymap["jump"])
        time.sleep(0.1)
        self.key_mgr.direct_release(dir_key)
        time.sleep(0.04 + random_number(0.1))
        self.key_mgr.direct_release(self.keymap["jump"])
        if wait:
            self._wait_drop(True)

    def drop(self, wait=True):
        """Blocking call"""
        self.key_mgr.direct_press(DIK_DOWN)
        time.sleep(0.05 + random_number())
        self.key_mgr.direct_press(self.keymap["jump"])
        time.sleep(0.05 + random_number())
        self.key_mgr.direct_release(self.keymap["jump"])
        time.sleep(0.1 + random_number())
        self.key_mgr.direct_release(DIK_DOWN)
        if wait:
            self._wait_drop(False)

    def _wait_drop(self, wait_jump):
        """Wait until dropped to ground"""
        y = self.y
        eq_count = 0
        dropping = not wait_jump
        jumped = not wait_jump
        for _ in range(250):
            time.sleep(0.02)
            self.update()
            if self.y == y:
                if not jumped or not dropping:
                    continue
                eq_count += 1
                if eq_count == 5:
                    break
            elif self.y > y:
                dropping = True
                eq_count = 0
            else:
                if dropping:  # hit by monster after dropped to ground
                    break
                jumped = True
                eq_count = 0
            y = self.y

    def shikigami_haunting(self, wait_delay=True):
        for _ in range(3):
            self.key_mgr.single_press(self.keymap["shikigami_haunting"])
            time.sleep(0.06 + random_number(0.005))
        self.skill_cast_counter += 1
        if wait_delay:
            time.sleep(self.shikigami_haunting_delay)

    def shiki_exo_shiki(self, x, wait=True):
        dis = abs(self.x - x)
        if dis > self.SHIKIGAMI_HAUNTING_RANGE:
            self.shikigami_haunting_sweep_move(x)
        elif dis > 2:
            self.horizontal_move_goal(x)

        self._call_poll()

        if abs(self.x - x) < self.horizontal_goal_offset:
            dir_ = random.choice((DIK_LEFT, DIK_RIGHT))
        else:
            dir_ = DIK_RIGHT if self.x < x else DIK_LEFT
        self.key_mgr.single_press(dir_)
        self.shikigami_haunting()
        time.sleep(0.05)
        self.exorcist_charm(False)
        self.stay(1.22 + random_number(0.05), x)
        self.key_mgr.single_press(DIK_LEFT if dir_ == DIK_RIGHT else DIK_RIGHT)
        self.shikigami_haunting()

        self._call_poll()

        if wait:
            self.stay(1.22 + random_number(0.05), x)
        else:
            self.key_mgr.single_press(dir_)
            self.shikigami_haunting()
            self.key_mgr.single_press(DIK_LEFT if dir_ == DIK_RIGHT else DIK_RIGHT)
            self.shikigami_haunting()
            self.stay(0.2 + random_number(0.05), x)

    def exorcist_charm(self, wait_delay=True):
        self.key_mgr.single_press(self.keymap["exorcist_charm"])
        self.skill_cast_counter += 1
        if wait_delay:
            time.sleep(1.1 + random_number(0.01))

    def vanquisher_move(self, dir_key, timeout):
        if not self.is_skill_key_set('vanquisher_charm'):
            return
        self.key_mgr.direct_press(self.keymap['vanquisher_charm'])
        time.sleep(0.02)
        self.key_mgr.direct_press(dir_key)
        time.sleep(timeout)
        self.key_mgr.direct_release(dir_key)
        time.sleep(0.02)
        self.key_mgr.direct_release(self.keymap['vanquisher_charm'])
        time.sleep(0.15 + random_number(0.05))

    def use_set_skill(self, skill_name):
        for i in range(2):
            self.key_mgr.single_press(self.keymap[skill_name], duration=0.2 + random_number(0.04),
                                      additional_duration=0 if i == 1 else 0.36 + random_number(0.04))
        self.last_skill_use_time[skill_name] = time.time()
        self.skill_cast_counter += 1
        time.sleep(self.SET_SKILL_COMMON_DELAY + random_number(0.1))

        return True

    def is_skill_usable(self, skill_name):
        return (self.keymap.get(skill_name) is not None
                and time.time() - self.last_skill_use_time.get(skill_name, 0) > self.skill_cooldown[skill_name])

    def _use_buff_skill(self, skill_name, skill_cd, wait_before=0.0):
        if self.keymap.get(skill_name) is None:
            return False

        if time.time() - self.last_skill_use_time.get(skill_name, 0) > skill_cd + random.randint(0, 6):
            if wait_before:
                time.sleep(wait_before)
            for i in range(2):
                self.key_mgr.single_press(self.keymap[skill_name], duration=0.2 + random_number(0.04),
                                          additional_duration=0 if i == 1 else 0.1 + random_number(0.04))
            self.skill_cast_counter += 1
            self.last_skill_use_time[skill_name] = time.time()
            time.sleep(self.BUFF_COMMON_DELAY + random_number(0.04))
            return True

        return False

    def holy_symbol(self, wait_before=0):
        return self._use_buff_skill('holy_symbol', self.v_buff_cd, wait_before)

    def wild_totem(self, wait_before=0):
        return self._use_buff_skill('wild_totem', 100, wait_before)

    def speed_infusion(self, wait_before=0):
        return self._use_buff_skill('speed_infusion', self.v_buff_cd, wait_before)

    def mihile_link(self, wait_before=0):
        return self._use_buff_skill('mihile_link', self.v_buff_cd, wait_before)

    def haku_reborn(self, wait_before=0):
        return self._use_buff_skill('haku_reborn', 500, wait_before)

    def yuki_musume(self, wait_before=0):
        return self._use_buff_skill('yuki_musume', 75, wait_before)

    def is_on_platform(self, platform, offset=0):
        return ((platform.start_y-offset) <= self.y <= platform.start_y  # may being kicked by monster
                and (platform.start_x-offset) <= self.x <= (platform.end_x+offset))

    def is_skill_key_set(self, skill_name):
        return self.keymap.get(skill_name) is not None

    def _call_poll(self):
        if self._poll_func is not None:
            self._poll_func()
