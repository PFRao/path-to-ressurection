import libtcodpy as libtcod
import math
import textwrap
import shelve

#TO DO: messages telling you what's in the same tile as you, "nothing to pick up" message, message to acknowledge user cancelling mouse targeting

#KNOWN BUGS: trolls and shields are sometimes generated earlier than expected

SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50

MAP_WIDTH = 80
MAP_HEIGHT = 43

BAR_WIDTH = 20
PANEL_HEIGHT = 7
PANEL_Y = SCREEN_HEIGHT - PANEL_HEIGHT

MSG_X = BAR_WIDTH + 2
MSG_WIDTH = SCREEN_WIDTH - BAR_WIDTH - 2
MSG_HEIGHT = PANEL_HEIGHT - 1

CHARACTER_SCREEN_WIDTH = 30

ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 30

INVENTORY_WIDTH = 50

HEAL_AMOUNT = 40

LIGHTNING_DAMAGE = 40
LIGHTNING_RANGE = 5

CONFUSE_NUM_TURNS = 10
CONFUSE_RANGE = 8

FIREBALL_RADIUS = 3
FIREBALL_DAMAGE = 25

#experience and level-ups
LEVEL_UP_BASE = 200
LEVEL_UP_FACTOR = 150
LEVEL_SCREEN_WIDTH = 40 #width for level up menu

FOV_ALGO = 0  #default libtcod algorithm; try others later
FOV_LIGHT_WALLS = True
TORCH_RADIUS = 10

#color_dark_wall = libtcod.Color(0,0,100)
#color_dark_ground = libtcod.Color(50,50,150)
color_dark_wall = libtcod.darker_gray
color_dark_ground = libtcod.gray
color_light_wall = libtcod.Color(130,110,50)
color_light_ground = libtcod.Color(200,180,50)

LIMIT_FPS = 20

class Object:
	def __init__(self, x, y, char, name, color, blocks = False, always_visible = False, fighter = None, ai = None, item = None, equipment = None):
		self.x = x
		self.y = y
		self.char = char
		self.name = name
		self.color = color
		self.blocks = blocks
		self.always_visible = always_visible
		self.fighter = fighter
		if self.fighter:
			self.fighter.owner = self
		self.ai = ai
		if self.ai:
			self.ai.owner = self
		self.item = item
		if self.item:
			self.item.owner = self
		self.equipment = equipment
		if self.equipment:
			self.equipment.owner = self
			self.item = Item()
			self.item.owner = self
	
	def move(self, dx, dy):
		if not is_blocked(self.x + dx, self.y + dy):
			self.x += dx
			self.y += dy
	
	def draw(self):
		if (libtcod.map_is_in_fov(fov_map, self.x, self.y) or (self.always_visible and map[self.x][self.y].explored)):
			libtcod.console_set_default_foreground(con, self.color)
			libtcod.console_put_char(con, self.x, self.y, self.char, libtcod.BKGND_NONE)
		
	def clear(self):
		libtcod.console_put_char(con, self.x, self.y, ' ', libtcod.BKGND_NONE)
		
	def move_towards(self, target_x, target_y):
		#figure out why this works!
		dx = target_x - self.x
		dy = target_y - self.y
		distance = math.sqrt(dx ** 2 + dy **2)
		dx = int(round(dx / distance))
		dy = int(round(dy / distance))
		self.move(dx, dy)
	
	def distance_to(self, other):
		dx = other.x - self.x
		dy = other.y - self.y
		return math.sqrt(dx ** 2 + dy ** 2)
	
	def distance(self, x, y):
		#return the distance to some coordinates
		return math.sqrt((x - self.x) ** 2 + (y - self.y) ** 2)

class Tile:
	#more research required!
	def __init__(self, blocked, block_sight = None):
		self.blocked = blocked
		self.explored = False
		if block_sight is None: block_sight = blocked
		self.block_sight = block_sight

class Rect:
	def __init__(self, x, y, w, h):
		self.x1 = x
		self.y1 = y
		self.x2 = x + w
		self.y2 = y + h
		
	def center(self):
		center_x = (self.x1 + self.x2) / 2
		center_y = (self.y1 + self.y2) / 2
		return (center_x, center_y)
 
	def intersect(self, other):
		#returns true if this rectangle intersects with another one
		return (self.x1 <= other.x2 and self.x2 >= other.x1 and self.y1 <= other.y2 and self.y2 >= other.y1)

