## サンプル内容
`cv2`を使用してカメラで録画し、mp4ファイルに保存するプログラム。

## ディレクトリ構成
```
sample_004/
├── main.py
│
├── src/
│   └── camera_recorder.py
│
├── output/         ← 結果など
│
└── README.md
```

## 環境構築 
uvを使用します。uvの導入までは事前に行ってください。  

### 方法1
`sample_004/`をPCにコピーして、以下のコマンドを実行してください。
```
sample_004 % uv sync
```
### 方法2（推奨）
必要なライブラリ(cv2)が用意できていれば、`camera_recorder.py`のみでも動きます。  
リポジトリから`camera_recorder.py`をダウンロードして、ご自身のプロジェクト内で使用してください。  
```
sample_004 % uv add cv2
```

## 実行方法
### 方法1
`sample_004/`のフォルダごとコピーした方は、`main.py`の実行で動きます。
```
sample_004 % uv run main.py
```
### 方法2
`camera_recorder.py`をダウンロードした方は、`camera_recorder.py`の実行で動きます。
```
sample_004 % uv run camera_recorder.py
```