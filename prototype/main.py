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
        main_layout = QVBoxLayout(self)

        self.status_label = QLabel("新しいゲームを開始します...")
        self.status_label.setFont(QFont("Arial", 12))
        main_layout.addWidget(self.status_label)

        title_group_label = QLabel("--- 隠されたタイトル ---")
        title_group_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_group_label)

        self.hidden_title_label = QLabel("ロード中...")
        self.hidden_title_label.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        self.hidden_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hidden_title_label.setStyleSheet("padding: 20px; border: 2px solid #333;")
        main_layout.addWidget(self.hidden_title_label)

        hint_label = QLabel("ヒント (記事全文から答えの単語をマスク)")
        hint_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        main_layout.addWidget(hint_label)

        self.hint_view = QWebEngineView()
        self.hint_view.setFixedHeight(300)
        main_layout.addWidget(self.hint_view)

        input_layout = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("単語を入力してください...")
        self.input_field.returnPressed.connect(self.handle_guess)
        input_layout.addWidget(self.input_field)

        self.guess_button = QPushButton("回答をチェック")
        self.guess_button.clicked.connect(self.handle_guess)
        input_layout.addWidget(self.guess_button)

        self.answer_button = QPushButton("答えを表示")
        self.answer_button.clicked.connect(self.show_answer)
        input_layout.addWidget(self.answer_button)

        self.next_button = QPushButton("次の問題")
        self.next_button.clicked.connect(self.fetch_new_article)
        input_layout.addWidget(self.next_button)

        # デバッグモード切替ボタン
        self.debug_button = QPushButton("Debug: Off")
        self.debug_button.setCheckable(True)
        self.debug_button.clicked.connect(self.toggle_debug)
        input_layout.addWidget(self.debug_button)

        main_layout.addLayout(input_layout)

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

        # 3. タイトルを単語に分割せず、全体を1つの要素とする
        words = [title] if title else []

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

            self.status_label.setText(f"問題: {len(words)}語のタイトルを当ててください！")
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
        
        # マスク対象の単語（推測済みでないもの）
        words_to_mask = [w for w in self.words_to_guess if w not in self.guessed_words]
        
        # まず初期マスク対象（タイトル等）から正規表現を作り、
        # それにマッチする ruby の rt（ふりがな）をマスク対象に追加する。
        # まず、ページ内に存在するすべての rt（ふりがな）の文字列を収集しておく。
        # これにより、ruby タグ外に同じひらがな表記が存在する場合でもマスク対象にできます。
        furigana_to_mask = [rt_tag.string.strip() for rt_tag in soup.find_all('rt') if rt_tag.string and rt_tag.string.strip()]

        # タイトル全体も一旦含めた初期マスク語リストを作成
        initial_mask_candidates = list(words_to_mask)
        initial_mask_candidates.append(self.full_title)
        # 空文字を除外し、長さ順にソートして最長マッチを優先
        initial_mask_candidates = [w for w in initial_mask_candidates if w]
        initial_mask_candidates = sorted(initial_mask_candidates, key=len, reverse=True)

        initial_regex = None
        if initial_mask_candidates:
            initial_regex = re.compile('(' + '|'.join(re.escape(w) for w in initial_mask_candidates) + ')', re.IGNORECASE)

        if self.debug_mode:
            print("[DEBUG] initial_mask_candidates:", initial_mask_candidates)
            try:
                print("[DEBUG] initial_regex:", initial_regex.pattern if initial_regex else None)
            except Exception:
                print("[DEBUG] initial_regex: <unable to show pattern>")

        # --- 追加: 最初の説明（先頭段落）でタイトルの横にある読み（括弧内）や近傍の ruby/rt を取得 ---
        try:
            first_p = soup.find('p')
            if first_p:
                # テキストとして先頭段落を取得し、括弧内の読みをすべて抽出する
                first_p_text = first_p.get_text()
                for paren_match in re.finditer(r'[（(]([^）)]+)[）)]', first_p_text):
                    reading = paren_match.group(1).strip()
                    if not reading:
                        continue
                    # ひらがなが含まれるものを優先して追加
                    if re.search('[\u3040-\u309F]', reading) or re.search('[ぁ-ん]', reading):
                        if reading not in furigana_to_mask:
                            furigana_to_mask.append(reading)
                    else:
                        # ひらがなを含まない場合でも、短め（<=6文字）なら追加しておく
                        if len(reading) <= 6 and reading not in furigana_to_mask:
                            furigana_to_mask.append(reading)

                # 先頭段落内の ruby タグに含まれる rt をすべて追加
                for rt_tag in first_p.find_all('rt'):
                    if rt_tag.string:
                        v = rt_tag.string.strip()
                        if v and v not in furigana_to_mask:
                            furigana_to_mask.append(v)
        except Exception:
            if self.debug_mode:
                print('[DEBUG] error while extracting first-paragraph readings')
        # --- 追加終了 ---

        for ruby_tag in soup.find_all('ruby'):
            # rubyタグのコピーからrt, rpタグを取り除き、ベーステキストを抽出
            temp_ruby = copy.copy(ruby_tag)
            for tag in temp_ruby.find_all(['rt', 'rp']):
                tag.decompose()
            base_text = temp_ruby.get_text().strip()

            # base_text が初期マスク正規表現にマッチする場合、rt をマスク対象に追加
            if base_text and initial_regex and initial_regex.search(base_text):
                for rt_tag in ruby_tag.find_all('rt'):
                    if rt_tag.string:
                        v = rt_tag.string.strip()
                        if v and v not in furigana_to_mask:
                            furigana_to_mask.append(v)

        # 最終的なマスク語集合を作る
        all_words_to_mask_set = set(words_to_mask + furigana_to_mask)
        all_words_to_mask_set.add(self.full_title)
        # マッチが長い順になるようにソート
        all_words_to_mask = sorted(list(all_words_to_mask_set), key=len, reverse=True)

        if self.debug_mode:
            print("[DEBUG] furigana_to_mask:", furigana_to_mask)
            print("[DEBUG] all_words_to_mask (sorted):", all_words_to_mask)

        if not all_words_to_mask:
            self.hint_view.setHtml(self.original_html, QUrl(WIKI_PAGE_BASE_URL))
            return

        # マスク対象の単語を結合した正規表現を作成
        # 要求: 答えと読みをピンポイントで完全一致させる -> 前後が「単語文字」に続く場合は除外する
        # 日本語を含む「単語文字」相当の文字クラスを用意
        WORD_CHARS = r"0-9A-Za-z_\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF\uFF66-\uFF9F\u30FC"
        patterns = []
        for w in all_words_to_mask:
            if not w:
                continue
            # (?<![WORD_CHARS]) ... (?![WORD_CHARS]) で囲むことで周辺に単語文字がなければ一致
            p = r'(?<![' + WORD_CHARS + r'])' + re.escape(w) + r'(?![' + WORD_CHARS + r'])'
            patterns.append(p)

        if not patterns:
            self.hint_view.setHtml(self.original_html, QUrl(WIKI_PAGE_BASE_URL))
            return

        regex = re.compile('(' + '|'.join(patterns) + ')', re.IGNORECASE)
        if self.debug_mode:
            try:
                print('[DEBUG] final mask regex:', regex.pattern)
            except Exception:
                print('[DEBUG] final mask regex: <unable to show>')
        
        # 全てのテキストノードを探索
        for node in soup.find_all(string=True):
            # スクリプトやスタイルの中は無視
            if node.parent.name in ['script', 'style', 'head', 'title']:
                continue

            if regex.search(str(node)):
                new_nodes = []
                last_end = 0
                for match in regex.finditer(str(node)):
                    # マッチしなかった部分を追加
                    non_match_text = str(node)[last_end:match.start()]
                    if non_match_text:
                        new_nodes.append(NavigableString(non_match_text))
                    
                    # マッチした部分をマスクして追加
                    matched_word = match.group(1)
                    mask = '＿' * len(matched_word)
                    new_nodes.append(NavigableString(mask))
                    
                    last_end = match.end()

                # 最後のマッチ以降の残りテキストを追加
                rest_of_text = str(node)[last_end:]
                if rest_of_text:
                    new_nodes.append(NavigableString(rest_of_text))
                
                # 元のノードを新しいノード群で置き換え
                if new_nodes:
                    node.replace_with(*new_nodes)

        self.hint_view.setHtml(str(soup), QUrl(WIKI_PAGE_BASE_URL))

    def update_title_display(self):
        """現在の回答状況に応じてタイトル表示を更新"""
        display_parts = []
        for word in self.words_to_guess:
            if word in self.guessed_words or len(word) <= 1:
                display_parts.append(f"<span style='color: green; font-weight: bold;'>{word}</span>")
            else:
                display_parts.append(f"<span style='color: red;'>{'＿' * len(word)}</span>")
        self.hidden_title_label.setText(" ".join(display_parts))

    def show_answer(self):
        """答えをすべて表示し、ゲームを終了状態にする"""
        self.guessed_words.update(self.words_to_guess)
        self.update_title_display()

        self.status_label.setText(f"正解は「{self.full_title}」でした。")
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
                self.status_label.setText(f"🎉ゲームクリア！タイトルは「{self.full_title}」でした！")
                self.guess_button.setEnabled(False)
                self.input_field.setEnabled(False)
                self.answer_button.setEnabled(False)
                # クリアしたら元の記事全体を表示
                self.hint_view.load(QUrl(f"{WIKI_PAGE_BASE_URL}wiki/{self.full_title.replace(' ', '_')}"))
            else:
                self.status_label.setText(f"正解！「{guess}」が当たりました！ 残り{len(self.words_to_guess) - len(self.guessed_words)}語。")

        elif guess in self.guessed_words:
            self.status_label.setText(f"「{guess}」は既に当てられています。")
        else:
            self.status_label.setText(f"残念、「{guess}」は含まれていません。")

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