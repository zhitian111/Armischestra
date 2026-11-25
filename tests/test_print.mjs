import assert from "node:assert/strict";
import {test} from "node:test";
import {printPages} from "../editor/print.js";

const makeBundle = () => ({
  stage:{size_mm:[300,200],cell_mm:25,actors:{Kit:{marker_id:0,print_size_mm:[75,50],pickup_offset_mm:[15,-3],image:null}}},
  show:{title:"A & B"}
});

test("A4 board sheets carry adjacent measured bounds; A3 landscape keeps the whole stage",()=>{
  const bundle = makeBundle();
  const a4 = printPages(bundle, {paper:"A4",orientation:"portrait",content:"board"});
  assert.deepEqual(a4.map(p=>p.filename),["board-r1-c1.svg","board-r1-c2.svg"]);
  assert.match(a4[0].svg,/width="210mm" height="297mm"/);
  assert.match(a4[0].svg,/X 0–150 mm/);
  assert.match(a4[1].svg,/X 150–300 mm/);
  const a3 = printPages(bundle,{paper:"A3",orientation:"landscape",content:"all"});
  assert.deepEqual(a3.map(p=>p.filename),["board-r1-c1.svg","actors-1.svg"]);
  assert.match(a3[0].svg,/width="420mm" height="297mm"/);
  assert.match(a3[0].svg,/A &amp; B/);
});

test("cards get additional pages instead of shrinking; invalid physical sizes report the actor",()=>{
  const bundle = makeBundle(), actors = bundle.stage.actors;
  for (let i=0; i<5; ++i)
    actors["大卡"+i] = {marker_id:i+1,print_size_mm:[150,110],pickup_offset_mm:[0,0],image:null};
  assert.equal(printPages(bundle, {content:"actors"}).length,3);
  actors.Kit.print_size_mm=[300,200];
  assert.throws(()=>printPages(bundle,{content:"actors"}), /Kit.*放不下/);
  actors.Kit.print_size_mm=[60,40]; actors.Kit.pickup_offset_mm=[35,0];
  assert.throws(()=>printPages(bundle,{content:"actors"}), /Kit.*吸取点/);
});

test("offsets use card-centered XY in millimetres for both direct print and cut-out labels",()=>{
  const bundle = makeBundle(), card = bundle.stage.actors.Kit;
  card.marker_offset_mm = [-8,10];
  // At this card's top-left (12,20), the tag center is (41.5,35); black frame starts 9 mm earlier.
  const [direct] = printPages(bundle,{content:"actors"});
  assert.match(direct.svg,/translate\(32.5 26\) scale\(3\)/);
  const [art, tags] = printPages(bundle,{content:"actors",separateMarkers:true});
  assert.doesNotMatch(art.svg,/crispEdges/);
  assert.deepEqual([art.filename,tags.filename],["actors-1.svg","markers-1.svg"]);
  assert.match(tags.svg,/图心 → 标记  \(-8, 10\) mm/);
  assert.match(tags.svg,/标记 → 吸点  \(15, -3\) mm/);
  card.marker_offset_mm = [26,0];
  assert.throws(()=>printPages(bundle), /标记或白边/);
  card.marker_offset_mm = [20,0]; card.pickup_offset_mm = [18,0];
  assert.throws(()=>printPages(bundle), /吸取点超出/);
});


test("A5 and A2 retain ISO dimensions in both orientations",()=>{
  for (const [paper,width,height] of [["A5",148,210],["A2",420,594]]) {
    for (const landscape of [false,true]) {
      const pages = printPages(makeBundle(), {paper, orientation:landscape?"landscape":"portrait", content:"board"});
      const expected = landscape ? [height,width] : [width,height];
      for (const p of pages) assert.deepEqual([p.width,p.height],expected);
      assert.equal(paper==="A5" ? pages.length>1 : pages.length===1,true);
    }
  }
});

test("reserve overlays cross paper seams and prop markers identify measured preset positions",()=>{
  const bundle=makeBundle(), stage=bundle.stage;
  stage.reserves=[{name:"火焰 & 刀光",origin_mm:[130,10],size_mm:[60,30]}];
  stage.actors.Kit.kind="prop";stage.actors.Kit.start_mm=[160,20];
  const [left,right,cards]=printPages(bundle,{paper:"A4",orientation:"portrait"});
  assert.match(left.svg,/x="130" y="160" width="60" height="30"/);
  assert.match(right.svg,/x="-20" y="160" width="60" height="30"/);
  assert.match(right.svg,/火焰 &amp; 刀光/);
  assert.match(right.svg,/translate\(10 180\)/);
  assert.doesNotMatch(left.svg,/>ID 0<\/text>/);
  assert.match(cards.svg,/道具 · Kit · ID 0/);
  assert.match(cards.svg,/预置吸点 160, 20 mm/);
});

test("physical HP areas keep the board unfilled; marked red cards retain a visible border",()=>{
  const b=makeBundle(); b.stage.actors.Hunter={...b.stage.actors.Kit,marker_id:3};
  b.stage.actors.heart={kind:"prop",start_mm:[145,25],print_size_mm:[24,24],marker_id:23,image:null,pickup_offset_mm:[0,0]};
  b.stage.health_bars=[{name:"生命格",actor:"Hunter",origin_mm:[130,10],size_mm:[60,30],tokens:["heart"]}];
  const pages=printPages(b,{content:"all"});
  for(const p of pages.filter(p=>p.filename.startsWith('board'))){
    assert.match(p.svg,/生命格 · Hunter · 1 格/);
    assert.match(p.svg,/width="60" height="30" fill="none" stroke="#ae3235"/);
  }
  const art=pages.find(p=>p.filename.startsWith('actors')).svg;
  assert.match(art,/width="24" height="24" fill="#c9433d"/);
  assert.match(art,/Hunter · 血块 23/);
  assert.match(art,/scale\(1\.92\)/);
});
