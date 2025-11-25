import sys
import os
import re
import requests
import copy
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QFont

# 必要なライブラリがインストールされているか確認
try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebEngineCore import QWebEngineProfile
except ImportError:
    print("エラー: PySide6-WebEngine が見つかりません。")
    print("インストールしてください: uv pip install PySide6-WebEngine")
    sys.exit(1)

try:
    from bs4 import BeautifulSoup, NavigableString
except ImportError:
    print("エラー: beautifulsoup4 が見つかりません。")
    print("インストールしてください: uv pip install beautifulsoup4 lxml")
    sys.exit(1)


# Wikipedia APIのベースURL（日本語版）
API_BASE_URL = "https://ja.wikipedia.org/w/api.php"
WIKI_PAGE_BASE_URL = "https://ja.wikipedia.org/"

# User-Agentの設定 (Wikimediaのポリシー推奨)
USER_AGENT = 'WikiGuesserGame/0.4 (https://github.com/your-repo/wikiguesser; your-email@example.com)'

class WikiGameApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WikiGuesser ver.b0.10")
        self.setGeometry(100, 100, 800, 700)

        # ゲームの状態を初期化
        self.full_title = ""
        self.words_to_guess = []
        self.guessed_words = set()
        self.original_html = ""
        self.debug_mode = False

        self.setup_ui()
        self.fetch_new_article()

    def setup_ui(self):
        """UIコンポーネントの配置"""
        main_layout = QHBoxLayout(self)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        self.status_label = QLabel("新しいゲームを開始します...")
        self.status_label.setFont(QFont("Arial", 12))
        left_layout.addWidget(self.status_label)

        title_group_label = QLabel("単語")
        title_group_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(title_group_label)

        self.hidden_title_label = QLabel("ロード中...")
        self.hidden_title_label.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        self.hidden_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hidden_title_label.setStyleSheet("padding: 20px; border: 2px solid #333;")
        left_layout.addWidget(self.hidden_title_label)

        left_layout.addStretch(1)

        guess_layout = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("単語を入力してください...")
        self.input_field.returnPressed.connect(self.handle_guess)
        guess_layout.addWidget(self.input_field)

        self.guess_button = QPushButton("回答をチェック")
        self.guess_button.clicked.connect(self.handle_guess)
        guess_layout.addWidget(self.guess_button)
        
        controls_layout = QHBoxLayout()
        self.answer_button = QPushButton("答えを表示")
        self.answer_button.clicked.connect(self.show_answer)
        controls_layout.addWidget(self.answer_button)

        self.next_button = QPushButton("次の問題")
        self.next_button.clicked.connect(self.fetch_new_article)
        controls_layout.addWidget(self.next_button)

        debug_layout = QHBoxLayout()
        self.debug_button = QPushButton("Debug: Off")
        self.debug_button.setCheckable(True)
        self.debug_button.clicked.connect(self.toggle_debug)
        debug_layout.addWidget(self.debug_button)
        debug_layout.addStretch(1)

        left_layout.addLayout(guess_layout)
        left_layout.addLayout(controls_layout)
        left_layout.addLayout(debug_layout)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        self.hint_view = QWebEngineView()
        right_layout.addWidget(self.hint_view)

        main_layout.addWidget(left_widget, 1)
        main_layout.addWidget(right_widget, 2)

    def get_random_article_data(self):
        """Wikipedia APIを呼び出し、ランダムな記事のタイトルと全文HTMLを取得"""
        headers = {'User-Agent': USER_AGENT}
        
        # 1. ランダムタイトル取得
        random_params = {'action': 'query', 'format': 'json', 'list': 'random', 'rnlimit': '1', 'rnnamespace': '0'}
        try:
            random_response = requests.get(API_BASE_URL, params=random_params, timeout=15, headers=headers)
            random_response.raise_for_status()
            random_data = random_response.json()
            title = random_data['query']['random'][0]['title']
        except (requests.exceptions.RequestException, KeyError, IndexError) as e:
            print(f"APIリクエスト失敗 (ランダム記事取得): {e}")
            return None, None, None

        # 2. 記事の全文をHTMLで取得
        parse_params = {'action': 'parse', 'format': 'json', 'page': title, 'prop': 'text', 'redirects': 1}
        full_html = ""
        try:
            parse_response = requests.get(API_BASE_URL, params=parse_params, timeout=15, headers=headers)
            parse_response.raise_for_status()
            parse_data = parse_response.json()
            if 'error' in parse_data:
                raise KeyError(f"API error: {parse_data['error']['info']}")
            full_html = parse_data['parse']['text']['*']
        except (requests.exceptions.RequestException, KeyError, IndexError) as e:
            print(f"APIリクエスト失敗 (記事本文取得): {e}")
            return title, [], f"<p>記事本文の取得に失敗しました: {e}</p>"

        # 3. タイトルを単語に分割する（カッコ内は除外）
        title_for_words = re.sub(r'\s*[（\(][^）\)]*[）\)]', '', title).strip()
        words = title_for_words.split() if title_for_words else []

        return title, words, full_html

    def fetch_new_article(self):
        """新しい記事を取得し、ゲームをリセット"""
        self.status_label.setText("Wikipediaから記事を取得中...")
        QApplication.processEvents()

        title, words, html = self.get_random_article_data()

        if title:
            self.full_title = title
            self.words_to_guess = words
            self.guessed_words = set()
            self.original_html = html

            self.update_title_display()
            self.update_view_with_masks() # マスキングして表示

            self.status_label.setText(f"単語を当ててください")
            self.input_field.setText("")
            self.input_field.setFocus()
            self.input_field.setEnabled(True)
            self.guess_button.setEnabled(True)
            self.answer_button.setEnabled(True)
        else:
            self.status_label.setText("記事の取得に失敗しました。ネットワーク接続を確認してください。")
            self.hint_view.setHtml("<h1>記事の取得に失敗しました</h1>")

    def update_view_with_masks(self):
        """現在の推測状況に応じてHTMLをマスキングしてWebViewに表示する"""
        if not self.original_html:
            return

        soup = BeautifulSoup(self.original_html, 'lxml')
        
        self._disable_links_in_html(soup)
        
        self._mask_parentheses_in_html(soup)
        
        words_to_mask, furigana_to_mask = self._collect_mask_words(soup)
        
        masking_regex = self._build_masking_regex(words_to_mask, furigana_to_mask)

        if not masking_regex:
            self.hint_view.setHtml(str(soup), QUrl(WIKI_PAGE_BASE_URL))
            return
        
        self._apply_mask_to_html(soup, masking_regex)

        self.hint_view.setHtml(str(soup), QUrl(WIKI_PAGE_BASE_URL))

    def _collect_mask_words(self, soup):
        words_to_mask = [w for w in self.words_to_guess if w not in self.guessed_words]
        
        # Extract furigana (rt tags) to prevent hints from readings
        furigana_to_mask = [rt.string.strip() for rt in soup.find_all('rt') if rt.string]

        # Also extract readings from the first paragraph, which often contains furigana in parentheses
        try:
            first_p = soup.find('p')
            if first_p:
                first_p_text = first_p.get_text()
                for paren_match in re.finditer(r'[（(]([^）)]+)[）)]', first_p_text):
                    reading = paren_match.group(1).strip()
                    if reading and reading not in furigana_to_mask:
                        furigana_to_mask.append(reading)
                
                for rt_tag in first_p.find_all('rt'):
                    v = rt_tag.string.strip() if rt_tag.string else ''
                    if v and v not in furigana_to_mask:
                        furigana_to_mask.append(v)
        except Exception:
            if self.debug_mode:
                print('[DEBUG] Error while extracting first-paragraph readings')

        # Find furigana for words that are part of the title
        initial_mask_candidates = sorted(list(set(words_to_mask + [self.full_title])), key=len, reverse=True)
        if initial_mask_candidates:
            initial_regex = re.compile('(' + '|'.join(re.escape(w) for w in initial_mask_candidates if w) + ')', re.IGNORECASE)
            for ruby_tag in soup.find_all('ruby'):
                temp_ruby = copy.copy(ruby_tag)
                for tag in temp_ruby.find_all(['rt', 'rp']):
                    tag.decompose()
                base_text = temp_ruby.get_text().strip()

                if base_text and initial_regex.search(base_text):
                    for rt_tag in ruby_tag.find_all('rt'):
                        v = rt_tag.string.strip() if rt_tag.string else ''
                        if v and v not in furigana_to_mask:
                            furigana_to_mask.append(v)
        
        return words_to_mask, list(set(furigana_to_mask))

    def _build_masking_regex(self, words_to_mask, furigana_to_mask):
        all_words_to_mask = sorted(list(set(words_to_mask + furigana_to_mask + [self.full_title])), key=len, reverse=True)

        if self.debug_mode:
            print("[DEBUG] all_words_to_mask (sorted):", all_words_to_mask)

        if not all_words_to_mask:
            return None

        # This regex component matches Japanese and alphanumeric characters,
        # forming a basis for what we consider a "word".
        WORD_CHARS = r"0-9A-Za-z_\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF\uFF66-\uFF9F\u30FC"
        patterns = []
        
        for w in all_words_to_mask:
            if not w:
                continue
            
            # If the string contains any whitespace, treat it as a phrase
            # and build a pattern that's flexible with whitespace.
            if any(c.isspace() for c in w):
                parts = [re.escape(part) for part in w.split()]
                p = r'\s+'.join(parts)
            # For single words, enforce word boundaries to avoid masking substrings.
            # e.g., '日本' should not mask the '日本' in '日本人'.
            else:
                p = r'(?<![' + WORD_CHARS + r'])' + re.escape(w) + r'(?![' + WORD_CHARS + r'])'
            
            patterns.append(p)

        if not patterns:
            return None

        regex = re.compile('(' + '|'.join(patterns) + ')', re.IGNORECASE)
        if self.debug_mode:
            print('[DEBUG] final mask regex:', regex.pattern)
        
        return regex

    def _apply_mask_to_html(self, soup, regex):
        for node in soup.find_all(string=True):
            if node.parent.name in ['script', 'style', 'head', 'title']:
                continue

            if regex.search(str(node)):
                new_nodes = []
                last_end = 0
                for match in regex.finditer(str(node)):
                    non_match_text = str(node)[last_end:match.start()]
                    if non_match_text:
                        new_nodes.append(NavigableString(non_match_text))
                    
                    matched_word = match.group(1)
                    mask = '＿' * len(matched_word)
                    new_nodes.append(NavigableString(mask))
                    
                    last_end = match.end()

                rest_of_text = str(node)[last_end:]
                if rest_of_text:
                    new_nodes.append(NavigableString(rest_of_text))
                
                if new_nodes:
                    node.replace_with(*new_nodes)

    def _mask_parentheses_in_html(self, soup):
        """
        Masks the content of parentheses in the HTML, except for the first paragraph.
        """
        first_p = soup.find('p')

        paren_regex = re.compile(r'[（(]([^）)]+)[）)]')

        for node in soup.find_all(string=True):
            if node.parent.name in ['script', 'style', 'head', 'title']:
                continue

            if first_p and node.find_parent('p') is first_p:
                continue

            original_text = str(node)
            
            def mask_content(match):
                inner_content = match.group(1)
                return f"{match.group(0)[0]}{'＿' * len(inner_content)}{match.group(0)[-1]}"

            new_text = paren_regex.sub(mask_content, original_text)

            if new_text != original_text:
                node.replace_with(NavigableString(new_text))

    def _disable_links_in_html(self, soup):
        """
        Finds all hyperlink (<a>) tags and effectively disables them
        by turning them into <span> tags and removing the href attribute.
        """
        for a_tag in soup.find_all('a', href=True):
            a_tag.name = 'span'
            del a_tag['href']

    def update_title_display(self):
        """現在の回答状況に応じてタイトル表示を更新"""
        guessed_chars = set("".join(self.guessed_words))

        # タイトルをカッコの内外で分割
        # 例: "A (B) C" -> ["A ", "(B)", " C"]
        parts = re.split(r'([（\(][^）\)]*[）\)])', self.full_title)

        display_html = ""
        for part in parts:
            if not part:
                continue

            # カッコで囲まれた部分はそのまま表示
            if part.startswith(('(', '（')) and part.endswith((')', '）')):
                display_html += part
                continue

            # それ以外の部分はマスキング処理
            part_html = []
            for char in part:
                if char == ' ':
                    part_html.append(' ')
                elif char in guessed_chars:
                    part_html.append(f"<span style='color: green; font-weight: bold;'>{char}</span>")
                else:
                    part_html.append(f"<span style='color: red;'>＿</span>")
            display_html += "".join(part_html)

        self.hidden_title_label.setText(display_html)

    def show_answer(self):
        """答えをすべて表示し、ゲームを終了状態にする"""
        self.guessed_words.update(self.words_to_guess)
        self.update_title_display()

        self.status_label.setText(f"正解は「{self.full_title}」")
        self.guess_button.setEnabled(False)
        self.input_field.setEnabled(False)
        self.answer_button.setEnabled(False)

        # WebViewに元の記事全体を読み込む
        self.hint_view.load(QUrl(f"{WIKI_PAGE_BASE_URL}wiki/{self.full_title.replace(' ', '_')}"))

    def handle_guess(self):
        """ユーザーの回答をチェック"""
        guess = self.input_field.text().strip()
        if not guess:
            return
        self.input_field.setText("")

        if guess in self.words_to_guess and guess not in self.guessed_words:
            self.guessed_words.add(guess)
            self.update_title_display()
            self.update_view_with_masks() # マスク状態を更新

            if len(self.guessed_words) == len(self.words_to_guess):
                self.status_label.setText(f"correct. タイトルは「{self.full_title}」")
                self.guess_button.setEnabled(False)
                self.input_field.setEnabled(False)
                self.answer_button.setEnabled(False)
                # クリアしたら元の記事全体を表示
                self.hint_view.load(QUrl(f"{WIKI_PAGE_BASE_URL}wiki/{self.full_title.replace(' ', '_')}"))
            else:
                self.status_label.setText(f"correct「{guess}」 残り{len(self.words_to_guess) - len(self.guessed_words)}語")

        elif guess in self.guessed_words:
            self.status_label.setText(f"「{guess}」は既に当てられています")
        else:
            self.status_label.setText(f"incorrect. 「{guess}」ではありません")

    def toggle_debug(self):
        """デバッグモードの ON/OFF を切り替える"""
        self.debug_mode = not self.debug_mode
        if self.debug_mode:
            self.debug_button.setText("Debug: On")
            # 簡易的にステータスにも表示
            self.status_label.setText("デバッグ: ON")
        else:
            self.debug_button.setText("Debug: Off")
            self.status_label.setText("")

        # デバッグ時はマスク表示を再描画してコンソールに情報を出す
        self.update_view_with_masks()


if __name__ == '__main__':
    os.environ['QT_QUICK_CONTROLS_STYLE'] = 'Basic'
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    
    app = QApplication(sys.argv)
    
    profile = QWebEngineProfile.defaultProfile()
    profile.setHttpUserAgent(USER_AGENT)
    
    window = WikiGameApp()
    window.show()
    sys.exit(app.exec())