class Fighter:
	#component for objects that can fight
	def __init__(self, hp, defense, power, xp, death_function = None):
		self.base_max_hp = hp
		self.hp = hp
		self.base_defense = defense
		self.base_power = power
		self.xp = xp
		self.death_function = death_function
	
	@property
	def power(self):
		#a dynamic read-only property
		bonus = sum(equipment.power_bonus for equipment in get_all_equipped(self.owner))
		return self.base_power + bonus
		
	@property
	def defense(self):
		#return actual defense, by summing up the bonuses from all equipped items
		bonus = sum(equipment.defense_bonus for equipment in get_all_equipped(self.owner))
		return self.base_defense + bonus
		
	@property
	def max_hp(self):
		#return actual max_hp, by summing up the bonuses from all equipped items
		bonus = sum(equipment.max_hp_bonus for equipment in get_all_equipped(self.owner))
		return self.base_max_hp + bonus
	
	def take_damage(self, damage):
		if damage > 0:
			self.hp -= damage
		if self.hp <= 0:
			function = self.death_function
			if function is not None:
				#if the object can die, then it dies
				function(self.owner)
			if self.owner != player:
				#give the player xp
				player.fighter.xp += self.xp
			
	def attack(self, target):
		damage = self.power - target.fighter.defense
		if damage > 0:
			message(self.owner.name.capitalize() + ' attacks ' + target.name + ' for ' + str(damage) + ' hit points.')
			target.fighter.take_damage(damage)
		else:
			message(self.owner.name.capitalize() + ' attacks ' + target.name + ' but it has no effect!')
	
	def heal(self, amount):
		self.hp += amount
		if self.hp > self.max_hp:
			self.hp = self.max_hp
		
class BasicMonster:
	#component for basic melee minions
	def take_turn(self):
		monster = self.owner
		if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):
			if monster.distance_to(player) >= 2:
				monster.move_towards(player.x, player.y)
			elif player.fighter.hp > 0:
				monster.fighter.attack(player)

class ConfusedMonster:
	#component for confused monsters; reverts after CONFUSE_NUM_TURNS turns have passed
	def __init__(self, old_ai, num_turns = CONFUSE_NUM_TURNS):
		self.old_ai = old_ai
		self.num_turns = num_turns #turns remaining in the confusion effect
		
	def take_turn(self):
		if self.num_turns > 0:
			#move randomly
			self.owner.move(libtcod.random_get_int(0, -1, 1), libtcod.random_get_int(0, -1, 1))
			self.num_turns -= 1
		else:
			#restore previous AI
			self.owner.ai = self.old_ai
			message('The ' + self.owner.name + ' seems to have regained his (her?) bearings.', libtcod.red)
				
class Item:
	#component for things you can pick up
	def __init__(self, use_function = None):
		self.use_function = use_function
		
	def use(self):
		#special case for equipment
		if self.owner.equipment:
			self.owner.equipment.toggle_equip()
			return
		if self.use_function == None:
			message("The " + self.owner.name + " cannot be used.")
		else:
			if self.use_function() != 'cancelled':
				#destroy item after use
				inventory.remove(self.owner)
		
	def pick_up(self):
		#add to inventory, remove from map
		if len(inventory) >= 26:
			message("Your pack is too full to pick up " + self.owner.name + ".", libtcod.red)
		else:
			inventory.append(self.owner)
			objects.remove(self.owner)
			message("You picked up a " + self.owner.name + ".", libtcod.green)
		#if the item is a piece of equipment and you have no item equipped it that slot already, equip it
		if self.owner.equipment and get_equipped_in_slot(self.owner.equipment.slot) is None:
			self.owner.equipment.equip()
	
	def drop(self):
		#add to objects array, remove from inventory
		objects.append(self.owner)
		inventory.remove(self.owner)
		send_to_back(self.owner)
		#special case: if the object has the Equipment component, dequip it before dropping
		if self.owner.equipment:
			self.owner.equipment.dequip()
		self.owner.x = player.x
		self.owner.y = player.y
		message("You dropped a " + self.owner.name + ".", libtcod.yellow)
		

class Equipment:
	#component for things that can be equipped, yielding bonuses. automatically adds the Item component.
	def __init__(self, slot, power_bonus=0, defense_bonus=0, max_hp_bonus=0):
		self.slot = slot
		self.is_equipped = False
		self.power_bonus = power_bonus
		self.defense_bonus = defense_bonus
		self.max_hp_bonus = max_hp_bonus
	
	def toggle_equip(self):
		if self.is_equipped:
			self.dequip()
		else:
			self.equip()
	
	def equip(self):
		#if something is there already, then dequip it
		old_equipment = get_equipped_in_slot(self.slot)
		if old_equipment is not None:
			old_equipment.dequip()
		self.is_equipped = True
		message('Equipped ' + self.owner.name + ' on ' + self.slot + '.', libtcod.light_green)
		
	def dequip(self):
		if not self.is_equipped: return
		self.is_equipped = False
		message('Removed ' + self.owner.name + ' from ' + self.slot + '.', libtcod.light_yellow)
		
