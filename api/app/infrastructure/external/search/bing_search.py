import base64
import logging
import re
import time
from typing import Optional
from urllib.parse import parse_qs, urlparse

import httpx
from bs4 import BeautifulSoup

from app.domain.external.search import SearchEngine
from app.domain.models.search import SearchResults, SearchResultItem
from app.domain.models.tool_result import ToolResult

logger = logging.getLogger(__name__)

_DATE_FILTERS = {
    "past_hour": 'ex1:"ez1"',
    "past_day": 'ex1:"ez1"',
    "past_week": 'ex1:"ez2"',
    "past_month": 'ex1:"ez3"',
}


class BingSearchEngine(SearchEngine):
    """bing搜索引擎"""

    def __init__(self):
        """构造函数，完成bing搜索引擎初始化，涵盖基础URL、headers、cookies"""
        self.base_url = "https://www.bing.com/search"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36 Edg/147.0.0.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        self.cookies = httpx.Cookies()

    async def invoke(self, query: str, date_range: Optional[str] = None) -> ToolResult[SearchResults]:
        """传递query+date_range使用httpx+bs4调用bing搜索并获取搜索结果"""
        # 1.构建请求参数
        params = self._build_params(query, date_range)

        try:
            # 6.使用httpx创建异步客户端
            async with httpx.AsyncClient(
                    headers=self.headers,
                    cookies=self.cookies,
                    timeout=60,
                    follow_redirects=True,
            ) as client:
                # Bing's current Chinese HTML no longer reliably exposes ``li.b_algo``.
                # Its public RSS feed is stable across that presentation change.
                response = await client.get(self.base_url, params={**params, "format": "rss"})
                response.raise_for_status()

                # 8.更新cookie信息
                self.cookies.update(response.cookies)

                rss_results = self._parse_rss_results(response.text)
                if rss_results:
                    return ToolResult(success=True, data=SearchResults(
                        query=query,
                        date_range=date_range,
                        total_results=len(rss_results),
                        results=rss_results,
                    ))

                # RSS may be empty for a small number of queries; retain the legacy
                # HTML parser as a compatibility fallback.
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()

                # 9.使用bs4解析html内容
                soup = BeautifulSoup(response.text, "html.parser")

                # 10.定义搜索结果并解析li.b_alog对应的dom元素
                search_results = []
                result_items = soup.find_all("li", class_="b_algo")

                # 11.循环遍历所有匹配的dom
                for item in result_items:
                    try:
                        # 12.定义变量存储数据
                        title, url = ("", "")

                        # 13.解析搜索结果中的标题与URL链接
                        title_tag = item.find("h2")
                        if title_tag:
                            a_tag = title_tag.find("a")
                            if a_tag:
                                title = a_tag.get_text(strip=True)
                                url = a_tag.get("href", "")

                        # 14.判断标题如果不存在提取该dom下的a标签
                        if not title:
                            a_tags = item.find_all("a")
                            for a_tag in a_tags:
                                # 15.提取标签中的文本并判断文本的长度是否超过10+不以http为开头
                                text = a_tag.get_text(strip=True)
                                if len(text) > 10 and not text.startswith("http"):
                                    title = text
                                    url = a_tag.get("href", "")
                                    break

                        # 16.如果两种查询方式都找不到title则跳过这次数据
                        if not title:
                            continue

                        # 17.提取检索数据的摘要信息
                        snippet = ""
                        snippet_items = item.find_all(
                            ["p", "div"],
                            class_=re.compile(r'b_lineclamp|b_descript|b_caption')
                        )
                        if snippet_items:
                            snippet = snippet_items[0].get_text(strip=True)

                        # 18.如果未找到摘要则查询所有p标签(段落标签)
                        if not snippet:
                            p_tags = item.find_all("p")
                            for p in p_tags:
                                text = p.get_text(strip=True)
                                if len(text) > 20:
                                    snippet = text
                                    break

                        # 19.如果还找不到摘要数据，则提取选项中的所有文本并使用常见的分隔符分割
                        if not snippet:
                            all_text = item.get_text(strip=True)
                            # 20.将所有文本分割成对应的句子，并循环遍历取出长度>20的句子
                            sentences = re.split(r'[.!?\n。！]', all_text)
                            for sentence in sentences:
                                clean_sentence = sentence.strip()
                                if len(clean_sentence) > 20 and clean_sentence != title:
                                    snippet = clean_sentence
                                    break

                        # 21.补全相对路径的url链接与缺失协议的部分
                        if url and not url.startswith("http"):
                            if url.startswith("//"):
                                url = "https:" + url
                            elif url.startswith("/"):
                                url = "https://www.bing.com" + url

                        # Bing /ck/a 链接包含会变化的追踪参数；以真实原文链接进行抓取和去重。
                        canonical_url = self._canonicalize_result_url(url)
                        if canonical_url:
                            search_results.append(SearchResultItem(
                                title=title,
                                url=canonical_url,
                                snippet=snippet,
                            ))

                    except Exception as e:
                        # 23.记录错误信息并继续解析
                        logger.warning(f"Bing搜索结果解析失败: {str(e)}")
                        continue

                # 24.提取整个页面的内容并查找`results`对应的文本
                total_results = 0
                result_stats = soup.find_all(string=re.compile(r"\d+[,\d+]\s*results"))
                if result_stats:
                    for stat in result_stats:
                        # 25.匹配出对应的数字分组
                        match = re.search(r"([\d,]+)\s*results", stat)
                        if match:
                            try:
                                # 26.取出匹配的分组内容，去除逗号转换为整型
                                total_results = int(match.group(1).replace(",", ""))
                                break
                            except Exception:
                                continue

                # 27.如果使用正则匹配找不到results(有可能是页面结构不一致)则使用新逻辑
                if total_results == 0:
                    # 28.使用类元素查找器
                    count_elements = soup.find_all(
                        ["span", "div", "p"],
                        class_=re.compile(r"sb_count|b_focusTextMedium")
                    )
                    for element in count_elements:
                        # 29.提取dom的文本并获取数字
                        text = element.get_text(strip=True)
                        match = re.search(r"([\d,]+)\s*results", text)
                        if match:
                            try:
                                total_results = int(match.group(1).replace(',', ''))
                                break
                            except Exception:
                                continue

                # 30.返回搜索结果
                results = SearchResults(
                    query=query,
                    date_range=date_range,
                    total_results=total_results,
                    results=search_results,
                )
                return ToolResult(success=True, data=results)
        except Exception as e:
            # 31.记录日志并返回错误工具调用结果
            logger.error(f"Bing搜索出错: {str(e)}")
            error_results = SearchResults(
                query=query,
                date_range=date_range,
                total_results=0,
                results=[],
            )
            return ToolResult(
                success=False,
                message=f"Bing搜索出错: {str(e)}",
                data=error_results,
            )

    @staticmethod
    def _parse_rss_results(content: str) -> list[SearchResultItem]:
        """Parse Bing RSS without requiring an XML-only BeautifulSoup parser."""
        soup = BeautifulSoup(content, "html.parser")
        results: list[SearchResultItem] = []
        for item in soup.find_all("item"):
            title_tag = item.find("title")
            link_tag = item.find("link")
            description_tag = item.find("description")
            title = title_tag.get_text(" ", strip=True) if title_tag else ""
            # Bing emits ``<link/>https://target`` rather than a normal link element.
            url = str(link_tag.next_sibling or "").strip() if link_tag else ""
            snippet = description_tag.get_text(" ", strip=True) if description_tag else ""
            canonical_url = BingSearchEngine._canonicalize_result_url(url)
            if title and canonical_url:
                results.append(SearchResultItem(title=title, url=canonical_url, snippet=snippet))
        return results

    @staticmethod
    def _build_params(query: str, date_range: Optional[str]) -> dict[str, str]:
        """Build raw params and let httpx URL-encode them exactly once."""
        params = {"q": query, "mkt": "zh-CN", "setlang": "zh-hans"}
        if date_range == "past_year":
            days_since_epoch = int(time.time() / (24 * 60 * 60))
            params["filters"] = f'ex1:"ez5_{days_since_epoch - 365}_{days_since_epoch}"'
        elif date_range in _DATE_FILTERS:
            params["filters"] = _DATE_FILTERS[date_range]
        return params

    @staticmethod
    def _canonicalize_result_url(url: str) -> str:
        """Return the original target behind Bing's /ck/a tracking link."""
        if not url:
            return ""
        parsed = urlparse(url)
        if not parsed.hostname or not parsed.hostname.lower().endswith("bing.com") or not parsed.path.startswith("/ck/"):
            return url
        encoded_target = parse_qs(parsed.query).get("u", [""])[0]
        if encoded_target.startswith("a1"):
            encoded_target = encoded_target[2:]
        if not encoded_target:
            return ""
        try:
            padding = "=" * (-len(encoded_target) % 4)
            target = base64.urlsafe_b64decode(encoded_target + padding).decode("utf-8")
        except (UnicodeDecodeError, ValueError):
            return ""
        return target if target.startswith(("http://", "https://")) else ""


if __name__ == "__main__":
    import asyncio


    async def test():
        search_engine = BingSearchEngine()
        result = await search_engine.invoke("小米股价", "past_day")

        print(result)
        for item in result.data.results:
            print(item)


    asyncio.run(test())
