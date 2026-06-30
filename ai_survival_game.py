"""
AI SURVIVAL GAME - Godmode Observer
Xem mấy con AI tự đấu nhau, drama, survive, evolve
Dùng Groq API (free)
"""

import os
import random
import time
import json
from groq import Groq
from colorama import init, Fore, Back, Style

init(autoreset=True)

# ========== CONFIG ==========
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")  # Đặt key trong file .env hoặc biến môi trường
MODEL = "llama-3.3-70b-versatile"
DELAY_BETWEEN_TURNS = 1.5  # giây, tránh rate limit
MAX_TURNS = 30

# ========== COLORS cho từng agent ==========
AGENT_COLORS = [
    Fore.RED,
    Fore.CYAN,
    Fore.GREEN,
    Fore.YELLOW,
    Fore.MAGENTA,
]

# ========== AGENT DEFINITIONS ==========
AGENT_TEMPLATES = [
    {
        "name": "Kael",
        "personality": "aggressive warrior, thích combat trực tiếp, kiêu ngạo, không sợ chết",
        "trait": "BERSERKER",
        "color": Fore.RED,
    },
    {
        "name": "Lyra",
        "personality": "cunning rogue, thích backstab, hay nói dối, chỉ tin vào bản thân",
        "trait": "ROGUE",
        "color": Fore.CYAN,
    },
    {
        "name": "Brom",
        "personality": "cautious survivor, tránh combat khi có thể, hay tích trữ đồ, paranoid",
        "trait": "SURVIVOR",
        "color": Fore.GREEN,
    },
    {
        "name": "Zara",
        "personality": "charismatic manipulator, hay dụ dỗ người khác liên minh rồi phản bội",
        "trait": "MANIPULATOR",
        "color": Fore.YELLOW,
    },
    {
        "name": "Drex",
        "personality": "honorable knight, có nguyên tắc, bảo vệ kẻ yếu, ghét kẻ phản bội",
        "trait": "KNIGHT",
        "color": Fore.MAGENTA,
    },
]

# ========== ITEMS ==========
POSSIBLE_ITEMS = [
    "health potion", "iron sword", "wooden shield",
    "poison dagger", "rope trap", "food ration",
    "ancient scroll", "smoke bomb", "steel armor"
]

# ========== MAP ==========
MAP_LOCATIONS = [
    "Dark Forest", "Ruined Castle", "Swamp", 
    "Mountain Pass", "Abandoned Village", "Cave"
]

# ========== AGENT CLASS ==========
class Agent:
    def __init__(self, template, idx):
        self.name = template["name"]
        self.personality = template["personality"]
        self.trait = template["trait"]
        self.color = template["color"]
        self.idx = idx
        
        # Stats
        self.hp = 100
        self.max_hp = 100
        self.attack = random.randint(15, 25)
        self.defense = random.randint(5, 15)
        self.speed = random.randint(1, 10)
        
        # Inventory
        self.items = random.sample(POSSIBLE_ITEMS, 2)
        self.gold = random.randint(10, 50)
        
        # Memory & Relations
        self.memory = []  # list of events nhớ
        self.allies = []  # tên đồng minh
        self.enemies = []  # tên kẻ thù
        self.kills = 0
        self.survived_turns = 0
        
        # Location
        self.location = random.choice(MAP_LOCATIONS)
        
        # Evolution tracking
        self.xp = 0
        self.level = 1
        self.alive = True

    def is_alive(self):
        return self.hp > 0

    def add_memory(self, event):
        self.memory.append(event)
        if len(self.memory) > 8:  # giữ 8 memory gần nhất
            self.memory.pop(0)

    def gain_xp(self, amount):
        self.xp += amount
        if self.xp >= self.level * 50:
            self.level_up()

    def level_up(self):
        self.level += 1
        self.max_hp += 10
        self.hp = min(self.hp + 10, self.max_hp)
        self.attack += 3
        self.defense += 2
        self.xp = 0
        log_system(f"⬆️  {self.name} LEVEL UP! Now Level {self.level} | ATK:{self.attack} DEF:{self.defense} HP:{self.hp}/{self.max_hp}")

    def status_str(self):
        bar_len = 10
        filled = int((self.hp / self.max_hp) * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)
        return f"HP[{bar}]{self.hp}/{self.max_hp} LV{self.level} ATK{self.attack} DEF{self.defense}"

    def to_context(self, all_agents):
        others = []
        for a in all_agents:
            if a.name != self.name and a.is_alive():
                relation = "ALLY" if a.name in self.allies else ("ENEMY" if a.name in self.enemies else "NEUTRAL")
                others.append(f"- {a.name} [{a.trait}] HP:{a.hp}/{a.max_hp} LV{a.level} @ {a.location} | Relation: {relation}")
        
        return f"""
Tên: {self.name} [{self.trait}]
Tính cách: {self.personality}
Stats: HP {self.hp}/{self.max_hp} | LV{self.level} | ATK {self.attack} | DEF {self.defense} | Gold {self.gold}
Items: {', '.join(self.items) if self.items else 'nothing'}
Vị trí: {self.location}
Đồng minh: {', '.join(self.allies) if self.allies else 'none'}
Kẻ thù: {', '.join(self.enemies) if self.enemies else 'none'}
Kills: {self.kills}
Memory gần đây:
{chr(10).join(self.memory[-5:]) if self.memory else '(chưa có gì)'}

Agents còn sống:
{chr(10).join(others)}
"""

