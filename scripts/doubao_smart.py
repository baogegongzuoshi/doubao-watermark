#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
doubao_smart.py — 豆包分享链接"智能过滤下载"工作流脚本
与 doubao-online-parser 的区别：下载前增加"大模型审图"环节，
跳过生成失败的作品（畸形、乱码、空白、与提示词严重不符等）。

子命令:
  candidates <share_url> --review DIR
      解析链接并下载"待审样本"（图片用缩略图、视频用封面图），
      生成 review/manifest.json 供大模型逐项判断。
  download <share_url> --out DIR --verdicts review/verdicts.json [--type ...]
      按大模型给出的 verdicts（keep/skip + reason）下载通过的作品。
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import doubao_engine as E  # noqa: E402


def cmd_candidates(args):
    r = E.parse_share(args.url)
    os.makedirs(args.review, exist_ok=True)
    entries = []
    # 图片：优先缩略图 thumb，其次 preview
    for i, it in enumerate(r["images"], 1):
        thumb = it.get("thumb") or it.get("preview") or it.get("url")
        tf = ""
        if thumb:
            ext = "jpg"
            tf = os.path.join(args.review, f"img_{i:03d}_{(it.get('id') or 'x')[-8:]}.{ext}")
            try:
                E.download_file(thumb, tf)
            except Exception as e:
                tf = ""
                it["_thumb_err"] = str(e)
        entries.append({"kind": "image", "idx": i, "id": it.get("id"),
                        "time": it.get("time"), "epoch": it.get("epoch"),
                        "width": it.get("width"), "height": it.get("height"),
                        "status": it.get("status"), "tips": it.get("tips"),
                        "prompt": it.get("prompt"), "context": it.get("context"),
                        "thumb": tf})
    # 视频：封面图 + 状态信息
    for i, it in enumerate(r["videos"], 1):
        tf = ""
        if it.get("poster"):
            tf = os.path.join(args.review, f"vid_{i:03d}_{(it.get('vid') or 'x')[-8:]}.jpg")
            try:
                E.download_file(it["poster"], tf)
            except Exception as e:
                tf = ""
                it["_thumb_err"] = str(e)
        entries.append({"kind": "video", "idx": i, "id": it.get("id"), "vid": it.get("vid"),
                        "time": it.get("time"), "epoch": it.get("epoch"),
                        "width": it.get("width"), "height": it.get("height"),
                        "duration": it.get("duration"), "status": it.get("status"),
                        "model_status": it.get("model_status"),
                        "model_message": it.get("model_message"),
                        "tips": it.get("tips"),
                        "prompt": it.get("prompt"), "context": it.get("context"),
                        "thumb": tf})
    manifest = {"share_url": args.url, "share_name": r["share_name"],
                "review_dir": args.review, "candidates": entries}
    mf = os.path.join(args.review, "manifest.json")
    with open(mf, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    n_img = sum(1 for x in entries if x["kind"] == "image")
    n_vid = len(entries) - n_img
    print(f"待审样本就绪: 图片 {n_img} 张, 视频 {n_vid} 个 -> {args.review}")
    print(f"清单: {mf}")
    print("下一步: 用视觉能力逐项查看 thumb 图片, 结合 prompt/context 判断, 写 verdicts.json")
    # 打印速览
    for x in entries:
        mark = "✔样本" if x["thumb"] else "✘无样本"
        bad = ""
        if x["kind"] == "video" and x.get("status") not in (3, None):
            bad = f"  ⚠视频status={x.get('status')}"
        print(f"  {x['kind']}-idx{x['idx']:02d} [{x.get('time')}] {mark}{bad} prompt={(x.get('prompt') or x.get('context') or '')[:50]}")


def cmd_download(args):
    r = E.parse_share(args.url)
    verdicts = {}
    if args.verdicts:
        with open(args.verdicts, encoding="utf-8") as f:
            vd = json.load(f)
        if isinstance(vd, dict):
            vd = vd.get("verdicts", [])
        for v in vd:
            verdicts[str(v.get("id"))] = v
    items = []
    if args.type in ("all", "image"):
        items += r["images"]
    if args.type in ("all", "video"):
        items += r["videos"]
    skipped, keep = [], []
    for it in items:
        v = verdicts.get(str(it.get("id")))
        if v and v.get("verdict") == "skip":
            skipped.append((it, v.get("reason", "")))
        else:
            keep.append(it)
    # 近 -> 远
    keep.sort(key=lambda x: x.get("epoch") or 0, reverse=True)
    print(f"通过 {len(keep)} 项, 跳过 {len(skipped)} 项")
    for it, why in skipped:
        print(f"  ⏭ skip [{it.get('time')}] {it['kind']} id={it.get('id')} 理由: {why[:80]}")
    if not keep:
        print("没有需要下载的内容")
        return
    if args.dry_run:
        for i, it in enumerate(keep, 1):
            print(f"  {i:02d}. [{it.get('time')}] {it['kind']} id={it.get('id')} {(it.get('prompt') or '')[:50]}")
        return
    os.makedirs(args.out, exist_ok=True)
    ok = 0
    for i, it in enumerate(keep, 1):
        stamp = (it.get("time") or "").replace("-", "").replace(":", "").replace(" ", "_") or "unknown"
        if it["kind"] == "image":
            fname = f"{i:03d}_{stamp}_img_{(it.get('id') or 'x')[-8:]}.{it.get('format') or 'jpg'}"
            path = os.path.join(args.out, fname)
            try:
                E.download_file(it["url"], path)
                print(f"  ✔ {fname}")
                ok += 1
            except Exception as e:
                print(f"  ✘ {fname}: {e}")
        else:
            fname = f"{i:03d}_{stamp}_vid_{(it.get('vid') or 'x')[-8:]}.mp4"
            path = os.path.join(args.out, fname)
            try:
                url, entry = E.resolve_video_url(it, prefer_h264=not args.best)
                E.download_file(url, path)
                E._maybe_remux(path)
                print(f"  ✔ {fname}")
                ok += 1
            except Exception as e:
                print(f"  ✘ {fname}: {e}")
    print(f"完成 {ok}/{len(keep)} -> {args.out}")


def main():
    ap = argparse.ArgumentParser(description="豆包分享链接智能过滤下载")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("candidates", help="下载待审样本(缩略图/封面)+清单")
    p.add_argument("url")
    p.add_argument("--review", required=True)
    p.set_defaults(func=cmd_candidates)

    p = sub.add_parser("download", help="按 verdicts 下载通过的作品")
    p.add_argument("url")
    p.add_argument("--out", required=True)
    p.add_argument("--verdicts", required=True, help="大模型审读后写的 verdicts.json")
    p.add_argument("--type", choices=["all", "image", "video"], default="all")
    p.add_argument("--tier", choices=["all", "core"], default="all",
                   help="core=只要判定为核心满足的；all=核心+合格都要")
    p.add_argument("--best", action="store_true", help="视频选最高分辨率(可能H.265)")
    p.add_argument("--dry-run", action="store_true", help="只列出将下载的项")
    p.set_defaults(func=cmd_download)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
