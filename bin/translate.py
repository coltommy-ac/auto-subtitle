#!/usr/bin/env python3
"""
translate.py: 翻译 SRT 字幕文件，支持 DeepL 和百度翻译引擎

用法:
  python3 bin/translate.py -i <input.srt> -o <output.srt> -s <src_lang> -t <tgt_lang> [--engine deepl|baidu]

密钥读取顺序:
  1. ~/.autosub_credentials 文件（推荐）
  2. 环境变量

  ~/.autosub_credentials 格式:
    DEEPL_APIKEY=你的deepl_api_key
    BAIDU_APPID=你的appid
    BAIDU_APPKEY=你的appkey

语言代码对照（DeepL）:
  中文: ZH  日语: JA  英语: EN  西班牙语: ES  阿拉伯语: AR
"""

import argparse
import hashlib
import json
import os
import random
import sys
import time
import urllib.parse
import urllib.request

# 每批合并翻译的最大字幕条数
BATCH_SIZE = 20
# 百度翻译免费版 QPS=1，每次调用后等待
BAIDU_SLEEP_SECONDS = 1.0

# autosub 语言代码 → DeepL 语言代码映射
DEEPL_LANG_MAP = {
    "zh": "ZH",
    "en": "EN",
    "ja": "JA",
    "es": "ES",
    "ar": "AR",
}


def load_credentials():
    """从 ~/.autosub_credentials 或环境变量读取所有密钥，返回 dict。"""
    creds = {}
    cred_file = os.path.expanduser("~/.autosub_credentials")
    if os.path.exists(cred_file):
        with open(cred_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    creds[k.strip()] = v.strip()

    # 环境变量作为 fallback
    for key in ("DEEPL_APIKEY", "BAIDU_APPID", "BAIDU_APPKEY"):
        if key not in creds and os.environ.get(key):
            creds[key] = os.environ[key]

    return creds


# ── DeepL ────────────────────────────────────────────────────────────────────

def translate_batch_deepl(sentences, tgt_lang, api_key):
    """
    DeepL Free API 批量翻译。
    一次请求可传多个 text 参数，返回与输入等长的列表。
    """
    deepl_lang = DEEPL_LANG_MAP.get(tgt_lang.lower(), tgt_lang.upper())

    # DeepL Free endpoint
    url = "https://api-free.deepl.com/v2/translate"
    params = [("target_lang", deepl_lang)]
    for s in sentences:
        params.append(("text", s))

    data = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", f"DeepL-Auth-Key {api_key}")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode("utf-8"))

    return [item["text"] for item in result["translations"]]


# ── 百度 ──────────────────────────────────────────────────────────────────────

def translate_batch_baidu(sentences, tgt_lang, appid, appkey):
    """百度翻译批量翻译，\n 分隔多条，返回与输入等长的列表。"""
    query = "\n".join(sentences)
    salt = str(random.randint(1, 65536))
    sign = hashlib.md5((appid + query + salt + appkey).encode("utf-8")).hexdigest()

    params = urllib.parse.urlencode({
        "q":     query,
        "from":  "auto",
        "to":    tgt_lang,
        "appid": appid,
        "salt":  salt,
        "sign":  sign,
    })
    url = f"https://api.fanyi.baidu.com/api/trans/vip/translate?{params}"

    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    if "error_code" in data:
        raise RuntimeError(f"Baidu API error {data['error_code']}: {data.get('error_msg')}")

    return [item["dst"] for item in data["trans_result"]]


# ── 主流程 ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Translate SRT subtitles")
    parser.add_argument("-i", dest="input",    required=True, help="input SRT file")
    parser.add_argument("-o", dest="output",   required=True, help="output SRT file")
    parser.add_argument("-s", dest="src_lang", required=True, help="source language")
    parser.add_argument("-t", dest="tgt_lang", required=True, help="target language")
    parser.add_argument("--engine", dest="engine", default="deepl",
                        choices=["deepl", "baidu"], help="translation engine (default: deepl)")
    args = parser.parse_args()

    creds = load_credentials()

    # 校验所需密钥
    if args.engine == "deepl":
        api_key = creds.get("DEEPL_APIKEY")
        if not api_key:
            print("[error] 未找到 DeepL API key。")
            print("  请在 ~/.autosub_credentials 中配置：")
            print("    DEEPL_APIKEY=你的api_key")
            sys.exit(1)
    else:
        appid  = creds.get("BAIDU_APPID")
        appkey = creds.get("BAIDU_APPKEY")
        if not appid or not appkey:
            print("[error] 未找到百度翻译密钥。")
            print("  请在 ~/.autosub_credentials 中配置：")
            print("    BAIDU_APPID=你的appid")
            print("    BAIDU_APPKEY=你的appkey")
            sys.exit(1)

    if not os.path.exists(args.input):
        print(f"file not exist: {args.input}")
        sys.exit(1)

    with open(args.input, encoding="utf-8") as f:
        content = f.read()

    subs   = [s.strip() for s in content.strip().split("\n\n") if s.strip()]
    parsed = []
    for sub in subs:
        parts = sub.split("\n", 2)
        if len(parts) != 3:
            continue
        parsed.append((parts[0], parts[1], parts[2]))

    total  = len(parsed)
    failed = []

    tmp_output = args.output + ".tmp"
    try:
        with open(tmp_output, "w", encoding="utf-8") as out:
            for batch_start in range(0, total, BATCH_SIZE):
                batch     = parsed[batch_start: batch_start + BATCH_SIZE]
                sentences = [s for _, _, s in batch]
                batch_end = min(batch_start + BATCH_SIZE, total)

                print(f"[{args.engine}] translating [{batch_start + 1}-{batch_end}/{total}]...")
                try:
                    if args.engine == "deepl":
                        translated = translate_batch_deepl(sentences, args.tgt_lang, api_key)
                    else:
                        translated = translate_batch_baidu(sentences, args.tgt_lang, appid, appkey)
                except Exception as e:
                    print(f"[warn] batch {batch_start + 1}-{batch_end} failed: {e}")
                    translated = sentences   # 失败保留原文
                    failed.extend(range(batch_start + 1, batch_end + 1))

                for (idx, timestamp, _), dst in zip(batch, translated):
                    out.write(f"{idx}\n{timestamp}\n{dst}\n\n")

                # 百度限速 QPS=1；DeepL Free 无需限速
                if args.engine == "baidu" and batch_end < total:
                    time.sleep(BAIDU_SLEEP_SECONDS)

        if os.path.exists(args.output):
            os.remove(args.output)
        os.rename(tmp_output, args.output)

    except Exception as e:
        if os.path.exists(tmp_output):
            os.remove(tmp_output)
        print(f"[error] {e}")
        sys.exit(2)

    if failed:
        print(f"[warn] 以下字幕条目翻译失败（已保留原文）: {failed}")
        sys.exit(3)

    print(f"done! translated {total} subtitles -> {args.output}")
    sys.exit(0)


if __name__ == "__main__":
    main()