def handle_keys():
	global playerx, playery
	global fov_recompute
	global key
	#buttons for controlling the game
	if key.vk ==  libtcod.KEY_ENTER and key.lalt:
		libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())
	elif key.vk == libtcod.KEY_ESCAPE:
		return 'exit'
	#buttons for movement and combat
	if game_state == 'playing':
		if key.vk == libtcod.KEY_UP or key.vk == libtcod.KEY_KP8:
			player_move_or_attack(0, -1)
		elif key.vk == libtcod.KEY_DOWN or key.vk == libtcod.KEY_KP2:
			player_move_or_attack(0, 1)
		elif key.vk == libtcod.KEY_LEFT or key.vk == libtcod.KEY_KP4:
			player_move_or_attack(-1, 0)
		elif key.vk == libtcod.KEY_RIGHT or key.vk == libtcod.KEY_KP6:
			player_move_or_attack(1, 0)
		elif key.vk == libtcod.KEY_HOME or key.vk == libtcod.KEY_KP7:
			player_move_or_attack(-1, -1)
		elif key.vk == libtcod.KEY_PAGEUP or key.vk == libtcod.KEY_KP9:
			player_move_or_attack(1, -1)
		elif key.vk == libtcod.KEY_END or key.vk == libtcod.KEY_KP1:
			player_move_or_attack(-1, 1)
		elif key.vk == libtcod.KEY_PAGEDOWN or key.vk == libtcod.KEY_KP3:
			player_move_or_attack(1, 1)
		elif key.vk == libtcod.KEY_KP5 or key.vk == ".":
			#do nothing ie wait for the monster to come to you
			pass
		else:
		#testing for other keys
			key_char = chr(key.c)
			if key_char == "g":
				#pick up an item
				for object in objects:
					#find all objects that are in the player's tile
					if object.x == player.x and object.y == player.y and object.item:
						object.item.pick_up()
						break
			if key_char == "i":
				#show inventory
				chosen_item = inventory_menu("Press the key next to the item name to use it, or any other to cancel. \n")
				if chosen_item is not None:
					chosen_item.use()
			if key_char == "d":
				#show inventory, drop item
				chosen_item = inventory_menu("Press the key next to the item name to drop it, or any other to cancel. \n")
				if chosen_item is not None:
					chosen_item.drop()
			if key_char == ">":
				#go downstairs
				if stairs.x == player.x and stairs.y == player.y:
					next_level()
			if key_char == "<":
				#go upstairs
				if up_stairs.x == player.x and up_stairs.y == player.y:
					prev_level()
			if key_char == "c":
				#open the character screen
				level_up_xp = LEVEL_UP_BASE + player_level * LEVEL_UP_FACTOR
				msgbox('Character Information\n\nLevel: ' + str(player_level) + '\nExperience: ' + str(player.fighter.xp) + '\nExperience to level up: ' + str(level_up_xp) + '\n\nMaximum HP: ' + str(player.fighter.max_hp) + '\nAttack: ' + str(player.fighter.power) + '\nDefense: ' + str(player.fighter.defense), CHARACTER_SCREEN_WIDTH)
			return 'didnt-take-turn'
		
def make_map():
	global map, objects, stairs, up_stairs, floors
	objects = [player]
	map = [[Tile(True) for y in range(MAP_HEIGHT)] for x in range(MAP_WIDTH)]
	rooms = []
	num_rooms = 0
	for r in range(MAX_ROOMS):
		w = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
		h = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
		x = libtcod.random_get_int(0, 0, MAP_WIDTH - w - 1)
		y = libtcod.random_get_int(0, 0, MAP_HEIGHT - h - 1)
		new_room = Rect(x, y, w, h)
		failed = False
		for other_room in rooms:
			if new_room.intersect(other_room):
				failed = True
				break
		if not failed:
			create_room(new_room)
			place_objects(new_room)
			(new_x, new_y) = new_room.center()
			if num_rooms == 0:
				player.x = new_x
				player.y = new_y
			else:
				(prev_x, prev_y) = rooms[num_rooms - 1].center()
				if libtcod.random_get_int(0, 0, 1) == 1:
					create_h_tunnel(prev_x, new_x, prev_y)
					create_v_tunnel(prev_y, new_y, new_x)
				else:
					create_v_tunnel(prev_y, new_y, prev_x)
					create_h_tunnel(prev_x, new_x, new_y)
			rooms.append(new_room)
			num_rooms += 1
	#make some stairs down in the last room
	stairs = Object(new_x, new_y, ">", "stairs", libtcod.white, always_visible = True)
	objects.append(stairs)
	send_to_back(stairs)
	#and now, the stairs back up as well
	up_stairs = Object(player.x, player.y, "<", "up stairs", libtcod.white, always_visible = True)
	objects.append(up_stairs)
	send_to_back(up_stairs)
	#save layout to create a persistent dungeon
	floors.append(map)
			
def render_bar(x, y, total_width, name, value, maximum, bar_color, back_color):
	#HOW DOES THIS WORK??
	#render a bar (HP, experience, etc). first calculate the width of the bar
	bar_width = int(float(value) / maximum * total_width)
	#render the background first
	libtcod.console_set_default_background(panel, back_color)
	libtcod.console_rect(panel, x, y, total_width, 1, False, libtcod.BKGND_SCREEN)
	#now render the bar on top
	libtcod.console_set_default_background(panel, bar_color)
	if bar_width > 0:
		libtcod.console_rect(panel, x, y, bar_width, 1, False, libtcod.BKGND_SCREEN)
	#finally, some centered text with the values
	libtcod.console_set_default_foreground(panel, libtcod.white)
	libtcod.console_print_ex(panel, x + total_width / 2, y, libtcod.BKGND_NONE, libtcod.CENTER, name + ': ' + str(value) + '/' + str(maximum))
	
