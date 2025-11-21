import sys
import requests
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QLineEdit, QPushButton, QTextEdit
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

# Wikipedia APIのベースURL（日本語版）
BASE_URL = "https://ja.wikipedia.org/w/api.php"

class WikiGameApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PySide Wikipedia 単語当てゲーム")
        self.setGeometry(100, 100, 800, 600)
        
        # ゲームの状態を初期化
        self.full_title = ""
        self.words_to_guess = []
        self.guessed_words = set()
        
        self.setup_ui()
        self.fetch_new_article()

    def setup_ui(self):
        """UIコンポーネントの配置"""
        main_layout = QVBoxLayout(self)
        
        # 1. メッセージ/ステータス表示
        self.status_label = QLabel("新しいゲームを開始します...")
        self.status_label.setFont(QFont("Arial", 12))
        main_layout.addWidget(self.status_label)
        
        # 2. 隠されたタイトル表示エリア
        title_group_label = QLabel("--- 隠されたタイトル ---")
        title_group_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_group_label)
        
        self.hidden_title_label = QLabel("ロード中...")
        self.hidden_title_label.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        self.hidden_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hidden_title_label.setStyleSheet("padding: 20px; border: 2px solid #333;")
        main_layout.addWidget(self.hidden_title_label)
        
        # 3. 記事本文（ヒント）表示エリア
        hint_label = QLabel("📚 ヒント (Wikipedia記事の冒頭)")
        hint_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        main_layout.addWidget(hint_label)
        
        self.hint_text = QTextEdit()
        self.hint_text.setReadOnly(True)
        self.hint_text.setFixedHeight(200)
        main_layout.addWidget(self.hint_text)
        
        # 4. 回答入力とボタン
        input_layout = QHBoxLayout()
        
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("単語を入力してください...")
        input_layout.addWidget(self.input_field)
        
        self.guess_button = QPushButton("回答をチェック")
        self.guess_button.clicked.connect(self.handle_guess)
        input_layout.addWidget(self.guess_button)
        
        self.next_button = QPushButton("次の問題")
        self.next_button.clicked.connect(self.fetch_new_article)
        input_layout.addWidget(self.next_button)
        
        main_layout.addLayout(input_layout)

    def get_random_article_data(self):
        """Wikipedia APIを呼び出し、ランダムな記事のタイトルと本文を取得"""
        # 1. ランダムタイトル取得
        random_params = {'action': 'query', 'format': 'json', 'list': 'random', 'rnlimit': '1', 'rnnamespace': '0'}
        try:
            random_response = requests.get(BASE_URL, params=random_params)
            random_data = random_response.json()
            title = random_data['query']['random'][0]['title']
        except Exception:
            return None, None, None

        # 2. 記事の要約（Extract）を取得
        extract_params = {
            'action': 'query', 'format': 'json', 'titles': title, 'prop': 'extracts',
            'exintro': True, 'explaintext': True, 'redirects': 1
        }
        try:
            extract_response = requests.get(BASE_URL, params=extract_params)
            extract_data = extract_response.json()
            pages = extract_data['query']['pages']
            page_id = next(iter(pages))
            extract = pages[page_id].get('extract', '記事の本文が見つかりませんでした。')
        except Exception:
            extract = "記事本文の取得に失敗しました。"

        # 3. タイトルを単語に分割 (簡易的な分割)
        # 日本語の適切な分かち書きはより高度なライブラリ（MeCabなど）が必要だが、ここでは区切り文字で簡易分割
        words = [w for w in title.replace('（', ' ').replace('）', ' ').replace(':', ' ').split() if w]
        if not words:
            words = [title] 
            
        return title, words, extract

    def fetch_new_article(self):
        """新しい記事を取得し、ゲームをリセット"""
        self.status_label.setText("Wikipediaから記事を取得中...")
        QApplication.processEvents() # UIを更新
        
        title, words, extract = self.get_random_article_data()
        
        if title:
            self.full_title = title
            self.words_to_guess = words
            self.guessed_words = set()
            
            self.hint_text.setText(extract)
            self.update_title_display()
            self.status_label.setText(f"問題:{len(words)}語のタイトルを当ててください！")
            self.input_field.setText("")
            self.guess_button.setEnabled(True)
        else:
            self.status_label.setText("記事の取得に失敗しました。ネットワーク接続を確認してください。")

    def update_title_display(self):
        """現在の回答状況に応じてタイトル表示を更新"""
        display_parts = []
        for word in self.words_to_guess:
            # 既に当てた単語、または短い単語（ヒントとして表示）
            if word in self.guessed_words or len(word) <= 1:
                display_parts.append(f"<span style='color: green; font-weight: bold;'>{word}</span>")
            else:
                # 隠された単語
                display_parts.append(f"<span style='color: red;'>{'＿' * len(word)}</span>")
                
        self.hidden_title_label.setText(" ".join(display_parts))

    def handle_guess(self):
        """ユーザーの回答をチェック"""
        guess = self.input_field.text().strip()
        self.input_field.setText("") # 入力欄をクリア

        if not guess:
            return

        if guess in self.words_to_guess and guess not in self.guessed_words:
            # 正解
            self.guessed_words.add(guess)
            self.update_title_display()
            
            # ゲームクリア判定
            if len(self.guessed_words) == len(self.words_to_guess):
                self.status_label.setText(f"🎉ゲームクリア！タイトルは「{self.full_title}」でした！")
                self.guess_button.setEnabled(False)
            else:
                self.status_label.setText(f"正解！「{guess}」が当たりました！ 残り{len(self.words_to_guess) - len(self.guessed_words)}語。")

        elif guess in self.guessed_words:
            # 既に回答済み
            self.status_label.setText(f"「{guess}」は既に当てられています。")
        else:
            # 不正解
            self.status_label.setText(f"残念、「{guess}」は含まれていません。")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = WikiGameApp()
    window.show()
    sys.exit(app.exec())
