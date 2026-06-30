"""
AI SURVIVAL GAME - Web UI Version
Flask server + real-time log streaming
"""
import json
import os
import random
import time
import threading
import queue
from flask import Flask, render_template, Response, jsonify, request
from groq import Groq

# ========== CONFIG ==========
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")  # Đặt key trong file .env hoặc biến môi trường
MODEL = "llama-3.3-70b-versatile"
TURN_DELAY = 3.0  # giây giữa mỗi turn
MAX_TURNS = 30

app = Flask(__name__)
log_queue = queue.Queue()
game_state = {"running": False, "paused": False, "turn": 0, "agents": [], "log": []}
game_thread = None

# ========== AGENT TEMPLATES ==========
AGENT_TEMPLATES = [
    {"name": "Kael",  "personality": "chiến binh hung hãn, thích đánh trực tiếp, kiêu ngạo, không sợ chết", "trait": "CHIẾN BINH", "color": "#ff4444"},
    {"name": "Lyra",  "personality": "kẻ trộm xảo quyệt, thích đâm sau lưng, hay nói dối, chỉ tin bản thân", "trait": "SÁT THỦ",   "color": "#44ddff"},
    {"name": "Brom",  "personality": "kẻ sinh tồn thận trọng, tránh chiến đấu khi có thể, hay tích trữ đồ, paranoid", "trait": "SINH TỒN", "color": "#44ff88"},
    {"name": "Zara",  "personality": "kẻ thao túng duyên dáng, hay dụ dỗ liên minh rồi phản bội", "trait": "MƯU SĨ",   "color": "#ffdd44"},
    {"name": "Drex",  "personality": "hiệp sĩ danh dự, có nguyên tắc, bảo vệ kẻ yếu, ghét kẻ phản bội", "trait": "HIỆP SĨ",  "color": "#dd88ff"},
]

MAP_LOCATIONS = ["Rừng Tối", "Lâu Đài Hoang", "Đầm Lầy", "Đèo Núi", "Làng Bỏ Hoang", "Hang Động"]
POSSIBLE_ITEMS = ["bình hồi máu", "kiếm sắt", "khiên gỗ", "dao độc", "bẫy dây", "lương thực", "cuộn giấy cổ", "bom khói", "giáp thép"]

# ========== AGENT CLASS ==========
class Agent:
    def __init__(self, t, idx):
        self.name = t["name"]
        self.personality = t["personality"]
        self.trait = t["trait"]
        self.color = t["color"]
        self.hp = 100
        self.max_hp = 100
        self.attack = random.randint(15, 25)
        self.defense = random.randint(5, 15)
        self.items = random.sample(POSSIBLE_ITEMS, 2)
        self.gold = random.randint(10, 50)
        self.memory = []
        self.allies = []
        self.enemies = []
        self.kills = 0
        self.survived_turns = 0
        self.location = random.choice(MAP_LOCATIONS)
        self.xp = 0
        self.level = 1
        self.alive = True
        self.last_action = ""
        self.last_dialogue = ""
        self.emotion = "bình thản"

    def is_alive(self): return self.hp > 0

    def add_memory(self, e):
        self.memory.append(e)
        if len(self.memory) > 8: self.memory.pop(0)

    def gain_xp(self, amt):
        self.xp += amt
        if self.xp >= self.level * 50:
            self.level += 1
            self.max_hp += 10
            self.hp = min(self.hp + 10, self.max_hp)
            self.attack += 3
            self.defense += 2
            self.xp = 0
            push_log("levelup", f"⬆️ {self.name} lên cấp {self.level}! ATK:{self.attack} DEF:{self.defense}", self.name, extra={"level": self.level, "attack": self.attack, "defense": self.defense})

    def to_dict(self):
        return {
            "name": self.name, "trait": self.trait, "color": self.color,
            "hp": self.hp, "max_hp": self.max_hp, "level": self.level,
            "attack": self.attack, "defense": self.defense,
            "gold": self.gold, "kills": self.kills,
            "location": self.location, "alive": self.is_alive(),
            "allies": self.allies, "enemies": self.enemies,
            "items": self.items, "survived_turns": self.survived_turns,
            "last_action": self.last_action,
            "last_dialogue": self.last_dialogue,
            "emotion": self.emotion,
        }

    def to_context(self, all_agents):
        others = []
        for a in all_agents:
            if a.name != self.name and a.is_alive():
                rel = "ĐỒNG MINH" if a.name in self.allies else ("KẺ THÙ" if a.name in self.enemies else "TRUNG LẬP")
                others.append(f"- {a.name} [{a.trait}] HP:{a.hp}/{a.max_hp} Cấp{a.level} @ {a.location} | Quan hệ: {rel}")
        return f"""
Tên: {self.name} [{self.trait}] | Tính cách: {self.personality}
Stats: HP {self.hp}/{self.max_hp} | Cấp {self.level} | ATK {self.attack} | DEF {self.defense} | Vàng {self.gold}
Đồ: {', '.join(self.items) if self.items else 'trống'}
Vị trí: {self.location}
Đồng minh: {', '.join(self.allies) if self.allies else 'không có'}
Kẻ thù: {', '.join(self.enemies) if self.enemies else 'không có'}
Số lần giết: {self.kills}
Ký ức gần đây:
{chr(10).join(self.memory[-5:]) if self.memory else '(chưa có gì)'}
Các nhân vật còn sống:
{chr(10).join(others)}
"""