def render_all():
	global color_light_wall
	global color_light_ground
	global fov_recompute, dungeon_level
	if fov_recompute:
		fov_recompute = False
		libtcod.map_compute_fov(fov_map, player.x, player.y, TORCH_RADIUS, FOV_LIGHT_WALLS, FOV_ALGO)
		for y in range(MAP_HEIGHT):
			for x in range(MAP_WIDTH):
				visible = libtcod.map_is_in_fov(fov_map, x, y)
				wall = map[x][y].block_sight
				if not visible:
					if map[x][y].explored:
						if wall:
							libtcod.console_set_char_background(con, x, y, color_dark_wall, libtcod.BKGND_SET )
						else:
							libtcod.console_set_char_background(con, x, y, color_dark_ground, libtcod.BKGND_SET )
				else:
					if wall:
						libtcod.console_set_char_background(con, x, y, color_light_wall, libtcod.BKGND_SET )
					else:
						libtcod.console_set_char_background(con, x, y, color_light_ground, libtcod.BKGND_SET )
					map[x][y].explored = True
	for object in objects:
		if object != player:
			object.draw()
	player.draw()
	libtcod.console_blit(con, 0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, 0, 0, 0)
	libtcod.console_set_default_background(panel, libtcod.black)
	libtcod.console_clear(panel)
	y = 1
	for (line, color) in game_msgs:
		libtcod.console_set_default_foreground(panel, color)
		libtcod.console_print_ex(panel, MSG_X, y,libtcod.BKGND_NONE, libtcod.LEFT, line)
		y += 1
	render_bar(1, 1, BAR_WIDTH, 'HP', player.fighter.hp, player.fighter.max_hp, libtcod.light_red, libtcod.darker_red)
	#display dungeon level
	libtcod.console_print_ex(panel, 1, 3, libtcod.BKGND_NONE, libtcod.LEFT, 'Dungeon level ' + str(dungeon_level))
	#this part is the calls the mouse look function
	libtcod.console_set_default_foreground(panel, libtcod.light_gray)
	libtcod.console_print_ex(panel, 1, 0, libtcod.BKGND_NONE, libtcod.LEFT, get_names_under_mouse())
	#blit
	libtcod.console_blit(panel, 0, 0, SCREEN_WIDTH, PANEL_HEIGHT, 0, 0, PANEL_Y)
	
def create_room(room):
	global map
	for x in range(room.x1 + 1, room.x2):
		for y in range(room.y1 + 1, room.y2):
			map[x][y].blocked = False
			map[x][y].block_sight = False

def create_h_tunnel(x1,x2,y):
	global map
	for x in range(min(x1,x2), max(x1,x2) + 1):
		map[x][y].blocked = False
		map[x][y].block_sight = False
		
def create_v_tunnel(y1,y2,x):
	global map
	for y in range(min(y1,y2), max(y1,y2) + 1):
		map[x][y].blocked = False
		map[x][y].block_sight = False
		
