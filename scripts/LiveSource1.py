import urllib.request
from urllib.parse import urlparse
import re
import os
from datetime import datetime, timedelta, timezone
import random
import opencc
import socket
import time

# 创建输出目录（如果不存在）
os.makedirs('output/custom1/', exist_ok=True)

# 简繁转换
def traditional_to_simplified(text: str) -> str:
    converter = opencc.OpenCC('t2s')
    return converter.convert(text)

# 执行开始时间
timestart = datetime.now()

# 读取文本方法
def read_txt_to_array(file_name):
    try:
        with open(file_name, 'r', encoding='utf-8') as file:
            lines = file.readlines()
            lines = [line.strip() for line in lines if line.strip()]
            return lines
    except FileNotFoundError:
        print(f"文件未找到: {file_name}")
        return []
    except Exception as e:
        print(f"读取文件错误: {e}")
        return []

# 读取黑名单
def read_blacklist_from_txt(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()
        return [line.split(',')[1].strip() for line in lines if ',' in line]
    except Exception as e:
        print(f"读取黑名单错误: {e}")
        return []

# 加载黑名单
blacklist_auto = read_blacklist_from_txt('assets/blacklist1/blacklist_auto.txt') 
blacklist_manual = read_blacklist_from_txt('assets/blacklist1/blacklist_manual.txt') 
combined_blacklist = set(blacklist_auto + blacklist_manual)

# 定义多个对象用于存储不同内容的行文本
ys_lines = []  # CCTV
ws_lines = []  # 卫视频道
sh_lines = []  # 地方台-上海频道
zj_lines = []  # 地方台-浙江频道
jsu_lines = []  # 地方台-江苏频道
gd_lines = []  # 地方台-广东频道
hn_lines = []  # 地方台-湖南频道
ah_lines = []  # 地方台-安徽频道
hain_lines = []  # 地方台-海南频道
nm_lines = []  # 地方台-内蒙频道
hb_lines = []  # 地方台-湖北频道
ln_lines = []  # 地方台-辽宁频道
sx_lines = []  # 地方台-陕西频道
shanxi_lines = []  # 地方台-山西频道
shandong_lines = []  # 地方台-山东频道
yunnan_lines = []  # 地方台-云南频道
bj_lines = []  # 地方台-北京频道
cq_lines = []  # 地方台-重庆频道
fj_lines = []  # 地方台-福建频道
gs_lines = []  # 地方台-甘肃频道
gx_lines = []  # 地方台-广西频道
gz_lines = []  # 地方台-贵州频道
heb_lines = []  # 地方台-河北频道
hen_lines = []  # 地方台-河南频道
hlj_lines = []  # 地方台-黑龙江频道
jl_lines = []  # 地方台-吉林频道
jx_lines = []  # 地方台-江西频道
nx_lines = []  # 地方台-宁夏频道
qh_lines = []  # 地方台-青海频道
sc_lines = []  # 地方台-四川频道
tj_lines = []  # 地方台-天津频道
xj_lines = []  # 地方台-新疆频道

ty_lines = []  # 体育频道
tyss_lines = []  # 体育赛事
sz_lines = []  # 数字频道
yy_lines = []  # 音乐频道
gj_lines = []  # 国际频道
js_lines = []  # 解说
cw_lines = []  # 春晚
dy_lines = []  # 电影
dsj_lines = []  # 电视剧
gat_lines = []  # 港澳台
xg_lines = []  # 香港
aomen_lines = []  # 澳门
tw_lines = []  # 台湾
dhp_lines = []  # 动画片
douyu_lines = []  # 斗鱼直播
huya_lines = []  # 虎牙直播
radio_lines = []  # 收音机
zb_lines = []  # 直播中国
zy_lines = []  # 综艺频道
game_lines = []  # 游戏频道
xq_lines = []  # 戏曲
jlp_lines = []  # 记录片

other_lines = []
other_lines_url = []

def process_name_string(input_str):
    """处理频道名称字符串"""
    parts = input_str.split(',')
    processed_parts = [process_part(part) for part in parts]
    return ','.join(processed_parts)

def process_part(part_str):
    """处理单个频道名称部分"""
    if "CCTV" in part_str and "://" not in part_str:
        part_str = part_str.replace("IPV6", "").replace("PLUS", "+").replace("1080", "")
        filtered_str = ''.join(char for char in part_str if char.isdigit() or char == 'K' or char == '+')
        
        if not filtered_str.strip():
            filtered_str = part_str.replace("CCTV", "")

        # 修复逻辑：正确处理4K/8K标签
        if len(filtered_str) > 2:
            if re.search(r'4K|8K', filtered_str):
                filtered_str = re.sub(r'(4K|8K).*', r'\1', filtered_str)
                # 检查除了4K/8K外是否还有其他内容
                remaining_chars = filtered_str.replace('4K', '').replace('8K', '')
                if len(remaining_chars) > 2:
                    filtered_str = re.sub(r'(4K|8K)', r'(\1)', filtered_str)

        return "CCTV" + filtered_str 
        
    elif "卫视" in part_str:
        pattern = r'卫视「.*」'
        return re.sub(pattern, '卫视', part_str)
    
    return part_str

def get_url_file_extension(url):
    """获取URL文件扩展名"""
    parsed_url = urlparse(url)
    path = parsed_url.path
    return os.path.splitext(path)[1]

def convert_m3u_to_txt(m3u_content):
    """转换M3U格式为TXT格式"""
    lines = m3u_content.split('\n')
    txt_lines = []
    channel_name = ""
    
    for line in lines:
        if line.startswith("#EXTM3U"):
            continue
        if line.startswith("#EXTINF"):
            channel_name = line.split(',')[-1].strip()
        elif line.startswith("http") or line.startswith("rtmp") or line.startswith("p3p"):
            txt_lines.append(f"{channel_name},{line.strip()}")
        
        if "#genre#" not in line and "," in line and "://" in line:
            pattern = r'^[^,]+,[^\s]+://[^\s]+$'
            if bool(re.match(pattern, line)):
                txt_lines.append(line)
    
    return '\n'.join(txt_lines)

def check_url_existence(data_list, url):
    """检查URL是否已存在"""
    urls = [item.split(',')[1] for item in data_list]
    return url not in urls

def clean_url(url):
    """清理URL中的$符号及之后内容"""
    last_dollar_index = url.rfind('$')
    return url[:last_dollar_index] if last_dollar_index != -1 else url

# 添加channel_name前剔除部分特定字符
removal_list = ["_电信", "电信", "高清", "频道", "（HD）", "-HD","英陆","_ITV","(北美)","(HK)","AKtv","「IPV4」","「IPV6」",
                "频陆","备陆","壹陆","贰陆","叁陆","肆陆","伍陆","陆陆","柒陆", "频晴","频粤","[超清]","高清","超清","标清","斯特",
                "粤陆", "国陆","肆柒","频英","频特","频国","频壹","频贰","肆贰","频测","咪咕","闽特","高特","频高","频标","汝阳"]

def clean_channel_name(channel_name, removal_list):
    """清理频道名称"""
    for item in removal_list:
        channel_name = channel_name.replace(item, "")

    if channel_name.endswith("HD"):
        channel_name = channel_name[:-2]
    
    if channel_name.endswith("台") and len(channel_name) > 3:
        channel_name = channel_name[:-1]

    return channel_name

def process_channel_line(line):
    """处理单行频道数据"""
    if "#genre#" not in line and "#EXTINF:" not in line and "," in line and "://" in line:
        channel_name = line.split(',')[0].strip()
        channel_name = clean_channel_name(channel_name, removal_list)
        channel_name = traditional_to_simplified(channel_name)

        channel_address = clean_url(line.split(',')[1].strip())
        line = channel_name + "," + channel_address

        if channel_address not in combined_blacklist:
            distribute_channel(channel_name, channel_address, line)

def distribute_channel(channel_name, channel_address, line):
    """分发频道到对应的列表"""
    # 央视频道
    if "CCTV" in channel_name and check_url_existence(ys_lines, channel_address):
        ys_lines.append(process_name_string(line.strip()))
    # 卫视频道
    elif channel_name in ws_dictionary and check_url_existence(ws_lines, channel_address):
        ws_lines.append(process_name_string(line.strip()))
    # 地方频道分发
    elif channel_name in zj_dictionary and check_url_existence(zj_lines, channel_address):
        zj_lines.append(process_name_string(line.strip()))
    elif channel_name in jsu_dictionary and check_url_existence(jsu_lines, channel_address):
        jsu_lines.append(process_name_string(line.strip()))
    elif channel_name in gd_dictionary and check_url_existence(gd_lines, channel_address):
        gd_lines.append(process_name_string(line.strip()))
    elif channel_name in hn_dictionary and check_url_existence(hn_lines, channel_address):
        hn_lines.append(process_name_string(line.strip()))
    elif channel_name in hb_dictionary and check_url_existence(hb_lines, channel_address):
        hb_lines.append(process_name_string(line.strip()))
    elif channel_name in ah_dictionary and check_url_existence(ah_lines, channel_address):
        ah_lines.append(process_name_string(line.strip()))
    elif channel_name in hain_dictionary and check_url_existence(hain_lines, channel_address):
        hain_lines.append(process_name_string(line.strip()))
    elif channel_name in nm_dictionary and check_url_existence(nm_lines, channel_address):
        nm_lines.append(process_name_string(line.strip()))
    elif channel_name in ln_dictionary and check_url_existence(ln_lines, channel_address):
        ln_lines.append(process_name_string(line.strip()))
    elif channel_name in sx_dictionary and check_url_existence(sx_lines, channel_address):
        sx_lines.append(process_name_string(line.strip()))
    elif channel_name in shanxi_dictionary and check_url_existence(shanxi_lines, channel_address):
        shanxi_lines.append(process_name_string(line.strip()))
    elif channel_name in shandong_dictionary and check_url_existence(shandong_lines, channel_address):
        shandong_lines.append(process_name_string(line.strip()))
    elif channel_name in yunnan_dictionary and check_url_existence(yunnan_lines, channel_address):
        yunnan_lines.append(process_name_string(line.strip()))
    elif channel_name in bj_dictionary and check_url_existence(bj_lines, channel_address):
        bj_lines.append(process_name_string(line.strip()))
    elif channel_name in cq_dictionary and check_url_existence(cq_lines, channel_address):
        cq_lines.append(process_name_string(line.strip()))
    elif channel_name in fj_dictionary and check_url_existence(fj_lines, channel_address):
        fj_lines.append(process_name_string(line.strip()))
    elif channel_name in gs_dictionary and check_url_existence(gs_lines, channel_address):
        gs_lines.append(process_name_string(line.strip()))
    elif channel_name in gx_dictionary and check_url_existence(gx_lines, channel_address):
        gx_lines.append(process_name_string(line.strip()))
    elif channel_name in gz_dictionary and check_url_existence(gz_lines, channel_address):
        gz_lines.append(process_name_string(line.strip()))
    elif channel_name in heb_dictionary and check_url_existence(heb_lines, channel_address):
        heb_lines.append(process_name_string(line.strip()))
    elif channel_name in hen_dictionary and check_url_existence(hen_lines, channel_address):
        hen_lines.append(process_name_string(line.strip()))
    elif channel_name in hlj_dictionary and check_url_existence(hlj_lines, channel_address):
        hlj_lines.append(process_name_string(line.strip()))
    elif channel_name in jl_dictionary and check_url_existence(jl_lines, channel_address):
        jl_lines.append(process_name_string(line.strip()))
    elif channel_name in nx_dictionary and check_url_existence(nx_lines, channel_address):
        nx_lines.append(process_name_string(line.strip()))
    elif channel_name in jx_dictionary and check_url_existence(jx_lines, channel_address):
        jx_lines.append(process_name_string(line.strip()))
    elif channel_name in qh_dictionary and check_url_existence(qh_lines, channel_address):
        qh_lines.append(process_name_string(line.strip()))
    elif channel_name in sc_dictionary and check_url_existence(sc_lines, channel_address):
        sc_lines.append(process_name_string(line.strip()))
    elif channel_name in sh_dictionary and check_url_existence(sh_lines, channel_address):
        sh_lines.append(process_name_string(line.strip()))
    elif channel_name in tj_dictionary and check_url_existence(tj_lines, channel_address):
        tj_lines.append(process_name_string(line.strip()))
    elif channel_name in xj_dictionary and check_url_existence(xj_lines, channel_address):
        xj_lines.append(process_name_string(line.strip()))
    # 其他频道类型分发
    elif channel_name in sz_dictionary and check_url_existence(sz_lines, channel_address):
        sz_lines.append(process_name_string(line.strip()))
    elif channel_name in gj_dictionary and check_url_existence(gj_lines, channel_address):
        gj_lines.append(process_name_string(line.strip()))
    elif channel_name in ty_dictionary and check_url_existence(ty_lines, channel_address):
        ty_lines.append(process_name_string(line.strip()))
    # 修复：正确检查体育赛事关键词
    elif any(keyword in channel_name for keyword in tyss_dictionary) and check_url_existence(tyss_lines, channel_address):
        tyss_lines.append(process_name_string(line.strip()))
    elif channel_name in dy_dictionary and check_url_existence(dy_lines, channel_address):
        dy_lines.append(process_name_string(line.strip()))
    elif channel_name in dsj_dictionary and check_url_existence(dsj_lines, channel_address):
        dsj_lines.append(process_name_string(line.strip()))
    elif channel_name in gat_dictionary and check_url_existence(gat_lines, channel_address):
        gat_lines.append(process_name_string(line.strip()))
    elif channel_name in xg_dictionary and check_url_existence(xg_lines, channel_address):
        xg_lines.append(process_name_string(line.strip()))
    elif channel_name in aomen_dictionary and check_url_existence(aomen_lines, channel_address):
        aomen_lines.append(process_name_string(line.strip()))
    elif channel_name in tw_dictionary and check_url_existence(tw_lines, channel_address):
        tw_lines.append(process_name_string(line.strip()))
    elif channel_name in jlp_dictionary and check_url_existence(jlp_lines, channel_address):
        jlp_lines.append(process_name_string(line.strip()))
    elif channel_name in dhp_dictionary and check_url_existence(dhp_lines, channel_address):
        dhp_lines.append(process_name_string(line.strip()))
    elif channel_name in xq_dictionary and check_url_existence(xq_lines, channel_address):
        xq_lines.append(process_name_string(line.strip()))
    elif channel_name in js_dictionary and check_url_existence(js_lines, channel_address):
        js_lines.append(process_name_string(line.strip()))
    elif channel_name in cw_dictionary and check_url_existence(cw_lines, channel_address):
        cw_lines.append(process_name_string(line.strip()))
    elif channel_name in douyu_dictionary and check_url_existence(douyu_lines, channel_address):
        douyu_lines.append(process_name_string(line.strip()))
    elif channel_name in huya_dictionary and check_url_existence(huya_lines, channel_address):
        huya_lines.append(process_name_string(line.strip()))
    elif channel_name in zy_dictionary and check_url_existence(zy_lines, channel_address):
        zy_lines.append(process_name_string(line.strip()))
    elif channel_name in yy_dictionary and check_url_existence(yy_lines, channel_address):
        yy_lines.append(process_name_string(line.strip()))
    elif channel_name in game_dictionary and check_url_existence(game_lines, channel_address):
        game_lines.append(process_name_string(line.strip()))
    elif channel_name in radio_dictionary and check_url_existence(radio_lines, channel_address):
        radio_lines.append(process_name_string(line.strip()))
    elif channel_name in zb_dictionary and check_url_existence(zb_lines, channel_address):
        zb_lines.append(process_name_string(line.strip()))
    else:
        if channel_address not in other_lines_url:
            other_lines_url.append(channel_address)
            other_lines.append(line.strip())

def get_http_response(url, timeout=8, retries=2, backoff_factor=1.0):
    """获取HTTP响应"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as response:
                data = response.read()
                return data.decode('utf-8')
        except urllib.error.HTTPError as e:
            print(f"[HTTP错误] 代码: {e.code}, URL: {url}")
            break
        except urllib.error.URLError as e:
            print(f"[URL错误] 原因: {e.reason}, 尝试: {attempt + 1}")
        except socket.timeout:
            print(f"[超时] URL: {url}, 尝试: {attempt + 1}")
        except Exception as e:
            print(f"[异常] {type(e).__name__}: {e}, 尝试: {attempt + 1}")
        
        if attempt < retries - 1:
            time.sleep(backoff_factor * (2 ** attempt))
    
    return None

def process_url(url):
    """处理单个URL"""
    try:
        other_lines.append("◆◆◆ " + url)
        
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        with urllib.request.urlopen(req) as response:
            data = response.read()
            text = data.decode('utf-8').strip()
            
            is_m3u = text.startswith("#EXTM3U") or text.startswith("#EXTINF")
            if get_url_file_extension(url) in [".m3u", ".m3u8"] or is_m3u:
                text = convert_m3u_to_txt(text)
            
            lines = text.split('\n')
            print(f"处理行数: {len(lines)}")
            
            for line in lines:
                if "#genre#" not in line and "," in line and "://" in line and "tvbus://" not in line and "/udp/" not in line:
                    if "#" not in line.split(',')[1]:
                        process_channel_line(line)
                    else:
                        channel_name, channel_address = line.split(',', 1)
                        for single_url in channel_address.split('#'):
                            newline = f'{channel_name},{single_url}'
                            process_channel_line(newline)
            
            other_lines.append('\n')
            
    except Exception as e:
        print(f"处理URL时发生错误: {e}")

# 读取字典文本
ys_dictionary = read_txt_to_array('主频道/CCTV.txt')
ws_dictionary = read_txt_to_array('主频道/卫视频道.txt')
zj_dictionary = read_txt_to_array('地方台/浙江频道.txt')
jsu_dictionary = read_txt_to_array('地方台/江苏频道.txt')
gd_dictionary = read_txt_to_array('地方台/广东频道.txt')
gx_dictionary = read_txt_to_array('地方台/广西频道.txt')
jx_dictionary = read_txt_to_array('地方台/江西频道.txt')
hb_dictionary = read_txt_to_array('地方台/湖北频道.txt')
hn_dictionary = read_txt_to_array('地方台/湖南频道.txt')
ah_dictionary = read_txt_to_array('地方台/安徽频道.txt')
hain_dictionary = read_txt_to_array('地方台/海南频道.txt')
nm_dictionary = read_txt_to_array('地方台/内蒙频道.txt')
ln_dictionary = read_txt_to_array('地方台/辽宁频道.txt')
sx_dictionary = read_txt_to_array('地方台/陕西频道.txt')
shandong_dictionary = read_txt_to_array('地方台/山东频道.txt')
shanxi_dictionary = read_txt_to_array('地方台/山西频道.txt')
hen_dictionary = read_txt_to_array('地方台/河南频道.txt')
heb_dictionary = read_txt_to_array('地方台/河北频道.txt')
yunnan_dictionary = read_txt_to_array('地方台/云南频道.txt')
gz_dictionary = read_txt_to_array('地方台/贵州频道.txt')
sc_dictionary = read_txt_to_array('地方台/四川频道.txt')
fj_dictionary = read_txt_to_array('地方台/福建频道.txt')
gs_dictionary = read_txt_to_array('地方台/甘肃频道.txt')
hlj_dictionary = read_txt_to_array('地方台/黑龙江频道.txt')
jl_dictionary = read_txt_to_array('地方台/吉林频道.txt')
nx_dictionary = read_txt_to_array('地方台/宁夏频道.txt')
qh_dictionary = read_txt_to_array('地方台/青海频道.txt')
xj_dictionary = read_txt_to_array('地方台/新疆频道.txt')
bj_dictionary = read_txt_to_array('地方台/北京频道.txt')
sh_dictionary = read_txt_to_array('地方台/上海频道.txt')
tj_dictionary = read_txt_to_array('地方台/天津频道.txt')
cq_dictionary = read_txt_to_array('地方台/重庆频道.txt')

cw_dictionary = read_txt_to_array('主频道/春晚.txt')
dy_dictionary = read_txt_to_array('主频道/电影.txt')
dsj_dictionary = read_txt_to_array('主频道/电视剧.txt')
gat_dictionary = read_txt_to_array('主频道/港澳台.txt')
xg_dictionary = read_txt_to_array('主频道/香港.txt')
aomen_dictionary = read_txt_to_array('主频道/澳门.txt')
tw_dictionary = read_txt_to_array('主频道/台湾.txt')
dhp_dictionary = read_txt_to_array('主频道/动画片.txt')
radio_dictionary = read_txt_to_array('主频道/收音机.txt')
sz_dictionary = read_txt_to_array('主频道/数字频道.txt')
gj_dictionary = read_txt_to_array('主频道/国际频道.txt')
ty_dictionary = read_txt_to_array('主频道/体育频道.txt')
tyss_dictionary = read_txt_to_array('主频道/体育赛事.txt')
yy_dictionary = read_txt_to_array('主频道/音乐频道.txt')
js_dictionary = read_txt_to_array('主频道/解说频道.txt')
douyu_dictionary = read_txt_to_array('主频道/斗鱼直播.txt')
huya_dictionary = read_txt_to_array('主频道/虎牙直播.txt')
zb_dictionary = read_txt_to_array('主频道/直播中国.txt')
jlp_dictionary = read_txt_to_array('主频道/纪录片.txt')
zy_dictionary = read_txt_to_array('主频道/综艺频道.txt')
game_dictionary = read_txt_to_array('主频道/游戏频道.txt')
xq_dictionary = read_txt_to_array('主频道/戏曲频道.txt')

def load_corrections_name(filename):
    """读取纠错频道名称"""
    corrections = {}
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                parts = line.strip().split(',')
                correct_name = parts[0]
                for name in parts[1:]:
                    corrections[name] = correct_name
    except Exception as e:
        print(f"读取纠错文件错误: {e}")
    return corrections

def correct_name_data(corrections, data):
    """纠错频道名称"""
    corrected_data = []
    for line in data:
        line = line.strip()
        if ',' not in line:
            continue

        name, url = line.split(',', 1)
        if name in corrections and name != corrections[name]:
            name = corrections[name]

        corrected_data.append(f"{name},{url}")
    return corrected_data

def sort_data(order, data):
    """按照指定顺序排序数据"""
    order_dict = {name: i for i, name in enumerate(order)}
    
    def sort_key(line):
        name = line.split(',')[0]
        return order_dict.get(name, len(order))
    
    return sorted(data, key=sort_key)

# 处理URLs
urls = read_txt_to_array('assets/urls-daily.txt')
for url in urls:
    if url.startswith("http"):
        if "{MMdd}" in url:
            current_date_str = datetime.now().strftime("%m%d")
            url = url.replace("{MMdd}", current_date_str)

        if "{MMdd-1}" in url:
            yesterday_date_str = (datetime.now() - timedelta(days=1)).strftime("%m%d")
            url = url.replace("{MMdd-1}", yesterday_date_str)
            
        print(f"处理URL: {url}")
        process_url(url)

# 自定义排序函数
def extract_number(s):
    num_str = s.split(',')[0].split('-')[1]
    numbers = re.findall(r'\d+', num_str)
    return int(numbers[-1]) if numbers else 999

def custom_sort(s):
    if "CCTV-4K" in s:
        return 2
    elif "CCTV-8K" in s:
        return 3
    elif "(4K)" in s:
        return 1
    else:
        return 0

# 读取白名单
print("添加白名单...")
whitelist_auto_lines = read_txt_to_array('assets/blacklist1/whitelist_auto.txt')
for whitelist_line in whitelist_auto_lines:
    if "#genre#" not in whitelist_line and "," in whitelist_line and "://" in whitelist_line:
        whitelist_parts = whitelist_line.split(",")
        try:
            response_time = float(whitelist_parts[0].replace("ms", ""))
        except ValueError:
            response_time = 60000
        if response_time < 2000:
            process_channel_line(",".join(whitelist_parts[1:]))

# 日期格式化函数
def normalize_date_to_md(text):
    text = text.strip()

    def format_md(m):
        month = int(m.group(1))
        day = int(m.group(2))
        after = m.group(3) or ''
        if not after.startswith(' '):
            after = ' ' + after
        return f"{month}-{day}{after}"

    text = re.sub(r'^0?(\d{1,2})/0?(\d{1,2})(.*)', format_md, text)
    text = re.sub(r'^\d{4}-0?(\d{1,2})-0?(\d{1,2})(.*)', format_md, text)
    text = re.sub(r'^0?(\d{1,2})月0?(\d{1,2})日(.*)', format_md, text)

    return text

# AKTV处理
aktv_lines = []
aktv_url = "https://aktv.space/live.m3u"
aktv_text = get_http_response(aktv_url)
if aktv_text:
    print("AKTV成功获取内容")
    aktv_text = convert_m3u_to_txt(aktv_text)
    aktv_lines = aktv_text.strip().split('\n')
else:
    print("AKTV请求失败，从本地获取！")
    aktv_lines = read_txt_to_array('手工区/AKTV.txt')

def generate_playlist_html(data_list, output_file='output/custom1/sports.html'):
    """生成体育赛事HTML页面"""
    html_head = '''
    <!DOCTYPE html>
    <html lang="zh">
    <head>
        <meta charset="UTF-8">        
        <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-6061710286208572"
     crossorigin="anonymous"></script>
        <!-- Setup Google Analytics -->
        <script async src="https://www.googletagmanager.com/gtag/js?id=G-BS1Z4F5BDN"></script>
        <script> 
        window.dataLayer = window.dataLayer || []; 
        function gtag(){dataLayer.push(arguments);} 
        gtag('js', new Date()); 
        gtag('config', 'G-BS1Z4F5BDN'); 
        </script>
        <title>最新体育赛事</title>
        <style>
            body { font-family: sans-serif; padding: 20px; background: #f9f9f9; }
            .item { margin-bottom: 20px; padding: 12px; background: #fff; border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.06); }
            .title { font-weight: bold; font-size: 1.1em; color: #333; margin-bottom: 5px; }
            .url-wrapper { display: flex; align-items: center; gap: 10px; }
            .url {
                max-width: 80%;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
                font-size: 0.9em;
                color: #555;
                background: #f0f0f0;
                padding: 6px;
                border-radius: 4px;
                flex-grow: 1;
            }
            .copy-btn {
                background-color: #007BFF;
                border: none;
                color: white;
                padding: 6px 10px;
                border-radius: 4px;
                cursor: pointer;
                font-size: 0.8em;
            }
            .copy-btn:hover {
                background-color: #0056b3;
            }
        </style>
    </head>
    <body>
    <h2>📋 最新体育赛事列表</h2>
    '''
    
    html_body = ''
    for idx, entry in enumerate(data_list):
        if ',' not in entry:
            continue
        info, url = entry.split(',', 1)
        url_id = f"url_{idx}"
        html_body += f'''
        <div class="item">
            <div class="title">🕒 {info}</div>
            <div class="url-wrapper">
                <div class="url" id="{url_id}">{url}</div>
                <button class="copy-btn" onclick="copyToClipboard('{url_id}')">复制</button>
            </div>
        </div>
        '''
    
    html_tail = '''
    <script>
        function copyToClipboard(id) {
            const el = document.getElementById(id);
            const text = el.textContent;
            navigator.clipboard.writeText(text).then(() => {
                alert("已复制链接！");
            }).catch(err => {
                alert("复制失败: " + err);
            });
        }
    </script>
    </body>
    </html>
    '''
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_head + html_body + html_tail)
    print(f"✅ 网页已生成：{output_file}")

# 生成体育赛事页面
normalized_tyss_lines = [normalize_date_to_md(s) for s in tyss_lines]
generate_playlist_html(sorted(set(normalized_tyss_lines)), 'output/custom1/sports.html')

def get_random_url(file_path):
    """随机获取URL"""
    urls = []
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            for line in file:
                url = line.strip().split(',')[-1]
                urls.append(url)
    except Exception as e:
        print(f"读取随机URL错误: {e}")
    return random.choice(urls) if urls else None

# 生成版本信息和推荐
utc_time = datetime.now(timezone.utc)
beijing_time = utc_time + timedelta(hours=8)
formatted_time = beijing_time.strftime("%Y%m%d %H:%M:%S")

version = formatted_time + "," + (get_random_url('assets/今日推台.txt') or "默认URL")
about = "xiaoranmuze," + (get_random_url('assets/今日推台.txt') or "默认URL")

daily_mtv = "今日推荐," + (get_random_url('assets/今日推荐.txt') or "默认URL")
daily_mtv1 = "🔥低调," + (get_random_url('assets/今日推荐.txt') or "默认URL")
daily_mtv2 = "🔥使用," + (get_random_url('assets/今日推荐.txt') or "默认URL")
daily_mtv3 = "🔥禁止," + (get_random_url('assets/今日推荐.txt') or "默认URL")
daily_mtv4 = "🔥贩卖," + (get_random_url('assets/今日推荐.txt') or "默认URL")

# 添加手工区
print("处理手工区...")
zj_lines.extend(read_txt_to_array('手工区/浙江频道.txt'))
hb_lines.extend(read_txt_to_array('手工区/湖北频道.txt'))
gd_lines.extend(read_txt_to_array('手工区/广东频道.txt'))
sh_lines.extend(read_txt_to_array('手工区/上海频道.txt'))
jsu_lines.extend(read_txt_to_array('手工区/江苏频道.txt'))

# 读取纠错文件
corrections_name = load_corrections_name('assets/corrections_name.txt')

# 生成输出内容
all_lines = ["🌐央视频道,#genre#"] + sort_data(ys_dictionary, correct_name_data(corrections_name, ys_lines)) + ['\n'] + \
    ["📡卫视频道,#genre#"] + sort_data(ws_dictionary, correct_name_data(corrections_name, ws_lines)) + ['\n'] + \
    ["🕒更新时间,#genre#"] + [version] + [about] + [daily_mtv] + [daily_mtv1] + [daily_mtv2] + [daily_mtv3] + [daily_mtv4] + read_txt_to_array('手工区/about.txt') + ['\n']

all_lines_simple = ["央视频道,#genre#"] + sort_data(ys_dictionary, correct_name_data(corrections_name, ys_lines)) + ['\n'] + \
    ["卫视频道,#genre#"] + sort_data(ws_dictionary, correct_name_data(corrections_name, ws_lines)) + ['\n'] + \
    ["地方频道,#genre#"] + \
    sort_data(hb_dictionary, set(correct_name_data(corrections_name, hb_lines))) + \
    sort_data(hn_dictionary, set(correct_name_data(corrections_name, hn_lines))) + \
    sort_data(zj_dictionary, set(correct_name_data(corrections_name, zj_lines))) + \
    sort_data(gd_dictionary, set(correct_name_data(corrections_name, gd_lines))) + \
    sort_data(shandong_dictionary, set(correct_name_data(corrections_name, shandong_lines))) + \
    sorted(set(correct_name_data(corrections_name, jsu_lines))) + \
    sorted(set(correct_name_data(corrections_name, ah_lines))) + \
    sorted(set(correct_name_data(corrections_name, hain_lines))) + \
    sorted(set(correct_name_data(corrections_name, nm_lines))) + \
    sorted(set(correct_name_data(corrections_name, ln_lines))) + \
    sorted(set(correct_name_data(corrections_name, sx_lines))) + \
    sorted(set(correct_name_data(corrections_name, shanxi_lines))) + \
    sorted(set(correct_name_data(corrections_name, yunnan_lines))) + \
    sorted(set(correct_name_data(corrections_name, bj_lines))) + \
    sorted(set(correct_name_data(corrections_name, cq_lines))) + \
    sorted(set(correct_name_data(corrections_name, fj_lines))) + \
    sorted(set(correct_name_data(corrections_name, gs_lines))) + \
    sorted(set(correct_name_data(corrections_name, gx_lines))) + \
    sorted(set(correct_name_data(corrections_name, gz_lines))) + \
    sorted(set(correct_name_data(corrections_name, heb_lines))) + \
    sorted(set(correct_name_data(corrections_name, hen_lines))) + \
    sorted(set(correct_name_data(corrections_name, jl_lines))) + \
    sorted(set(correct_name_data(corrections_name, jx_lines))) + \
    sorted(set(correct_name_data(corrections_name, nx_lines))) + \
    sorted(set(correct_name_data(corrections_name, qh_lines))) + \
    sorted(set(correct_name_data(corrections_name, sc_lines))) + \
    sorted(set(correct_name_data(corrections_name, tj_lines))) + \
    sorted(set(correct_name_data(corrections_name, xj_lines))) + \
    sorted(set(correct_name_data(corrections_name, hlj_lines))) + \
    ['\n'] + \
    ["数字频道,#genre#"] + sort_data(sz_dictionary, set(correct_name_data(corrections_name, sz_lines))) + ['\n'] + \
    ["更新时间,#genre#"] + [version] + ['\n']

all_lines_custom = ["🌐央视频道,#genre#"] + sort_data(ys_dictionary, correct_name_data(corrections_name, ys_lines)) + ['\n'] + \
    ["📡卫视频道,#genre#"] + sort_data(ws_dictionary, correct_name_data(corrections_name, ws_lines)) + ['\n'] + \
    ["🕒更新时间,#genre#"] + [version] + [about] + [daily_mtv] + [daily_mtv1] + [daily_mtv2] + [daily_mtv3] + [daily_mtv4] + read_txt_to_array('手工区/about.txt') + ['\n']

# 写入输出文件
output_files = {
    "output/custom1/full.txt": all_lines,
    "output/custom1/simple.txt": all_lines_simple,
    "output/custom1/custom.txt": all_lines_custom,
    "output/custom1/others.txt": other_lines
}

for file_path, content in output_files.items():
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            for line in content:
                f.write(line + '\n')
        print(f"文件已保存: {file_path}")
    except Exception as e:
        print(f"保存文件错误 {file_path}: {e}")

# M3U文件生成
channels_logos = read_txt_to_array('assets/logo.txt')

def get_logo_by_channel_name(channel_name):
    """根据频道名称获取logo"""
    for line in channels_logos:
        if not line.strip():
            continue
        name, url = line.split(',')
        if name == channel_name:
            return url
    return None

def make_m3u(txt_file, m3u_file):
    """生成M3U文件"""
    try:
        output_text = '#EXTM3U x-tvg-url="https://live.fanmingming.cn/e.xml"\n'

        with open(txt_file, "r", encoding='utf-8') as file:
            input_text = file.read()

        lines = input_text.strip().split("\n")
        group_name = ""
        for line in lines:
            parts = line.split(",")
            if len(parts) == 2 and "#genre#" in line:
                group_name = parts[0]
            elif len(parts) == 2:
                channel_name = parts[0]
                channel_url = parts[1]
                logo_url = get_logo_by_channel_name(channel_name)
                if logo_url is None:
                    output_text += f"#EXTINF:-1 group-title=\"{group_name}\",{channel_name}\n"
                    output_text += f"{channel_url}\n"
                else:
                    output_text += f"#EXTINF:-1  tvg-name=\"{channel_name}\" tvg-logo=\"{logo_url}\"  group-title=\"{group_name}\",{channel_name}\n"
                    output_text += f"{channel_url}\n"

        with open(m3u_file, "w", encoding='utf-8') as file:
            file.write(output_text)

        print(f"M3U文件生成成功: {m3u_file}")
    except Exception as e:
        print(f"生成M3U文件错误: {e}")

# 生成M3U文件
make_m3u("output/custom1/full.txt", "output/custom1/full.m3u")
make_m3u("output/custom1/simple.txt", "output/custom1/simple.m3u")
make_m3u("output/custom1/custom.txt", "output/custom1/custom.m3u")

# 统计信息
timeend = datetime.now()
elapsed_time = timeend - timestart
total_seconds = elapsed_time.total_seconds()
minutes = int(total_seconds // 60)
seconds = int(total_seconds % 60)

print(f"开始时间: {timestart.strftime('%Y%m%d_%H_%M_%S')}")
print(f"结束时间: {timeend.strftime('%Y%m%d_%H_%M_%S')}")
print(f"执行时间: {minutes}分{seconds}秒")

combined_blacklist_hj = len(combined_blacklist)
all_lines_hj = len(all_lines)
other_lines_hj = len(other_lines)
all_lines_custom_hj = len(all_lines_custom)

print(f"黑名单行数: {combined_blacklist_hj}")
print(f"完整版行数: {all_lines_hj}")
print(f"其他行数: {other_lines_hj}")
print(f"定制版行数: {all_lines_custom_hj}")
