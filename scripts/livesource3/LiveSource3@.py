import urllib.request
from urllib.parse import urlparse
import re
import os
from datetime import datetime, timedelta, timezone
import random
import opencc
import socket
import time
import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import functools
from typing import List, Set, Dict, Any

# ==================== 配置区域 - 在这里修改 ====================

# 【修改位置1】输出目录配置
OUTPUT_DIR = '../../output/livesource3/'  # 从scripts/livesource3/到output/livesource3/
ASSETS_DIR = './'  # 当前目录就是scripts/livesource3/
BLACKLIST_DIR = 'blacklist/'  # 黑名单在scripts/livesource3/blacklist/

# 【修改位置2】频道文件路径配置 - 在这里添加或删除频道分类
CHANNEL_DIRS = {
    'ys': '主频道/CCTV.txt',           # 央视频道
    'ws': '主频道/卫视频道.txt',        # 卫视频道  
    'hb': '地方台/湖北频道.txt',        # 湖北频道
    'hn': '地方台/湖南频道.txt',        # 湖南频道
    'tyss': '主频道/体育赛事.txt',      # 体育赛事
    # 在这里添加新的频道分类，格式：'代号': '文件路径'
    # 例如：'zj': '地方台/浙江频道.txt'
}

# 【修改位置3】手工数据文件配置 - 在这里添加手工维护的文件
MANUAL_DIRS = {
    'hubei': '手工区/手工频道.txt',     # 手工频道数据
    'aktv': '手工区/AKTV.txt',         # AKTV数据
    'about': '手工区/about.txt',       # 关于信息
    # 在这里添加新的手工数据文件
}

# 【修改位置4】网络请求配置
TIMEOUT = 8
MAX_RETRIES = 2
MAX_WORKERS = 5
WHITELIST_THRESHOLD = 2000  # 白名单响应时间阈值(ms)

# 【修改位置5】需要清理的字符列表 - 在这里添加要清理的字符
REMOVAL_LIST = [
    "_电信", "电信", "高清", "频道", "（HD）", "-HD", "英陆", "_ITV", "(北美)", "(HK)", 
    "AKtv", "「IPV4」", "「IPV6」", "频陆", "备陆", "壹陆", "贰陆", "叁陆", "肆陆", 
    "伍陆", "陆陆", "柒陆", "频晴", "频粤", "[超清]", "高清", "超清", "标清", "斯特",
    "粤陆", "国陆", "肆柒", "频英", "频特", "频国", "频壹", "频贰", "肆贰", "频测", 
    "咪咕", "闽特", "高特", "频高", "频标", "汝阳"
    # 在这里添加新的需要清理的字符
]

# 【修改位置6】输入URL文件 - 在这里修改URL来源文件
URLS_FILE = 'urls-daily.txt'

# 【修改位置7】其他资源文件
CORRECTIONS_FILE = 'corrections_name.txt'
TODAY_RECOMMEND_FILE = '今日推荐.txt'
TODAY_PUSH_FILE = '今日推台.txt'
LOGO_FILE = 'logo.txt'

# ==================== 配置类 ====================
class Config:
    """配置管理类"""
    OUTPUT_DIR = OUTPUT_DIR
    ASSETS_DIR = ASSETS_DIR
    BLACKLIST_DIR = BLACKLIST_DIR
    CHANNEL_DIRS = CHANNEL_DIRS
    MANUAL_DIRS = MANUAL_DIRS
    TIMEOUT = TIMEOUT
    MAX_RETRIES = MAX_RETRIES
    MAX_WORKERS = MAX_WORKERS
    WHITELIST_THRESHOLD = WHITELIST_THRESHOLD
    REMOVAL_LIST = REMOVAL_LIST
    URLS_FILE = URLS_FILE
    CORRECTIONS_FILE = CORRECTIONS_FILE
    TODAY_RECOMMEND_FILE = TODAY_RECOMMEND_FILE
    TODAY_PUSH_FILE = TODAY_PUSH_FILE
    LOGO_FILE = LOGO_FILE