def place_objects(room):
	global objects
	#placing monsters
	max_monsters = from_dungeon_level([[2, 1], [3, 4], [5, 6]])
	#monster spawn chances
	monster_chances = {}
	monster_chances['orc'] = 80  #orc always shows up, even if all other monsters have 0 chance
	monster_chances['troll'] = from_dungeon_level([[15, 3], [30, 5], [60, 7]])
	#placing items
	max_items = from_dungeon_level([[1, 1], [2, 4]])
	#chance of each item (by default they have a chance of 0 at level 1, which then goes up)
	item_chances = {}
	#consumables
	item_chances['heal'] = 35  #healing potion always shows up, even if all other items have 0 chance
	item_chances['lightning'] = from_dungeon_level([[25, 4]])
	item_chances['fireball'] = from_dungeon_level([[25, 6]])
	item_chances['confuse'] = from_dungeon_level([[10, 2]])
	#equipment
	item_chances['sword'] = from_dungeon_level([[5, 4]])
	item_chances['shield'] = from_dungeon_level([[15, 8]])
	item_chances['helmet'] = from_dungeon_level([[10, 4]])
	item_chances['chain_armor'] = from_dungeon_level([[10, 8]])
	num_monsters = libtcod.random_get_int(0, 0, max_monsters)
	for i in range(num_monsters):
		x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
		y = libtcod.random_get_int(0, room.y1+1, room.y2-1)
		if not is_blocked(x, y):
			ai_component = BasicMonster()
			choice = random_choice(monster_chances)
			if choice == "orc":
				fighter_component = Fighter(hp = 20, defense = 0, power = 5, xp = 35, death_function = monster_death)
				monster = Object(x, y, 'o', "orc", libtcod.desaturated_green, blocks = True, fighter = fighter_component, ai = ai_component)
			elif choice == "troll":
				fighter_component = Fighter(hp = 30, defense = 2, power = 9, xp = 100, death_function = monster_death)
				monster = Object(x, y, 'T', "troll", libtcod.darker_green, blocks = True, fighter = fighter_component, ai = ai_component)
			else:
				pass
			objects.append(monster)
	num_items = libtcod.random_get_int(0, 0, max_items)
	for i in range(num_items):
		#choosing a random spot
		x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
		y = libtcod.random_get_int(0, room.y1+1, room.y2-1)
		#item is placed if the tile is not blocked
		if not is_blocked(x, y):
			choice = random_choice(item_chances)
			if choice == "heal":
				item_component = Item(use_function = cast_heal)
				item = Object(x, y, "!", "potion of healing", libtcod.violet, item = item_component)
			elif choice == "lightning":
				item_component = Item(use_function = cast_lightning)
				item = Object(x, y, "?", "scroll of lightning", libtcod.light_yellow, item = item_component)
			elif choice == "fireball":
				item_component = Item(use_function = cast_fireball)
				item = Object(x, y, "?", "scroll of fireball", libtcod.light_yellow, item = item_component)
			elif choice == "confuse":
				item_component = Item(use_function = cast_confuse)
				item = Object(x, y, "?", "scroll of confuse monster", libtcod.light_yellow, item = item_component)
			elif choice == "sword":
				equipment_component = Equipment(slot = 'right hand', power_bonus = 5)
				item = Object(x, y, ')', 'sword', libtcod.sky, equipment = equipment_component)
			elif choice == "shield":
				equipment_component = Equipment(slot = 'left hand', defense_bonus = 2)
				item = Object(x, y, '[', 'shield', libtcod.darker_orange, equipment = equipment_component)
			elif choice == "helmet":
				equipment_component = Equipment(slot = 'head', defense_bonus = 1)
				item = Object(x, y, '[', 'rusty helmet', libtcod.darker_orange, equipment = equipment_component)
			elif choice == "chain_armor":
				equipment_component = Equipment(slot = 'body', defense_bonus = 2, equipment = equipment_component)
				item = Object(x, y, '[', 'chain mail', libtcod.darker_orange, equipment = equipment_component)
			else:
				pass
			item.always_visible = True
			objects.append(item)
			send_to_back(item)

def is_blocked(x, y):
	global objects
	if map[x][y].blocked:
		return True
	for object in objects:
		if object.blocks and object.x == x and object.y == y:
			return True
	return False

def player_move_or_attack(dx, dy):
	global fov_recompute
	x = player.x + dx
	y = player.y + dy
	target = None
	for object in objects:
		if object.fighter and object.x == x and object.y == y:
			target = object
			break
	if target is not None:
		player.fighter.attack(target)
	else:
		player.move(dx, dy)
		fov_recompute = True
		
def player_death(player):
	global game_state
	message("You are dead.", libtcod.red)
	game_state = 'dead'
	player.char = "%"
	player.color = libtcod.dark_red

def monster_death(monster):
	message(monster.name.capitalize() + ' is dead.', libtcod.orange)
	monster.char = '%'
	monster.color = libtcod.dark_red
	monster.blocks = False
	monster.fighter = None
	monster.ai = None
	monster.name = 'remains of ' + monster.name
	send_to_back(monster)
	
def send_to_back(self):
	global objects
	objects.remove(self)
	objects.insert(0, self)
	
def message(new_msg, color = libtcod.white):
	new_msg_lines = textwrap.wrap(new_msg, MSG_WIDTH)
	for line in new_msg_lines:
		if len(game_msgs) == MSG_HEIGHT:
			del game_msgs[0]
		game_msgs.append((line, color))
		
def get_names_under_mouse():
	global mouse
	(x, y) = (mouse.cx, mouse.cy)
	names = [obj.name for obj in objects if obj.x == x and obj.y == y and libtcod.map_is_in_fov(fov_map, obj.x, obj.y)]
	names = ", ".join(names)
	return names.capitalize()
	
