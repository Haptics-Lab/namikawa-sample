## サンプル内容
東海光学の脳波測定装置（TOKAI Orb）からデータを取得し、CSVに保存するプログラム。

- 計測開始前にインピーダンスチェックを行う
- 計測中のEEGデータをCSVへ逐次保存する

## ディレクトリ構成
```
sample_008/
├── main.py
│
├── src/
│   ├── eeg_recorder.py
│   └── OrbViewAPI_py313.pyd
│
├── output/         ← 結果など
│
└── README.md
```

## 環境構築
OSはWindowsを想定しています。  
uvを使用します。uvの導入までは事前に行ってください。  
使用する脳波測定装置については、取扱説明書を参照してください。
プログラムの実行時は、脳波測定装置をPCにBluetooth接続してください。

`sample_008/`をPCにコピーして、以下のコマンドを実行してください。
```
sample_008 % uv sync
```

## 実行方法
使用するポートに合わせて、`main.py` の `com_port` を変更してください。

```python
recorder = EEGRecorder(com_port="COM3")
```

実行後は次の流れで動作します。

1. インピーダンスチェック開始
2. Enterキーでインピーダンスチェック停止・記録開始
3. Enterキーで記録停止

```
sample_008 % uv run main.py
```
