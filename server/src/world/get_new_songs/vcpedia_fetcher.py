import os
import sys

cwd = os.getcwd()
sys.path.insert(0, str(cwd))

import requests
import json
import os
import re
import asyncio
from typing import Dict, Any, Optional, List
from pathlib import Path
from src.utils.logger import get_logger
from src.utils.helpers import load_config
from src.world.get_new_songs.wiki_api import fetch_wikitext, user_agent
from src.world.get_new_songs.wikitext_parser import parse_details

class VCPediaFetcher:
    def __init__(self, config: Dict[str, Any], llm_module: Any | None = None):
        self.logger = get_logger(__name__)
        self.config = config
        self.activated = config.get("activated", False)
        crawler_config = config.get("vcpedia", {})
        self.base_url = crawler_config.get("base_url", "https://vcpedia.cn")

        self.llm_cfg = config.get("llm", {})
        self.use_llm = config.get("use_llm", False)
        self.llm_module = llm_module
        self.llm_client = None

        # Define directories to search
        self.data_dir = Path(config.get("data_dir", "data/crawled_data"))
        # Default save directory
        self.default_save_dir = Path(crawler_config.get("output_dir", "data/crawled_data"))
        
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent()})

    def fetch_entity_description(self, entity_name: str, short_summary: bool = True) -> Dict[str, Any]:
        """
        Fetch entity description from cache or VCPedia.
        Returns a JSON string of the entity data or empty string if not found.
        """
        if not self.activated:
            return ""
        # 1. Check local cache
        cached_data = self._check_cache(entity_name)
        if cached_data:
            self.logger.info(f"Found {entity_name} in cache.")
            return cached_data

        # 2. Crawl
        self.logger.info(f"Trying to crawl {entity_name} from VCPedia...")
        source = self._fetch_page(entity_name)
        if source is not None:
            try:
                data = parse_details(source, entity_name)
                if data:
                    if data["type"] == "Song":
                        data["short_summary"] = self._llm_summarize(data)
                    return data
            except Exception as e:
                self.logger.error(f"Error parsing {entity_name}: {e}")
        
        return None
    
    def _llm_summarize(self, data: Dict[str, Any]) -> str:
        summary_raw = "\n".join([str(x) for x in data.get("summary", []) if x])
        fallback = summary_raw[:100].strip() if summary_raw else ""
        if not data:
            return fallback

        if self.use_llm and self.llm_module is not None:
            try:
                data_payload = json.dumps(data, ensure_ascii=False, default=str)
                result = asyncio.run(self.llm_module.generate_response(song_data=data_payload))
                result = str(result or "").strip()
                return result if result else fallback
            except Exception as e:
                self.logger.error(f"LLM summarize failed: {e}")
                return fallback

        return fallback

        try:
            if not self.use_llm or self.llm_client is None:
                self.logger.error("knowledge.llm 配置缺失，使用回退摘要")
                return fallback

            
            data_payload = json.dumps(data, ensure_ascii=False, default=str)
            prompt = (
                "请基于以下歌曲数据(JSON)总结为不超过120字的中文，且仅保留三类信息："
                "1) 发布者(UP主)/演唱者/作词作曲等核心制作信息；"
                "2) 歌曲意义(如所属系列、重要演出或传播节点)；"
                "3) 歌曲主旨与大意。"
                "不要输出无关统计信息，不要编造。\n\n"
                f"歌曲数据：{data_payload}\n\n"
                "请直接输出摘要正文。"
            )
            return fallback
            result = ((result or {}).get("content", "") if isinstance(result, dict) else str(result)).strip()
            return result if result else fallback
        except Exception as e:
            self.logger.error(f"LLM summarize failed: {e}")
            return fallback

    def _check_cache(self, entity_name: str) -> Optional[Dict[str, Any]]:
        # Normalize name for filename
        safe_name = "".join([c for c in entity_name if c.isalnum() or c in (' ', '-', '_')]).strip()
        
        file_path = self.data_dir / f"{safe_name}.json"
        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.error(f"Error reading cache {file_path}: {e}")
        return None

    def _fetch_page(self, page_name: str) -> Optional[str]:
        """取页面 wikitext 源码；API 失败或挑战未通过时返回 None。"""
        try:
            return fetch_wikitext(self.base_url, page_name, self.session.get, 10)
        except Exception as e:
            self.logger.error(f"Error fetching {page_name} from VCPedia API: {e}")
            return None

    def _save_data(self, data: Dict[str, Any]):
        save_dir = self.default_save_dir
        
        save_dir.mkdir(parents=True, exist_ok=True)
        
        safe_title = "".join([c for c in data['name'] if c.isalnum() or c in (' ', '-', '_')]).strip()
        file_path = save_dir / f"{safe_title}.json"
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.logger.info(f"Saved {data['name']} to {file_path}")
        except Exception as e:
            self.logger.error(f"Error saving data to {file_path}: {e}")

    def _format_data(self, data: Dict[str, Any], short_summary:bool = True) -> str:
        if short_summary:
            data.pop("summary", None)
        else:
            data.pop("short_summary", None)
        return json.dumps(data, ensure_ascii=False)

if __name__ == "__main__":
    # Example usage
    config = {
        "activated": True,
        "vcpedia": {
            "base_url": "https://vcpedia.cn",
            "output_dir": "data/crawled_data"
        },
        "data_dir": "data/crawled_data"
    }
    fetcher = VCPediaFetcher(config)
    entity_name = "洛天依"  # Example entity
    description = fetcher.fetch_entity_description("煌")
    print(description)