# ========== LOG PUSH ==========
def push_log(type_, msg, agent_name=None, extra=None):
    entry = {"type": type_, "msg": msg, "agent": agent_name, "extra": extra or {}, "time": time.strftime("%H:%M:%S")}
    game_state["log"].append(entry)
    log_queue.put(entry)

# ========== AI DECISION ==========
def get_ai_decision(client, agent, all_agents):
    alive_others = [a for a in all_agents if a.name != agent.name and a.is_alive()]
    prompt = f"""
Bạn đang đóng vai một nhân vật trong game sinh tồn. Hãy quyết định hành động.

{agent.to_context(all_agents)}

CÁC HÀNH ĐỘNG CÓ THỂ:
- combat: tấn công một nhân vật khác
- flee: chạy trốn sang địa điểm khác
- negotiate: thương lượng / lập liên minh với nhân vật khác
- scavenge: tìm đồ ở địa điểm hiện tại
- heal: dùng bình hồi máu nếu có
- betray: phản bội đồng minh, tấn công bất ngờ (+15 ATK)
- rest: nghỉ ngơi hồi 10 HP

Trả về JSON (CHỈ JSON, không thêm text):
{{
  "action": "combat|flee|negotiate|scavenge|heal|betray|rest",
  "target": "tên nhân vật nếu cần, null nếu không",
  "reasoning": "lý do quyết định (1-2 câu tiếng Việt, đúng tính cách nhân vật)",
  "dialogue": "1 câu nhân vật nói ra (tiếng Việt, đúng tính cách)",
  "emotion": "tức giận|sợ hãi|tự tin|nghi ngờ|hưng phấn|buồn bã|bình thản"
}}
"""
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9, max_tokens=300,
        )
        raw = resp.choices[0].message.content.strip()
        s, e = raw.find('{'), raw.rfind('}') + 1
        if s >= 0 and e > s:
            return json.loads(raw[s:e])
    except Exception as ex:
        push_log("system", f"Lỗi API cho {agent.name}: {ex}")
    return {
        "action": random.choice(["combat", "flee", "scavenge", "rest"]),
        "target": alive_others[0].name if alive_others else None,
        "reasoning": "hành động theo bản năng",
        "dialogue": "...",
        "emotion": "bình thản"
    }