def menu(header, options, width):
	if len(options) > 26: raise ValueError('Cannot have a menu with more than 26 options.') #menu cannot have more than 26 options
	#calculate total height for the header (after auto-wrap) and one line per option
	header_height = libtcod.console_get_height_rect(con, 0, 0, width, SCREEN_HEIGHT, header)
	if header == "":
		header_height = 0
	height = len(options) + header_height
	#creating new window to draw menu
	window = libtcod.console_new(width, height)
	#print header
	libtcod.console_set_default_foreground(window, libtcod.white)
	libtcod.console_print_rect_ex(window, 0, 0, width, height, libtcod.BKGND_NONE, libtcod.LEFT, header)
	#print options
	y = header_height
	letter_index = ord("a")
	for option_text in options:
		text = "(" + chr(letter_index) + ") " + option_text
		libtcod.console_print_ex(window, 0, y, libtcod.BKGND_NONE, libtcod.LEFT, text)
		y += 1
		letter_index += 1
	#blit to main screen
	x = SCREEN_WIDTH/2 - width/2
	y = SCREEN_HEIGHT/2 - height/2
	libtcod.console_blit(window, 0, 0, width, height, 0, x, y, 1.0, 0.7) #last two parameters represent foreground and background transparency, respectively
	#flush and wait for keypress
	libtcod.console_flush()
	key = libtcod.console_wait_for_keypress(True)
	if key.vk == libtcod.KEY_ENTER and key.lalt:
		libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())
	#convert the ASCII code to an index; if it corresponds to an option, return it
	index = key.c - ord('a')
	if index >= 0 and index < len(options): return index
	return None
	
def inventory_menu(header):
	#inventory menu, duh!
	global inventory
	if len(inventory) == 0:
		options = ["Your inventory is empty."]
	else:
		options = []
		for item in inventory:
			text = item.name
			if item.equipment and item.equipment.is_equipped:
			#if it's equipped, then tell the player that
				text = text + ' (' + item.equipment.slot + ')'
			options.append(text)
	index = menu(header, options, INVENTORY_WIDTH)
	#return the item if one was chosen
	if index is None or len(inventory) == 0: return None
	return inventory[index].item
	
def closest_monster(max_range):
	#find the closest monster, within max_range, within FOV
	closest_enemy = None
	closest_dist = max_range + 1 #slightly more than max_range, so that all monsters outside this range are rejected
	for object in objects:
		if object.fighter and not object == player and libtcod.map_is_in_fov(fov_map, object.x, object.y):
			dist = player.distance_to(object)
			if dist < closest_dist:
				#it's closer
				closest_enemy = object
				closest_dist = dist
	return closest_enemy
	
def target_tile(max_range = None):
	#return the coordinates of a left click, or cancel in the event of a right click
	global key, mouse
	while True:
		#re-render the screen. this is necessary to remove the inventory screen (if applicable) and show objects under the mouse
		libtcod.console_flush()
		#absorb any irrelevant key-presses
		libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS|libtcod.EVENT_MOUSE,key,mouse)
		render_all()
		(x, y) = (mouse.cx, mouse.cy)
		if (mouse.lbutton_pressed and libtcod.map_is_in_fov(fov_map, x, y) and (max_range is None or player.distance(x, y) <= max_range)):
			#accept the target if the player clicked in FOV, and in case a range is specified, if it's in that range
			return (x, y)
		if mouse.rbutton_pressed or key.vk == libtcod.KEY_ESCAPE:
			#cancel
			message("Ok, maybe not.", libtcod.white)
			return (None, None)
			
def target_monster(max_range = None):
	#returns a clicked monster inside FOV up to a range, or None if right-clicked
	while True:
		(x, y) = target_tile(max_range)
		if x is None:
			return None
		for obj in objects:
			if obj.x == x and obj.y == y and obj.fighter and obj != player:
				return obj

def cast_heal():
	#heal yourself
	if player.fighter.hp == player.fighter.max_hp:
		message("You are already at full health.")
		return "cancelled"
	message("Your wounds feel better!", libtcod.light_violet)
	player.fighter.heal(HEAL_AMOUNT)

def cast_lightning():
	#shoot a lightning bolt at the nearest enemy
	monster = closest_monster(LIGHTNING_RANGE)
	if monster is None:
		#no enemy has been found within range
		message("There isn't an enemy close enough to strike.", libtcod.red)
		return "cancelled"
	#otherwise, zap the son of a bitch
	message("Lightning lances forth from the scroll to strike the " + monster.name + " for " + str(LIGHTNING_DAMAGE) + " damage!", libtcod.light_blue)
	monster.fighter.take_damage(LIGHTNING_DAMAGE)
	
def cast_confuse():
	#confuse a monster within range, chosen by player
	message('Left-click an enemy to confuse it, or right-click to cancel.', libtcod.light_cyan)
	monster = target_monster(CONFUSE_RANGE)
	if monster is None:
		return "cancelled"
	#otherwise, replace the enemy's AI with ConfusedMonster component
	old_ai = monster.ai
	monster.ai = ConfusedMonster(old_ai)
	monster.ai.owner = monster #set new owner
	message("The " + monster.name + "'s fearsome scowl is replaced by a vacant stare as he begins to stumble around aimlessly.", libtcod.light_green)

def cast_fireball():
	#a ground-targeted AoE attack
	message('Left-click a target tile for the fireball, or right-click to cancel.', libtcod.light_cyan)
	(x, y) = target_tile()
	if x is None: return 'cancelled'
	message('The fireball explodes, burning everything within ' + str(FIREBALL_RADIUS) + ' tiles!', libtcod.orange)
	for obj in objects:  
		#damage every fighter in range, including the player
		if obj.distance(x, y) <= FIREBALL_RADIUS and obj.fighter:
			message('The ' + obj.name + ' gets burned for ' + str(FIREBALL_DAMAGE) + ' hit points.', libtcod.orange)
			obj.fighter.take_damage(FIREBALL_DAMAGE)
			
