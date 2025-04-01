import re
import base64
import uuid
import shutil # Import shutil for moving files
from pathlib import Path
import os
import glob
from urllib.parse import quote # 導入 quote 函數

from config import IMAGES_DIR # Destination base directory

def process_markdown_images(content: str, task_id: str, image_export_mode: str, output_base_name: str, output_dir_path: Path) -> str:
    """處理 Markdown 中的圖片，根據指定的匯出模式處理圖片
    
    參數:
        content: Markdown 內容
        task_id: 任務 ID，用於生成唯一檔名
        image_export_mode: 圖片處理模式，可為 'embedded' (內嵌), 'referenced' (引用) 或 'placeholder' (佔位符)
        output_base_name: 輸出檔案的基本名稱，用於建立圖片子目錄
        output_dir_path: The directory where the main output file (and potentially docling's image dir) is saved.
    """
    print(f"[process_markdown_images] Received image_export_mode: {image_export_mode}")
    print(f"[process_markdown_images] Output base name: {output_base_name}, Output dir: {output_dir_path}")
    
    # --- 三種可能的圖片模式 ---
    # 1. data URI 格式的圖片 (base64)
    base64_img_pattern = r'!\[(.*?)\]\((data:image\/([^;]+);base64,([^)]+))\)'
    
    # 2. 標準相對路徑圖片連結
    std_img_pattern = r'!\[(.*?)\]\((?!data:|https?:|/)([^)]+?)\)'
    
    # 3. 註解標記圖片
    comment_img_pattern = r'<!-- image -->'
    
    # 輸出前 100 個字元以進行偵錯
    print(f"[process_markdown_images] Content preview: {content[:100].replace(chr(10), ' ')}")
    
    # 尋找各種類型的圖片引用
    base64_matches = list(re.finditer(base64_img_pattern, content))
    std_matches = list(re.finditer(std_img_pattern, content))
    comment_matches = list(re.finditer(comment_img_pattern, content))
    
    print(f"[process_markdown_images] Found matches - base64: {len(base64_matches)}, standard: {len(std_matches)}, comments: {len(comment_matches)}")
    
    # 顯示找到的匹配
    for i, m in enumerate(base64_matches[:3]):
        print(f"  Base64 Match {i+1}: alt={m.group(1)}, type={m.group(3)}, data_len={len(m.group(4))}")
    
    for i, m in enumerate(std_matches[:3]):
        print(f"  Std Match {i+1}: alt={m.group(1)}, path={m.group(2)}")
    
    if image_export_mode != "referenced":
        # 如果不是引用模式，直接返回原始內容
        return content
    
    # 確保目標目錄存在
    # 對 output_base_name 進行編碼，用於檔案系統路徑（儘管通常檔案系統能處理，但保持一致）
    # 注意：檔案系統路徑通常不需要 URL 編碼，但 Web 路徑需要
    # static_image_dest_dir = IMAGES_DIR / quote(output_base_name, safe='') # 檔案系統路徑通常不需要編碼
    static_image_dest_dir = IMAGES_DIR / output_base_name # 檔案系統路徑保持原樣
    static_image_dest_dir.mkdir(parents=True, exist_ok=True)
    
    # 編碼用於 Web 路徑的目錄名
    encoded_output_base_name = quote(output_base_name, safe='')
    
    processed_images_count = 0
    
    # --- 處理 base64 嵌入圖片 ---
    def replace_base64_img(match):
        nonlocal processed_images_count
        alt_text = match.group(1)
        img_url = match.group(2)
        img_type = match.group(3)
        encoded_data = match.group(4)
        
        print(f"[process_markdown_images] Processing base64 image (alt: {alt_text})")
        
        try:
            # 解碼 base64 數據
            img_data = base64.b64decode(encoded_data)
            
            # 生成唯一檔名
            img_filename = f"{task_id}_{uuid.uuid4().hex}.{img_type}"
            dest_img_path = static_image_dest_dir / img_filename
            
            # 儲存圖片
            with open(dest_img_path, 'wb') as f:
                f.write(img_data)
            
            processed_images_count += 1
            
            # 構建 Web 路徑，對檔名進行編碼 (雖然 UUID 生成的通常不需要，但保持健壯性)
            encoded_img_filename = quote(img_filename, safe='')
            web_path = f"/static/images/{encoded_output_base_name}/{encoded_img_filename}"
            
            print(f"[process_markdown_images] Saved base64 image to {dest_img_path}, web path: {web_path}")
            
            # 確保 alt_text 中的特殊字元不會破壞 Markdown 語法 (例如 ] )
            safe_alt_text = alt_text.replace(']', '\\]')
            return f'![{safe_alt_text}]({web_path})'
            
        except base64.binascii.Error as e:
            print(f"[process_markdown_images] Base64 decode error: {e}")
            return match.group(0)
        except Exception as e:
            print(f"[process_markdown_images] Error processing base64 image: {e}")
            return match.group(0)
    
    # 先處理 base64 圖片
    processed_content = re.sub(base64_img_pattern, replace_base64_img, content)
    
    # --- 查找相關圖片目錄 ---
    possible_img_dirs = [
        output_dir_path / output_base_name,
        output_dir_path / f"{output_base_name}_images",
        output_dir_path / "images",
    ]
    
    # 還要考慮當前輸出目錄中可能存在的隱式相對目錄
    possible_img_dirs.extend(
        p for p in output_dir_path.iterdir() 
        if p.is_dir() and not p.name.startswith('.')
    )
    
    # 顯示所有可能的圖片目錄
    print(f"[process_markdown_images] Checking potential image directories:")
    for img_dir in possible_img_dirs:
        if img_dir.is_dir():
            print(f"  Found directory: {img_dir}")
            # 列出目錄內容
            files = list(img_dir.glob("*"))
            if files:
                print(f"  Contains {len(files)} files: {', '.join(str(f.name) for f in files[:5])}")
            else:
                print(f"  Directory is empty")
    
    # --- 收集所有可能的圖片檔案 ---
    all_image_files = []
    for img_dir in possible_img_dirs:
        if img_dir.is_dir():
            for ext in ['*.png', '*.jpg', '*.jpeg', '*.gif', '*.webp', '*.svg']:
                all_image_files.extend(img_dir.glob(ext))
                all_image_files.extend(img_dir.glob(ext.upper()))
    
    # 輸出找到的圖片
    print(f"[process_markdown_images] Found {len(all_image_files)} total image files in all directories")
    if all_image_files:
        print(f"  First few images: {', '.join(str(f.name) for f in all_image_files[:5])}")
    
    # --- 處理標準相對路徑圖片 ---
    def replace_std_img(match):
        nonlocal processed_images_count
        alt_text = match.group(1)
        relative_img_path_str = match.group(2)
        
        print(f"[process_markdown_images] Processing standard image path: {relative_img_path_str}")
        
        try:
            # 嘗試不同的源路徑組合
            source_paths_to_try = [
                output_dir_path / relative_img_path_str,  # 直接相對路徑
                Path(relative_img_path_str).resolve(),    # 嘗試解析絕對路徑
            ]
            
            # 對於可能的圖片目錄，也嘗試在其中查找
            for img_dir in possible_img_dirs:
                if img_dir.is_dir():
                    img_basename = os.path.basename(relative_img_path_str)
                    source_paths_to_try.append(img_dir / img_basename)
            
            source_img_path = None
            
            # 嘗試找到存在的圖片檔案
            for path_to_try in source_paths_to_try:
                if path_to_try.is_file():
                    source_img_path = path_to_try
                    print(f"[process_markdown_images] Found image at: {source_img_path}")
                    break
            
            if not source_img_path:
                print(f"[process_markdown_images] Warning: Could not find image file for path {relative_img_path_str}")
                print(f"  Tried paths: {[str(p) for p in source_paths_to_try]}")
                return match.group(0)
            
            # 生成唯一檔名
            img_filename = f"{task_id}_{uuid.uuid4().hex}{source_img_path.suffix}"
            dest_img_path = static_image_dest_dir / img_filename
            
            # 複製檔案
            print(f"[process_markdown_images] Copying image from {source_img_path} to {dest_img_path}")
            shutil.copy2(str(source_img_path), str(dest_img_path))
            processed_images_count += 1
            
            # 構建 Web 路徑，進行編碼
            encoded_img_filename = quote(img_filename, safe='')
            web_path = f"/static/images/{encoded_output_base_name}/{encoded_img_filename}"
            
            safe_alt_text = alt_text.replace(']', '\\]')
            return f'![{safe_alt_text}]({web_path})'
            
        except Exception as e:
            print(f"[process_markdown_images] Error processing image {relative_img_path_str}: {e}")
            return match.group(0)
    
    # 處理標準圖片連結
    processed_content = re.sub(std_img_pattern, replace_std_img, processed_content)
    
    # --- 處理註解標記 ---
    if comment_matches and all_image_files:
        print(f"[process_markdown_images] Processing {len(comment_matches)} comment image tags with {len(all_image_files)} available images")
        
        # 將圖片文件排序，確保處理順序一致
        all_image_files.sort(key=lambda p: p.name)
        
        img_index = 0
        
        def replace_comment_img(match):
            nonlocal img_index, processed_images_count
            
            if img_index >= len(all_image_files):
                print(f"[process_markdown_images] Warning: Not enough image files for all <!-- image --> tags")
                return match.group(0)
            
            source_img_path = all_image_files[img_index]
            img_index += 1
            
            try:
                # 生成唯一檔名
                img_filename = f"{task_id}_{uuid.uuid4().hex}{source_img_path.suffix}"
                dest_img_path = static_image_dest_dir / img_filename
                
                # 複製檔案
                print(f"[process_markdown_images] Copying comment image {img_index} from {source_img_path} to {dest_img_path}")
                shutil.copy2(str(source_img_path), str(dest_img_path))
                processed_images_count += 1
                
                # 構建 Web 路徑，進行編碼
                encoded_img_filename = quote(img_filename, safe='')
                web_path = f"/static/images/{encoded_output_base_name}/{encoded_img_filename}"
                
                # 使用檔名作為替代文字
                alt_text = source_img_path.stem
                
                # 確保 alt_text 中的特殊字元不會破壞 Markdown 語法 (例如 ] )
                safe_alt_text = alt_text.replace(']', '\\]')
                return f'![{safe_alt_text}]({web_path})'
                
            except Exception as e:
                print(f"[process_markdown_images] Error processing comment image {source_img_path}: {e}")
                return match.group(0)
        
        # 替換所有註解圖片標記
        processed_content = re.sub(comment_img_pattern, replace_comment_img, processed_content)
    
    # --- 如果沒有找到任何圖片引用，但有圖片檔案，則嘗試添加到文件末尾 ---
    if processed_images_count == 0 and all_image_files and image_export_mode == "referenced":
        print(f"[process_markdown_images] No image references processed, but found {len(all_image_files)} images. Adding at end of document.")
        
        processed_content += "\n\n## 圖片\n\n"
        
        for img_file in all_image_files:
            try:
                # 生成唯一檔名
                img_filename = f"{task_id}_{uuid.uuid4().hex}{img_file.suffix}"
                dest_img_path = static_image_dest_dir / img_filename
                
                # 複製檔案
                print(f"[process_markdown_images] Copying additional image from {img_file} to {dest_img_path}")
                shutil.copy2(str(img_file), str(dest_img_path))
                processed_images_count += 1
                
                # 構建 Web 路徑，進行編碼
                encoded_img_filename = quote(img_filename, safe='')
                web_path = f"/static/images/{encoded_output_base_name}/{encoded_img_filename}"
                
                # 使用檔名作為替代文字
                alt_text = img_file.stem
                
                # 確保 alt_text 中的特殊字元不會破壞 Markdown 語法 (例如 ] )
                safe_alt_text = alt_text.replace(']', '\\]')
                
                processed_content += f'![{safe_alt_text}]({web_path})\n\n'
                
            except Exception as e:
                print(f"[process_markdown_images] Error processing additional image {img_file}: {e}")
    
    # --- 輸出處理結果 ---
    if processed_images_count > 0:
        print(f"[process_markdown_images] Successfully processed {processed_images_count} images to /static/images/{output_base_name}/")
    elif image_export_mode == "referenced":
        if base64_matches or std_matches or comment_matches:
            print(f"[process_markdown_images] Warning: Found image references but failed to process any images")
        else:
            print(f"[process_markdown_images] No image references found in the content")
    
    return processed_content

