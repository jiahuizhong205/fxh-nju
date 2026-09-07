"""把人工收集的 PDF 政策文件提取为可审查、可版本控制的 UTF-8 正文。"""

from __future__ import annotations

import argparse
from pathlib import Path


def extract(input_path: Path, output_path: Path) -> int:
    import fitz

    document = fitz.open(input_path)
    pages = []
    for number, page in enumerate(document, start=1):
        text = page.get_text("text", sort=True).strip()
        if text:
            pages.append(f"\n\n===== 第 {number} 页 =====\n{text}")

    content = "".join(pages).strip() + "\n"
    if not content:
        raise ValueError(f"未能从 {input_path} 提取到可用正文")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return len(content)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    count = extract(args.input, args.output)
    print(f"已提取 {args.input.name}：{count} 字符 -> {args.output}")


if __name__ == "__main__":
    main()
