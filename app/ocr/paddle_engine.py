from paddleocr import PaddleOCR
import traceback
import os

# Initialize PaddleOCR
ocr = PaddleOCR(use_angle_cls=True, lang="en")

def _get_top_y(box):
    """Extract the minimum Y coordinate from a bounding box"""
    if not box:
        return 0
    try:
        if isinstance(box, (list, tuple)) and len(box) > 0:
            if isinstance(box[0], (list, tuple)):
                # Box format: [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                return min(point[1] for point in box)
            elif len(box) >= 2:
                # Flat format: [x1, y1, x2, y2, ...]
                return box[1]
        return 0
    except (IndexError, TypeError, ValueError):
        return 0

def _group_lines_into_blocks(lines, y_threshold=18):
    if not lines:
        return []
    valid_lines = [line for line in lines if line.get("box") is not None]
    if not valid_lines:
        return []
    try:
        sorted_lines = sorted(valid_lines, key=lambda x: _get_top_y(x["box"]))
    except Exception as e:
        print(f"⚠️ Warning: Could not sort lines: {e}")
        sorted_lines = valid_lines

    blocks = []
    current_block = [sorted_lines[0]]
    for line in sorted_lines[1:]:
        prev_y = _get_top_y(current_block[-1]["box"])
        curr_y = _get_top_y(line["box"])
        if prev_y == 0 or curr_y == 0:
            blocks.append(current_block)
            current_block = [line]
            continue
        if abs(curr_y - prev_y) <= y_threshold:
            current_block.append(line)
        else:
            blocks.append(current_block)
            current_block = [line]
    blocks.append(current_block)
    return blocks

def _extract_page_data(page_res):
    """
    Helper to extract lines from a PaddleOCR 3.x result object/dict.
    Ensures we get a list of [box, (text, conf)] to avoid single-letter iteration.
    """
    # If it's already a list (Classic PaddleOCR 2.x format), return as is
    if isinstance(page_res, list):
        return page_res
    
    # Try to get data as a dictionary (PaddleOCR 3.x Result objects often have .res or can be converted)
    res_dict = page_res
    if not isinstance(page_res, dict) and hasattr(page_res, 'to_dict'):
        res_dict = page_res.to_dict()
    elif not isinstance(page_res, dict) and hasattr(page_res, 'res'):
        res_dict = page_res.res

    # Extraction Logic 1: Standard 'dt_polys' and 'rec_res' (Most 3.x versions)
    if isinstance(res_dict, dict) and 'dt_polys' in res_dict and 'rec_res' in res_dict:
        return [[box, rec] for box, rec in zip(res_dict['dt_polys'], res_dict['rec_res'])]
    
    # Extraction Logic 2: 'rec_texts' and 'rec_polys' (Some specific PP-Structure outputs)
    if isinstance(res_dict, dict) and 'rec_texts' in res_dict:
        texts = res_dict.get('rec_texts', [])
        scores = res_dict.get('rec_scores', [])
        boxes = res_dict.get('rec_polys', [])
        return [[boxes[i] if i < len(boxes) else [], (texts[i], scores[i] if i < len(scores) else 1.0)] 
                for i in range(len(texts))]

    return []

def run_ocr(img_paths):
    """
    Processes multi-page PDFs/images using predict() and semantic block grouping.
    """
    if isinstance(img_paths, str):
        img_paths = [img_paths]

    all_lines = []
    raw_text_list = []

    for img_path in img_paths:
        try:
            abs_path = os.path.abspath(img_path)
            # Use predict() for PaddleOCR 3.x
            results = ocr.predict(abs_path)
            
            if not results:
                continue

            # In PaddleOCR 3.x, predict() returns a list where each item is one page
            for page_res in results:
                # 1. Convert the page object/dict into a list of lines
                page_data = _extract_page_data(page_res)
                
                # 2. Process each line using logic from your 2nd code snippet
                for line in page_data:
                    try:
                        # [ [box], (text, confidence) ]
                        if isinstance(line, (list, tuple)) and len(line) > 1:
                            box = line[0]
                            text_info = line[1] # The (text, confidence) tuple
                            
                            # Snippet 2 Unpacking Logic
                            if isinstance(text_info, (tuple, list)):
                                text = str(text_info[0])
                                confidence = float(text_info[1])
                            else:
                                text = str(text_info)
                                confidence = 1.0
                                
                            if not text.strip():
                                continue

                            line_data = {
                                "text": text,
                                "confidence": confidence,
                                "box": box
                            }
                            all_lines.append(line_data)
                            raw_text_list.append(text)
                    except Exception:
                        continue
        except Exception as e:
            traceback.print_exc()
            continue

    if not all_lines:
        return {"raw_text": "", "lines": [], "item_blocks": []}

    # Group into blocks (Snippet 1 logic)
    blocks = _group_lines_into_blocks(all_lines)
    item_blocks = []
    for block in blocks:
        merged_text = " ".join(line["text"] for line in block)
        item_blocks.append({"text": merged_text, "lines": block})

    return {
        "raw_text": "\n".join(raw_text_list),
        "lines": all_lines,
        "item_blocks": item_blocks
    }