import os
import json
import time
import re
import requests
from bs4 import BeautifulSoup

# jsonの名前
CACHE_FILE = "plugins.json"

# BOOTHのIDから公開時期を推定する関数
def estimate_booth_date(item_id_str):
    try:
        item_id = int(item_id_str)
        if item_id == 0:
            return "1970-01-01T00:00:00Z"
        estimated_ts = 1546300800 + (item_id - 1000000) * 31.5
        
        current_ts = time.time()
        if estimated_ts > current_ts:
            estimated_ts = current_ts
        if estimated_ts < 1388534400:
            estimated_ts = 1388534400
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(estimated_ts))
    except Exception:
        return "1970-01-01T00:00:00Z"

# 全プラグインのデータ収集関数
def get_ymm4_plugins():
    print("BOOTHとGitHubから最新のデータを取得します...")
    plugins_list = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # 1. BOOTHのスクレイピング
    page = 1
    max_pages = 5
    while page <= max_pages:
        booth_url = f"https://booth.pm/ja/items?page={page}&tags[]=YMM4Plugin"
        try:
            response = requests.get(booth_url, headers=headers, timeout=5)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                items = soup.find_all("li", class_="item-card")
                if not items:
                    break
                
                for item in items:
                    title_div = item.find("div", class_="item-card__title")
                    if title_div:
                        link_element = title_div.find("a")
                        title = link_element.text.strip() if link_element else "不明なプラグイン"
                        link = link_element["href"] if link_element else booth_url
                    else:
                        title = "不明なプラグイン"
                        link = booth_url
                    
                    if not link.startswith("http"):
                        link = "https://booth.pm" + link
                    
                    shop_name = item.get("data-product-brand")
                    if not shop_name:
                        shop_element = item.find(class_=re.compile("shop-name|user-name|brand"))
                        shop_name = shop_element.text.strip() if shop_element else "不明な開発者"
                    
                    booth_id_match = re.search(r'/items/(\d+)', link)
                    booth_id_str = booth_id_match.group(1) if booth_id_match else "0"
                    
                    estimated_date = estimate_booth_date(booth_id_str)
                    plugins_list.append({
                        "title": title,
                        "site": "BOOTH",
                        "author": shop_name, 
                        "info": f"開発者: {shop_name}",
                        "url": link,
                        "tags": [],
                        "updated": estimated_date
                    })
                time.sleep(1)
                page += 1
            else:
                break
        except Exception as e:
            print(f"BOOTHの取得に失敗 (page {page}): {e}")
            break

    # 2. GitHubのスクレイピング
    git_page = 1
    max_git_pages = 10
    github_scraped_successfully = False
    github_plugins = []
    
    while git_page <= max_git_pages:
        github_url = f"https://github.com/topics/ymm4-plugin?page={git_page}"
        print(f"GitHubトピックページを解析中... (ページ {git_page})")
        try:
            response = requests.get(github_url, headers=headers, timeout=5)
            if response.status_code != 200:
                print(f"⚠️ GitHubスクレイピング遮断 (ステータス: {response.status_code})。APIフォールバックに移行。")
                break
            soup = BeautifulSoup(response.text, "html.parser")
            articles = soup.find_all("article")
            if not articles:
                github_scraped_successfully = True
                break
            for article in articles:
                links = article.find_all("a")
                owner, repo_name, repo_url = "", "", ""
                for link in links:
                    href = link.get("href", "")
                    parts = [p for p in href.split("/") if p]
                    if len(parts) == 2 and parts[0] not in ["topics", "collections", "trending", "features", "explore", "site", "about"]:
                        owner = parts[0]
                        repo_name = parts[1]
                        repo_url = "https://github.com" + href
                        break
                
                if repo_url:
                    time_elem = article.find("relative-time")
                    updated_str = time_elem.get("datetime") if time_elem else ""
                    tags = []
                    for link in article.find_all("a"):
                        href = link.get("href", "")
                        if href.startswith("/topics/"):
                            tags.append(href.replace("/topics/", "").strip().lower())
                    p_desc = article.find("p")
                    description = p_desc.text.strip() if p_desc else "説明はありません"
                    if not any(p["url"] == repo_url for p in github_plugins):
                        github_plugins.append({
                            "title": repo_name,
                            "site": "GitHub",
                            "author": owner,
                            "info": f"開発者: {owner} | 説明: {description}",
                            "url": repo_url,
                            "tags": tags,
                            "updated": updated_str
                        })
            github_scraped_successfully = True
            time.sleep(1)
            git_page += 1
        except Exception as e:
            print(f"GitHubの取得に失敗 (page {git_page}): {e}")
            break

    # 3. GitHub APIでのフォールバック
    if not github_scraped_successfully or len(github_plugins) == 0:
        print("GitHub APIを使用してデータを取得します...")
        api_page = 1
        max_api_pages = 2
        
        while api_page <= max_api_pages:
            github_api_url = f"https://api.github.com/search/repositories?q=topic:ymm4-plugin&per_page=100&page={api_page}"
            try:
                api_headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                    "Accept": "application/vnd.github.v3+json"
                }
                api_response = requests.get(github_api_url, headers=api_headers, timeout=5)
                if api_response.status_code == 200:
                    data = api_response.json()
                    items = data.get("items", [])
                    if not items:
                        break
                    for item in items:
                        repo_name = item.get("name")
                        owner = item.get("owner", {}).get("login")
                        description = item.get("description") or "説明はありません"
                        link = item.get("html_url")
                        updated_str = item.get("pushed_at") or item.get("updated_at") or ""
                        tags = [t.lower() for t in item.get("topics", [])]
                        
                        if not any(p["url"] == link for p in github_plugins):
                            github_plugins.append({
                                "title": repo_name,
                                "site": "GitHub",
                                "author": owner, 
                                "info": f"開発者: {owner} | 説明: {description}",
                                "url": link,
                                "tags": tags,
                                "updated": updated_str
                            })
                    api_page += 1
                    time.sleep(1)
                else:
                    break
            except Exception as e:
                print(f"GitHub API取得エラー: {e}")
                break

    plugins_list.extend(github_plugins)
    
    # 作者名（author）の補完
    for p in plugins_list:
        if not p.get("author"):
            match = re.search(r'開発者:\s*([^|\s]+)', p.get("info", ""))
            p["author"] = match.group(1) if match else "不明"

    # JSONに出力
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(plugins_list, f, ensure_ascii=False, indent=4)
        print("データを plugins.json に保存しました。")
    except Exception as e:
        print(f"保存失敗: {e}")

if __name__ == "__main__":
    get_ymm4_plugins()