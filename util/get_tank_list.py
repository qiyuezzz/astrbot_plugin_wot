import requests
import json


def fetch_all_tank_data():
    url = "https://wotgame.cn/wotpbe/tankopedia/api/vehicles/by_filters/"

    payload = {
        'filter[nation]': 'ussr,usa,france,germany,uk,japan,czech,sweden,poland,italy,china',
        'filter[language]': 'zh-cn',
        'filter[premium]': '0,1',
        'filter[apply_modified_ttc]': '1'
    }

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://wotgame.cn/zh-cn/tankopedia/',
        'X-Requested-With': 'XMLHttpRequest'
    }

    try:
        print("正在获取全量坦克数据...")
        response = requests.post(url, data=payload, headers=headers)
        response.raise_for_status()

        result = response.json()
        inner_data = result.get('data', {})

        params = inner_data.get('parameters', [])
        tank_rows = inner_data.get('data', [])

        # 建立名称索引字典
        name_indexed_library = {}

        for row in tank_rows:
            # 将该行所有数据与参数名一一对应
            tank_details = {params[i]: row[i] for i in range(len(params))}

            # 使用名称作为 Key
            tank_name = tank_details.get('name')
            if tank_name:
                # 如果存在重名车，可以通过组合 [名称+ID] 或者覆盖
                name_indexed_library[tank_name] = tank_details

        # 保存为 JSON
        with open('data/plugins/astrbot_plugin_wot/static/json/wot_tanks_full.json', 'w', encoding='utf-8') as f:
            json.dump(name_indexed_library, f, ensure_ascii=False, indent=4)

        print(f"成功！已保存 {len(name_indexed_library)} 辆坦克的全字段信息。")
        print(f"包含字段: {', '.join(params[:10])} ... 等共 {len(params)} 个字段")

    except Exception as e:
        print(f"运行失败: {e}")