def new_game():
	global player, inventory, game_msgs, game_state, dungeon_level, player_level, floors, stash
	#make player
	fighter_component = Fighter(hp = 100, defense = 0, power = 1, xp = 0, death_function = player_death)
	player = Object(0, 0, '@', "player", libtcod.white, blocks = True, fighter = fighter_component)
	player_level = 1
	dungeon_level = 1
	#array to keep track of floors
	floors = []
	#array to keep track of objects on each floor
	stash = []
	#make map
	make_map()
	initialize_fov()
	game_state = 'playing'
	inventory = []
	#make messages
	game_msgs = []
	message('Welcome to the dungeon! Prepare yourself, for none have ever returned from this wretched place...')
	#initial equipment: a dagger
	equipment_component = Equipment(slot='right hand', power_bonus=3)
	obj = Object(0, 0, ')', 'dagger', libtcod.sky, equipment = equipment_component)
	inventory.append(obj)
	equipment_component.equip()
	equipment_component = Equipment(slot='body', defense_bonus=1)
	obj = Object(0, 0, '[', 'tunic', libtcod.darker_orange, equipment = equipment_component)
	inventory.append(obj)
	equipment_component.equip()
	obj.always_visible = True
	
def initialize_fov():
	#initialize the FOV
	global fov_recompute, fov_map
	fov_recompute = True
	libtcod.console_clear(con)  #unexplored areas start black (which is the default background color)
	#create FOV map
	fov_map = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
	for y in range(MAP_HEIGHT):
		for x in range(MAP_WIDTH):
			libtcod.map_set_properties(fov_map, x, y, not map[x][y].block_sight, not map[x][y].blocked)
			
def play_game():
	global key, mouse
	player_action = None
	mouse = libtcod.Mouse()
	key = libtcod.Key()
	while not libtcod.console_is_window_closed():
		#render the screen
		libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS | libtcod.EVENT_MOUSE, key, mouse)
		render_all()
		libtcod.console_flush()
		#did the player level up?
		check_level_up()
		#erase objects at old locations, before they move
		for object in objects:
			object.clear()
		#take player input
		player_action = handle_keys()
		if player_action == 'exit':
			save_game()
			break
		#monster turn
		if game_state == 'playing' and player_action != 'didnt-take-turn':
			for object in objects:
				if object.ai:
					object.ai.take_turn()
					
def main_menu():
	img = libtcod.image_load("menu_background.png")
	while not libtcod.console_is_window_closed():
		#show the background image, at twice the regular console resolution
		libtcod.image_blit_2x(img, 0, 0, 0)
		#title and credits
		libtcod.console_set_default_foreground(0, libtcod.light_yellow)
		libtcod.console_print_ex(0, SCREEN_WIDTH/2, SCREEN_HEIGHT/2-4, libtcod.BKGND_NONE, libtcod.CENTER, 'JESUS CHRIST: PATH TO RESSURECTION')
		libtcod.console_print_ex(0, SCREEN_WIDTH/2, SCREEN_HEIGHT-2, libtcod.BKGND_NONE, libtcod.CENTER, 'a game by Peter Rao')
		#show main menu
		choice = menu("", ["Play a new game", "Continue last game", "Quit"], 24)
		if choice == 0:
			#new game
			new_game()
			play_game()
		if choice == 1:
			#load game
			try:
				load_game()
			except:
				msgbox('\n No saved game to load.\n', 24)
				#libtcod.console_wait_for_keypress(True)
				continue
			play_game()
		if choice == 2:
			#quit
			break

def msgbox(text, width=50):
	menu(text, [], width)  #message box for use within menus
	
def next_level():
	#advance to the next level
	global dungeon_level, objects, floors, stash, stairs, up_stairs, map, player
	message('You proceed down the staircase to the next level.', libtcod.light_green)
	#save the objects on the floor, so that we may create a persistent dungeon
	send_to_back(stairs)
	send_to_back(up_stairs)
	#save player state
	current_player = objects[objects.index(player)]
	objects.remove(player)
	try:
		stash[dungeon_level - 1] = objects
	except:
		stash.append(objects)
	floors[dungeon_level - 1] = map
	dungeon_level += 1
	if dungeon_level <= len(floors):
		#load next floor's data
		map = floors[dungeon_level - 1]
		objects = stash[dungeon_level - 1]
		#place the player at the appropriate location
		up_stairs = objects[0]
		stairs = objects[1]
		player = current_player
		player.x = up_stairs.x
		player.y = up_stairs.y
		objects.append(player)
	else:
		make_map()
	initialize_fov()

