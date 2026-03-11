import json
import hashlib
import time
import os
from flask import Flask, request, jsonify
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from curl_cffi import requests
from playwright.sync_api import sync_playwright

app = Flask(__name__)

def get_fresh_token():
    v_token = None
    with sync_playwright() as p:
        # Render/Docker වලට හරියන්න Arguments පාස් කරනවා
        context = p.chromium.launch_persistent_context(
            "./fixart_browser_data", 
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"] 
        )
        page = context.pages[0] if context.pages else context.new_page()
        
        def handle_request(route):
            nonlocal v_token
            req_obj = route.request
            
            # vtoken එක තියෙනවද කියලා බලනවා
            if "vtoken" in req_obj.headers:
                v_token = req_obj.headers["vtoken"]
            
            # පින්තූර, CSS සහ ෆොන්ට් ලෝඩ් වෙන එක නවත්තනවා RAM එක ඉතුරු කරන්න
            if req_obj.resource_type in ["image", "stylesheet", "font", "media"]:
                route.abort()
            else:
                route.continue_()
        
        page.route("**/*", handle_request)
        
        try:
            # සම්පූර්ණයෙන්ම ලෝඩ් වෙනකන් ඉන්නේ නෑ, domcontentloaded වලින් නවත්තනවා. Timeout එක 120s කරනවා.
            page.goto("https://fixart.ai/text-to-image/", timeout=120000, wait_until="domcontentloaded")
            
            # ටෝකන් එක එනකන් තත්පර 30ක් උපරිම බලන් ඉන්නවා
            for _ in range(30):
                if v_token:
                    break
                page.wait_for_timeout(1000)
                
        except Exception as e:
            print(f"Page load info (ignore if token is caught): {e}")
            
        context.close()
        
    return v_token

def generate_params(endpoint, payload_dict):
    json_str = json.dumps(payload_dict, separators=(',', ':'), ensure_ascii=False)
    raw_md5_str = f"nobody{endpoint}use{json_str}md5forencrypt"
    md5_hash = hashlib.md5(raw_md5_str.encode('utf-8')).hexdigest()
    target_str = f"{endpoint}-36cd479b6b5-{json_str}-36cd479b6b5-{md5_hash}"
    
    key = b"e82ckenh8dichen8"
    cipher = AES.new(key, AES.MODE_ECB)
    padded_data = pad(target_str.encode('utf-8'), AES.block_size)
    encrypted = cipher.encrypt(padded_data)
    
    return encrypted.hex().upper()

def get_proxies():
    host = "resident.lightningproxies.net"
    port = "8080"
    username = "JkGnaDonKa3sQHY_lightning_proxy-country-any"
    password = "ls5yu3a1zi"
    proxy_url = f"http://{username}:{password}@{host}:{port}"
    return {"http": proxy_url, "https": proxy_url}

@app.route('/generate', methods=['GET'])
def generate_image():
    user_prompt = request.args.get('prompt')
    
    if not user_prompt:
        return jsonify({"error": "Prompt ekak deepan bn"}), 400

    try:
        v_token = get_fresh_token()
        if not v_token:
            return jsonify({"error": "Failed to fetch vToken"}), 500

        endpoint = "/tools/image/txt2image"
        payload = {
            "name": "FixArt 1.1",
            "options": {
                "prompt": user_prompt,
                "aspect_ratio": "1:1"
            }
        }

        encrypted_params = generate_params(endpoint, payload)
        
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/x-www-form-urlencoded", 
            "vToken": v_token, 
            "Origin": "https://fixart.ai",
            "Referer": "https://fixart.ai/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }

        proxies = get_proxies()

        res = requests.post(
            f"https://backend.fixart.ai/api{endpoint}",
            data={"params": encrypted_params}, 
            headers=headers,
            proxies=proxies,
            impersonate="chrome120",
            timeout=60,
            verify=False 
        )

        if res.status_code == 200:
            resp_json = res.json()
            if resp_json.get("code") == 1:
                job_id = resp_json["data"]["job_id"]
                query_url = f"https://backend.fixart.ai/api/tools/job/queryV1?job_id={job_id}"
                
                for _ in range(30):
                    time.sleep(5)
                    q_res = requests.get(query_url, headers=headers, proxies=proxies, impersonate="chrome120", timeout=60, verify=False)
                    q_data = q_res.json()
                    
                    if q_data["data"]["job_process"]["status"] == "success":
                        image_url = q_data["data"]["info"]["output_resource"]
                        return jsonify({"status": "success", "image_url": image_url})
                        
                return jsonify({"error": "Timeout - Image generation took too long"}), 504
            else:
                return jsonify({"error": "API Error", "details": resp_json}), 500
        else:
            return jsonify({"error": "HTTP Error", "status_code": res.status_code}), 500

    except Exception as e:
        return jsonify({"error": "Critical Error", "details": str(e)}), 500

if __name__ == "__main__":
    # Render එකට ඕනේ port එක 10000 විදියට දෙනවා
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
