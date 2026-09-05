"""图片元数据工具：解析/重建 WebUI infotext，并读写图片中的模板信息。

WebUI (ForgeNeo) 保存图片时会把 infotext 写入：
- PNG: tEXt 文本块，键为 "parameters"
- JPG/JPEG/WebP/AVIF/JXL/HEIF: EXIF 的 UserComment 字段

infotext 格式（AUTOMATIC1111 风格）：
    <正向提示词>
    Negative prompt: <负向提示词>
    Steps: 20, Sampler: ..., ..., Template: "...", Negative Template: "...", ...

本模块负责把 infotext 中的 "Template" / "Negative Template" 键
替换（或插入）为 genPrompt.json 中的模板内容。
"""

import json
import re
from pathlib import Path

from PIL import Image, PngImagePlugin

# 注意：import piexif 不会自动加载 piexif.helper 子模块，
# 必须显式导入，否则 piexif.helper 访问会抛 AttributeError
try:
    import piexif
    import piexif.helper as piexif_helper
except ImportError:
    piexif = None
    piexif_helper = None

TEMPLATE_LABEL = "Template"
NEGATIVE_TEMPLATE_LABEL = "Negative Template"

# 与 modules/infotext_utils.py 中 re_param_code 保持一致
_re_param = re.compile(r'\s*([\w\s\-\/]+):\s*("(?:\\.|[^\\"])+"|[^,]*)(?:,|$)')


def _quote(text) -> str:
    """与 WebUI infotext_utils.quote 一致：含特殊字符时用 JSON 字符串包裹。"""
    text = str(text)
    if "," not in text and "\n" not in text and ":" not in text:
        return text
    try:
        return json.dumps(text, ensure_ascii=False)
    except Exception:
        return text


def _unquote(text: str) -> str:
    if not text or not (text.startswith('"') and text.endswith('"')):
        return text
    try:
        return json.loads(text)
    except Exception:
        return text


def parse_infotext(infotext: str):
    """解析 infotext，返回 (prompt, negative_prompt, params)。

    params 为 [(key, value), ...] 列表，按出现顺序排列。
    """
    lines = infotext.strip().split("\n")
    if not lines:
        return "", "", []
    *body, lastline = lines
    if len(_re_param.findall(lastline)) < 3:
        body.append(lastline)
        lastline = ""

    prompt_lines = []
    neg_lines = []
    in_negative = False
    for line in body:
        line = line.strip()
        if line.startswith("Negative prompt:"):
            line = line.replace("Negative prompt:", "").strip()
            in_negative = True
        (neg_lines if in_negative else prompt_lines).append(line)

    params = [(k.strip(), _unquote(v.strip()))
              for k, v in _re_param.findall(lastline)]
    return "\n".join(prompt_lines), "\n".join(neg_lines), params


def rebuild_infotext(prompt, negative_prompt, params) -> str:
    """根据解析结果重建 infotext 文本（与 WebUI 格式一致）。"""
    param_text = ", ".join(
        k if k == v else f"{k}: {_quote(v)}"
        for k, v in params
        if v is not None
    )
    neg_text = f"\nNegative prompt: {negative_prompt}" if negative_prompt else ""
    return f"{prompt}{neg_text}\n{param_text}".strip()


def set_template_info(infotext: str, template_prompt: str,
                      template_negative: str) -> str:
    """把 infotext 中的 Template / Negative Template 改为模板内容。

    - 已存在则原位替换
    - 不存在则追加到参数尾部
    - 返回新的 infotext；若 infotext 为空或无法解析，原样返回
    """
    if not infotext or not infotext.strip():
        return infotext

    prompt, negative, params = parse_infotext(infotext)

    new_params = []
    has_template = False
    has_neg_template = False
    for k, v in params:
        if k == TEMPLATE_LABEL:
            new_params.append((k, template_prompt))
            has_template = True
        elif k == NEGATIVE_TEMPLATE_LABEL:
            new_params.append((k, template_negative))
            has_neg_template = True
        else:
            new_params.append((k, v))
    if not has_template:
        new_params.append((TEMPLATE_LABEL, template_prompt))
    if not has_neg_template:
        new_params.append((NEGATIVE_TEMPLATE_LABEL, template_negative))

    return rebuild_infotext(prompt, negative, new_params)


