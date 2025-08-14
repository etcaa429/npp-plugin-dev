import tkinter as tk
from tkinter import scrolledtext, messagebox, Menu, filedialog, Toplevel
import google.generativeai as genai
import os
import sys
import pyperclip
import threading
import json
import markdown
from tkhtmlview import HTMLScrolledText  # 需pip install tkhtmlview

# --- 配置 ---
script_dir = os.path.dirname(os.path.abspath(__file__))
JSON_FILE = os.path.join(script_dir, 'prompts.json')
default_prompts = {
    "翻譯成繁體中文": "請將以下文字翻譯成專業、通順的繁體中文：",
    "翻譯成英文": "Please translate the following text into fluent, professional English:",
    "修正語法與錯字": "Please correct any grammar and spelling mistakes...",
    "總結成三點": "請將以下內容整理成三個重點條列："
}

# 檢查並創建JSON配置文件
if not os.path.exists(JSON_FILE):
    with open(JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump({"prompts": default_prompts}, f, ensure_ascii=False, indent=4)

API_KEY = os.getenv('GEMINI_API_KEY')
if not API_KEY:
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror("錯誤", "未找到GEMINI_API_KEY環境變數")
    sys.exit()
genai.configure(api_key=API_KEY)

# --- GUI 設計 ---
class JSONEditor:
    """JSON編輯器窗口"""
    def __init__(self, parent, json_file, callback=None):
        self.parent = parent
        self.json_file = json_file
        self.callback = callback
        
        # 創建編輯窗口
        self.window = Toplevel(parent)
        self.window.title("編輯 prompts.json")
        self.window.geometry("600x500")
        self.window.transient(parent)
        self.window.grab_set()
        
        # 創建主框架
        main_frame = tk.Frame(self.window, padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 標題
        title_label = tk.Label(main_frame, text="JSON提示詞編輯器", font=("", 12, "bold"))
        title_label.pack(fill=tk.X, pady=(0, 10))
        
        # 文本編輯區
        self.text_editor = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, font=("Consolas", 10))
        self.text_editor.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # 按鈕框架
        button_frame = tk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        # 儲存按鈕
        save_button = tk.Button(button_frame, text="儲存", command=self.save_json, 
                               bg="#4CAF50", fg="white", font=("", 10, "bold"))
        save_button.pack(side=tk.LEFT, padx=(0, 5))
        
        # 放棄按鈕
        cancel_button = tk.Button(button_frame, text="放棄", command=self.cancel_edit)
        cancel_button.pack(side=tk.LEFT)
        
        # 格式化按鈕
        format_button = tk.Button(button_frame, text="格式化JSON", command=self.format_json)
        format_button.pack(side=tk.RIGHT)
        
        # 載入現有內容
        self.load_json()
        
        # 設置窗口關閉事件
        self.window.protocol("WM_DELETE_WINDOW", self.cancel_edit)
    
    def load_json(self):
        """載入JSON文件內容"""
        try:
            with open(self.json_file, 'r', encoding='utf-8') as f:
                content = f.read()
            self.text_editor.insert("1.0", content)
        except Exception as e:
            messagebox.showerror("錯誤", f"讀取JSON文件失敗: {e}")
    
    def format_json(self):
        """格式化JSON內容"""
        try:
            content = self.text_editor.get("1.0", tk.END).strip()
            json_data = json.loads(content)
            formatted = json.dumps(json_data, ensure_ascii=False, indent=4)
            
            self.text_editor.delete("1.0", tk.END)
            self.text_editor.insert("1.0", formatted)
            messagebox.showinfo("成功", "JSON格式化完成")
        except json.JSONDecodeError as e:
            messagebox.showerror("錯誤", f"JSON格式錯誤: {e}")
        except Exception as e:
            messagebox.showerror("錯誤", f"格式化失敗: {e}")
    
    def save_json(self):
        """儲存JSON內容"""
        try:
            content = self.text_editor.get("1.0", tk.END).strip()
            # 驗證JSON格式
            json_data = json.loads(content)
            
            # 儲存到文件
            with open(self.json_file, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=4)
            
            messagebox.showinfo("成功", "JSON文件儲存成功")
            
            # 執行回調函數更新主程式
            if self.callback:
                self.callback()
            
            self.window.destroy()
            
        except json.JSONDecodeError as e:
            messagebox.showerror("錯誤", f"JSON格式錯誤，無法儲存: {e}")
        except Exception as e:
            messagebox.showerror("錯誤", f"儲存失敗: {e}")
    
    def cancel_edit(self):
        """取消編輯"""
        if messagebox.askyesno("確認", "確定要放棄編輯嗎？"):
            self.window.destroy()

class GeminiApp:
    def __init__(self, root, initial_prompt=""):
        self.root = root
        self.root.title("Gemini AI 助理 v5")
        self.root.geometry("800x650")
        
        # --- 變量 ---
        self.selected_model = tk.StringVar(value='gemini-1.5-flash')
        self.custom_prompts = {}
        self.markdown_enabled = True  # 是否啟用Markdown渲染
        self.preview_mode = False  # 是否處於預覽模式
        
        # --- 建立菜單 ---
        self.create_menu()
        
        # --- 主框架 ---
        main_frame = tk.Frame(root, padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # --- 上半部分：提問區和按鈕區的容器 ---
        top_container = tk.Frame(main_frame)
        top_container.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # --- 提問區（左側，佔據大部分空間）---
        prompt_frame = tk.Frame(top_container)
        prompt_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        prompt_label = tk.Label(prompt_frame, text="您的問題或選取的文字：", anchor='w')
        prompt_label.pack(fill=tk.X)
        
        # 創建文本輸入區域
        self.prompt_text = scrolledtext.ScrolledText(prompt_frame, height=12, wrap=tk.WORD)
        self.prompt_text.pack(fill=tk.BOTH, expand=True)
        
        # 創建HTML預覽區域（初始隱藏）
        self.prompt_preview = HTMLScrolledText(prompt_frame, height=12)
        # 不打包，只在預覽時顯示
        
        # --- 按鈕區（右側垂直排列）---
        button_frame = tk.Frame(top_container, width=150)
        button_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 0))
        button_frame.pack_propagate(False)  # 防止框架收縮
        
        # 添加一個標籤作為按鈕區的標題
        button_title = tk.Label(button_frame, text="操作選項：", font=("", 9, "bold"))
        button_title.pack(fill=tk.X, pady=(0, 5))
        
        self.submit_button = tk.Button(button_frame, text="傳送給 Gemini", 
                                      command=self.start_gemini_thread, 
                                      height=2, bg="#4CAF50", fg="white", font=("", 9, "bold"))
        self.submit_button.pack(fill=tk.X, pady=2)
        
        self.copy_button = tk.Button(button_frame, text="複製回應", 
                                    command=self.copy_response, state=tk.DISABLED, height=2)
        self.copy_button.pack(fill=tk.X, pady=2)
        
        # --- 響應區（下半部分，與提問區平分空間）---
        response_frame = tk.Frame(main_frame)
        response_frame.pack(fill=tk.BOTH, expand=True)
        
        response_label = tk.Label(response_frame, text="Gemini 的回應：", anchor='w')
        response_label.pack(fill=tk.X)
        
        # 使用HTMLScrolledText渲染Markdown轉換後的HTML
        self.response_html = HTMLScrolledText(response_frame, height=12)
        self.response_html.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        
        # 備用的純文本顯示區域（隱藏）
        self.response_text = scrolledtext.ScrolledText(response_frame, height=12, wrap=tk.WORD, state=tk.DISABLED)
        # 不打包 response_text，只在需要時使用
        
        # --- 啟動時加載 ---
        self.load_prompts_from_json()
        if initial_prompt:
            self.prompt_text.insert("1.0", initial_prompt)
        threading.Thread(target=self.populate_models_menu, daemon=True).start()

    def create_menu(self):
        menubar = Menu(self.root)
        self.root.config(menu=menubar)

        # --- 模型選單 ---
        self.model_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="模型 (Model)", menu=self.model_menu)
        self.model_menu.add_radiobutton(label="gemini-1.5-flash", variable=self.selected_model, value='gemini-1.5-flash')
        self.model_menu.add_separator()
        self.model_menu.add_command(label="加載模型中...", state=tk.DISABLED)

        # --- 提示詞選單 ---
        self.prompt_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="自訂提示詞 (Prompts)", menu=self.prompt_menu)
        
        # 按照需求順序添加菜單項目
        self.prompt_menu.add_command(label="導入Markdown提示詞", command=self.import_markdown)
        self.prompt_menu.add_command(label="預覽Markdown", command=self.toggle_preview_markdown)
        self.prompt_menu.add_command(label="編輯prompts.json", command=self.edit_prompts_json)
        self.prompt_menu.add_separator()
        
        # --- 幫助選單 ---
        menubar.add_cascade(label="幫助", command=self.show_help)

    def edit_prompts_json(self):
        """打開JSON編輯器"""
        JSONEditor(self.root, JSON_FILE, self.load_prompts_from_json)

    def populate_models_menu(self):
        try:
            models = [m.name.replace('models/', '') for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            self.root.after(0, self.update_model_menu, models)
        except Exception as e:
            self.root.after(0, lambda: self.model_menu.entryconfig(2, label=f"模型加載失敗: {e}"))

    def update_model_menu(self, models):
        self.model_menu.delete(2, tk.END)
        for model in sorted(models):
            self.model_menu.add_radiobutton(label=model, variable=self.selected_model, value=model)

    def load_prompts_from_json(self):
        try:
            with open(JSON_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.custom_prompts = data.get("prompts", {})

            # 清除現有的自訂提示詞選項（保留前4個固定選項和分隔線）
            menu_length = self.prompt_menu.index(tk.END)
            if menu_length is not None and menu_length >= 4:
                self.prompt_menu.delete(4, tk.END)
            
            # 添加自訂提示詞
            for name, prompt in self.custom_prompts.items():
                self.prompt_menu.add_command(label=name, command=lambda p=prompt: self.apply_prompt(p))
        except Exception as e:
            self.prompt_menu.add_command(label=f"加載提示詞失敗: {e}", state=tk.DISABLED)

    def apply_prompt(self, prompt_template):
        current_text = self.prompt_text.get("1.0", tk.END).strip()
        if not current_text:
            messagebox.showwarning("提示", "請先輸入文本")
            return

        combined_prompt = f"{prompt_template}\n\n---\n{current_text}"
        
        # 如果在預覽模式，先切換回編輯模式
        if self.preview_mode:
            self.toggle_preview_markdown()
            
        self.prompt_text.delete("1.0", tk.END)
        self.prompt_text.insert("1.0", combined_prompt)

    def toggle_preview_markdown(self):
        """切換提問區的Markdown預覽模式"""
        if not self.preview_mode:
            # 切換到預覽模式
            markdown_text = self.prompt_text.get("1.0", tk.END)
            if not markdown_text.strip():
                messagebox.showwarning("提示", "請先輸入Markdown內容")
                return
                
            try:
                html = markdown.markdown(markdown_text, extensions=['extra', 'codehilite'])
                
                # 隱藏文本輸入區，顯示預覽區
                self.prompt_text.pack_forget()
                self.prompt_preview.pack(fill=tk.BOTH, expand=True)
                self.prompt_preview.set_html(html)
                
                # 更新按鈕文字和狀態
                self.preview_mode = True
                messagebox.showinfo("提示", "已切換到預覽模式，再次點擊可回到編輯模式")
                
            except Exception as e:
                messagebox.showerror("錯誤", f"Markdown預覽失敗: {e}")
        else:
            # 切換回編輯模式
            self.prompt_preview.pack_forget()
            self.prompt_text.pack(fill=tk.BOTH, expand=True)
            
            # 恢復按鈕狀態
            self.preview_mode = False

    def import_markdown(self):
        """導入Markdown文件作為提示詞"""
        file_path = filedialog.askopenfilename(
            title="選擇Markdown文件",
            filetypes=[("Markdown文件", "*.md"), ("文字文件", "*.txt"), ("所有文件", "*.*")]
        )
        if not file_path:
            return

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                md_content = f.read()

            # 簡單解析Markdown標題作為提示詞名稱
            lines = md_content.split('\n')
            title = lines[0].lstrip('# ').strip() if lines and lines[0].startswith('# ') else os.path.basename(file_path)

            # 更新JSON配置
            self.custom_prompts[title] = md_content
            with open(JSON_FILE, 'w', encoding='utf-8') as f:
                json.dump({"prompts": self.custom_prompts}, f, ensure_ascii=False, indent=4)

            # 刷新提示詞菜單
            self.load_prompts_from_json()
            messagebox.showinfo("成功", f"已導入提示詞: {title}")
        except Exception as e:
            messagebox.showerror("錯誤", f"導入失敗: {e}")

    def show_help(self):
        help_text = """Gemini AI 助理 v5 使用說明

🔧 功能說明：
1. 模型選單：切換不同的Gemini模型
2. 自訂提示詞：
   - 編輯prompts.json檔案新增提示詞
   - 支援Markdown格式
   - 可從檔案導入提示詞

3. Markdown功能：
   - 預覽Markdown：在上方提問區切換預覽模式
   - 編輯模式：切換回文字編輯模式
   - 導入Markdown提示詞：從.md檔案導入

📝 prompts.json格式範例：
{
  "prompts": {
    "提示詞名稱": "# 標題\\n- 列表項1\\n- 列表項2",
    "翻譯助手": "請將以下文字翻譯成繁體中文："
  }
}

💡 使用技巧：
- 可直接在問題區輸入Markdown格式文字
- 點擊預覽Markdown按鈕在上方查看格式化效果
- 預覽模式下點擊編輯模式返回文字編輯
- 善用自訂提示詞提高效率"""
        
        messagebox.showinfo("幫助", help_text)

    def start_gemini_thread(self):
        # 如果在預覽模式，先切換回編輯模式取得原始文本
        if self.preview_mode:
            self.toggle_preview_markdown()
            
        self.submit_button.config(state=tk.DISABLED, text="處理中...")
        self.copy_button.config(state=tk.DISABLED)
        
        # 在HTML區域顯示處理中訊息
        processing_html = f"<div style='text-align: center; padding: 20px; color: #666;'>正在使用 <strong>{self.selected_model.get()}</strong> 模型思考中...</div>"
        self.response_html.set_html(processing_html)

        prompt = self.prompt_text.get("1.0", tk.END).strip()
        threading.Thread(target=self.call_gemini, args=(prompt,), daemon=True).start()

    def call_gemini(self, prompt):
        if not prompt:
            self.update_ui_after_call("錯誤：提問內容不能為空", error=True)
            return

        try:
            model = genai.GenerativeModel(self.selected_model.get())
            response = model.generate_content(prompt)
            self.update_ui_after_call(response.text)
        except Exception as e:
            self.update_ui_after_call(f"API錯誤：{e}", error=True)

    def update_ui_after_call(self, result_text, error=False):
        try:
            # 將響應轉換為Markdown格式並渲染
            if error:
                error_html = f"<div style='color: red; padding: 10px; border: 1px solid red; border-radius: 5px;'>{result_text}</div>"
                self.response_html.set_html(error_html)
            else:
                response_html = markdown.markdown(result_text, extensions=['extra', 'codehilite'])
                self.response_html.set_html(response_html)
        except Exception as e:
            # 如果HTML渲染失敗，使用純文本顯示
            fallback_html = f"<pre style='white-space: pre-wrap; font-family: monospace;'>{result_text}</pre>"
            self.response_html.set_html(fallback_html)

        self.submit_button.config(state=tk.NORMAL, text="傳送給 Gemini")
        if not error:
            self.copy_button.config(state=tk.NORMAL)

    def copy_response(self):
        # 從HTML widget中提取純文本（如果可能的話）
        try:
            # 嘗試從HTML widget取得文本，這需要根據tkhtmlview的實際API調整
            response = self.response_html.get_html()  # 這可能需要調整
            # 如果get_html()不存在，可能需要其他方法提取文本
        except:
            # 備用方案：提示用戶手動複製
            messagebox.showinfo("提示", "請手動選取並複製回應內容")
            return
            
        if response:
            # 移除HTML標籤，保留純文本
            import re
            text_only = re.sub(r'<[^>]+>', '', response)
            pyperclip.copy(text_only)
            messagebox.showinfo("成功", "響應已複製到剪貼板")

if __name__ == "__main__":
    # 強制設定系統編碼為 UTF-8
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    try:
        import locale
        locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
    except:
        pass  # 忽略locale設置錯誤

    initial_text = ""
    is_from_notepad = False

    # 處理命令行參數
    if len(sys.argv) > 1:
        initial_text = sys.argv[1]
        is_from_notepad = initial_text != "$(SELECTION)" and initial_text != ""

    # 若Notepad++參數無效，則從剪貼板獲取
    if not is_from_notepad:
        try:
            initial_text = pyperclip.paste()
        except pyperclip.PyperclipException:
            initial_text = ""

    # 清空$(SELECTION)字符串
    if initial_text == "$(SELECTION)":
        initial_text = ""

    root = tk.Tk()
    app = GeminiApp(root, initial_prompt=initial_text)
    root.mainloop()