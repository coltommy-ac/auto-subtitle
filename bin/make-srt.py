#!/usr/bin/env python3
"""
make-srt.py: 将 STT JSON 输出合并生成标准 SRT 字幕文件
改写自 make-srt.php，彻底移除 PHP 依赖

用法:
  python3 bin/make-srt.py -d <cache_dir> -l <language>
  python3 bin/make-srt.py -f <single_txt_file>
"""

import json
import os
import sys
import argparse

# 相邻字幕间隔小于此值（秒）则合并
MERGE_GAP     = 0.5
# 单条字幕最长时长（秒）
MAX_DURATION  = 5.0


def srt_timestamp(t):
    """将秒数转为 SRT 时间格式 HH:MM:SS,mmm"""
    h  = int(t // 3600)
    m  = int((t % 3600) // 60)
    s  = int(t % 60)
    ms = int(round((t - int(t)) * 1000))
    # 毫秒必须补零到3位
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def extract_segments(txt_file, offset):
    """
    读取一个 STT JSON 文件，返回 [(start, end, transcript), ...] 列表。
    offset 为该片段在整个视频中的起始秒数。
    出错时返回 None（调用方决定是否跳过）。
    """
    if not os.path.exists(txt_file):
        print(f"[skip] file not exist: {txt_file}")
        return None

    try:
        with open(txt_file, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"[warn] failed to decode JSON: {txt_file}: {e}")
        return None

    results = data.get("results")
    if results is None:
        print(f"[warn] bad format (no 'results'): {txt_file}")
        return None

    segments = []
    for result in results:
        alts = result.get("alternatives", [])
        if not alts:
            continue
        alt        = alts[0]
        transcript = alt.get("transcript", "").strip()
        timestamps = alt.get("timestamps", [])
        if not transcript or not timestamps:
            continue
        start = float(timestamps[0][1])  + offset
        end   = float(timestamps[-1][2]) + offset
        if end <= start:
            end = start + 0.1
        segments.append((start, end, transcript))

    return segments


def merge_segments(segments):
    """
    合并相邻碎片字幕：
    - 相邻两条间隔 < MERGE_GAP 且合并后时长 <= MAX_DURATION 则合并
    - 否则输出当前条，开始新的一条
    """
    if not segments:
        return []

    merged = []
    cur_start, cur_end, cur_text = segments[0]

    for start, end, text in segments[1:]:
        gap     = start - cur_end
        new_dur = end - cur_start
        if gap < MERGE_GAP and new_dur <= MAX_DURATION:
            # 合并：延伸结束时间，拼接文本
            cur_end  = end
            cur_text = cur_text + " " + text
        else:
            merged.append((cur_start, cur_end, cur_text))
            cur_start, cur_end, cur_text = start, end, text

    merged.append((cur_start, cur_end, cur_text))
    return merged


def make_srt_for_file(txt_file, srt_file, index, offset):
    """
    读取一个 STT JSON 文件，追加写入 SRT 文件。
    返回 (ret_code, 更新后的index)
    单个文件失败时返回 (-1, index)，不中断整体流程。
    """
    segments = extract_segments(txt_file, offset)
    if segments is None:
        return -1, index

    merged = merge_segments(segments)

    with open(srt_file, "a", encoding="utf-8") as out:
        for start, end, transcript in merged:
            if start >= 0 and end > start:
                out.write(f"{index}\n")
                out.write(f"{srt_timestamp(start)} --> {srt_timestamp(end)}\n")
                out.write(f"{transcript}\n\n")
                index += 1

    print(f"subtitle updated: {srt_file}, last index: {index - 1}")
    return 0, index


def main():
    parser = argparse.ArgumentParser(description="Generate SRT from STT JSON")
    parser.add_argument("-d", dest="dir",  help="cache directory")
    parser.add_argument("-l", dest="lang", help="language code")
    parser.add_argument("-f", dest="file", help="single STT text file")
    args = parser.parse_args()

    # 单文件模式
    if args.file:
        base     = os.path.splitext(args.file)[0]
        srt_file = base + ".srt"
        if os.path.exists(srt_file):
            os.remove(srt_file)
        ret, _ = make_srt_for_file(args.file, srt_file, 1, 0.0)
        sys.exit(0 if ret >= 0 else ret)

    # 目录模式
    if not args.dir or not args.lang:
        print("Usage: make-srt.py -d <dir> -l <lang>  OR  -f <file>")
        sys.exit(1)

    if not os.path.isdir(args.dir):
        print(f"dir not exist: {args.dir}")
        sys.exit(2)

    index_file = os.path.join(args.dir, "index")
    if not os.path.exists(index_file):
        print(f"index file not exist: {index_file}")
        sys.exit(3)

    srt_file     = os.path.join(args.dir, f"output.{args.lang}.srt")
    srt_file_tmp = srt_file + ".tmp"

    if os.path.exists(srt_file_tmp):
        os.remove(srt_file_tmp)

    index   = 1
    skipped = []
    with open(index_file) as f:
        offsets = [line.strip() for line in f if line.strip()]

    for offset_str in offsets:
        offset   = float(offset_str)
        txt_file = os.path.join(args.dir, f"clip_{int(offset)}.{args.lang}.txt")
        ret, index = make_srt_for_file(txt_file, srt_file_tmp, index, offset)
        if ret < 0:
            # 单个 clip 失败：跳过，继续处理后续 clip
            skipped.append(txt_file)

    if index == 1:
        # 没有写入任何内容
        if os.path.exists(srt_file_tmp):
            os.remove(srt_file_tmp)
        print("[error] no subtitle content generated")
        sys.exit(4)

    # 全部完成，原子替换
    if os.path.exists(srt_file):
        os.remove(srt_file)
    os.rename(srt_file_tmp, srt_file)

    if skipped:
        print(f"[warn] skipped {len(skipped)} clip(s): {skipped}")

    sys.exit(0)


if __name__ == "__main__":
    main()
