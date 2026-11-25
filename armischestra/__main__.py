"""Launch the editor, rehearse, locate actors, or perform with a Dobot arm."""

import argparse
import json
from pathlib import Path

from .hardware import build_camera
from .project import EXAMPLES, example_document, parse_project, rehearse as simulate
from .show import load_json, load_show, load_stage
from .vision import MarkerMissing, aruco_markers


def main():
    parser = argparse.ArgumentParser(description="棋盘机械臂小剧场")
    commands = parser.add_subparsers(dest="command", required=True)
    editor = commands.add_parser("editor", help="启动本机剧本编辑器")
    editor.add_argument("--port", type=int, default=8765)
    live = commands.add_parser("perform", help="使用已标定的 Dobot 和相机表演")
    live.add_argument("project", type=Path, help="编辑器导出的工程 JSON")
    live.add_argument("--calibration", type=Path, required=True)
    live.add_argument("--device", type=Path, required=True)
    live.add_argument("--sdk-dir", type=Path, required=True)
    live.add_argument("--lens", type=Path, help="使用镜头档案自动进行 XY 标定并预检")
    live.add_argument("--preflight-only", action="store_true", help="完成标定和预检后结束，不演出")
    lens = commands.add_parser("lens", help="由多个视角的定位码棋盘照片建立镜头档案")
    lens.add_argument("--project", type=Path, required=True)
    lens.add_argument("--output", type=Path, required=True)
    lens.add_argument("--device", type=Path, help="从设备配置的视频流逐张取景")
    lens.add_argument("photos", nargs="*", type=Path)
    rehearse = commands.add_parser("rehearse", help="在虚拟棋盘上排练并生成回放")
    rehearse.add_argument("--project", type=Path, help="编辑器导出的工程 JSON")
    rehearse.add_argument("--stage", type=Path)
    rehearse.add_argument("--show", type=Path)
    rehearse.add_argument("--replay", type=Path, default=Path("rehearsal.html"))
    rehearse.add_argument("--trace", type=Path, help="另存含每步吸盘、角色状态的 JSON")
    locate = commands.add_parser("locate", help="根据一张照片或角点记录定位角色")
    locate.add_argument("actor")
    stage_source = locate.add_mutually_exclusive_group()
    stage_source.add_argument("--project", type=Path)
    stage_source.add_argument("--stage", type=Path)
    score = commands.add_parser("score", help="从整张棋盘照片读取双方实体血块")
    score.add_argument("--project", type=Path, required=True)
    for reader in (locate, score):
        reader.add_argument("--calibration", type=Path, required=True)
        source = reader.add_mutually_exclusive_group(required=True)
        source.add_argument("--image", type=Path)
        source.add_argument("--markers", type=Path, help="保存的标记角点 JSON，可离线定位")
    args = parser.parse_args()
    try:
        if args.command == "editor":
            from .editor import serve
            serve(args.port)
            return
        if args.command == "rehearse" and args.project and (args.stage or args.show):
            raise ValueError("--project 已包含舞台和剧本，请单独使用")
        project = parse_project(load_json(args.project)) if args.project else None
        if args.command == "rehearse" and not (project or args.stage or args.show):
            project = parse_project(example_document())
        stage = project.stage if project else load_stage(args.stage or EXAMPLES / "stage.json")
        if args.command == "lens":
            from .registration import lens_profile
            if bool(args.photos) == bool(args.device):
                raise ValueError("请提供标定照片，或使用 --device 现场取景")
            def frames():
                from .dobot import fresh_frame
                cfg = load_json(args.device)
                for i in range(8):
                    input(f"调整手机倾角和位置，让四码入镜，回车拍第 {i+1}/8 张：")
                    yield fresh_frame(cfg["camera_source"], cfg.get("camera_size_px"))
            profile = lens_profile(stage, args.photos, frames=frames())
            args.output.write_text(json.dumps(profile, indent=2), encoding="utf-8")
            print(f"镜头标定完成 RMS {profile['rms_px']:.2f} px")
            return
        if args.command == "perform":
            from .dobot import run_dobot
            run_dobot(stage, project.show, load_json(args.calibration),
                      load_json(args.device), args.sdk_dir, lens=load_json(args.lens) if args.lens else None,
                      preflight_only=args.preflight_only)
            return
        if args.command in ("locate", "score"):
            if args.image:
                markers = aruco_markers(args.image)
            else:
                markers = {int(k): v for k, v in load_json(args.markers).items()}
            cam = build_camera(stage, load_json(args.calibration), lambda: markers)
            if args.command == "score":
                if not stage.health_bars:
                    raise ValueError("该工程没有配置血条")
                complete = True
                for bar in stage.health_bars:
                    remaining = 0
                    missing = []
                    for token in bar.tokens:
                        try:
                            remaining += bar.contains(cam.locate(token))
                        except MarkerMissing:
                            missing.append(token)
                    if missing:
                        complete = False
                        print(f"{bar.actor}：已确认区内 {remaining} 块；未能定位 {'、'.join(missing)}")
                    else:
                        state = "（血量耗尽）" if remaining == 0 else ""
                        print(f"{bar.actor}：{remaining}/{len(bar.tokens)}{state}")
                if not complete:
                    raise ValueError("血量未完全确认，请将血条区和弃置区一同拍清楚后重试")
                return
            point = cam.locate(args.actor)
            stage.check(point)
            print(f"{args.actor} 吸取点 ({point.x:.2f}, {point.y:.2f}) mm")
            return

        show = project.show if project else load_show(args.show or EXAMPLES / "show.json", stage)
        sim = simulate(stage, show)
        args.replay.parent.mkdir(parents=True, exist_ok=True)
        sim.write_replay(args.replay, cell_mm=stage.cell, title=show.title,
                         cards=project.cards if project else None,
                         reserves=project.reserves if project else None)
        if args.trace:
            args.trace.parent.mkdir(parents=True, exist_ok=True)
            args.trace.write_text(json.dumps(sim.events, ensure_ascii=False, indent=2) + "\n",
                                  encoding="utf-8")
        print(f"{show.title}｜排练完成，虚拟时长 {sim.time_s:.1f} 秒")
        for name, p in sim.actors.items():
            print(f"  {name} ({p.x:g}, {p.y:g}) mm")
        print(f"回放 {args.replay.resolve()}")
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        parser.exit(1, f"小剧场：{exc}\n")


if __name__ == "__main__":
    main()
