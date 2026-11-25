"""A shared, deterministic tabletop for the arm, camera and rehearsal clock."""

import json
import math
from pathlib import Path

from .motion import Point
from .show import HealthBar


class Simulation:
    """Board XY is measured in mm from the bottom left, at each card's pickup point."""

    def __init__(self, width_mm, height_mm, actors: dict[str, Point], health_bars: tuple[HealthBar, ...] = ()):
        if not all(math.isfinite(n) and n > 0 for n in (width_mm, height_mm)):
            raise ValueError("舞台宽、高必须是正数")
        self.width_mm = width_mm
        self.height_mm = height_mm
        self.actors = dict(actors)
        self.health_bars = health_bars
        for point in self.actors.values():
            self._check_point(point)
        self.position = Point(0, 0)
        self.level = "high"
        self.held = None
        self.pump_mode = "release"
        self.time_s = 0.0
        self.events = []
        self.caption = ""
        self._record("start", "排练开始")

    def _check_point(self, point):
        if not (0 <= point.x <= self.width_mm and 0 <= point.y <= self.height_mm):
            raise ValueError(f"坐标超出棋盘范围 {point}")

    def _record(self, action, detail):
        self.events.append({
            "action": action, "detail": detail, "time_s": self.time_s,
            "arm": [self.position.x, self.position.y], "height": self.level,
            "pump": self.pump_mode, "held": self.held, "cue": self.caption,
            "actors": {name: [p.x, p.y] for name, p in self.actors.items()},
            "health": {bar.actor: bar.remaining(self.actors) for bar in self.health_bars},
        })

    def locate(self, actor):
        if actor not in self.actors:
            raise LookupError(f"相机未找到角色 {actor!r}")
        point = self.actors[actor]
        self._record("locate", actor)
        return point

    def move_xy(self, x, y):
        target = Point(x, y)
        self._check_point(target)
        if self.level != "high":
            raise RuntimeError("横移前需要先升高吸盘")
        dx, dy = x - self.position.x, y - self.position.y
        if self.held is not None:
            card = self.actors[self.held]
            destination = Point(card.x + dx, card.y + dy)
            self._check_point(destination)
            self.actors[self.held] = destination
        self.time_s += math.hypot(dx, dy) / 100.0
        self.position = target
        self._record("move_xy", f"({x:g}, {y:g}) mm")

    def push_xy(self, x, y, *, object_at: Point):
        if self.level != "low" or self.held is not None or self.pump_mode != "release":
            raise RuntimeError("纸片推移需要低位、气泵释放且吸盘空载")
        target = Point(x, y)
        self._check_point(target)
        actors = [name for name, p in self.actors.items()
                  if math.hypot(p.x - object_at.x, p.y - object_at.y) <= 1]
        if len(actors) != 1:
            raise RuntimeError(f"推移起点有 {len(actors)} 个可定位物件，应为 1 个")
        actor = actors[0]
        dx, dy = x-self.position.x, y-self.position.y
        card = self.actors[actor]
        destination = Point(card.x+dx, card.y+dy)
        self._check_point(destination)
        self.actors[actor] = destination
        self.position = target
        self.time_s += math.hypot(dx, dy) / 100.0
        self._record("move_xy", f"低位推「{actor}」至 ({x:g}, {y:g}) mm")

    def set_height(self, level):
        if level not in ("high", "low"):
            raise ValueError(f"未知高度 {level!r}")
        if self.level != level:
            self.time_s += 0.25
        self.level = level
        self._record("set_height", level)

    def pump(self, mode):
        if mode not in ("suck", "release", "blow"):
            raise ValueError(f"未知气泵指令 {mode!r}")
        if mode == "suck" and self.held is None:
            if self.level != "low":
                raise RuntimeError("吸取前需要先降低吸盘")
            candidates = [
                name for name, p in self.actors.items()
                if math.hypot(p.x - self.position.x, p.y - self.position.y) <= 1.0
            ]
            if len(candidates) != 1:
                raise RuntimeError(f"吸盘接触范围内有 {len(candidates)} 个吸取点，应为 1 个")
            self.held = candidates[0]
        elif mode in ("release", "blow") and self.held is not None:
            if self.level != "low":
                raise RuntimeError("释放角色前需要先降低吸盘")
            self.held = None
        self.pump_mode = mode
        self._record("pump", mode)

    def wait(self, seconds):
        if not math.isfinite(seconds) or seconds < 0:
            raise ValueError("等待时间必须是非负有限数")
        self.time_s += seconds
        self._record("wait", f"{seconds:g} s")

    def cue(self, text):
        self.caption = text
        self._record("cue", text)

    def write_replay(self, path, cell_mm=25, title="棋盘小剧场", labels=None, cards=None, reserves=None):
        """Write a standalone browser player, with linearly interpolated XY moves."""
        if not math.isfinite(cell_mm) or cell_mm <= 0:
            raise ValueError("格距必须是有限正数")
        bars = [{"name": b.name, "actor": b.actor, "tokens": b.tokens,
                 "origin_mm": [b.origin.x, b.origin.y], "size_mm": [b.size.x, b.size.y]}
                for b in self.health_bars]
        data = {"health_bars": bars, "title": title, "width": self.width_mm, "height": self.height_mm,
                "cell": cell_mm, "labels": labels or {}, "frames": self.events, "cards": cards or {}, "reserves": reserves or []}
        payload = json.dumps(data, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c")
        Path(path).write_text(_PLAYER.replace("/*REPLAY*/", payload), encoding="utf-8")


_PLAYER = """<!doctype html>
<html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>棋盘小剧场</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#162521;color:#f3eece;font:16px/1.5 system-ui,sans-serif}
main{max-width:900px;margin:auto;padding:clamp(12px,3vw,32px)}h1{font:600 clamp(22px,4vw,32px)/1.2 Georgia,serif;margin:0 0 14px}
canvas{width:100%;height:auto;display:block;background:#233c32;border-radius:8px}
#health{display:flex;gap:.65em 1.8em;flex-wrap:wrap;font-weight:600;color:#ffdecd}
#health:not(:empty){margin-top:12px}
#cue{min-height:2em;margin:12px 0 4px;font-size:1.2em}footer{display:flex;align-items:center;gap:12px}
button{border:0;background:#f0c86c;color:#25271f;border-radius:4px;padding:6px 15px;font:inherit}
input{flex:1;min-width:25px;accent-color:#f0c86c}output{font-variant-numeric:tabular-nums}
</style><main><h1></h1><canvas aria-label="机械臂与演员在棋盘上的位置"></canvas>
<div id="health" aria-label="双方剩余血量"></div><p id="cue"></p><footer><button id="play">播放</button><input type="range" aria-label="回放进度" id="seek" min="0" max="10000" step="1" value="0"><output></output></footer>
</main><script type="application/json" id="data">/*REPLAY*/</script><script>
"use strict";
const data=JSON.parse(document.querySelector("#data").textContent);
const frames=data.frames, end=frames[frames.length-1].time_s;
const canvas=document.querySelector("canvas"), ctx=canvas.getContext("2d");
const button=document.querySelector("#play"), seek=document.querySelector("#seek");
document.title=document.querySelector("h1").textContent=data.title;
const pad=44, scale=Math.min(760/data.width,480/data.height);
const w=data.width*scale,h=data.height*scale;
canvas.width=Math.ceil(w)+pad*2;canvas.height=Math.ceil(h)+pad*2;
seek.disabled=end===0;
let t=0,running=false,last=0;
const color=["#f7c566","#f09387","#77d8d2","#cbc0ef"];
const artwork=new Map();
for(const [id,card] of Object.entries(data.cards)){
  if(!card.image)continue;
  const img=new Image();artwork.set(id,img);img.onload=()=>draw();img.src=card.image;
}
const healthTokens=new Set(data.health_bars.flatMap(bar=>bar.tokens));
const scoreLabels=data.health_bars.map(()=>{
  const label=document.createElement("span");document.querySelector("#health").append(label);return label;
});
function dot(x,y,r,fill){ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.fillStyle=fill;ctx.fill()}
function draw(){
  let i=0;while(i+1<frames.length && frames[i+1].time_s<=t)i++;
  const f=frames[i],n=frames[i+1];
  const s=n && n.action==="move_xy"?(t-f.time_s)/(n.time_s-f.time_s):0;
  const mix=(a,b)=>[a[0]+(b[0]-a[0])*s,a[1]+(b[1]-a[1])*s];
  const xy=([x,y])=>[pad+x*scale,pad+h-y*scale];
  const actorPosition=id=>mix(f.actors[id],n?n.actors[id]:f.actors[id]);
  ctx.clearRect(0,0,canvas.width,canvas.height);ctx.fillStyle="#3e5747";ctx.fillRect(pad,pad,w,h);
  const cell=data.cell*scale;
  // Draw individual cells only while they are large enough to resolve on this canvas.
  if(cell>=3){
    for(let row=0;row*cell<h;row++){
      for(let col=row%2;col*cell<w;col+=2){
        const ch=Math.min(cell,h-row*cell);
        ctx.fillStyle="#50674f";ctx.fillRect(pad+col*cell,pad+h-row*cell-ch,Math.min(cell,w-col*cell),ch);
      }
    }
  }
  for(const zone of data.reserves){
    const [x,y]=zone.origin_mm,[zw,zh]=zone.size_mm;
    const left=pad+x*scale, top=pad+h-(y+zh)*scale;
    ctx.save();ctx.setLineDash([5,4]);ctx.strokeStyle="#e4c67a";ctx.strokeRect(left,top,zw*scale,zh*scale);
    ctx.font="12px sans-serif";ctx.textAlign="left";ctx.fillStyle="#f8e4a6";ctx.fillText(zone.name,left+4,top+14);ctx.restore();
  }
  data.health_bars.forEach((bar,index)=>{
    const [x,y]=bar.origin_mm,[width,height]=bar.size_mm;
    const [left,top]=xy([x,y+height]);
    ctx.strokeStyle="#f3bab5";ctx.lineWidth=2;ctx.strokeRect(left,top,width*scale,height*scale);
    const hp=bar.tokens.filter(id=>{
      const [px,py]=actorPosition(id);return px>=x&&px<=x+width&&py>=y&&py<=y+height;
    }).length;
    scoreLabels[index].textContent=bar.actor+" "+hp+" / "+bar.tokens.length+(hp===0?"（血量耗尽）":"");
  });
  ctx.font="14px sans-serif";ctx.fillStyle="#d7dfcc";ctx.textAlign="center";
  ctx.fillText("0",pad,pad+h+22);ctx.fillText(data.width+" mm  X",pad+w-15,pad+h+22);
  ctx.fillText("Y  "+data.height+" mm",pad+10,pad-12);
  let k=0;
  for(const id of Object.keys(f.actors)){
    const [x,y]=xy(actorPosition(id));
    const art=artwork.get(id),card=data.cards[id];
    if(art && art.naturalWidth){
      const [width,height]=card.print_size_mm;
      const [mx,my]=card.marker_offset_mm??[0,0];
      const [dx,dy]=card.pickup_offset_mm;
      const factor=scale*Math.min(width/art.naturalWidth,height/art.naturalHeight);
      const aw=art.naturalWidth*factor,ah=art.naturalHeight*factor;
      ctx.drawImage(art,x-(dx+mx)*scale-aw/2,y+(dy+my)*scale-ah/2,aw,ah);
    }else if(healthTokens.has(id)){
      const [width,height]=card?.print_size_mm??[16,16];
      ctx.fillStyle="#e8423a";ctx.fillRect(x-width*scale/2,y-height*scale/2,width*scale,height*scale);
    }else{dot(x,y,12,color[k++%color.length])}
    if(healthTokens.has(id))continue;
    ctx.font="bold 15px sans-serif";ctx.lineWidth=4;ctx.strokeStyle="#203629";ctx.textAlign="center";
    const label=data.labels[id]??id;
    const lx=Math.max(30,Math.min(canvas.width-30,x)),ly=y+((y-pad<25)?29:-18);
    ctx.strokeText(label,lx,ly);ctx.fillStyle="#fff6dc";ctx.fillText(label,lx,ly);
  }
  const [x,y]=xy(mix(f.arm,n?n.arm:f.arm)),radius=f.height==="high"?18:12;
  ctx.strokeStyle="#fff8db";ctx.lineWidth=2;ctx.beginPath();ctx.arc(x,y,radius,0,Math.PI*2);ctx.stroke();
  ctx.beginPath();ctx.moveTo(x-5,y);ctx.lineTo(x+5,y);ctx.moveTo(x,y-5);ctx.lineTo(x,y+5);ctx.stroke();
  document.querySelector("#cue").textContent=f.cue||"排练就绪";
  document.querySelector("output").textContent=t.toFixed(1)+" / "+end.toFixed(1)+" s";
  seek.value=end?Math.round(t/end*10000):0;seek.setAttribute("aria-valuetext",t.toFixed(1)+" 秒");
}
function tick(now){
  if(!running)return;
  t=Math.min(end,t+(now-last)/1000);last=now;draw();
  if(t>=end){running=false;button.textContent="重播"}else{raf=requestAnimationFrame(tick)}
}
let raf=0;
button.onclick=()=>{
  if(running){running=false;cancelAnimationFrame(raf);button.textContent="播放";return}
  if(t>=end)t=0;running=true;button.textContent="暂停";last=performance.now();raf=requestAnimationFrame(tick);
};
seek.oninput=()=>{
  t=Number(seek.value)/10000*end;last=performance.now();
  if(!running)button.textContent=t===end?"重播":"播放";draw();
};
draw();
</script></html>"""