def prev_level():
	#go up a floor... access the array known as floor
	global dungeon_level, floors, stash, objects, player, up_stairs, stairs, map
	if dungeon_level == 1:
		message('You cannot leave without completing your quest!', libtcod.red)
	else:
		message('You proceed up the staircase to the previous level.', libtcod.light_green)
		#save the floor, so that we may create a persistent dungeon
		send_to_back(stairs)
		send_to_back(up_stairs)
		#save player state
		current_player = objects[objects.index(player)]
		objects.remove(player)
		try:
			stash[dungeon_level - 1] = objects
		except:
			stash.append(objects)
		dungeon_level -= 1
		#load previous floor's data
		map = floors[dungeon_level - 1]
		objects = stash[dungeon_level - 1]
		#place the player at the appropriate location
		up_stairs = objects[0]
		stairs = objects[1]
		player = current_player
		player.x = stairs.x
		player.y = stairs.y
		objects.append(player)
		initialize_fov()	
	
def check_level_up():
	#check if the player has enough xp to level up
	global player_level
	level_up_xp = LEVEL_UP_BASE + player_level * LEVEL_UP_FACTOR
	if player.fighter.xp >= level_up_xp:
		#levelling up
		player_level += 1
		player.fighter.xp -= level_up_xp
		message('Welcome to level ' + str(player_level) + '.', libtcod.yellow)
		choice = None
		while choice == None:
			choice = menu("Level up! Choose a stat to raise:\n",['Constitution (+20 HP, from ' + str(player.fighter.base_max_hp) + ')', 'Strength (+1 attack, from ' + str(player.fighter.base_power) + ')', 'Toughness (+1 defense, from ' + str(player.fighter.base_defense) + ')'], LEVEL_SCREEN_WIDTH)
		if choice == 0:
			player.fighter.base_max_hp += 20
			player.fighter.hp += 20
			message('You feel healthy!', libtcod.yellow)
		elif choice == 1:
			player.fighter.base_power += 1
			message('You feel strong!', libtcod.yellow)
		elif choice == 2:
			player.fighter.base_defense += 1
			message('You feel tough!', libtcod.yellow)
			
def random_choice_index(chances):
	#choose one from a list of choices, returning its index
	dice = libtcod.random_get_int(0, 0, sum(chances))
	#go through all the chances, keeping a running sum
	running_sum = 0
	choice = 0
	for i in chances:
		running_sum += i
		#is this where the "dice" landed?
		if dice <= running_sum:
			return choice
		choice += 1
		
def random_choice(chances_dict):
	#choose one option from dictionary of chances, returning its key
	chances = chances_dict.values()
	strings = chances_dict.keys()
	return strings[random_choice_index(chances)]
	
def from_dungeon_level(table):
	#returns a value that depends on level. the table specifies what value occurs after each level, default is 0
	for (value, level) in reversed(table):
		if dungeon_level >= level:
			return value
	return 0
	
def get_equipped_in_slot(slot):
	#returns the equipment in a slot, or None if it's empty
	for obj in inventory:
		if obj.equipment and obj.equipment.slot == slot and obj.equipment.is_equipped:
			return obj.equipment
	return None
	
def get_all_equipped(obj):
	#return a list of equipped items
	if obj == player:
		equipped_list = []
		for item in inventory:
			if item.equipment and item.equipment.is_equipped:
				equipped_list.append(item.equipment)
		return equipped_list
	else:
		#non-player objects do not carry equipment... yet...
		return []

def save_game():
	#open a new shelve, which is basically a dictionary
	file = shelve.open("savegame", "n")
	file["map"] = map
	file["objects"] = objects
	file["player_index"] = objects.index(player) #store player index rather than the object itself to avoid duplication
	file['up_stairs_index'] = objects.index(up_stairs) #do it again for the up_stairs
	file['stairs_index'] = objects.index(stairs) #same for stairs
	file["inventory"] = inventory
	file['game_msgs'] = game_msgs
	file['game_state'] = game_state
	file['dungeon_level'] = dungeon_level
	file["player_level"] = player_level
	file['floors'] = floors
	file['stash'] = stash
	file.close()
	
def load_game():
	#load that previous shelve
	global map, objects, player, up_stairs, stairs, inventory, game_msgs, game_state, dungeon_level, player_level, floors, stash
	file = shelve.open("savegame", "r")
	map = file["map"]
	objects = file["objects"]
	player = objects[file['player_index']]
	up_stairs = objects[file['up_stairs_index']]
	stairs = objects[file['stairs_index']]
	inventory = file['inventory']
	game_msgs = file['game_msgs']
	game_state = file['game_state']
	dungeon_level = file['dungeon_level']
	player_level = file['player_level']
	floors = file['floors']
	stash = file['stash']
	file.close()
	initialize_fov()
		
libtcod.console_set_custom_font('arial10x10.png', libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_TCOD)
libtcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, 'Path to Ressurection', False)
con = libtcod.console_new(MAP_WIDTH, MAP_HEIGHT)
panel = libtcod.console_new(SCREEN_WIDTH, PANEL_HEIGHT)
libtcod.sys_set_fps(LIMIT_FPS)

main_menu()