# Streamlit キャッシュクリア手順

Streamlit は モジュールをキャッシュするため、コードを修正しても **古いバージョンを実行し続けることがあります**。

## 🔧 解決方法

### 方法 1: キャッシュディレクトリを削除（推奨）

**Windows**:
```powershell
# Streamlit キャッシュディレクトリを削除
Remove-Item -Recurse -Force $env:USERPROFILE\.streamlit\

# または
rmdir /s /q "%USERPROFILE%\.streamlit\"
```

**Mac/Linux**:
```bash
rm -rf ~/.streamlit/
```

その後、**Streamlit を再起動**:
```bash
streamlit run app/Home.py
```

---

### 方法 2: ブラウザキャッシュもクリア

1. **ブラウザの開発者ツール** を開く（F12）
2. **Application** タブを開く
3. **Cache Storage** 内の Streamlit キャッシュを削除
4. ページをリロード（Ctrl+Shift+R）

---

### 方法 3: Python モジュールキャッシュをクリア

```bash
# __pycache__ ディレクトリを削除
find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null

# または Windows
for /d /r . %d in (__pycache__) do @if exist "%d" rmdir /s /q "%d"
```

---

## ✅ 動作確認

修正後、以下のエラーが出なくなったか確認してください：

```
❌ エラー
スクレイピングエラー: fetch_upcoming_races() got an unexpected keyword argument 'use_mock'
```

**代わりに表示されるべき内容**:
```
📊 テストモード：14 日先までのモックレース情報を生成中...
✅ XX 件のレース情報を取得しました
```

---

## 🚀 推奨フロー

1. **ローカル修正を確認**:
   ```bash
   python -c "from scraper.fetch_future_races import fetch_upcoming_races; print('OK')"
   ```

2. **キャッシュをクリア** (方法 1 推奨)

3. **Streamlit を再起動**:
   ```bash
   streamlit run app/Home.py
   ```

4. **FutureRaces ページでテスト**:
   - 「テストモードを使用」にチェック
   - 「将来レース情報を取得」ボタンをクリック
   - モックレースが表示される

---

## 📝 トラブルシューティング

### まだエラーが出る場合

1. **Python をリスタート**:
   ```bash
   # Streamlit を完全に終了（Ctrl+C を複数回）
   # ターミナルを閉じて、新しいターミナルで再実行
   streamlit run app/Home.py
   ```

2. **仮想環境をリセット**:
   ```bash
   # Python 仮想環境を再作成（必要に応じて）
   python -m venv venv
   . venv/Scripts/activate  # Windows
   # または
   source venv/bin/activate  # Mac/Linux
   pip install -r requirements.txt
   ```

3. **ブラウザを完全にリセット**:
   - すべてのタブを閉じる
   - ブラウザキャッシュをクリア
   - 新しいブラウザウィンドウで `http://localhost:8501` にアクセス

---

## 🎯 予防策

今後、Streamlit のキャッシュ問題を避けるため：

1. **モジュール修正後は必ず Streamlit を再起動**
2. **重大な修正の場合は、キャッシュを事前にクリア**
3. **本番環境では Docker を使用**（キャッシュ問題なし）

