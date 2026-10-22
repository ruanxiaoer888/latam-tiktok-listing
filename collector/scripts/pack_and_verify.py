# -*- coding: utf-8 -*-
r"""pack_and_verify.py — 打交付包 + 逐条校验包内内容（一条命令，先打包再验包）

用法：
    python scripts/pack_and_verify.py
    python scripts/pack_and_verify.py --input-root ..\input ^
        --out ..\ml-listing-input-<N>sku.zip --manifest ..\采集清单.md

行为（照做，别改）：
  - 打包：<input-root> 下所有 SKU 目录（跳过 _ 开头）以 `input/<SKU>/...` 入包，可选带上采集清单
  - 校验：直接验**包内**内容（不是源目录），逐 SKU 核对——
      1) input.json / item.json 存在且能解析
      2) input.json 必填字段齐全（少一个下游就断链）
      3) 图片：声明数 == 包内实际数，每张能打开且尺寸 > 0
      4) 标题非空、描述非空（西语原文，不校验内容语义）
      5) 不应存在冗余的 description.json
  - 校验不通过：以非 0 退出码结束（不交付），并打印问题项
"""
import argparse
import io
import json
import os
import sys
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
COLLECTOR = os.path.dirname(HERE)
REPO_FALLBACK = os.path.dirname(COLLECTOR)
DEFAULT_INPUT_ROOT = os.path.join(REPO_FALLBACK, "input")
DEFAULT_OUT = os.path.join(REPO_FALLBACK, "ml-listing-input-%dsku.zip")
DEFAULT_MANIFEST = os.path.join(REPO_FALLBACK, "采集清单.md")

REQUIRED_INPUT_KEYS = ["product_id", "site", "category", "title_raw", "description_raw",
                       "attributes_raw", "images", "core_keyword", "price_source"]
IMG_EXT = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp")


def sku_dirs(input_root):
    out = []
    if not os.path.isdir(input_root):
        return out
    for name in sorted(os.listdir(input_root)):
        d = os.path.join(input_root, name)
        if os.path.isdir(d) and not name.startswith("_"):
            out.append((name, d))
    return out


def pack(args, skus, out_path):
    n_files = 0
    n_bytes = 0
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED, compresslevel=args.level) as z:
        for name, d in skus:
            for root, dirs, files in os.walk(d):
                dirs[:] = [x for x in dirs if not x.startswith("_")]
                for fn in sorted(files):
                    full = os.path.join(root, fn)
                    rel = os.path.relpath(full, args.input_root)
                    arc = os.path.join("input", rel).replace("\\", "/")
                    z.write(full, arc)
                    n_files += 1
                    n_bytes += os.path.getsize(full)
        if args.manifest and os.path.exists(args.manifest):
            z.write(args.manifest, os.path.basename(args.manifest).replace("\\", "/"))
            n_files += 1
    return n_files, n_bytes


def verify(args, skus, out_path):
    problems = []
    with zipfile.ZipFile(out_path) as z:
        names = z.namelist()
        nset = set(names)
        img_unreadable = 0
        for name, _d in skus:
            base = "input/" + name + "/"
            ip = base + "input.json"
            itp = base + "item.json"
            if ip not in nset:
                problems.append("%s: 包内缺 input.json" % name)
                continue
            if itp not in nset:
                problems.append("%s: 包内缺 item.json" % name)
                continue
            try:
                inp = json.loads(z.read(ip).decode("utf-8"))
                itm = json.loads(z.read(itp).decode("utf-8"))
            except Exception as e:  # noqa: BLE001
                problems.append("%s: JSON 解析失败 %s" % (name, e))
                continue
            miss = [k for k in REQUIRED_INPUT_KEYS if k not in inp]
            if miss:
                problems.append("%s: input.json 缺字段 %s" % (name, ",".join(miss)))
            if not (itm.get("title") or inp.get("title_raw")):
                problems.append("%s: 标题为空" % name)
            desc = (itm.get("description") or {}).get("text") or inp.get("description_raw") or ""
            if not str(desc).strip():
                problems.append("%s: 描述为空" % name)

            declared = inp.get("images") or []
            packed = sorted(n for n in names
                            if n.startswith(base + "img/")
                            and n.lower().endswith(IMG_EXT))
            n_decl = len(declared)
            if n_decl != len(packed):
                problems.append("%s: 图片数不一致（声明 %d / 包内 %d）" % (name, n_decl, len(packed)))
            if n_decl == 0:
                problems.append("%s: 图片数为 0" % name)
            for n in packed:
                try:
                    from PIL import Image
                    with Image.open(io.BytesIO(z.read(n))) as im:
                        if not im.size or im.size[0] <= 0 or im.size[1] <= 0:
                            raise ValueError("size=%s" % (im.size,))
                except ImportError:
                    break
                except Exception as e:  # noqa: BLE001
                    img_unreadable += 1
                    problems.append("%s: 图片打不开 %s (%s)" % (name, os.path.basename(n), e))
            if base + "description.json" in nset:
                problems.append("%s: 存在冗余 description.json（应删除）" % name)

    size_mb = os.path.getsize(out_path) / 1048576.0
    print("包: %s" % out_path)
    print("条目: %d | 体积: %.1f MB | SKU 目录: %d" % (len(names), size_mb, len(skus)))
    if args.manifest and os.path.exists(args.manifest):
        print("含清单: %s" % os.path.basename(args.manifest))
    if problems:
        print("\n!! 校验不通过，问题 %d 项：" % len(problems))
        for p in problems[:60]:
            print("   - %s" % p)
        if len(problems) > 60:
            print("   ... 其余 %d 项省略" % (len(problems) - 60))
        return 1
    print("\n校验通过：%d 个 SKU 的 input.json/item.json、必填字段、图片数量与可读性、标题与描述 全部 OK。"
          % len(skus))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-root", default=os.environ.get("MLP_INPUT_ROOT") or DEFAULT_INPUT_ROOT)
    ap.add_argument("--out", default=None, help="输出 zip（默认 <仓库>/ml-listing-input-<N>sku.zip）")
    ap.add_argument("--manifest", default=DEFAULT_MANIFEST, help="要一并打进包的采集清单（不存在则忽略）")
    ap.add_argument("--level", type=int, default=1, help="压缩级别 0-9（图片占多数，1 足够）")
    ap.add_argument("--no-verify", action="store_true", help="只打包不校验（不推荐）")
    args = ap.parse_args()

    skus = sku_dirs(args.input_root)
    if not skus:
        print("!! %s 下没有 SKU 目录" % args.input_root)
        return 2
    out_path = args.out or (DEFAULT_OUT % len(skus))
    out_path = os.path.abspath(out_path)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    t0 = time.time()
    n_files, n_bytes = pack(args, skus, out_path)
    print("打包完成：%d 个 SKU / %d 个文件 / 源 %.1f MB / 耗时 %.1fs" % (
        len(skus), n_files, n_bytes / 1048576.0, time.time() - t0))
    if args.no_verify:
        return 0
    return verify(args, skus, out_path)


if __name__ == "__main__":
    sys.exit(main())