# ========== LOGGING ==========
def log_system(msg):
    print(f"\n{Fore.WHITE}{Style.BRIGHT}[SYSTEM] {msg}{Style.RESET_ALL}")

def log_agent(agent, msg):
    print(f"\n{agent.color}{Style.BRIGHT}[{agent.name}]{Style.RESET_ALL} {agent.color}{msg}{Style.RESET_ALL}")

def log_combat(msg):
    print(f"\n{Fore.RED}{Style.BRIGHT}⚔️  {msg}{Style.RESET_ALL}")

def log_drama(msg):
    print(f"\n{Fore.WHITE}{Back.MAGENTA} DRAMA {Style.RESET_ALL} {Fore.MAGENTA}{msg}{Style.RESET_ALL}")

def log_death(msg):
    print(f"\n{Fore.RED}{Back.BLACK}{Style.BRIGHT}💀 {msg} 💀{Style.RESET_ALL}")

def log_separator(turn):
    print(f"\n{Fore.YELLOW}{'='*60}")
    print(f"{Fore.YELLOW}{Style.BRIGHT}  TURN {turn}")
    print(f"{Fore.YELLOW}{'='*60}{Style.RESET_ALL}")

def print_status_board(agents):
    print(f"\n{Fore.CYAN}{'─'*60}")
    print(f"{Fore.CYAN}{Style.BRIGHT}  STATUS BOARD")
    print(f"{Fore.CYAN}{'─'*60}{Style.RESET_ALL}")
    for a in agents:
        if a.is_alive():
            print(f"  {a.color}{Style.BRIGHT}{a.name:<10}{Style.RESET_ALL} {a.color}{a.status_str()} @ {a.location}{Style.RESET_ALL}")
        else:
            print(f"  {Fore.BLACK}{Style.BRIGHT}{a.name:<10} ☠  DEAD{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'─'*60}{Style.RESET_ALL}")