# ========== COMBAT ==========
def resolve_combat(attacker, defender, is_betray=False):
    bonus = 15 if is_betray else 0
    atk_roll = random.randint(1, 20) + attacker.attack + bonus
    def_roll = random.randint(1, 20) + defender.defense
    damage = max(0, atk_roll - def_roll)
    defender.hp -= damage
    attacker.gain_xp(10 + damage)

    push_log("combat", f"{attacker.name} tấn công {defender.name}! Tung xúc xắc: {atk_roll} vs {def_roll} → {damage} sát thương!", attacker.name, extra={"attacker": attacker.name, "defender": defender.name, "damage": damage, "is_betray": is_betray, "location": attacker.location})

    if defender.hp <= 0:
        defender.hp = 0
        attacker.kills += 1
        attacker.gold += defender.gold
        if defender.items:
            loot = random.choice(defender.items)
            attacker.items.append(loot)
            defender.items.remove(loot)
        attacker.gain_xp(50)
        push_log("death", f"{defender.name} đã bị {attacker.name} tiêu diệt! Mất {damage} máu.", defender.name, extra={"victim": defender.name, "killer": attacker.name, "location": defender.location})
        attacker.add_memory(f"Tôi đã giết {defender.name}. Lấy được vàng và đồ.")
        defender.add_memory(f"Tôi đã bị {attacker.name} giết.")
    else:
        attacker.add_memory(f"Tôi tấn công {defender.name}, gây {damage} sát thương. Họ còn {defender.hp} HP.")
        defender.add_memory(f"{attacker.name} tấn công tôi, tôi mất {damage} HP. Họ là kẻ thù của tôi.")
        if defender.name not in attacker.enemies: attacker.enemies.append(defender.name)
        if attacker.name not in defender.enemies: defender.enemies.append(attacker.name)

# ========== PROCESS ACTION ==========
def process_action(agent, decision, all_agents):
    action = decision.get("action", "rest")
    target_name = decision.get("target")
    reasoning = decision.get("reasoning", "")
    dialogue = decision.get("dialogue", "...")
    emotion = decision.get("emotion", "bình thản")

    agent.last_action = action
    agent.last_dialogue = dialogue
    agent.emotion = emotion

    emotion_emoji = {"tức giận":"😡","sợ hãi":"😨","tự tin":"😤","nghi ngờ":"🤨","hưng phấn":"😈","buồn bã":"😞","bình thản":"😐"}.get(emotion,"😐")

    push_log("dialogue", f'{emotion_emoji} "{dialogue}"', agent.name)
    push_log("thought", f'💭 {reasoning}', agent.name)

    target = next((a for a in all_agents if a.name == target_name and a.is_alive()), None) if target_name else None

    if action == "combat" and target:
        push_log("action", f"{agent.name} lao vào tấn công {target.name}!", agent.name, extra={"action": "combat", "target": target.name, "location": agent.location})
        resolve_combat(agent, target)

    elif action == "betray" and target and target.name in agent.allies:
        push_log("drama", f"🗡️ {agent.name} PHẢN BỘI đồng minh {target.name}!", agent.name, extra={"drama_type": "betrayal", "attacker": agent.name, "defender": target.name, "location": agent.location})
        agent.allies.remove(target.name)
        if target.name not in agent.enemies: agent.enemies.append(target.name)
        resolve_combat(agent, target, is_betray=True)
        agent.add_memory(f"Tôi đã phản bội {target.name}. Không thể quay đầu.")
        target.add_memory(f"{agent.name} đã PHẢN BỘI tôi. Tôi sẽ không bao giờ quên.")

    elif action == "negotiate" and target:
        if target.name not in agent.allies and target.name not in agent.enemies:
            agent.allies.append(target.name)
            target.allies.append(agent.name)
            push_log("drama", f"🤝 {agent.name} kết minh với {target.name}!", agent.name, extra={"drama_type": "alliance", "agent1": agent.name, "agent2": target.name, "location": agent.location})
            agent.add_memory(f"Tôi đã kết minh với {target.name}.")
            target.add_memory(f"{agent.name} đề nghị liên minh. Tôi chấp nhận.")
        else:
            push_log("action", f"{agent.name} cố thương lượng với {target.name}...", agent.name, extra={"action": "negotiate_fail", "target": target.name, "location": agent.location})

    elif action == "scavenge":
        item = random.choice(POSSIBLE_ITEMS)
        gold = random.randint(5, 20)
        agent.items.append(item)
        agent.gold += gold
        agent.gain_xp(5)
        push_log("action", f"🔍 {agent.name} lục lọ và tìm được: {item} + {gold} vàng!", agent.name, extra={"action": "scavenge", "item": item, "gold": gold, "location": agent.location})
        agent.add_memory(f"Tìm được {item} khi lục lọ tại {agent.location}.")

    elif action == "heal":
        if "bình hồi máu" in agent.items:
            agent.hp = min(agent.hp + 30, agent.max_hp)
            agent.items.remove("bình hồi máu")
            push_log("action", f"💊 {agent.name} dùng bình hồi máu! HP → {agent.hp}/{agent.max_hp}", agent.name, extra={"action": "heal", "amount": 30, "hp": agent.hp, "max_hp": agent.max_hp, "location": agent.location})
        else:
            agent.hp = min(agent.hp + 8, agent.max_hp)
            push_log("action", f"😴 {agent.name} không có bình, nghỉ ngơi. HP → {agent.hp}/{agent.max_hp}", agent.name, extra={"action": "rest", "amount": 8, "hp": agent.hp, "max_hp": agent.max_hp, "location": agent.location})

    elif action == "flee":
        old = agent.location
        agent.location = random.choice([l for l in MAP_LOCATIONS if l != agent.location])
        push_log("action", f"🏃 {agent.name} bỏ chạy từ {old} → {agent.location}", agent.name, extra={"action": "flee", "from": old, "to": agent.location, "location": agent.location})
        agent.add_memory(f"Tôi bỏ chạy đến {agent.location} để tránh nguy hiểm.")

    else:
        agent.hp = min(agent.hp + 10, agent.max_hp)
        push_log("action", f"😴 {agent.name} nghỉ ngơi. HP → {agent.hp}/{agent.max_hp}", agent.name, extra={"action": "rest", "amount": 10, "hp": agent.hp, "max_hp": agent.max_hp, "location": agent.location})

    agent.survived_turns += 1

