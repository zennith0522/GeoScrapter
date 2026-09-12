import pandas as pd
import os
import time
import base64
import math
import re  
from playwright.sync_api import sync_playwright

# ================= 輔助函式：不區分大小寫取得字典值 =================
def get_val(d, target_key):
    """從字典中忽略大小寫來尋找 key 的值"""
    if not isinstance(d, dict):
        return None
    for k, v in d.items():
        if k.lower() == target_key.lower():
            return v
    return None

# ================= 座標轉換函數 (WGS84 轉 Web Mercator) =================
def wgs84_to_web_mercator(lon, lat):
    x = lon * 20037508.34 / 180
    y = math.log(math.tan((90 + lat) * math.pi / 360)) / (math.pi / 180)
    y = y * 20037508.34 / 180
    return x, y

# ================= 初始設定與讀取紀錄 =================
csv_file = 'all_taiwan_geotech_holes.csv'
df = pd.read_csv(csv_file, dtype=str)
total_holes = len(df)

save_dir = "chart_photos" 
log_file = "processed_log_charts.txt" 

if not os.path.exists(save_dir):
    os.makedirs(save_dir)

processed_set = set()
if os.path.exists(log_file):
    with open(log_file, 'r', encoding='utf-8') as f:
        for line in f:
            processed_set.add(line.strip())
print(f"已讀取歷史紀錄：目前已處理 {len(processed_set)} 筆鑽孔柱狀圖。")

def mark_as_processed(lookup_key):
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(lookup_key + '\n')
    processed_set.add(lookup_key)

# ================= 主程式 =================
def main():
    with sync_playwright() as p:
        print("正在啟動瀏覽器...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
            ignore_https_errors=True
        )
        page = context.new_page()

        print("正在造訪首頁以獲取通行證...")
        try:
            page.goto("https://geotech.gsmma.gov.tw/imoeagis/Home/Map", wait_until="networkidle", timeout=30000)
            time.sleep(2) 
        except Exception as e:
            print(f"首頁載入超時或失敗: {e}")
            browser.close()
            return
            
        api_context = context.request
        print("\n================ 開始自動化爬取柱狀圖作業 ================\n")
        
        for index, row in df.iterrows():
            proj_no = str(row['proj_no']).strip()
            hole_no = str(row['hole_no']).strip()
            lookup_key = f"{proj_no}_{hole_no}"
            
            if lookup_key in processed_set:
                continue
                
            print(f"進度 [{index + 1}/{total_holes}] | 正在處理: 案件 {proj_no} - 孔號 {hole_no}")
            
            if pd.isna(row['coord_x']) or pd.isna(row['coord_y']):
                print(f" -> 缺少座標資料，略過。")
                mark_as_processed(lookup_key)
                continue
                
            try:
                lon = float(row['coord_x'])
                lat = float(row['coord_y'])
            except ValueError:
                print(f" -> 座標格式錯誤，略過。")
                mark_as_processed(lookup_key)
                continue
            
            mx, my = wgs84_to_web_mercator(lon, lat)
            offset = 50
            tiny_polygon = f"POLYGON(({mx-offset} {my-offset}, {mx-offset} {my+offset}, {mx+offset} {my+offset}, {mx+offset} {my-offset}, {mx-offset} {my-offset}))"
            
            coords_payload = {
                "aWKT": [tiny_polygon],
                "Limit": 0,
                "BeginDepth": "",
                "EndDepth": ""
            }
            
            target_id = None
            proj_key_id = None
            
            # ================= 第一階段：查出內部 ID 與 ProjectKeyId =================
            try:
                coords_res = api_context.post(
                    "https://geotech.gsmma.gov.tw/imoeagis/api/DrCoordsJson",
                    headers={
                        "Content-Type": "application/json; charset=utf-8",
                        "Referer": "https://geotech.gsmma.gov.tw/imoeagis/js/WebWorker/GetDrCoordsByWKT.js"
                    },
                    data=coords_payload,
                    timeout=45000  # ✅ 這裡已將 Timeout 放寬至 45 秒 (45000ms)
                )

                if coords_res.status == 200:
                    coords_data = coords_res.json()
                    
                    for item in coords_data:
                        api_proj = str(get_val(item, 'projNo') or '').strip()
                        api_hole = str(get_val(item, 'holePointNo') or '').strip()
                        
                        if api_proj.lower() == proj_no.lower() and api_hole.lower() == hole_no.lower():
                            target_id = get_val(item, 'keyid')
                            proj_key_id = get_val(item, 'projectkeyid') or get_val(item, 'projkeyid') or get_val(item, 'projectkey_id')
                            break
                else:
                    print(f" -> 查詢點位失敗，狀態碼: {coords_res.status}")
                    continue 
                    
            except Exception as e:
                print(f" -> 查詢點位發生網路錯誤，下次重試。({e})")
                continue 
                
            if not target_id or not proj_key_id:
                print(f" -> 未找到匹配點位 (TargetID: {target_id}, ProjKeyID: {proj_key_id})")
                mark_as_processed(lookup_key)
                continue
                
            print(f" -> 找到內部 KeyId: {target_id}, ProjectKeyId: {proj_key_id}，準備下載柱狀圖...")
            
            # ================= 第二階段：下載柱狀圖 =================
            chart_payload = {
                "Mode": "Chart",
                "ProjectKeyId": int(proj_key_id),
                "KeyId": int(target_id)
            }

            try:
                chart_api_url = "https://geotech.gsmma.gov.tw/Imoeagis/api/GeoReport" 

                img_res = api_context.post(
                    chart_api_url,
                    headers={
                        "Content-Type": "application/json; charset=utf-8",
                        "Referer": "https://geotech.gsmma.gov.tw/imoeagis/Home/Map"
                    },
                    data=chart_payload,  
                    timeout=300000
                )
                
                if img_res.status == 200:
                    chart_list = img_res.json()
                    
                    if not chart_list:
                        print(" -> API 回傳無資料。")
                    else:
                        for idx, html_string in enumerate(chart_list):
                            match = re.search(r'base64,\s*(.+?)"', html_string)
                            
                            if match:
                                base64_string = match.group(1)
                                img_data = base64.b64decode(base64_string)
                                
                                # ✅ 這裡加入了檔名過濾機制，避免含有斜線等特殊字元導致存檔失敗
                                raw_file_name = f"{proj_no}_{hole_no}_Chart_{idx+1}.png"
                                safe_file_name = re.sub(r'[\\/*?:"<>|]', '_', raw_file_name)
                                file_path = os.path.join(save_dir, safe_file_name)
                                
                                with open(file_path, 'wb') as f:
                                    f.write(img_data)
                                    
                                print(f"   [成功] 下載: {safe_file_name}")
                            else:
                                print(f"   [失敗] 無法從字串中解析出 Base64 格式")
                                
                    mark_as_processed(lookup_key)
                    
                else:
                    print(f" -> 請求柱狀圖失敗，狀態碼: {img_res.status}")
                    continue 
                    
            except Exception as e:
                print(f" -> 下載柱狀圖發生網路錯誤，下次重試。({e})")
                continue 
                
            time.sleep(1)

        print("\n[全台灣鑽孔柱狀圖自動化爬取任務，全部完成]")
        browser.close()

if __name__ == "__main__":
    main()