# ========== AI DECISION ==========
def get_ai_decision(client, agent, all_agents, turn):
    alive_others = [a for a in all_agents if a.name != agent.name and a.is_alive()]
    
    prompt = f"""
Bạn là một AI agent đang chơi game survival. Hãy quyết định hành động cho nhân vật này.

=== THÔNG TIN NHÂN VẬT ===
{agent.to_context(all_agents)}

=== LUẬT GAME ===
- Mục tiêu: Survive và trở thành kẻ cuối cùng còn sống, HOẶC đạt level cao nhất
- Mỗi turn bạn chọn 1 action
- Combat: tấn công agent khác (có thể thắng hoặc thua, rủi ro cao)
- Flee: chạy trốn sang location khác (an toàn nhưng mất cơ hội)
- Negotiate: thương lượng với agent khác (lập liên minh, đổi đồ, cảnh báo)
- Scavenge: tìm đồ ở location hiện tại
- Heal: dùng health potion nếu có (hồi 30 HP)
- Betray: phản bội đồng minh (nếu có), tấn công bất ngờ +15 ATK bonus
- Rest: nghỉ ngơi hồi 10 HP nhưng dễ bị tấn công

=== YÊU CẦU RESPONSE ===
Trả về JSON với format sau (CHỈ JSON, không text thêm):
{{
  "action": "combat|flee|negotiate|scavenge|heal|betray|rest",
  "target": "tên agent nếu action là combat/negotiate/betray, null nếu không",
  "reasoning": "lý do quyết định này (1-2 câu, thể hiện tính cách)",
  "dialogue": "1 câu nói to ra miệng (tiếng Anh, đúng tính cách)",
  "emotion": "cảm xúc hiện tại: angry/fearful/confident/suspicious/excited/sad"
}}
"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
            max_tokens=300,
        )
        raw = response.choices[0].message.content.strip()
        
        # Parse JSON
        # Tìm JSON trong response
        start = raw.find('{')
        end = raw.rfind('}') + 1
        if start >= 0 and end > start:
            json_str = raw[start:end]
            return json.loads(json_str)
    except Exception as e:
        log_system(f"API error for {agent.name}: {e}")
    
    # Fallback nếu lỗi
    return {
        "action": random.choice(["combat", "flee", "scavenge", "rest"]),
        "target": alive_others[0].name if alive_others else None,
        "reasoning": "acting on instinct",
        "dialogue": "...",
        "emotion": "neutral"
    }

# ========== COMBAT RESOLUTION ==========
def resolve_combat(attacker, defender, is_betray=False):
    bonus = 15 if is_betray else 0
    
    # Roll dice
    atk_roll = random.randint(1, 20) + attacker.attack + bonus
    def_roll = random.randint(1, 20) + defender.defense
    
    damage = max(0, atk_roll - def_roll)
    
    # Apply damage
    defender.hp -= damage
    
    # XP gain
    attacker.gain_xp(10 + damage)
    
    result = {
        "damage": damage,
        "attacker_won": damage > 0,
        "defender_died": defender.hp <= 0
    }
    
    log_combat(f"{attacker.name} attacks {defender.name}! Roll: {atk_roll} vs {def_roll} → {damage} damage!")
    
    if result["defender_died"]:
        defender.hp = 0
        attacker.kills += 1
        attacker.gold += defender.gold
        if defender.items:
            loot = random.choice(defender.items)
            attacker.items.append(loot)
            defender.items.remove(loot)
        attacker.gain_xp(50)
        log_death(f"{defender.name} has been slain by {attacker.name}!")
        
        # Update memories
        attacker.add_memory(f"Turn: I killed {defender.name}. Gained gold and loot.")
        for a in [attacker]:
            if defender.name in a.allies:
                a.allies.remove(defender.name)
            if defender.name not in a.enemies:
                pass  # đã chết rồi
    else:
        attacker.add_memory(f"I attacked {defender.name}, dealt {damage} damage. They have {defender.hp} HP left.")
        defender.add_memory(f"{attacker.name} attacked me, I lost {damage} HP. They are my enemy now.")
        
        # Auto thêm vào enemies list
        if defender.name not in attacker.enemies:
            attacker.enemies.append(defender.name)
        if attacker.name not in defender.enemies:
            defender.enemies.append(attacker.name)
    
    return result

# ========== PROCESS ACTION ==========
def process_action(agent, decision, all_agents):
    action = decision.get("action", "rest")
    target_name = decision.get("target")
    reasoning = decision.get("reasoning", "")
    dialogue = decision.get("dialogue", "...")
    emotion = decision.get("emotion", "neutral")
    
    emotion_emoji = {
        "angry": "😡", "fearful": "😨", "confident": "😤",
        "suspicious": "🤨", "excited": "😈", "sad": "😞", "neutral": "😐"
    }.get(emotion, "😐")
    
    # Log agent nói gì
    log_agent(agent, f'{emotion_emoji} "{dialogue}"')
    log_agent(agent, f"💭 {reasoning}")
    
    # Tìm target
    target = None
    if target_name:
        target = next((a for a in all_agents if a.name == target_name and a.is_alive()), None)
    
    if action == "combat" and target:
        log_combat(f"{agent.name} charges at {target.name}!")
        resolve_combat(agent, target)
        
    elif action == "betray" and target and target.name in agent.allies:
        log_drama(f"{agent.name} BETRAYS their ally {target.name}!")
        agent.allies.remove(target.name)
        if target.name not in agent.enemies:
            agent.enemies.append(target.name)
        resolve_combat(agent, target, is_betray=True)
        agent.add_memory(f"I betrayed {target.name}. No turning back.")
        target.add_memory(f"{agent.name} BETRAYED me. I will never forget this.")
        
    elif action == "negotiate" and target:
        # Tạo alliance
        if target.name not in agent.allies and target.name not in agent.enemies:
            agent.allies.append(target.name)
            target.allies.append(agent.name)
            log_drama(f"{agent.name} forms an alliance with {target.name}!")
            agent.add_memory(f"I allied with {target.name}.")
            target.add_memory(f"{agent.name} proposed alliance. I accepted.")
        elif target.name in agent.enemies:
            log_agent(agent, f"Tries to negotiate with enemy {target.name}... awkward.")
        else:
            log_agent(agent, f"Reinforces alliance with {target.name}.")
            
    elif action == "scavenge":
        new_item = random.choice(POSSIBLE_ITEMS)
        agent.items.append(new_item)
        gold_found = random.randint(5, 20)
        agent.gold += gold_found
        agent.gain_xp(5)
        log_agent(agent, f"🔍 Scavenges and finds: {new_item} + {gold_found} gold!")
        agent.add_memory(f"Found {new_item} while scavenging at {agent.location}.")
        
    elif action == "heal":
        if "health potion" in agent.items:
            heal_amount = 30
            agent.hp = min(agent.hp + heal_amount, agent.max_hp)
            agent.items.remove("health potion")
            log_agent(agent, f"💊 Uses health potion! Heals {heal_amount} HP → {agent.hp}/{agent.max_hp}")
        else:
            # Không có potion, rest thay
            heal_amount = 8
            agent.hp = min(agent.hp + heal_amount, agent.max_hp)
            log_agent(agent, f"😴 No potion, rests instead. Heals {heal_amount} HP → {agent.hp}/{agent.max_hp}")
            
    elif action == "flee":
        old_loc = agent.location
        agent.location = random.choice([l for l in MAP_LOCATIONS if l != agent.location])
        log_agent(agent, f"🏃 Flees from {old_loc} → {agent.location}")
        agent.add_memory(f"I fled to {agent.location} to avoid danger.")
        
    elif action == "rest":
        heal_amount = 10
        agent.hp = min(agent.hp + heal_amount, agent.max_hp)
        log_agent(agent, f"😴 Rests. Heals {heal_amount} HP → {agent.hp}/{agent.max_hp}")
    
    agent.survived_turns += 1

# ========== RANDOM EVENTS ==========
def random_event(agents):
    alive = [a for a in agents if a.is_alive()]
    if not alive:
        return
    
    events = [
        "plague",      # mất HP ngẫu nhiên
        "treasure",    # random agent tìm được đồ
        "storm",       # tất cả di chuyển ngẫu nhiên
        "none",
        "none",
        "none",
    ]
    
    event = random.choice(events)
    
    if event == "plague" and alive:
        victim = random.choice(alive)
        dmg = random.randint(10, 25)
        victim.hp -= dmg
        log_system(f"☠️  PLAGUE strikes {victim.name} for {dmg} damage! ({victim.hp} HP remaining)")
        victim.add_memory(f"I was hit by a plague and lost {dmg} HP.")
        if victim.hp <= 0:
            victim.hp = 0
            log_death(f"{victim.name} died from the plague!")
            
    elif event == "treasure" and alive:
        lucky = random.choice(alive)
        treasure = random.choice(POSSIBLE_ITEMS)
        gold = random.randint(20, 50)
        lucky.items.append(treasure)
        lucky.gold += gold
        log_system(f"💎 TREASURE! {lucky.name} finds {treasure} and {gold} gold!")
        
    elif event == "storm":
        log_system("🌪️  STORM! All agents are scattered!")
        for a in alive:
            a.location = random.choice(MAP_LOCATIONS)

# ========== MAIN GAME LOOP ==========
def main():
    print(f"""
{Fore.YELLOW}{Style.BRIGHT}
╔═══════════════════════════════════════════════╗
║         AI SURVIVAL GAME - GODMODE            ║
║   Watch AI agents fight, scheme, and evolve   ║
╚═══════════════════════════════════════════════╝
{Style.RESET_ALL}""")

    # Init client
    client = Groq(api_key=GROQ_API_KEY)
    
    # Init agents
    agents = [Agent(template, idx) for idx, template in enumerate(AGENT_TEMPLATES)]
    
    log_system("Agents enter the arena...")
    for a in agents:
        log_agent(a, f"[{a.trait}] HP:{a.hp} ATK:{a.attack} DEF:{a.defense} | Items: {', '.join(a.items)} | Location: {a.location}")
    
    time.sleep(1)
    
    # Game loop
    for turn in range(1, MAX_TURNS + 1):
        alive_agents = [a for a in agents if a.is_alive()]
        
        if len(alive_agents) <= 1:
            break
        
        log_separator(turn)
        print_status_board(agents)
        
        # Random event (20% chance)
        if random.random() < 0.2:
            random_event(agents)
        
        # Mỗi agent ra quyết định
        for agent in alive_agents:
            if not agent.is_alive():
                continue
            
            print(f"\n{agent.color}{'─'*40}{Style.RESET_ALL}")
            print(f"{agent.color}{Style.BRIGHT}  {agent.name}'s turn...{Style.RESET_ALL}")
            
            # Gọi AI
            decision = get_ai_decision(client, agent, agents, turn)
            process_action(agent, decision, agents)
            
            time.sleep(DELAY_BETWEEN_TURNS)
        
        # Kiểm tra người sống sót
        alive_agents = [a for a in agents if a.is_alive()]
        if len(alive_agents) <= 1:
            break
    
    # ===== GAME OVER =====
    print(f"\n{Fore.YELLOW}{Style.BRIGHT}{'='*60}")
    print(f"  GAME OVER - FINAL RESULTS")
    print(f"{'='*60}{Style.RESET_ALL}")
    
    alive_agents = [a for a in agents if a.is_alive()]
    
    if alive_agents:
        winner = max(alive_agents, key=lambda a: a.level * 100 + a.kills * 50 + a.hp)
        log_system(f"🏆 WINNER: {winner.name} [{winner.trait}]")
        log_agent(winner, f"Survived {winner.survived_turns} turns | Kills: {winner.kills} | Level: {winner.level} | Gold: {winner.gold}")
    else:
        log_system("💀 ALL AGENTS ARE DEAD. No winner.")
    
    print(f"\n{Fore.CYAN}=== FINAL STATS ==={Style.RESET_ALL}")
    for a in sorted(agents, key=lambda x: x.kills * 50 + x.level * 30 + x.survived_turns, reverse=True):
        status = "ALIVE 🟢" if a.is_alive() else "DEAD 💀"
        print(f"  {a.color}{a.name:<10}{Style.RESET_ALL} {status} | LV{a.level} | Kills:{a.kills} | Turns survived:{a.survived_turns} | Gold:{a.gold}")

if __name__ == "__main__":
    main()
