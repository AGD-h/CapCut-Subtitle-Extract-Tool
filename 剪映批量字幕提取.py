# -*- coding: utf-8 -*-
import os
import json
import re
import sys
import time

# ===================== 核心配置（无需修改任何内容）=====================
# 严格过滤规则：只保留纯中文汉字 + 标准中文标点，彻底过滤数字/英文/符号/乱码
ONLY_CHINESE_RULE = re.compile(r"[\u4e00-\u9fff，。！？、；：“”‘’（）【】《》…—]")
# 剪映固定字幕配置文件名（不要修改）
TARGET_JSON_NAME = "draft_content.json"
# 桌面输出的专属文件夹名
OUTPUT_FOLDER_NAME = "剪映批量提取字幕"

# ===================== 核心工具函数 =====================
def get_exe_current_dir():
    """获取exe/脚本所在的目录，完美兼容打包后exe运行和py脚本调试模式"""
    if getattr(sys, 'frozen', False):
        # 打包成exe后的运行模式，获取exe所在文件夹
        return os.path.dirname(sys.executable)
    else:
        # 直接运行py脚本的模式，获取脚本所在文件夹
        return os.path.dirname(os.path.abspath(__file__))

def get_windows_real_desktop():
    """双方案获取Windows真实桌面路径，兼容OneDrive同步/自定义桌面路径"""
    try:
        # 优先用Windows系统API读取真实桌面路径，兼容性最强
        import winreg
        reg_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders")
        desktop_path, _ = winreg.QueryValueEx(reg_key, "Desktop")
        desktop_path = os.path.expandvars(desktop_path)
        if os.path.exists(desktop_path):
            return desktop_path
    except Exception:
        pass
    # 兜底通用方案，适配所有Windows版本
    return os.path.join(os.path.expanduser("~"), "Desktop")

def get_pure_chinese_only(raw_text):
    """提取纯中文内容，彻底过滤所有无效字符"""
    valid_chars = ONLY_CHINESE_RULE.findall(raw_text)
    pure_text = "".join(valid_chars).strip()
    # 压缩多余空白字符，保证排版干净
    return re.sub(r"\s+", " ", pure_text)

def extract_subtitle_from_json(json_data):
    """精准提取剪映JSON里的字幕内容，只抓轨道上的有效字幕，杜绝无关内容"""
    subtitle_lines = []
    # 精准锁定剪映字幕专属存储路径：顶级materials -> texts数组（所有字幕都在这里）
    if not isinstance(json_data, dict):
        return subtitle_lines
    materials = json_data.get("materials", {})
    text_list = materials.get("texts", [])
    if not text_list:
        return subtitle_lines
    
    # 遍历所有字幕片段，提取纯中文内容
    for text_item in text_list:
        if not isinstance(text_item, dict):
            continue
        raw_content = text_item.get("content", "")
        if not raw_content:
            continue
        pure_line = get_pure_chinese_only(raw_content)
        if pure_line:
            subtitle_lines.append(pure_line)
    
    # 去重处理（保留字幕原始顺序，删除重复行）
    seen = set()
    unique_subtitles = []
    for line in subtitle_lines:
        if line not in seen:
            seen.add(line)
            unique_subtitles.append(line)
    return unique_subtitles

def find_all_draft_json(root_dir):
    """递归扫描根目录下所有剪映草稿的draft_content.json文件"""
    json_file_list = []
    # 遍历所有子文件夹，查找目标json文件
    for root, _, files in os.walk(root_dir):
        if TARGET_JSON_NAME in files:
            json_full_path = os.path.join(root, TARGET_JSON_NAME)
            # 提取工程信息，方便用户区分
            project_folder_name = os.path.basename(root)
            file_modify_time = time.strftime("%Y-%m-%d_%H-%M", time.localtime(os.path.getmtime(json_full_path)))
            json_file_list.append({
                "full_path": json_full_path,
                "project_name": project_folder_name,
                "modify_time": file_modify_time
            })
    return json_file_list

# ===================== 主程序入口 =====================
def main():
    print("="*55)
    print("         剪映全草稿批量纯字幕提取工具")
    print("="*55)

    # 1. 获取exe所在的目录（剪映工程根目录）
    root_scan_dir = get_exe_current_dir()
    print(f"📂 正在扫描剪映工程目录：{root_scan_dir}\n")

    # 2. 扫描所有草稿的json文件
    draft_json_list = find_all_draft_json(root_scan_dir)
    if not draft_json_list:
        print(f"❌ 错误：当前目录及子文件夹中，未找到任何 {TARGET_JSON_NAME} 文件")
        print("💡 请将exe放到剪映工程根目录后再运行！")
        input("\n按回车键关闭窗口...")
        sys.exit(1)

    print(f"✅ 共找到 {len(draft_json_list)} 个剪映草稿工程，开始批量提取...\n")

    # 3. 初始化变量
    success_count = 0
    fail_count = 0

    # 创建桌面输出文件夹
    desktop_path = get_windows_real_desktop()
    output_folder_path = os.path.join(desktop_path, OUTPUT_FOLDER_NAME)
    os.makedirs(output_folder_path, exist_ok=True)

    # 4. 批量处理每个草稿
    for index, draft_info in enumerate(draft_json_list, 1):
        json_path = draft_info["full_path"]
        project_name = draft_info["project_name"]
        modify_time = draft_info["modify_time"]
        print(f"[{index}/{len(draft_json_list)}] 正在处理草稿：{project_name}")

        # 读取并解析json文件，兼容全中文编码
        try:
            try:
                with open(json_path, "r", encoding="utf-8-sig") as f:
                    json_data = json.load(f)
            except UnicodeDecodeError:
                with open(json_path, "r", encoding="gbk") as f:
                    json_data = json.load(f)
        except Exception as e:
            print(f"   ❌ 解析失败：{str(e)}，已跳过该草稿")
            fail_count += 1
            continue

        # 提取纯中文字幕
        try:
            draft_subtitles = extract_subtitle_from_json(json_data)
        except Exception as e:
            print(f"   ❌ 字幕提取失败：{str(e)}，已跳过该草稿")
            fail_count += 1
            continue

        # 无有效字幕，跳过
        if not draft_subtitles:
            print(f"   ⚠️  该草稿无有效字幕，已跳过")
            fail_count += 1
            continue

        # 保存单个草稿的独立字幕文件
        output_file_name = f"草稿_{modify_time}_{project_name[:10]}.txt"
        output_file_full_path = os.path.join(output_folder_path, output_file_name)
        try:
            with open(output_file_full_path, "w", encoding="utf-8") as f:
                for line in draft_subtitles:
                    f.write(line + "\n")
            print(f"   ✅ 提取完成，共 {len(draft_subtitles)} 行有效字幕")
            success_count += 1
        except Exception as e:
            print(f"   ❌ 文件保存失败：{str(e)}，已跳过该草稿")
            fail_count += 1
            continue

    # 5. 最终结果汇总
    print("\n" + "="*55)
    print(f"📊 全部任务处理完成！")
    print(f"✅ 成功提取：{success_count} 个草稿")
    print(f"❌ 失败/无字幕：{fail_count} 个草稿")
    print(f"📂 所有独立字幕文件已保存到桌面：{OUTPUT_FOLDER_NAME} 文件夹")
    print("="*55)
    input("\n按回车键关闭窗口...")

if __name__ == "__main__":
    main()