# ==================== 日志设置 ====================
def setup_logging():
    """设置日志配置"""
    os.makedirs(Config.OUTPUT_DIR, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(f'{Config.OUTPUT_DIR}processing.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

# ==================== 工具类 ====================
class URLTracker:
    """URL跟踪器，用于去重"""
    def __init__(self):
        self.seen_urls: Set[str] = set()
    
    def add_url(self, url: str) -> bool:
        """添加URL并返回是否为新URL"""
        if url in self.seen_urls:
            return False
        self.seen_urls.add(url)
        return True

class ProcessingStats:
    """处理统计类"""
    def __init__(self):
        self.start_time = datetime.now()
        self.processed_urls = 0
        self.successful_urls = 0
        self.total_lines = 0
        self.categories = defaultdict(int)
    
    def log_final_stats(self):
        """记录最终统计信息"""
        elapsed = datetime.now() - self.start_time
        total_seconds = elapsed.total_seconds()
        minutes = int(total_seconds // 60)
        seconds = int(total_seconds % 60)
        
        logging.info(f"""
处理统计:
- 总URL数: {self.processed_urls}
- 成功URL数: {self.successful_urls}
- 总行数: {self.total_lines}
- 耗时: {minutes}分{seconds}秒
- 成功率: {(self.successful_urls/max(1, self.processed_urls))*100:.1f}%
- 分类统计: {dict(self.categories)}
        """)

# ==================== 缓存装饰器 ====================
@functools.lru_cache(maxsize=1000)
def traditional_to_simplified_cached(text: str) -> str:
    """缓存的繁简转换"""
    converter = opencc.OpenCC('t2s')
    return converter.convert(text)

@functools.lru_cache(maxsize=500)
def get_logo_by_channel_name_cached(channel_name: str) -> str:
    """缓存的频道logo查询"""
    return get_logo_by_channel_name(channel_name)

# ==================== 核心功能函数 ====================
def read_txt_to_array(file_name: str) -> List[str]:
    """读取文本文件到数组，支持空行过滤"""
    try:
        with open(file_name, 'r', encoding='utf-8') as file:
            return [line.strip() for line in file if line.strip()]
    except FileNotFoundError:
        logging.warning(f"文件未找到: {file_name}")
        return []
    except Exception as e:
        logging.error(f"读取文件错误 {file_name}: {e}")
        return []

def read_blacklist_from_txt(file_path: str) -> List[str]:
    """读取黑名单文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return [line.split(',')[1].strip() for line in file if ',' in line]
    except Exception as e:
        logging.error(f"读取黑名单错误 {file_path}: {e}")
        return []

def robust_http_request(url: str, timeout: int = Config.TIMEOUT, retries: int = Config.MAX_RETRIES) -> str:
    """健壮的网络请求函数"""
    headers = {'User-Agent': get_random_user_agent()}
    
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return response.read().decode('utf-8')
        except Exception as e:
            logging.warning(f"请求尝试 {attempt + 1} 失败 {url}: {e}")
            if attempt < retries:
                time.sleep(2 ** attempt)  # 指数退避
    
    logging.error(f"所有请求尝试都失败: {url}")
    return ""

def get_random_user_agent() -> str:
    """随机User-Agent"""
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.150 Safari/537.36",
    ]
    return random.choice(USER_AGENTS)

def clean_url(url: str) -> str:
    """清理URL，移除$之后的内容"""
    last_dollar_index = url.rfind('$')
    return url[:last_dollar_index] if last_dollar_index != -1 else url

def clean_channel_name(channel_name: str) -> str:
    """清理频道名称"""
    for item in Config.REMOVAL_LIST:
        channel_name = channel_name.replace(item, "")
    
    # 移除末尾特定字符
    if channel_name.endswith("HD"):
        channel_name = channel_name[:-2]
    if channel_name.endswith("台") and len(channel_name) > 3:
        channel_name = channel_name[:-1]
    
    return channel_name

def get_url_file_extension(url: str) -> str:
    """获取URL文件扩展名"""
    path = urlparse(url).path
    return os.path.splitext(path)[1]

def convert_m3u_to_txt(m3u_content: str) -> str:
    """转换M3U格式到TXT格式"""
    lines = m3u_content.split('\n')
    txt_lines = []
    channel_name = ""
    
    for line in lines:
        if line.startswith("#EXTM3U"):
            continue
        elif line.startswith("#EXTINF"):
            channel_name = line.split(',')[-1].strip()
        elif line.startswith(("http", "rtmp", "p3p")):
            txt_lines.append(f"{channel_name},{line.strip()}")
        elif "#genre#" not in line and "," in line and "://" in line:
            pattern = r'^[^,]+,[^\s]+://[^\s]+$'
            if re.match(pattern, line):
                txt_lines.append(line)
    
    return '\n'.join(txt_lines)

# ==================== 频道处理类 ====================
class ChannelProcessor:
    """频道处理器"""
    
    def __init__(self):
        self.stats = ProcessingStats()
        self.url_tracker = URLTracker()
        
        # 初始化数据存储 - 【修改位置8】在这里添加新的频道分类存储
        self.ys_lines = []
        self.ws_lines = []
        self.hb_lines = []
        self.hn_lines = []
        self.ty_lines = []
        self.tyss_lines = []
        self.other_lines = []
        # 在这里添加新的频道分类列表，例如：
        # self.zj_lines = []  # 浙江频道
        
        # 读取字典和配置
        self._load_dictionaries()
        self._load_blacklists()
        self._load_corrections()
        
    def _load_dictionaries(self):
        """加载频道字典"""
        # 【修改位置9】在这里添加新的频道字典
        self.ys_dictionary = read_txt_to_array(Config.CHANNEL_DIRS['ys'])
        self.ws_dictionary = read_txt_to_array(Config.CHANNEL_DIRS['ws'])
        self.hb_dictionary = read_txt_to_array(Config.CHANNEL_DIRS['hb'])
        self.hn_dictionary = read_txt_to_array(Config.CHANNEL_DIRS['hn'])
        self.tyss_dictionary = read_txt_to_array(Config.CHANNEL_DIRS['tyss'])
        # 在这里添加新的频道字典，例如：
        # self.zj_dictionary = read_txt_to_array(Config.CHANNEL_DIRS['zj'])
    
    def _load_blacklists(self):
        """加载黑名单"""
        blacklist_auto = read_blacklist_from_txt(f'{Config.BLACKLIST_DIR}blacklist_auto.txt')
        blacklist_manual = read_blacklist_from_txt(f'{Config.BLACKLIST_DIR}blacklist_manual.txt')
        self.combined_blacklist = set(blacklist_auto + blacklist_manual)
        
        # 加载白名单
        self.whitelist_auto_lines = read_txt_to_array(f'{Config.BLACKLIST_DIR}whitelist_auto.txt')
    
    def _load_corrections(self):
        """加载纠错配置"""
        self.corrections_name = self._load_corrections_name(Config.CORRECTIONS_FILE)
    
    def _load_corrections_name(self, filename: str) -> Dict[str, str]:
        """加载名称纠错配置"""
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
            logging.error(f"加载纠错配置错误: {e}")
        return corrections

    def process_name_string(self, input_str: str) -> str:
        """处理频道名称字符串"""
        parts = input_str.split(',')
        processed_parts = [self._process_part(part) for part in parts]
        return ','.join(processed_parts)
    
    def _process_part(self, part_str: str) -> str:
        """处理单个频道名称部分"""
        if "CCTV" in part_str and "://" not in part_str:
            part_str = part_str.replace("IPV6", "").replace("PLUS", "+").replace("1080", "")
            filtered_str = ''.join(char for char in part_str if char.isdigit() or char in 'K+')
            
            if not filtered_str.strip():
                filtered_str = part_str.replace("CCTV", "")
            
            if len(filtered_str) > 2 and re.search(r'4K|8K', filtered_str):
                filtered_str = re.sub(r'(4K|8K).*', r'\1', filtered_str)
                if len(filtered_str) > 2:
                    filtered_str = re.sub(r'(4K|8K)', r'(\1)', filtered_str)
            
            return "CCTV" + filtered_str
        elif "卫视" in part_str:
            return re.sub(r'卫视「.*」', '卫视', part_str)
        
        return part_str

    def process_channel_line(self, line: str):
        """处理单行频道数据"""
        if not self._is_valid_line(line):
            return
        
        channel_name, channel_address = line.split(',', 1)
        channel_name = clean_channel_name(channel_name)
        channel_name = traditional_to_simplified_cached(channel_name)
        channel_address = clean_url(channel_address.strip())
        
        line = f"{channel_name},{channel_address}"
        
        if channel_address in self.combined_blacklist:
            return
        
        # 分类处理
        category = self._categorize_channel(channel_name, channel_address)
        if category:
            processed_line = self.process_name_string(line)
            getattr(self, f'{category}_lines').append(processed_line)
            self.stats.categories[category] += 1
    
    def _is_valid_line(self, line: str) -> bool:
        """检查是否为有效行"""
        return (line and ',' in line and "://" in line and 
                "#genre#" not in line and "#EXTINF:" not in line and
                "tvbus://" not in line and "/udp/" not in line)
    
    def _categorize_channel(self, channel_name: str, channel_address: str) -> str:
        """频道分类"""
        # 【修改位置10】在这里添加新的频道分类逻辑
        if "CCTV" in channel_name and self.url_tracker.add_url(channel_address):
            return "ys"
        elif channel_name in self.ws_dictionary and self.url_tracker.add_url(channel_address):
            return "ws"
        elif channel_name in self.hn_dictionary and self.url_tracker.add_url(channel_address):
            return "hn"
        elif channel_name in self.hb_dictionary and self.url_tracker.add_url(channel_address):
            return "hb"
        elif any(tyss in channel_name for tyss in self.tyss_dictionary) and self.url_tracker.add_url(channel_address):
            return "tyss"
        # 在这里添加新的分类逻辑，例如：
        # elif channel_name in self.zj_dictionary and self.url_tracker.add_url(channel_address):
        #     return "zj"
        elif self.url_tracker.add_url(channel_address):
            self.other_lines.append(f"{channel_name},{channel_address}")
            return "other"
        return ""

    def process_single_url(self, url: str):
        """处理单个URL"""
        self.stats.processed_urls += 1
        logging.info(f"处理URL: {url}")
        
        try:
            # 处理日期模板
            url = self._process_date_templates(url)
            
            content = robust_http_request(url)
            if content:
                self._process_url_content(content)
                self.stats.successful_urls += 1
        except Exception as e:
            logging.error(f"处理URL失败 {url}: {e}")
    
    def _process_date_templates(self, url: str) -> str:
        """处理URL中的日期模板"""
        if "{MMdd}" in url:
            current_date_str = datetime.now().strftime("%m%d")
            url = url.replace("{MMdd}", current_date_str)
        if "{MMdd-1}" in url:
            yesterday_date_str = (datetime.now() - timedelta(days=1)).strftime("%m%d")
            url = url.replace("{MMdd-1}", yesterday_date_str)
        return url
    
    def _process_url_content(self, content: str):
        """处理URL内容"""
        # 处理M3U格式
        if content.startswith("#EXTM3U") or content.startswith("#EXTINF"):
            content = convert_m3u_to_txt(content)
        
        lines = content.split('\n')
        self.stats.total_lines += len(lines)
        
        for line in lines:
            if self._is_valid_line(line):
                if "#" not in line.split(',', 1)[1]:
                    self.process_channel_line(line)
                else:
                    self._process_hashed_urls(line)
    
    def _process_hashed_urls(self, line: str):
        """处理带#号的URL"""
        channel_name, channel_address = line.split(',', 1)
        url_list = channel_address.split('#')
        for channel_url in url_list:
            newline = f'{channel_name},{channel_url}'
            self.process_channel_line(newline)

    def process_whitelist(self):
        """处理白名单"""
        logging.info("处理白名单...")
        whitelist_count = 0
        
        for whitelist_line in self.whitelist_auto_lines:
            if not self._is_valid_line(whitelist_line):
                continue
            
            parts = whitelist_line.split(",")
            try:
                response_time = float(parts[0].replace("ms", ""))
                if response_time < Config.WHITELIST_THRESHOLD:
                    self.process_channel_line(",".join(parts[1:]))
                    whitelist_count += 1
            except ValueError:
                logging.warning(f"白名单响应时间转换失败: {whitelist_line}")
        
        logging.info(f"白名单处理完成，有效源: {whitelist_count}")

    def process_manual_data(self):
        """处理手工数据"""
        logging.info("处理手工数据...")
        
        # 【修改位置11】在这里添加新的手工数据处理
        # 手工频道数据
        manual_channels = read_txt_to_array(Config.MANUAL_DIRS['hubei'])
        for line in manual_channels:
            self.process_channel_line(line)
        
        # AKTV数据
        self._process_aktv_data()
        
        # 在这里添加新的手工数据处理
        # 例如：zj_manual = read_txt_to_array(Config.MANUAL_DIRS['zhejiang'])
    
    def _process_aktv_data(self):
        """处理AKTV数据"""
        aktv_url = "https://aktv.space/live.m3u"
        content = robust_http_request(aktv_url)
        
        if content:
            logging.info("AKTV在线获取成功")
            content = convert_m3u_to_txt(content)
            aktv_lines = content.strip().split('\n')
        else:
            logging.info("AKTV使用本地数据")
            aktv_lines = read_txt_to_array(Config.MANUAL_DIRS['aktv'])
        
        for line in aktv_lines:
            self.process_channel_line(line)

# ==================== 排序和输出类 ====================
class OutputGenerator:
    """输出生成器"""
    
    def __init__(self, processor: ChannelProcessor):
        self.processor = processor
    
    def correct_name_data(self, data: List[str]) -> List[str]:
        """纠正频道名称"""
        corrected_data = []
        for line in data:
            if ',' not in line:
                continue
            name, url = line.split(',', 1)
            if name in self.processor.corrections_name:
                name = self.processor.corrections_name[name]
            corrected_data.append(f"{name},{url}")
        return corrected_data
    
    def sort_data(self, order: List[str], data: List[str]) -> List[str]:
        """按指定顺序排序数据"""
        order_dict = {name: i for i, name in enumerate(order)}
        
        def sort_key(line):
            name = line.split(',')[0]
            return order_dict.get(name, len(order))
        
        return sorted(data, key=sort_key)
    
    def _custom_sort(self, s: str) -> int:
        """自定义排序函数"""
        if "CCTV-4K" in s:
            return 2
        elif "CCTV-8K" in s:
            return 3
        elif "(4K)" in s:
            return 1
        else:
            return 0
    
    def generate_output_files(self):
        """生成所有输出文件"""
        logging.info("生成输出文件...")
        
        # 处理日期格式化
        normalized_tyss_lines = [self._normalize_date_to_md(s) for s in self.processor.tyss_lines]
        
        # 生成网页
        self._generate_sports_html(normalized_tyss_lines)
        
        # 生成各版本文件
        self._generate_version_files(normalized_tyss_lines)
        
        # 生成others文件
        self._generate_others_file()
    
    def _normalize_date_to_md(self, text: str) -> str:
        """日期统一格式化为MM-DD格式"""
        text = text.strip()
        
        def format_md(m):
            month = int(m.group(1))
            day = int(m.group(2))
            after = m.group(3) or ''
            if not after.startswith(' '):
                after = ' ' + after
            return f"{month}-{day}{after}"
        
        # 处理各种日期格式
        text = re.sub(r'^0?(\d{1,2})/0?(\d{1,2})(.*)', format_md, text)
        text = re.sub(r'^\d{4}-0?(\d{1,2})-0?(\d{1,2})(.*)', format_md, text)
        text = re.sub(r'^0?(\d{1,2})月0?(\d{1,2})日(.*)', format_md, text)
        
        return text
    
    def _generate_sports_html(self, tyss_lines: List[str]):
        """生成体育赛事网页"""
        generate_playlist_html(sorted(set(tyss_lines)), f'{Config.OUTPUT_DIR}sports.html')
    
    def _generate_version_files(self, normalized_tyss_lines: List[str]):
        """生成各版本文件"""
        # 获取动态内容
        version_info = self._get_version_info()
        about_info = self._get_about_info()
        daily_recommendations = self._get_daily_recommendations()
        
        # 全集版
        full_content = self._build_full_content(normalized_tyss_lines, version_info, about_info, daily_recommendations)
        self._save_file('full.txt', full_content)
        
        # 精简版  
        lite_content = self._build_lite_content(version_info)
        self._save_file('lite.txt', lite_content)
        
        # 定制版
        custom_content = self._build_custom_content(normalized_tyss_lines, version_info, about_info, daily_recommendations)
        self._save_file('custom.txt', custom_content)
    
    def _get_version_info(self) -> str:
        """获取版本信息"""
        utc_time = datetime.now(timezone.utc)
        beijing_time = utc_time + timedelta(hours=8)
        formatted_time = beijing_time.strftime("%Y%m%d %H:%M:%S")
        random_url = self._get_random_url(Config.TODAY_PUSH_FILE)
        return f"{formatted_time},{random_url}"
    
    def _get_about_info(self) -> str:
        """获取关于信息"""
        random_url = self._get_random_url(Config.TODAY_PUSH_FILE)
        return f"xiaoranmuze,{random_url}"
    
    def _get_daily_recommendations(self) -> List[str]:
        """获取每日推荐"""
        recommendations = []
        prefixes = ["今日推荐", "🔥低调", "🔥使用", "🔥禁止", "🔥贩卖"]
        
        for prefix in prefixes:
            random_url = self._get_random_url(Config.TODAY_RECOMMEND_FILE)
            if random_url:
                recommendations.append(f"{prefix},{random_url}")
        
        return recommendations
    
    def _get_random_url(self, file_path: str) -> str:
        """随机获取URL"""
        urls = []
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                for line in file:
                    url = line.strip().split(',')[-1]
                    urls.append(url)
            return random.choice(urls) if urls else ""
        except Exception as e:
            logging.error(f"获取随机URL失败 {file_path}: {e}")
            return ""
    
    def _build_full_content(self, tyss_lines: List[str], version: str, about: str, daily: List[str]) -> List[str]:
        """构建全集版内容"""
        about_lines = read_txt_to_array(Config.MANUAL_DIRS['about'])
        
        content = [
            "🌐央视频道,#genre#"
        ] + self.sort_data(self.processor.ys_dictionary, self.correct_name_data(self.processor.ys_lines)) + ['\n'] + [
            "📡卫视频道,#genre#"
        ] + self.sort_data(self.processor.ws_dictionary, self.correct_name_data(self.processor.ws_lines)) + ['\n']
        
        # 【修改位置12】在这里添加新的频道分类到输出
        content += [
            "☘️湖北频道,#genre#"
        ] + self.sort_data(self.processor.hb_dictionary, set(self.correct_name_data(self.processor.hb_lines))) + ['\n'] + [
            "☘️湖南频道,#genre#"
        ] + self.sort_data(self.processor.hn_dictionary, set(self.correct_name_data(self.processor.hn_lines))) + ['\n']
        
        # 在这里添加新的频道分类，例如：
        # content += [
        #     "🍁浙江频道,#genre#"
        # ] + self.sort_data(self.processor.zj_dictionary, set(self.correct_name_data(self.processor.zj_lines))) + ['\n']
        
        content += [
            "🏆体育赛事,#genre#"
        ] + tyss_lines + ['\n'] + [
            "🕒更新时间,#genre#"
        ] + [version, about] + daily + about_lines + ['\n']
        
        return content
    
    def _build_lite_content(self, version: str) -> List[str]:
        """构建精简版内容"""
        return [
            "央视频道,#genre#"
        ] + self.sort_data(self.processor.ys_dictionary, self.correct_name_data(self.processor.ys_lines)) + ['\n'] + [
            "卫视频道,#genre#"
        ] + self.sort_data(self.processor.ws_dictionary, self.correct_name_data(self.processor.ws_lines)) + ['\n'] + [
            "更新时间,#genre#"
        ] + [version] + ['\n']
    
    def _build_custom_content(self, tyss_lines: List[str], version: str, about: str, daily: List[str]) -> List[str]:
        """构建定制版内容"""
        about_lines = read_txt_to_array(Config.MANUAL_DIRS['about'])
        
        return [
            "🌐央视频道,#genre#"
        ] + self.sort_data(self.processor.ys_dictionary, self.correct_name_data(self.processor.ys_lines)) + ['\n'] + [
            "📡卫视频道,#genre#"
        ] + self.sort_data(self.processor.ws_dictionary, self.correct_name_data(self.processor.ws_lines)) + ['\n'] + [
            "🏆体育赛事,#genre#"
        ] + tyss_lines + ['\n'] + [
            "🕒更新时间,#genre#"
        ] + [version, about] + daily + about_lines + ['\n']
    
    def _save_file(self, filename: str, content: List[str]):
        """保存文件"""
        try:
            filepath = f"{Config.OUTPUT_DIR}{filename}"
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write('\n'.join(content))
            logging.info(f"文件已保存: {filepath}")
            
            # 生成对应的M3U文件
            m3u_file = filepath.replace(".txt", ".m3u")
            make_m3u(filepath, m3u_file)
        except Exception as e:
            logging.error(f"保存文件失败 {filename}: {e}")
    
    def _generate_others_file(self):
        """生成others文件"""
        try:
            filepath = f"{Config.OUTPUT_DIR}others.txt"
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("其它频道,#genre#\n")
                for line in self.processor.other_lines:
                    if line and "," in line and "://" in line and not line.startswith("◆◆◆"):
                        f.write(line + '\n')
            logging.info(f"Others文件已保存: {filepath}")
            
            # 生成对应的M3U文件
            m3u_file = filepath.replace(".txt", ".m3u")
            make_m3u(filepath, m3u_file)
        except Exception as e:
            logging.error(f"保存Others文件失败: {e}")

# ==================== 保留的原有函数 ====================
def generate_playlist_html(data_list, output_file='playlist.html'):
    """生成体育赛事网页（保留原有实现）"""
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
    logging.info(f"网页已生成: {output_file}")

def get_logo_by_channel_name(channel_name):
    """获取频道logo（保留原有实现）"""
    channels_logos = read_txt_to_array(Config.LOGO_FILE)
    for line in channels_logos:
        if not line.strip():
            continue
        name, url = line.split(',')
        if name == channel_name:
            return url
    return None

def make_m3u(txt_file, m3u_file):
    """生成M3U文件（保留原有实现）"""
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
                logo_url = get_logo_by_channel_name_cached(channel_name)
                if logo_url is None:
                    output_text += f"#EXTINF:-1 group-title=\"{group_name}\",{channel_name}\n"
                    output_text += f"{channel_url}\n"
                else:
                    output_text += f"#EXTINF:-1  tvg-name=\"{channel_name}\" tvg-logo=\"{logo_url}\"  group-title=\"{group_name}\",{channel_name}\n"
                    output_text += f"{channel_url}\n"
        
        with open(f"{m3u_file}", "w", encoding='utf-8') as file:
            file.write(output_text)
        
        logging.info(f"M3U文件生成成功: {m3u_file}")
    except Exception as e:
        logging.error(f"生成M3U文件失败: {e}")

# ==================== 主执行函数 ====================
def main():
    """主执行函数"""
    setup_logging()
    logging.info("开始处理直播源...")
    
    # 初始化处理器
    processor = ChannelProcessor()
    output_generator = OutputGenerator(processor)
    
    try:
        # 1. 处理URL列表
        urls = read_txt_to_array(Config.URLS_FILE)
        http_urls = [url for url in urls if url.startswith("http")]
        
        # 使用线程池并行处理URL
        with ThreadPoolExecutor(max_workers=Config.MAX_WORKERS) as executor:
            list(executor.map(processor.process_single_url, http_urls))
        
        # 2. 处理白名单
        processor.process_whitelist()
        
        # 3. 处理手工数据
        processor.process_manual_data()
        
        # 4. 生成输出文件
        output_generator.generate_output_files()
        
        # 5. 输出统计信息
        processor.stats.log_final_stats()
        
        logging.info("处理完成！")
        
    except Exception as e:
        logging.error(f"主执行过程发生错误: {e}")
        raise

if __name__ == "__main__":
    main()