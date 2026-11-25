// The numbered tip touches the physical board boundary on each outer sheet.
export function boardCorners([w, h]) {
  return [
    {id: 1, name: "左下", x: 0, y: 0},
    {id: 2, name: "右下", x: w, y: 0},
    {id: 3, name: "右上", x: w, y: h},
    {id: 4, name: "左上", x: 0, y: h},
  ];
}

export function deploymentGuide(size) {
  const [w,h] = size;
  const corners = boardCorners(size);
  const diagram = corners.map(({id,x,y}) => {
    const px = x ? 271 : 59, py = y ? 50 : 154;
    return `<rect x="${px-6}" y="${py-6}" width="12" height="12" fill="white" stroke="#738373" stroke-width=".5"/><rect x="${px-4.5}" y="${py-4.5}" width="9" height="9" fill="#273829"/>
      <text x="${px + (x ? 10 : -10)}" y="${py+4}" text-anchor="${x ? "start" : "end"}">${44+id}</text>`;
  }).join("");
  return `<div class="deployment">
    <svg viewBox="0 0 330 200" role="img" aria-label="手机俯视示意图。四个标定码从左下起依次为 45 至 48，X 向右，Y 向上">
      <defs><pattern id="deployment-grid" width="20" height="20" patternUnits="userSpaceOnUse"><path d="M0 0h10v10H0z M10 10h10v10H10z" fill="#d1dacd"/></pattern></defs>
      <rect x="18" y="8" width="294" height="182" rx="9" fill="#f6f7ef" stroke="#738373" stroke-dasharray="4 3"/>
      <text x="165" y="29" text-anchor="middle">手机俯视画面</text>
      <rect x="65" y="44" width="200" height="116" fill="url(#deployment-grid)" stroke="#455d4a"/>
      <text x="165" y="109" text-anchor="middle">${w} × ${h} mm</text>
      <text x="165" y="180" text-anchor="middle">X →</text><text x="26" y="107">Y ↑</text>${diagram}
    </svg>
    <h3>棋盘四角</h3>
    <p>按 100% 打印棋盘，用尺核对 50 mm 校尺，沿裁切线拼齐。另印标定码，沿裁切线剪出 24 mm 方片。45、48 紧贴棋盘左边外侧，46、47 紧贴右边外侧；上面两片与棋盘上边齐平，下面两片与下边齐平。四码保持打印朝向，与纸卡码面共面。</p>
    <ol>${corners.map(c => `<li>ID ${44+c.id} · ${c.name}角（${c.x}, ${c.y}）mm</li>`).join("")}</ol>
    <p>手机画面须包含四张标定码。两场之间可以挪手机，开场会重新定位棋盘。演出时固定支架，关闭自动切镜头和可变裁剪。</p>
    <h3>吸盘与机械臂</h3>
    <p>把 49 号码水平固定在吸盘正上方，中心对准吸盘轴线。手动测一次接触低位和抬起高位，量低位时码面到棋盘码面的垂直距离。角色与血块使用 ID 0–44。</p>
    <p>首次用同一视频模式从至少六个不同倾角拍下棋盘，建立镜头档案。开场从已设高位启动，机械臂在预留的空旷正方形内自动采点并复核，然后检查剧本路线。命令见项目 docs/dobot.md。</p></div>`;
}