# ========== RANDOM EVENTS ==========
def random_event(agents):
    alive = [a for a in agents if a.is_alive()]
    if not alive: return
    ev = random.choice(["dịch bệnh","kho báu","bão","không có","không có","không có"])
    if ev == "dịch bệnh":
        v = random.choice(alive)
        d = random.randint(10, 25)
        v.hp -= d
        push_log("event", f"☠️ DỊCH BỆNH tấn công {v.name}, mất {d} HP! (còn {v.hp} HP)", v.name, extra={"event": "plague", "target": v.name, "damage": d, "location": v.location})
        v.add_memory(f"Tôi bị dịch bệnh tấn công và mất {d} HP.")
        if v.hp <= 0:
            v.hp = 0
            push_log("death", f"{v.name} chết vì dịch bệnh!", v.name, extra={"victim": v.name, "killer": "plague", "location": v.location})
    elif ev == "kho báu":
        lucky = random.choice(alive)
        item = random.choice(POSSIBLE_ITEMS)
        gold = random.randint(20, 50)
        lucky.items.append(item)
        lucky.gold += gold
        push_log("event", f"💎 KHO BÁU! {lucky.name} tìm được {item} và {gold} vàng!", lucky.name, extra={"event": "treasure", "target": lucky.name, "item": item, "gold": gold, "location": lucky.location})
    elif ev == "bão":
        push_log("event", "🌪️ BÃO! Tất cả nhân vật bị phân tán!", extra={"event": "storm"})
        for a in alive:
            a.location = random.choice(MAP_LOCATIONS)

