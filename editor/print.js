import { boardCorners } from "./deployment.js";
// Paper, stage, cards and SVG view boxes all use millimetres.
const PAPERS = { A5: [148, 210], A4: [210, 297], A3: [297, 420], A2: [420, 594] };
const LEFT = 12, TOP = 20, BOTTOM = 22;
const INK = "#142228";
const DICT_4X4_50 = [
  // OpenCV generateImageMarker(..., id, 6): sixteen payload cells, white = 1, in reading order.
  0xb532, 0x0f9a, 0x332d, 0x9946, 0x549e, 0x79cd, 0x9e2e, 0xc4f2, 0xfeda, 0xcf56,
  0xf991, 0x11a7, 0x0eb7, 0x2a0f, 0x24b1, 0x263e, 0x4665, 0x6600, 0x6c5e, 0x76af,
  0x868b, 0xb02b, 0xccd5, 0xdd82, 0xfe47, 0x9471, 0xace4, 0xa554, 0x2123, 0x346f,
  0x4415, 0x57b2, 0x9ecf, 0xf0cb, 0x08ae, 0x0929, 0x1875, 0x04ff, 0x0df6, 0x1c5a,
  0x1718, 0x2a28, 0x328c, 0x38b2, 0x24e8, 0x2eeb, 0x2d3f, 0x4b64, 0x502e, 0x5013
];