def process_html_images(content: str, task_id: str, image_export_mode: str, output_base_name: str, output_dir_path: Path) -> str:
    """處理 HTML 中的圖片，根據指定的匯出模式處理圖片
    
    參數:
        content: HTML 內容
        task_id: 任務 ID，用於生成唯一檔名
        image_export_mode: 圖片處理模式，可為 'embedded' (內嵌), 'referenced' (引用) 或 'placeholder' (佔位符)
        output_base_name: 輸出檔案的基本名稱，用於建立圖片子目錄
        output_dir_path: The directory where the main output file (and potentially docling's image dir) is saved.
    """
    print(f"[process_html_images] Received image_export_mode: {image_export_mode}")
    print(f"[process_html_images] Output base name: {output_base_name}, Output dir: {output_dir_path}")
    
    # --- 三種可能的圖片模式 ---
    # 1. data URI 格式的圖片 (base64)
    base64_img_pattern = r'<img(?:[^>]*?)src="(data:image\/([^;]+);base64,([^"]+))"(?:[^>]*?)alt="([^"]*)"(?:[^>]*?)>'
    base64_img_pattern_no_alt = r'<img(?:[^>]*?)src="(data:image\/([^;]+);base64,([^"]+))"(?:[^>]*?)>'
    
    # 2. 標準相對路徑圖片連結 (非 http, https, / 開頭)
    std_img_pattern = r'<img(?:[^>]*?)src="(?!data:|https?:|/)([^"]+)"(?:[^>]*?)alt="([^"]*)"(?:[^>]*?)>'
    std_img_pattern_no_alt = r'<img(?:[^>]*?)src="(?!data:|https?:|/)([^"]+)"(?:[^>]*?)>'
    
    # 3. 註解標記圖片
    comment_img_pattern = r'<!-- image -->'
    
    # 輸出前 100 個字元以進行偵錯
    print(f"[process_html_images] Content preview: {content[:100].replace(chr(10), ' ')}")
    
    # 尋找各種類型的圖片引用
    base64_matches = list(re.finditer(base64_img_pattern, content))
    base64_matches_no_alt = list(re.finditer(base64_img_pattern_no_alt, content))
    
    std_matches = list(re.finditer(std_img_pattern, content))
    std_matches_no_alt = list(re.finditer(std_img_pattern_no_alt, content))
    
    comment_matches = list(re.finditer(comment_img_pattern, content))
    
    print(f"[process_html_images] Found matches - base64: {len(base64_matches)} (no alt: {len(base64_matches_no_alt)}), "
          f"standard: {len(std_matches)} (no alt: {len(std_matches_no_alt)}), comments: {len(comment_matches)}")
    
    # 顯示找到的匹配
    for i, m in enumerate(base64_matches[:3]):
        print(f"  Base64 Match {i+1}: alt={m.group(4)}, type={m.group(2)}, data_len={len(m.group(3))}")
    
    for i, m in enumerate(std_matches[:3]):
        print(f"  Std Match {i+1}: src={m.group(1)}, alt={m.group(2)}")
    
    if image_export_mode != "referenced":
        # 如果不是引用模式，直接返回原始內容
        return content
    
    # 確保目標目錄存在 (檔案系統路徑保持原樣)
    static_image_dest_dir = IMAGES_DIR / output_base_name
    static_image_dest_dir.mkdir(parents=True, exist_ok=True)
    
    # 編碼用於 Web 路徑的目錄名
    encoded_output_base_name = quote(output_base_name, safe='')
    
    processed_images_count = 0
    
    # --- 處理 base64 嵌入圖片 (帶 alt 文字) ---
    def replace_base64_img(match):
        nonlocal processed_images_count
        img_url = match.group(1)
        img_type = match.group(2)
        encoded_data = match.group(3)
        alt_text = match.group(4)
        
        print(f"[process_html_images] Processing base64 image (alt: {alt_text})")
        
        try:
            # 解碼 base64 數據
            img_data = base64.b64decode(encoded_data)
            
            # 生成唯一檔名
            img_filename = f"{task_id}_{uuid.uuid4().hex}.{img_type}"
            dest_img_path = static_image_dest_dir / img_filename
            
            # 儲存圖片
            with open(dest_img_path, 'wb') as f:
                f.write(img_data)
            
            processed_images_count += 1
            
            # 構建 Web 路徑，進行編碼
            encoded_img_filename = quote(img_filename, safe='')
            web_path = f"/static/images/{encoded_output_base_name}/{encoded_img_filename}"
            
            print(f"[process_html_images] Saved base64 image to {dest_img_path}, web path: {web_path}")
            
            # HTML alt 屬性中的引號需要轉義
            safe_alt_text = alt_text.replace('"', '&quot;')
            return f'<img src="{web_path}" alt="{safe_alt_text}">'
            
        except base64.binascii.Error as e:
            print(f"[process_html_images] Base64 decode error: {e}")
            return match.group(0)
        except Exception as e:
            print(f"[process_html_images] Error processing base64 image: {e}")
            return match.group(0)
    
    # --- 處理 base64 嵌入圖片 (無 alt 文字) ---
    def replace_base64_img_no_alt(match):
        nonlocal processed_images_count
        img_url = match.group(1)
        img_type = match.group(2)
        encoded_data = match.group(3)
        alt_text = "image"  # 默認 alt 文字
        
        print(f"[process_html_images] Processing base64 image (no alt)")
        
        try:
            # 解碼 base64 數據
            img_data = base64.b64decode(encoded_data)
            
            # 生成唯一檔名
            img_filename = f"{task_id}_{uuid.uuid4().hex}.{img_type}"
            dest_img_path = static_image_dest_dir / img_filename
            
            # 儲存圖片
            with open(dest_img_path, 'wb') as f:
                f.write(img_data)
            
            processed_images_count += 1
            
            # 構建 Web 路徑，進行編碼
            encoded_img_filename = quote(img_filename, safe='')
            web_path = f"/static/images/{encoded_output_base_name}/{encoded_img_filename}"
            
            print(f"[process_html_images] Saved base64 image to {dest_img_path}, web path: {web_path}")
            
            # alt 屬性中的引號需要轉義
            safe_alt_text = alt_text.replace('"', '&quot;')
            return f'<img src="{web_path}" alt="{safe_alt_text}">'
            
        except base64.binascii.Error as e:
            print(f"[process_html_images] Base64 decode error: {e}")
            return match.group(0)
        except Exception as e:
            print(f"[process_html_images] Error processing base64 image: {e}")
            return match.group(0)
    
    # 先處理 base64 圖片
    processed_content = re.sub(base64_img_pattern, replace_base64_img, content)
    processed_content = re.sub(base64_img_pattern_no_alt, replace_base64_img_no_alt, processed_content)
    
    # --- 查找相關圖片目錄 ---
    possible_img_dirs = [
        output_dir_path / output_base_name,
        output_dir_path / f"{output_base_name}_images",
        output_dir_path / "images",
    ]
    
    # 還要考慮當前輸出目錄中可能存在的隱式相對目錄
    possible_img_dirs.extend(
        p for p in output_dir_path.iterdir() 
        if p.is_dir() and not p.name.startswith('.')
    )
    
    # 顯示所有可能的圖片目錄
    print(f"[process_html_images] Checking potential image directories:")
    for img_dir in possible_img_dirs:
        if img_dir.is_dir():
            print(f"  Found directory: {img_dir}")
            # 列出目錄內容
            files = list(img_dir.glob("*"))
            if files:
                print(f"  Contains {len(files)} files: {', '.join(str(f.name) for f in files[:5])}")
            else:
                print(f"  Directory is empty")
    
    # --- 收集所有可能的圖片檔案 ---
    all_image_files = []
    for img_dir in possible_img_dirs:
        if img_dir.is_dir():
            for ext in ['*.png', '*.jpg', '*.jpeg', '*.gif', '*.webp', '*.svg']:
                all_image_files.extend(img_dir.glob(ext))
                all_image_files.extend(img_dir.glob(ext.upper()))
    
    # 輸出找到的圖片
    print(f"[process_html_images] Found {len(all_image_files)} total image files in all directories")
    if all_image_files:
        print(f"  First few images: {', '.join(str(f.name) for f in all_image_files[:5])}")
    
    # --- 處理標準相對路徑圖片 (帶 alt 文字) ---
    def replace_std_img(match):
        nonlocal processed_images_count
        relative_img_path_str = match.group(1)
        alt_text = match.group(2)
        
        print(f"[process_html_images] Processing standard image path: {relative_img_path_str}")
        
        try:
            # 嘗試不同的源路徑組合
            source_paths_to_try = [
                output_dir_path / relative_img_path_str,  # 直接相對路徑
                Path(relative_img_path_str).resolve(),    # 嘗試解析絕對路徑
            ]
            
            # 對於可能的圖片目錄，也嘗試在其中查找
            for img_dir in possible_img_dirs:
                if img_dir.is_dir():
                    img_basename = os.path.basename(relative_img_path_str)
                    source_paths_to_try.append(img_dir / img_basename)
            
            source_img_path = None
            
            # 嘗試找到存在的圖片檔案
            for path_to_try in source_paths_to_try:
                if path_to_try.is_file():
                    source_img_path = path_to_try
                    print(f"[process_html_images] Found image at: {source_img_path}")
                    break
            
            if not source_img_path:
                print(f"[process_html_images] Warning: Could not find image file for path {relative_img_path_str}")
                print(f"  Tried paths: {[str(p) for p in source_paths_to_try]}")
                return match.group(0)
            
            # 生成唯一檔名
            img_filename = f"{task_id}_{uuid.uuid4().hex}{source_img_path.suffix}"
            dest_img_path = static_image_dest_dir / img_filename
            
            # 複製檔案
            print(f"[process_html_images] Copying image from {source_img_path} to {dest_img_path}")
            shutil.copy2(str(source_img_path), str(dest_img_path))
            processed_images_count += 1
            
            # 構建 Web 路徑，進行編碼
            encoded_img_filename = quote(img_filename, safe='')
            web_path = f"/static/images/{encoded_output_base_name}/{encoded_img_filename}"
            
            safe_alt_text = alt_text.replace('"', '&quot;')
            return f'<img src="{web_path}" alt="{safe_alt_text}">'
            
        except Exception as e:
            print(f"[process_html_images] Error processing image {relative_img_path_str}: {e}")
            return match.group(0)
    
    # --- 處理標準相對路徑圖片 (無 alt 文字) ---
    def replace_std_img_no_alt(match):
        nonlocal processed_images_count
        relative_img_path_str = match.group(1)
        alt_text = "image"  # 默認 alt 文字
        
        print(f"[process_html_images] Processing standard image path: {relative_img_path_str} (no alt)")
        
        try:
            # 與帶 alt 文字的處理邏輯相同
            source_paths_to_try = [
                output_dir_path / relative_img_path_str,
                Path(relative_img_path_str).resolve(),
            ]
            
            for img_dir in possible_img_dirs:
                if img_dir.is_dir():
                    img_basename = os.path.basename(relative_img_path_str)
                    source_paths_to_try.append(img_dir / img_basename)
            
            source_img_path = None
            
            for path_to_try in source_paths_to_try:
                if path_to_try.is_file():
                    source_img_path = path_to_try
                    print(f"[process_html_images] Found image at: {source_img_path}")
                    break
            
            if not source_img_path:
                print(f"[process_html_images] Warning: Could not find image file for path {relative_img_path_str}")
                return match.group(0)
            
            img_filename = f"{task_id}_{uuid.uuid4().hex}{source_img_path.suffix}"
            dest_img_path = static_image_dest_dir / img_filename
            
            print(f"[process_html_images] Copying image from {source_img_path} to {dest_img_path}")
            shutil.copy2(str(source_img_path), str(dest_img_path))
            processed_images_count += 1
            
            # 構建 Web 路徑，進行編碼
            encoded_img_filename = quote(img_filename, safe='')
            web_path = f"/static/images/{encoded_output_base_name}/{encoded_img_filename}"
            
            safe_alt_text = alt_text.replace('"', '&quot;')
            return f'<img src="{web_path}" alt="{safe_alt_text}">'
            
        except Exception as e:
            print(f"[process_html_images] Error processing image {relative_img_path_str}: {e}")
            return match.group(0)
    
    # 處理標準圖片連結
    processed_content = re.sub(std_img_pattern, replace_std_img, processed_content)
    processed_content = re.sub(std_img_pattern_no_alt, replace_std_img_no_alt, processed_content)
    
    # --- 處理註解標記 ---
    if comment_matches and all_image_files:
        print(f"[process_html_images] Processing {len(comment_matches)} comment image tags with {len(all_image_files)} available images")
        
        # 將圖片文件排序，確保處理順序一致
        all_image_files.sort(key=lambda p: p.name)
        
        img_index = 0
        
        def replace_comment_img(match):
            nonlocal img_index, processed_images_count
            
            if img_index >= len(all_image_files):
                print(f"[process_html_images] Warning: Not enough image files for all <!-- image --> tags")
                return match.group(0)
            
            source_img_path = all_image_files[img_index]
            img_index += 1
            
            try:
                # 生成唯一檔名
                img_filename = f"{task_id}_{uuid.uuid4().hex}{source_img_path.suffix}"
                dest_img_path = static_image_dest_dir / img_filename
                
                # 複製檔案
                print(f"[process_html_images] Copying comment image {img_index} from {source_img_path} to {dest_img_path}")
                shutil.copy2(str(source_img_path), str(dest_img_path))
                processed_images_count += 1
                
                # 構建 Web 路徑，進行編碼
                encoded_img_filename = quote(img_filename, safe='')
                web_path = f"/static/images/{encoded_output_base_name}/{encoded_img_filename}"
                
                alt_text = source_img_path.stem
                safe_alt_text = alt_text.replace('"', '&quot;')
                
                return f'<img src="{web_path}" alt="{safe_alt_text}">'
                
            except Exception as e:
                print(f"[process_html_images] Error processing comment image {source_img_path}: {e}")
                return match.group(0)
        
        # 替換所有註解圖片標記
        processed_content = re.sub(comment_img_pattern, replace_comment_img, processed_content)
    
    # --- 如果沒有找到任何圖片引用，但有圖片檔案，則嘗試添加到文件末尾 ---
    if processed_images_count == 0 and all_image_files and image_export_mode == "referenced":
        print(f"[process_html_images] No image references processed, but found {len(all_image_files)} images. Adding at end of document.")
        
        processed_content += "\n\n<h2>圖片</h2>\n\n"
        
        for img_file in all_image_files:
            try:
                # 生成唯一檔名
                img_filename = f"{task_id}_{uuid.uuid4().hex}{img_file.suffix}"
                dest_img_path = static_image_dest_dir / img_filename
                
                # 複製檔案
                print(f"[process_html_images] Copying additional image from {img_file} to {dest_img_path}")
                shutil.copy2(str(img_file), str(dest_img_path))
                processed_images_count += 1
                
                # 構建 Web 路徑，進行編碼
                encoded_img_filename = quote(img_filename, safe='')
                web_path = f"/static/images/{encoded_output_base_name}/{encoded_img_filename}"
                
                alt_text = img_file.stem
                safe_alt_text = alt_text.replace('"', '&quot;')
                
                processed_content += f'<p><img src="{web_path}" alt="{safe_alt_text}"></p>\n\n'
                
            except Exception as e:
                print(f"[process_html_images] Error processing additional image {img_file}: {e}")
    
    # --- 輸出處理結果 ---
    if processed_images_count > 0:
        print(f"[process_html_images] Successfully processed {processed_images_count} images to /static/images/{output_base_name}/")
    elif image_export_mode == "referenced":
        if base64_matches or std_matches or comment_matches:
            print(f"[process_html_images] Warning: Found image references but failed to process any images")
        else:
            print(f"[process_html_images] No image references found in the content")
    
    return processed_content