# ========== GAME LOOP (chạy trong thread) ==========
def game_loop():
    client = Groq(api_key=GROQ_API_KEY)
    agents = [Agent(t, i) for i, t in enumerate(AGENT_TEMPLATES)]
    game_state["agents"] = agents

    push_log("system", "⚔️  TRÒ CHƠI BẮT ĐẦU! Các nhân vật bước vào đấu trường...")
    for a in agents:
        push_log("system", f"  {a.name} [{a.trait}] HP:{a.hp} ATK:{a.attack} DEF:{a.defense} | Đồ: {', '.join(a.items)} | Vị trí: {a.location}", a.name)

    for turn in range(1, MAX_TURNS + 1):
        alive = [a for a in agents if a.is_alive()]
        if len(alive) <= 1:
            break

        game_state["turn"] = turn
        push_log("turn", f"===== LƯỢT {turn} | Còn {len(alive)} nhân vật =====")

        if random.random() < 0.2:
            random_event(agents)

        for agent in alive:
            if not agent.is_alive(): continue

            # Đợi nếu pause
            while game_state["paused"]:
                time.sleep(0.5)

            if not game_state["running"]: return

            push_log("agent_turn", f"Đến lượt {agent.name}...", agent.name)
            decision = get_ai_decision(client, agent, agents)
            process_action(agent, decision, agents)

            # Gửi state update
            log_queue.put({"type": "state_update", "agents": [a.to_dict() for a in agents]})
            time.sleep(TURN_DELAY)

    # Kết thúc
    alive = [a for a in game_state["agents"] if a.is_alive()]
    push_log("gameover", "🏁 TRÒ CHƠI KẾT THÚC!")
    if alive:
        winner = max(alive, key=lambda a: a.level * 100 + a.kills * 50 + a.hp)
        push_log("gameover", f"🏆 NGƯỜI CHIẾN THẮNG: {winner.name} [{winner.trait}] | Cấp {winner.level} | Kills: {winner.kills}")
    else:
        push_log("gameover", "💀 TẤT CẢ ĐÃ CHẾT. Không có người chiến thắng.")
    game_state["running"] = False

# ========== FLASK ROUTES ==========
@app.route("/")
def index():
    return render_template("game.html")

@app.route("/set_speed", methods=["POST"])
def set_speed():
    global TURN_DELAY
    try:
        data = request.get_json()
        speed = float(data.get("speed", 3.0))
        # Giới hạn tốc độ từ 0.5s đến 10.0s
        TURN_DELAY = max(0.5, min(10.0, speed))
        return jsonify({"status": "success", "speed": TURN_DELAY})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route("/start", methods=["POST"])
def start_game():
    global game_thread
    if game_state["running"]:
        return jsonify({"status": "already running"})
    game_state["running"] = True
    game_state["paused"] = False
    game_state["turn"] = 0
    game_state["log"] = []
    while not log_queue.empty(): log_queue.get()
    game_thread = threading.Thread(target=game_loop, daemon=True)
    game_thread.start()
    return jsonify({"status": "started"})

@app.route("/pause", methods=["POST"])
def pause_game():
    game_state["paused"] = not game_state["paused"]
    return jsonify({"paused": game_state["paused"]})

@app.route("/stop", methods=["POST"])
def stop_game():
    game_state["running"] = False
    game_state["paused"] = False
    return jsonify({"status": "stopped"})

@app.route("/state")
def get_state():
    agents = [a.to_dict() for a in game_state["agents"]] if game_state["agents"] else []
    return jsonify({"turn": game_state["turn"], "running": game_state["running"], "paused": game_state["paused"], "agents": agents})

@app.route("/stream")
def stream():
    def event_gen():
        while True:
            try:
                item = log_queue.get(timeout=30)
                yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
            except:
                yield f"data: {json.dumps({'type':'ping'})}\n\n"
    return Response(event_gen(), mimetype="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

if __name__ == "__main__":
    print("🎮 AI Survival Game đang chạy tại http://localhost:5000")
    app.run(debug=False, threaded=True, port=5000)
