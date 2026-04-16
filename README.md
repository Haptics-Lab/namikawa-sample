# Python Sample
このリポジトリは、Pythonプログラムのサンプル集です。  
各サンプルは独立した小さなプロジェクトとして構成されています。

## ディレクトリ構成
```
repository/
├── sample_001/
├── sample_002/
```
各サンプルは基本的に以下のような構成を持ちます：
```
sample_xxx/
├── main.py
├── src/ 
├── pyproject.toml
├── README.md
├── data/
└── output/
```

## サンプル一覧
### sample_001
- CSVファイルを読み込む
- データをプロットする
- 画像として保存する

### sample_002
- NIのDAQデバイスでデータを取得する
- CSVファイルにデータを保存する

### sample_003
- 録音してwavファイルに保存する

### sample_004
- 録画してmp4ファイルに保存する

### sample_005
- MotiveからストリーミングによりOptiTrackのモーションキャプチャデータを取得する
- CSVファイルに保存する

## 注意点
- `.venv/` はGit管理されていません
- `output/` フォルダもGitには含まれません
- 必要に応じて各サンプルでフォルダを作成してください