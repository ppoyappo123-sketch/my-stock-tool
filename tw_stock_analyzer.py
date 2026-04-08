            if data and 'tables' in data and data['tables']:
                table = data['tables'][0]
                for row in table.get('data', []):
                    if len(row) < 10 or row[0] != stock_id:   # row[0] 是股票代號
                        continue
                    
                    # 日期需要從 URL 或額外處理，這裡用 temp_date 月份 + 假設 row 有日期（實測看結構）
                    # 建議改用下面 CSV 方式更穩定
                    try:
                        ad_date = temp_date.replace(day=int(row[?]))  # 視實際欄位調整
                    except:
                        continue