function escapeText(value) {
  return String(value).replace(/[&<>"']/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[char]);
}
const fmt = n => Number(n.toFixed(4));
function positivePair(pair, name) {
  if (!Array.isArray(pair) || pair.length !== 2 || !pair.every(n => Number.isFinite(n) && n > 0))
    throw new Error(name + "的宽和高须为正数（毫米）");
  return pair;
}

function paperGeometry(paper, orientation) {
  if (!Object.hasOwn(PAPERS, paper) || !["portrait", "landscape"].includes(orientation))
    throw new Error("请选择 A5、A4、A3 或 A2 及纸张方向");
  let [width, height] = PAPERS[paper];
  if (orientation === "landscape") [width, height] = [height, width];
  return {width, height, areaW: width - 2 * LEFT, areaH: height - TOP - BOTTOM};
}

function cutMarks(x, y, w, h) {
  const sections = [];
  for (const [px, signX] of [[x, -1], [x+w, 1]]) {
    for (const [py, signY] of [[y, -1], [y+h, 1]]) {
      sections.push('M'+(px+signX*0.4)+' '+py+'h'+(signX*2.8),
                    'M'+px+' '+(py+signY*0.4)+'v'+(signY*2.8));
    }
  }
  return '<path d="'+sections.join(" ")+'" fill="none" stroke="#687077" stroke-width=".16"/>';
}

function ruler(y) {
  let path = 'M12 '+y+'h50';
  for (let i=0; i<=50; i+=5) path += ' M'+(12+i)+' '+y+'v'+(i%10 ? -1.5 : -2.5);
  return '<path d="'+path+'" fill="none" stroke="#222" stroke-width=".25"/>'+
    '<text x="65" y="'+(y+0.8)+'" font-size="3">50 mm 校尺</text>';
}

function sheetSvg(g, title, section, body, note, number) {
  return `<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="${g.width}mm" height="${g.height}mm" viewBox="0 0 ${g.width} ${g.height}">
<title>${escapeText(title)} · ${escapeText(section)}</title>
<rect width="100%" height="100%" fill="white"/>
<g font-family="sans-serif" fill="${INK}">
<svg x="12" y="6" width="${g.width-72}" height="9" overflow="hidden"><text y="6" font-size="4.5" font-weight="bold">${escapeText(title)}</text></svg>
<text x="${g.width-12}" y="12" font-size="3.8" text-anchor="end">${escapeText(section)}</text>
${body}
<text x="12" y="${g.height-13.2}" font-size="3">${escapeText(note)}</text>
${ruler(g.height-7)}
<text x="${g.width-12}" y="${g.height-7}" font-size="3" text-anchor="end">${escapeText(number)}</text>
</g></svg>`;
}

// Keep the minimum page count; align a seam to cell boundaries when space permits.
function tileStep(length, limit, cell) {
  const count = Math.ceil(length / limit);
  const aligned = Math.ceil((length/count) / cell) * cell;
  return aligned <= limit ? aligned : limit;
}

// Clip to the current physical sheet so the same world coordinates stay aligned at seams.
function stagingOverlay(stage, x, y, tw, th) {
  const upper = y + th;
  const regions = (stage.reserves || []).filter(r => {
    const [rx,ry] = r.origin_mm, [rw,rh] = r.size_mm;
    return rx < x+tw && rx+rw > x && ry < upper && ry+rh > y;
  });
  const strokes = regions.map(({name,origin_mm:[rx,ry],size_mm:[rw,rh]})=>{
    const left=rx-x, top=upper-(ry+rh);
    return `<rect x="${left}" y="${top}" width="${rw}" height="${rh}" fill="none" stroke="#e29d46" stroke-width=".7" stroke-dasharray="2 1"/>
<svg x="${left+1}" y="${top+1}" width="${Math.max(0,rw-2)}" height="${Math.max(0,rh-2)}" overflow="hidden"><text x=".4" y="3.5" font-size="3.2" font-weight="bold" fill="#8a390a" stroke="white" stroke-width=".6" paint-order="stroke">${escapeText(name)}</text></svg>`;
  });
  const bars=stage.health_bars||[];
  const tokenNames=new Set(bars.flatMap(b=>b.tokens));
  for(const bar of bars){
    const [bx,by]=bar.origin_mm,[bw,bh]=bar.size_mm;
    if(bx>=x+tw || bx+bw<=x || by>=upper || by+bh<=y)continue;
    const left=bx-x,top=upper-by-bh;
    strokes.push(`<rect x="${left}" y="${top}" width="${bw}" height="${bh}" fill="none" stroke="#ae3235" stroke-width=".9"/>
<svg x="${left+1}" y="${top+.4}" width="${Math.max(.1,bw-2)}" height="${Math.max(.1,bh-1)}" overflow="hidden"><text y="3" font-size="2.8" font-weight="bold" fill="#9a2229" stroke="white" stroke-width=".65" paint-order="stroke">${escapeText(bar.name)} · ${escapeText(bar.actor)} · ${bar.tokens.length} 格</text></svg>`);
  }
  for (const [name,a] of Object.entries(stage.actors || {})){
    if(a.kind !== "prop") continue;
    const [ax,ay]=a.start_mm;
    if(ax < x || ay < y || ax > x+tw || ay > upper)continue;
    const px=ax-x, py=upper-ay;
    const ink=tokenNames.has(name)?"#a32c30":"#8a390a";
    strokes.push(`<g transform="translate(${px} ${py})"><path d="M-2 0h4 M0 -2v4" fill="none" stroke="${tokenNames.has(name)?ink:"#e29d46"}" stroke-width=".55"/><text x="2" y="-1" font-size="2.8" fill="${ink}" stroke="white" stroke-width=".6" paint-order="stroke">ID ${a.marker_id}</text></g>`);
  }
  return strokes.length ? `<svg x="${LEFT}" y="${TOP}" width="${tw}" height="${th}" viewBox="0 0 ${tw} ${th}" overflow="hidden">${strokes.join("")}</svg>` : "";
}

function boardSheets(stage, g) {
  const [w,h] = positivePair(stage.size_mm, "棋盘");
  const c = stage.cell_mm;
  if (!Number.isFinite(c) || c <= 0) throw new Error("棋盘格距须为正数");
  const stepX = tileStep(w, g.areaW, c), stepY = tileStep(h, g.areaH, c);
  const cols = Math.ceil(w / stepX), rows = Math.ceil(h / stepY);
  if (cols * rows > 200) throw new Error("棋盘将超过 200 页，请核对棋盘毫米尺寸或选择较大纸张");
  const pages = [];
  for (let row=0; row<rows; ++row) {
    for (let col=0; col<cols; ++col) {
      const x = col*stepX, y = row*stepY;
      const tw = Math.min(w-x,stepX), th = Math.min(h-y,stepY);
      const section = '棋盘 · 第 '+(row+1)+' 行 / '+(col+1)+' 列';
      const note = '按裁切线拼接 · 左下角为原点 · X '+fmt(x)+'–'+fmt(x+tw)+' mm / Y '+fmt(y)+'–'+fmt(y+th)+' mm';
      const tip = Math.min(7, tw/3, th/3);
      const labels = boardCorners([w,h]).filter(c =>
        (c.x ? col === cols-1 : col === 0) && (c.y ? row === rows-1 : row === 0)
      ).map(c => {
        const dx = c.x ? -1 : 1, dy = c.y ? 1 : -1;
        return `<g transform="translate(${LEFT+(c.x ? tw : 0)} ${TOP+(c.y ? 0 : th)})"><path d="M0 0 l${dx*tip} ${dy*tip/3} l${-dx*tip*2/3} ${dy*tip*2/3} Z" fill="#bf5026"/><text x="${dx*tip*.47}" y="${dy*tip*.47+tip*.15}" fill="white" text-anchor="middle" font-size="${tip*.42}">${c.id}</text></g>`;
      }).join("");
      const body = `<defs><pattern id="checks" x="0" y="0" width="${2*c}" height="${2*c}" patternUnits="userSpaceOnUse"><path d="M0 0h${c}v${c}H0z M${c} ${c}h${c}v${c}h-${c}z" fill="#000"/></pattern></defs>
<g transform="translate(${LEFT-x} ${TOP+th+y}) scale(1 -1)"><rect x="${x}" y="${y}" width="${tw}" height="${th}" fill="url(#checks)"/></g>
${stagingOverlay(stage,x,y,tw,th)}
${labels}
${cutMarks(LEFT,TOP,tw,th)}`;
      pages.push({section, body, note, filename: 'board-r'+(row+1)+'-c'+(col+1)+'.svg'});
    }
  }
  return pages;
}

function markerCell(shortSide, healthToken) { return (healthToken ? Math.min(12, shortSide*0.48) : Math.min(18, shortSide*0.75))/6; }

export function marker(id, cx, cy, shortSide, healthToken=false) {
  if (!Number.isInteger(id) || id < 0 || id >= DICT_4X4_50.length)
    throw new Error("角色标记须为 0 至 49 的整数");
  const cell = markerCell(shortSide,healthToken);
  let white = "";
  for (let i=0; i<16; i++) {
    if (DICT_4X4_50[id] & (1 << (15-i)))
      white += 'M'+(1+i%4)+' '+(1+Math.floor(i/4))+'h1v1h-1z ';
  }
  return `<g transform="translate(${cx-3*cell} ${cy-3*cell}) scale(${cell})" shape-rendering="crispEdges"><rect x="-1" y="-1" width="8" height="8" fill="white"/><rect width="6" height="6" fill="black"/><path d="${white}" fill="white"/></g>`;
}

function packCards(items, g, section, prefix, note) {
  const pages = [];
  let current = null, x = 0, y = 0, rowHeight = 0;
  const gap = 8;
  for (const item of items) {
    const {name, w, h, labelW, lines} = item;
    const printW = Math.max(w, labelW);
    const labelArea = 4*lines.length+5;
    if (printW > g.areaW || h+labelArea > g.areaH)
      throw new Error(name+" 的卡片放不下。本纸张可放 "+g.areaW+" × "+(g.areaH-labelArea)+" mm，请更换纸型、方向或调整角色尺寸");
    if (x+printW > g.areaW) { x=0; y+=rowHeight+gap; rowHeight=0; }
    if (!current || y+h+labelArea > g.areaH) {
      current = {section:section+' · '+(pages.length+1), body:'', note, filename:prefix+'-'+(pages.length+1)+'.svg'};
      pages.push(current);
      x=0; y=0; rowHeight=0;
    }
    const px = LEFT+x, py = TOP+y;
    const labels = lines.map((line,i)=>'<text y="'+(4*i+3.7)+'" font-size="3.3">'+escapeText(line)+'</text>').join('');
    current.body += item.draw(px,py) + cutMarks(px,py,w,h) +
      `<svg x="${px}" y="${py+h+1.8}" width="${printW}" height="${labelArea-2}" overflow="hidden">${labels}</svg>`;
    x += printW+gap;
    rowHeight = Math.max(rowHeight,h+labelArea);
  }
  return pages;
}

function cardSheetParts(stage, g, separate) {
  const cards = [], stickers = [];
  const owners=new Map((stage.health_bars||[]).flatMap(b=>b.tokens.map(n=>[n,b.actor])));
  for (const [name, actor] of Object.entries(stage.actors)) {
    const [w,h] = positivePair(actor.print_size_mm, name);
    const shortSide = Math.min(w,h);
    if (shortSide < 16) throw new Error(name+" 的卡片宽和高都需至少 16 mm，以保留标记白边");
    const mark = actor.marker_offset_mm ?? [0,0];
    const offset = actor.pickup_offset_mm;
    const hp=owners.has(name);
    const tagSide = 8*markerCell(shortSide,hp);
    if (!Array.isArray(mark) || mark.length !== 2 || !mark.every(Number.isFinite) ||
        Math.abs(mark[0])+tagSide/2 > w/2 || Math.abs(mark[1])+tagSide/2 > h/2)
      throw new Error(name+" 的标记或白边超出卡片，请调整图心到标记的偏移");
    if (!Array.isArray(offset) || offset.length !== 2 || !offset.every(Number.isFinite) ||
        Math.abs(mark[0]+offset[0]) > w/2 || Math.abs(mark[1]+offset[1]) > h/2)
      throw new Error(name+" 的吸取点超出卡片，请调整偏移或卡片尺寸");
    if (actor.image != null && (typeof actor.image !== 'string' || !/^data:image\/png;base64,[A-Za-z0-9+/=]+$/.test(actor.image)))
      throw new Error(name+' 的角色图须为编辑器导入的 PNG');
    const label = hp ? owners.get(name)+" · 血块 "+actor.marker_id : (actor.kind==='prop'?'道具 · ':'')+name+' · ID '+actor.marker_id;
    cards.push({name, w, h, labelW:hp?Math.max(w,37):w, lines:actor.kind==="prop" ? [label,'预置吸点 '+actor.start_mm.map(fmt).join(', ')+' mm'] : [label], draw:(px,py)=>{
      const image = actor.image ? `<image x="${px}" y="${py}" width="${w}" height="${h}" preserveAspectRatio="xMidYMid meet" xlink:href="${actor.image}"/>` : '';
      return (hp ? `<rect x="${px}" y="${py}" width="${w}" height="${h}" fill="#c9433d"/>` : "") + image + (separate ? '' : marker(actor.marker_id, px+w/2+mark[0], py+h/2-mark[1], shortSide,hp));
    }});
    if (separate) stickers.push({
      name, w:tagSide, h:tagSide, labelW:60,
      lines:[label, '图心 → 标记  ('+fmt(mark[0])+', '+fmt(mark[1])+') mm', '标记 → 吸点  ('+fmt(offset[0])+', '+fmt(offset[1])+') mm'],
      draw:(px,py)=>marker(actor.marker_id,px+tagSide/2,py+tagSide/2,shortSide,hp)
    });
  }
  if (!cards.length) throw new Error("请先添加需要打印的角色");
  return [
    ...packCards(cards,g,separate?'纸片原图':'角色与道具卡','actors',
      separate?'沿四角裁切标记剪下 · 在另页裁下并粘贴对应编号的标记':'沿四角裁切标记剪下 · 标记上沿指向卡片上方'),
    ...packCards(stickers,g,'纸片标记','markers',
      '保留白边，保持本页朝向 · 右、上为正 · 贴好后请实测并更新图心到标记、标记到吸点的偏移')
  ];
}

export function printPages(bundle, {paper="A4", orientation="portrait", content="all", separateMarkers=false}={}) {
  const g = paperGeometry(paper, orientation);
  if (!["all","board","actors","calibration"].includes(content)) throw new Error("未选择打印内容");
  const pages = [
    ...(content==="calibration" ? packCards(
      ["左下 · 贴左侧","右下 · 贴右侧","右上 · 贴右侧","左上 · 贴左侧","吸盘 · 中心朝上"].map((name,i) => ({
        name, w:24, h:24, labelW:48, lines:[(45+i)+" · "+name],
        draw:(x,y)=>marker(45+i,x+12,y+12,24)
      })), g,"自动标定码","calibration","按裁切线保留 24 mm 白底 · 黑框 18 mm · 四个棋盘码保持印刷朝向"
    ) : []),
    ...(["all","board"].includes(content) ? boardSheets(bundle.stage,g) : []),
    ...(["all","actors"].includes(content) ? cardSheetParts(bundle.stage,g,separateMarkers) : [])
  ];
  return pages.map(({section,body,note,filename},i) => ({
    title: section, filename, width:g.width, height:g.height,
    svg: sheetSvg(g,bundle.show.title,section,body,note,paper+' · '+(i+1)+' / '+pages.length)
  }));
}

export function printStage(bundle, options={}) {
  const initialPages = printPages(bundle, options);
  const child = window.open("", "_blank");
  if (!child) throw new Error("请允许弹出窗口，以打开印品预览");
  child.opener = null;
  const doc = child.document, {width,height} = initialPages[0];
  doc.open();
  doc.write(`<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>印品预览</title><style>
*{box-sizing:border-box}html,body{margin:0}body{font:15px/1.5 system-ui,sans-serif;color:#23302d;background:#e6e9e5}header{position:sticky;top:0;z-index:1;background:#172e29;color:white;padding:12px 5%;display:flex;align-items:center;justify-content:space-between;gap:1rem;flex-wrap:wrap}header strong{display:block;font-size:18px}header small{color:#cbd6ce}button{cursor:pointer;border:0;border-radius:6px;background:#d6f57e;padding:.65rem 1rem;color:#183727;font:inherit;font-weight:bold}article{width:min(96%,${width}mm);margin:26px auto}article nav{display:flex;align-items:center;justify-content:space-between;padding:4px 0 9px}a{color:#244937}.paper{background:white;box-shadow:0 3px 14px #23302d25}.paper>svg{display:block;width:100%;height:auto}
@page{size:${width}mm ${height}mm;margin:0}
@media print{html,body{width:${width}mm;background:white}header,article nav{display:none}article,.paper{width:${width}mm;height:${height}mm;margin:0;padding:0;box-shadow:none}.paper>svg{width:${width}mm;height:${height}mm}article{break-after:page;break-inside:avoid}article:last-child{break-after:auto}*{print-color-adjust:exact;-webkit-print-color-adjust:exact}}
</style></head><body><header><div><strong>印品预览</strong><small>选择匹配的纸张，缩放设为 100%，关闭页眉页脚。打印后用尺核对 50 mm 校尺。</small></div><label><input type="checkbox" id="separate"> 纸片插图与标记分开打印</label><button type="button">打印 / 保存 PDF</button></header><main></main></body></html>`);
  doc.close();
  doc.title = bundle.show.title+' · 印品预览';
  const button = doc.querySelector("button");
  button.onclick = () => child.print();
  const check = doc.querySelector('#separate');
  check.parentElement.hidden = ['board','calibration'].includes(options.content);
  check.checked = Boolean(options.separateMarkers);
  const main = doc.querySelector('main');
  function render(pages) {
    for (const link of main.querySelectorAll('a[download]')) child.URL.revokeObjectURL(link.href);
    main.replaceChildren();
    for (const page of pages) {
      const article = doc.createElement('article'), nav = doc.createElement('nav'), label = doc.createElement('strong');
      const link = doc.createElement('a'), figure = doc.createElement('div');
      label.textContent = page.title;
      link.textContent = '下载此页 SVG';
      link.download = page.filename;
      link.href = child.URL.createObjectURL(new Blob([page.svg],{type:'image/svg+xml;charset=utf-8'}));
      nav.append(label,link);
      figure.className = 'paper';
      // Image references are self-contained PNGs, dynamic text is XML escaped.
      figure.innerHTML = page.svg;
      article.append(nav,figure);
      main.append(article);
    }
  }
  render(initialPages);
  check.onchange = () => render(printPages(bundle, {...options,separateMarkers:check.checked}));
}