def _decode_user_comment(raw: bytes) -> str:
    """解析 EXIF UserComment 原始字节（兼容 piexif.helper 不可用的情况）。"""
    if not raw:
        return ""
    # PieXif UserComment 格式：前 8 字节为字符集标记 + '\0'*2
    if raw.startswith(b"UNICODE\x00\x00"):
        return raw[8:].decode("utf-16", errors="ignore")
    if raw.startswith(b"ASCII\x00\x00\x00\x00"):
        return raw[8:].decode("ascii", errors="ignore")
    try:
        return raw.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _encode_user_comment(text: str) -> bytes:
    """生成 EXIF UserComment 字节（与 piexif.helper.UserComment.dump 一致）。"""
    if piexif_helper is not None:
        return piexif_helper.UserComment.dump(text or "", encoding="unicode")
    return b"UNICODE\x00\x00" + (text or "").encode("utf-16")


def read_infotext(path: str | Path) -> str:
    """从图片文件读取 infotext（PNG tEXt parameters / EXIF UserComment）。"""
    path = Path(path)
    ext = path.suffix.lower()
    try:
        if ext == ".png":
            with Image.open(path) as img:
                return img.info.get("parameters", "")
        # 非 PNG：读取 EXIF UserComment
        if piexif is None:
            return ""
        try:
            exif_dict = piexif.load(str(path))
        except Exception:
            return ""
        raw = exif_dict.get("Exif", {}).get(piexif.ExifIFD.UserComment, b"")
        if not raw:
            return ""
        try:
            if piexif_helper is not None:
                return piexif_helper.UserComment.load(raw)
        except Exception:
            pass
        return _decode_user_comment(raw)
    except Exception:
        return ""


def write_infotext(path: str | Path, infotext: str) -> bool:
    """把 infotext 写回图片元数据。成功返回 True。"""
    path = Path(path)
    ext = path.suffix.lower()
    try:
        if ext == ".png":
            with Image.open(path) as img:
                pnginfo = PngImagePlugin.PngInfo()
                # 保留原有文本元数据（workflows 等），仅覆盖 parameters
                for k, v in img.info.items():
                    if isinstance(v, str) and k != "parameters":
                        pnginfo.add_text(k, v)
                if infotext:
                    pnginfo.add_text("parameters", infotext)
                save_kwargs = {"format": "PNG", "pnginfo": pnginfo}
                if img.info.get("icc_profile"):
                    save_kwargs["icc_profile"] = img.info["icc_profile"]
                if img.info.get("dpi"):
                    save_kwargs["dpi"] = img.info["dpi"]
                img.save(path, **save_kwargs)
            return True

        # 非 PNG：写 EXIF UserComment
        if piexif is None:
            raise ValueError("piexif 未安装，无法写入 EXIF")
        exif_bytes = piexif.dump({
            "Exif": {
                piexif.ExifIFD.UserComment: _encode_user_comment(infotext or ""),
            },
        })
        if ext in (".jpg", ".jpeg", ".webp", ".avif", ".jxl", ".heif"):
            try:
                # JPG 与部分 WebP 环境可直接 insert
                piexif.insert(exif_bytes, str(path))
                return True
            except Exception:
                if ext not in (".webp",):
                    raise
        if ext == ".webp":
            # PieXif 对 WebP 支持不佳时：无损重存并附带 exif
            with Image.open(path) as img:
                img.save(path, format="WEBP", exif=exif_bytes, lossless=True)
            return True
        raise ValueError(f"不支持的图片格式: {ext}")
    except Exception as e:
        logger = __import__("logging").getLogger(__name__)
        logger.warning(f"写回元数据失败 {path.name}: {e}")
        return False
