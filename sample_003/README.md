## サンプル内容
`sounddevice`を使用してマイクで録音し、wavファイルに保存するプログラム。

## ディレクトリ構成
```
sample_003/
├── main.py
│
├── src/
│   └── audio_recorder.py
│
├── output/         ← 結果など
│
└── README.md
```

## 環境構築 
uvを使用します。uvの導入までは事前に行ってください。  

### 方法1
`sample_003/`をPCにコピーして、以下のコマンドを実行してください。
```
sample_003 % uv sync
```
### 方法2（推奨）
必要なライブラリ(numpy, sounddevice, scipy)が用意できていれば、`audio_recorder.py`のみでも動きます。  
リポジトリから`audio_recorder.py`をダウンロードして、ご自身のプロジェクト内で使用してください。  
```
sample_003 % uv add numpy sounddevice scipy
```

## 実行方法
### 方法1
`sample_003/`のフォルダごとコピーした方は、`main.py`の実行で動きます。
```
sample_003 % uv run main.py
```
### 方法2
`audio_recorder.py`をダウンロードした方は、`audio_recorder.py`の実行で動きます。
```
sample_003 % uv run audio_recorder.py
```