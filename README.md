# GeoScrapter
台灣鑽孔柱狀圖自動化爬取工具 (Taiwan Drill Hole Chart Scraper)自動化爬蟲工具，專門設計用來從政府工程地質探勘資料庫，批次下載全台灣的鑽孔柱狀圖 (Drill Hole Charts)。
🚀 核心功能
   1.突破防火牆封鎖：使用 Playwright 模擬真實無頭瀏覽器 (Headless Browser) 行為，自動造訪首頁取得合法的連線憑證，輕鬆繞過嚴格的 API 驗證機制。
   2.精準座標對位與查詢：內建 WGS84 轉 Web Mercator (EPSG:3857) 座標轉換函數，透過構造周邊的微小多邊形 (Polygon)精準鎖定鑽孔位置，取得內部的 ProjectKeyId 與 KeyId。
   3.Base64 圖檔自動解析：自動向 API 請求柱狀圖資料，並從回傳的資料中萃取Base64 加密字串，解碼還原成實體的 .png 柱狀圖圖片。
   4.檔名安全處理：下載的圖檔會以 案件編號_孔號_Chart_序號.png 的格式命名，並利用正規表達式自動過濾掉不合法的特殊字元（如斜線、星號等），防止系統存檔報錯。
   5.斷點續傳機制：自動建立並追蹤 processed_log_charts.txt。若因網路問題中斷，重新啟動程式會瞬間跳過已處理的鑽孔，從失敗處繼續執行，不怕浪費時間做白工。
🛠️ 環境需求與安裝步驟
   1 系統需求Python 3.8 或以上版本穩定的網路連線
   2.安裝必備套件請打開終端機 (Terminal 或 PowerShell) ，進入工具所在的資料夾，並執行以下指令，
    安裝所有需要的核心套件：Bashpip install pandas playwright requests urllib3
   3 安裝 Playwright 瀏覽器引擎這是本工具能成功繞過防護的關鍵，請務必執行此指令下載模擬用的 Chromium 瀏覽器：Bashpython -m playwright install chromium
📂 準備輸入資料請確保你的工作目錄中包含一個名為 all_taiwan_geotech_holes.csv 的檔案。
    這個檔案必須包含以下核心欄位（大小寫須完全一致）：  proj_no: 案件編號  hole_no: 孔號  coord_x: 經度 (WGS84)  coord_y: 緯度 (WGS84)  
▶️ 執行教學確認資料準備完畢後，在終端機中執行主程式：Bashpython scraper_chart.py

執行時的運作流程：
 1.程式會先啟動無頭瀏覽器，造訪地圖首頁以獲取合法的通行證。
 2.逐筆讀取 CSV 中的鑽孔資料，若發現缺少座標或格式錯誤會自動略過。
 3.檢查 processed_log_charts.txt，若該孔號已處理過則會極速跳過。
 4.將經緯度轉換為 Web Mercator，發送空間查詢以取得 ProjectKeyId 與 KeyId。
 5.請求柱狀圖的 Base64 字串，解碼後自動存入 chart_photos 資料夾中。
